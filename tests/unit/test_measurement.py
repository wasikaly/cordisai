"""
Unit tests for models/measurement — lvef.py and engine.py.
Run with: python -m pytest tests/unit/test_measurement.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pytest

from models.measurement.lvef import (
    compute_lv_areas,
    find_ed_es_frames,
    mask_to_volume_ml,
    compute_lvef,
)
from models.measurement.engine import classify_ef, flag_abnormal, run_measurements


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _circle_mask(H=112, W=112, cx=56, cy=56, r=20, label=1):
    """Return (H, W) mask with a filled circle of given label."""
    mask = np.zeros((H, W), dtype=np.int32)
    y, x = np.ogrid[:H, :W]
    mask[(x - cx) ** 2 + (y - cy) ** 2 <= r ** 2] = label
    return mask


def _make_pulsatile_masks(T=20, H=112, W=112, r_ed=28, r_es=14):
    """
    T frames: LV (label=1) radius linearly shrinks from r_ed → r_es → r_ed.
    Frame 0 is ED (max), frame T//2 is ES (min).
    """
    masks = np.zeros((T, H, W), dtype=np.int32)
    half = T // 2
    for i in range(T):
        if i <= half:
            r = r_ed - (r_ed - r_es) * i / half
        else:
            r = r_es + (r_ed - r_es) * (i - half) / half
        masks[i] = _circle_mask(H, W, r=int(r), label=1)
    return masks


# ── compute_lv_areas ──────────────────────────────────────────────────────────

class TestComputeLvAreas:
    def test_zero_masks(self):
        masks = np.zeros((5, 112, 112), dtype=np.int32)
        areas = compute_lv_areas(masks)
        assert areas.shape == (5,)
        assert (areas == 0).all()

    def test_constant_circle(self):
        r = 20
        frame = _circle_mask(r=r)
        masks = np.stack([frame] * 4)
        areas = compute_lv_areas(masks)
        expected = (frame == 1).sum()
        np.testing.assert_array_equal(areas, expected)

    def test_only_label_1_counted(self):
        """Labels 2 (Myo) and 3 (LA) must not contribute to LV area."""
        frame = np.zeros((112, 112), dtype=np.int32)
        frame[20:40, 20:40] = 2   # myocardium
        frame[50:70, 50:70] = 3   # LA
        masks = frame[np.newaxis]
        areas = compute_lv_areas(masks)
        assert areas[0] == 0


# ── find_ed_es_frames ─────────────────────────────────────────────────────────

class TestFindEdEsFrames:
    def test_pulsatile(self):
        masks = _make_pulsatile_masks(T=20, r_ed=28, r_es=14)
        areas = compute_lv_areas(masks)
        ed, es = find_ed_es_frames(masks, areas=areas)
        # ED = max area = frame 0, ES = min = frame 10
        assert ed == 0
        assert es == 10

    def test_uses_passed_areas(self):
        """Should use pre-computed areas, not recompute from masks."""
        masks = np.zeros((5, 112, 112), dtype=np.int32)
        fake_areas = np.array([1.0, 5.0, 3.0, 2.0, 4.0])
        ed, es = find_ed_es_frames(masks, areas=fake_areas)
        assert ed == 1  # argmax of fake_areas
        assert es == 0  # argmin of fake_areas


# ── mask_to_volume_ml ─────────────────────────────────────────────────────────

class TestMaskToVolumeMl:
    def test_empty_mask(self):
        mask = np.zeros((112, 112), dtype=np.int32)
        assert mask_to_volume_ml(mask) == 0.0

    def test_positive_volume(self):
        mask = _circle_mask(r=25)
        vol = mask_to_volume_ml(mask, pixel_size_cm=0.1)
        assert vol > 0.0

    def test_larger_mask_bigger_volume(self):
        small = _circle_mask(r=15)
        large = _circle_mask(r=30)
        assert mask_to_volume_ml(large) > mask_to_volume_ml(small)

    def test_bigger_pixel_size_bigger_volume(self):
        mask = _circle_mask(r=20)
        v1 = mask_to_volume_ml(mask, pixel_size_cm=0.1)
        v2 = mask_to_volume_ml(mask, pixel_size_cm=0.2)
        assert v2 > v1


# ── compute_lvef ──────────────────────────────────────────────────────────────

class TestComputeLvef:
    def test_returns_all_keys(self):
        masks = _make_pulsatile_masks()
        result = compute_lvef(masks)
        for key in ("LVEF", "LVEDV", "LVESV", "ed_frame", "es_frame", "lv_areas"):
            assert key in result

    def test_lvef_in_physiological_range(self):
        masks = _make_pulsatile_masks(r_ed=28, r_es=14)
        result = compute_lvef(masks)
        # EF should be > 0 and < 100 for a pulsatile sequence
        assert 0 < result["LVEF"] < 100

    def test_lvedv_greater_than_lvesv(self):
        masks = _make_pulsatile_masks()
        result = compute_lvef(masks)
        assert result["LVEDV"] > result["LVESV"]

    def test_empty_masks_zero_ef(self):
        masks = np.zeros((10, 112, 112), dtype=np.int32)
        result = compute_lvef(masks)
        assert result["LVEF"] == 0.0
        assert result["LVEDV"] == 0.0

    def test_lv_areas_shape(self):
        T = 15
        masks = _make_pulsatile_masks(T=T)
        result = compute_lvef(masks)
        assert result["lv_areas"].shape == (T,)


# ── classify_ef ───────────────────────────────────────────────────────────────

class TestClassifyEf:
    @pytest.mark.parametrize("ef,expected", [
        (65.0, "Normal (HFpEF range)"),
        (53.0, "Normal (HFpEF range)"),
        (45.0, "Mildly reduced (HFmrEF)"),
        (41.0, "Mildly reduced (HFmrEF)"),
        (35.0, "Moderately reduced"),
        (30.0, "Moderately reduced"),
        (25.0, "Severely reduced (HFrEF)"),
    ])
    def test_categories(self, ef, expected):
        assert classify_ef(ef) == expected


# ── flag_abnormal ─────────────────────────────────────────────────────────────

class TestFlagAbnormal:
    def test_normal_ef(self):
        assert flag_abnormal("LVEF", 60.0) is None

    def test_low_ef(self):
        assert flag_abnormal("LVEF", 40.0) == "LOW"

    def test_high_lvedv(self):
        assert flag_abnormal("LVEDV", 120.0) == "HIGH"

    def test_unknown_key(self):
        assert flag_abnormal("UNKNOWN_PARAM", 99.0) is None

    def test_boundary_min(self):
        # LVEF min=53; value exactly at min should be normal
        assert flag_abnormal("LVEF", 53.0) is None

    def test_boundary_max(self):
        # LVEF max=73; value exactly at max should be normal
        assert flag_abnormal("LVEF", 73.0) is None


# ── run_measurements ─────────────────────────────────────────────────────────

class TestRunMeasurements:
    def test_returns_all_expected_keys(self):
        masks = _make_pulsatile_masks()
        result = run_measurements(masks)
        for key in ("LVEF", "LVEDV", "LVESV", "EF_category",
                    "IVSd", "LVIDd", "LVPWd", "RWT",
                    "LA_area", "ed_frame", "es_frame", "lv_areas",
                    "LV_geometry"):
            assert key in result, f"Missing key: {key}"

    def test_ef_category_is_string(self):
        masks = _make_pulsatile_masks()
        result = run_measurements(masks)
        assert isinstance(result["EF_category"], str)
        assert len(result["EF_category"]) > 0

    def test_lv_areas_forwarded(self):
        masks = _make_pulsatile_masks(T=12)
        result = run_measurements(masks)
        assert result["lv_areas"] is not None
        assert len(result["lv_areas"]) == 12
