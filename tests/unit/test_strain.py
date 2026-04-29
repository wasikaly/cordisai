"""
Unit tests for GLS / strain computation (models/measurement/strain.py).
"""
import numpy as np
import pytest
from models.measurement.strain import compute_gls, classify_gls


# ── Synthetic mask helpers ─────────────────────────────────────────────────────

def _ellipse_mask(h: int, w: int, cy: float, cx: float,
                  ry: float, rx: float) -> np.ndarray:
    """Fill an ellipse with label=1 in a (h, w) mask."""
    mask = np.zeros((h, w), dtype=int)
    Y, X = np.ogrid[:h, :w]
    inside = ((Y - cy) / ry) ** 2 + ((X - cx) / rx) ** 2 <= 1
    mask[inside] = 1
    return mask


def _pulsatile_masks(T: int = 20, h: int = 112, w: int = 112,
                     ed_ry: float = 28, ed_rx: float = 18,
                     es_ry: float = 20, es_rx: float = 13) -> np.ndarray:
    """
    Synthetic pulsatile sequence: ED at frame 0, ES at frame T//2.
    Radii linearly interpolate between ED and ES and back.
    """
    masks = []
    cy, cx = h / 2, w / 2
    half = T // 2
    for i in range(T):
        if i <= half:
            t = i / half
        else:
            t = (T - i) / half
        ry = ed_ry + (es_ry - ed_ry) * t
        rx = ed_rx + (es_rx - ed_rx) * t
        masks.append(_ellipse_mask(h, w, cy, cx, ry, rx))
    return np.stack(masks, axis=0)


# ── classify_gls ──────────────────────────────────────────────────────────────

class TestClassifyGls:
    def test_none_returns_not_computed(self):
        assert classify_gls(None) == "Not computed"

    def test_excellent(self):
        assert classify_gls(-22.0) == "Normal (excellent)"

    def test_normal(self):
        assert classify_gls(-17.0) == "Normal"

    def test_boundary_16_normal(self):
        assert classify_gls(-16.0) == "Normal"

    def test_mildly_impaired(self):
        assert classify_gls(-14.0) == "Mildly impaired"

    def test_moderately_impaired(self):
        assert classify_gls(-10.0) == "Moderately impaired"

    def test_severely_impaired(self):
        assert classify_gls(-5.0) == "Severely impaired"

    def test_positive_severely_impaired(self):
        # GLS > 0 is extremely abnormal
        assert classify_gls(2.0) == "Severely impaired"


# ── compute_gls — empty / degenerate inputs ───────────────────────────────────

class TestComputeGlsEmpty:
    def test_zero_masks_returns_none_gls(self):
        masks = np.zeros((10, 112, 112), dtype=int)
        result = compute_gls(masks, ed_idx=0, es_idx=5)
        assert result["GLS"] is None

    def test_zero_masks_reliable_false(self):
        masks = np.zeros((10, 112, 112), dtype=int)
        result = compute_gls(masks, ed_idx=0, es_idx=5)
        assert result["reliable"] is False

    def test_zero_masks_curve_length(self):
        masks = np.zeros((10, 112, 112), dtype=int)
        result = compute_gls(masks, ed_idx=0, es_idx=5)
        assert len(result["GLS_curve"]) == 10

    def test_tiny_lv_returns_none(self):
        # LV area < min_lv_area_px=200
        masks = np.zeros((10, 112, 112), dtype=int)
        masks[:, 55:60, 55:60] = 1   # 25 pixels — too small
        result = compute_gls(masks, ed_idx=0, es_idx=5)
        assert result["GLS"] is None


# ── compute_gls — pulsatile synthetic data ────────────────────────────────────

class TestComputeGlsPulsatile:
    def setup_method(self):
        self.masks = _pulsatile_masks(T=20)
        self.result = compute_gls(self.masks, ed_idx=0, es_idx=10,
                                  pixel_size_cm=0.1)

    def test_gls_is_not_none(self):
        assert self.result["GLS"] is not None

    def test_gls_is_negative(self):
        # Systolic shortening → negative strain
        assert self.result["GLS"] < 0

    def test_gls_physiological_range(self):
        # Reasonable range for synthetic hearts
        assert -40 < self.result["GLS"] < -5

    def test_reliable_true(self):
        assert self.result["reliable"] is True

    def test_l_ed_greater_than_l_es(self):
        # ED contour must be larger than ES
        assert self.result["L_ED"] > self.result["L_ES"]

    def test_curve_length_matches_frames(self):
        assert len(self.result["GLS_curve"]) == 20
        assert len(self.result["GLS_curve_raw"]) == 20

    def test_curve_starts_near_zero(self):
        # At ED frame (frame 0) strain should be ~0
        assert abs(self.result["GLS_curve_raw"][0]) < 1.0

    def test_curve_most_negative_near_es(self):
        # Minimum strain near ES frame (frame 10)
        curve = self.result["GLS_curve_raw"]
        min_idx = int(np.argmin(curve))
        assert abs(min_idx - 10) <= 3   # allow ±3 frames

    def test_gls_category_is_string(self):
        assert isinstance(self.result["GLS_category"], str)
        assert len(self.result["GLS_category"]) > 0

    def test_pixel_size_scaling(self):
        # Larger pixel size → same relative strain (ratio stays the same)
        r1 = compute_gls(self.masks, 0, 10, pixel_size_cm=0.1)
        r2 = compute_gls(self.masks, 0, 10, pixel_size_cm=0.2)
        assert abs(r1["GLS"] - r2["GLS"]) < 0.5


# ── engine integration ────────────────────────────────────────────────────────

class TestEngineIntegration:
    def test_gls_keys_in_engine_output(self):
        from models.measurement.engine import run_measurements
        masks = _pulsatile_masks(T=20)
        m = run_measurements(masks)
        for key in ("GLS", "GLS_category", "GLS_curve", "GLS_reliable"):
            assert key in m

    def test_gls_value_is_negative_for_pulsatile(self):
        from models.measurement.engine import run_measurements
        masks = _pulsatile_masks(T=20)
        m = run_measurements(masks)
        gls = m["GLS"]["value"]
        assert gls is not None
        assert gls < 0

    def test_gls_none_for_empty_masks(self):
        from models.measurement.engine import run_measurements
        masks = np.zeros((10, 112, 112), dtype=int)
        m = run_measurements(masks)
        assert m["GLS"]["value"] is None
