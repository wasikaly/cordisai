"""
Unit tests for models/measurement/wall_thickness.py
Run with: python -m pytest tests/unit/test_wall_thickness.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pytest

from models.measurement.wall_thickness import (
    compute_wall_thickness,
    compute_relative_wall_thickness,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_lv_mask(H=112, W=112,
                  ivs_px=8, lvid_px=45, lvpw_px=8,
                  lv_rows=60):
    """
    Build a synthetic mask with horizontal LV + myo bands at the mid row.
    Layout (centred horizontally):
      [myo=2 × ivs_px] [lv=1 × lvid_px] [myo=2 × lvpw_px]
    The band is placed across `lv_rows` rows at the vertical centre.
    """
    mask = np.zeros((H, W), dtype=np.int32)
    cx = W // 2
    total = ivs_px + lvid_px + lvpw_px
    start = cx - total // 2

    row_start = H // 2 - lv_rows // 2
    row_end   = row_start + lv_rows

    for r in range(row_start, row_end):
        c = start
        mask[r, c:c + ivs_px]               = 2   # septal myo
        c += ivs_px
        mask[r, c:c + lvid_px]              = 1   # LV cavity
        c += lvid_px
        mask[r, c:c + lvpw_px]              = 2   # posterior myo
    return mask


# ── compute_wall_thickness ─────────────────────────────────────────────────────

class TestComputeWallThickness:
    def test_empty_mask_returns_zeros(self):
        mask = np.zeros((112, 112), dtype=np.int32)
        result = compute_wall_thickness(mask)
        assert result == {"IVSd": 0.0, "LVIDd": 0.0, "LVPWd": 0.0}

    def test_returns_all_keys(self):
        mask = _make_lv_mask()
        result = compute_wall_thickness(mask)
        assert set(result.keys()) == {"IVSd", "LVIDd", "LVPWd"}

    def test_positive_values(self):
        mask = _make_lv_mask(ivs_px=8, lvid_px=40, lvpw_px=8)
        result = compute_wall_thickness(mask)
        assert result["IVSd"]  > 0
        assert result["LVIDd"] > 0
        assert result["LVPWd"] > 0

    def test_lvid_proportional_to_pixel_size(self):
        mask = _make_lv_mask(lvid_px=40)
        r1 = compute_wall_thickness(mask, pixel_size_cm=0.1)
        r2 = compute_wall_thickness(mask, pixel_size_cm=0.2)
        assert abs(r2["LVIDd"] - 2 * r1["LVIDd"]) < 0.05

    def test_thicker_walls_give_larger_ivsd(self):
        thin = _make_lv_mask(ivs_px=5,  lvid_px=40, lvpw_px=5)
        thick = _make_lv_mask(ivs_px=12, lvid_px=40, lvpw_px=12)
        r_thin  = compute_wall_thickness(thin)
        r_thick = compute_wall_thickness(thick)
        assert r_thick["IVSd"]  > r_thin["IVSd"]
        assert r_thick["LVPWd"] > r_thin["LVPWd"]

    def test_larger_lv_gives_larger_lvidd(self):
        small = _make_lv_mask(lvid_px=30)
        large = _make_lv_mask(lvid_px=50)
        r_small = compute_wall_thickness(small)
        r_large = compute_wall_thickness(large)
        assert r_large["LVIDd"] > r_small["LVIDd"]

    def test_too_few_lv_rows_returns_zeros(self):
        # Only 3 rows of LV — below the ≥4 row threshold
        mask = _make_lv_mask(lv_rows=3)
        result = compute_wall_thickness(mask)
        assert result == {"IVSd": 0.0, "LVIDd": 0.0, "LVPWd": 0.0}

    def test_values_in_cm(self):
        # 8 px × 0.1 cm/px = 0.8 cm for IVSd/LVPWd, 45 px × 0.1 = 4.5 cm LVIDd
        mask = _make_lv_mask(ivs_px=8, lvid_px=45, lvpw_px=8, lv_rows=60)
        result = compute_wall_thickness(mask, pixel_size_cm=0.1)
        assert abs(result["IVSd"]  - 0.8) < 0.05
        assert abs(result["LVPWd"] - 0.8) < 0.05
        assert abs(result["LVIDd"] - 4.5) < 0.1


# ── compute_relative_wall_thickness ──────────────────────────────────────────

class TestComputeRelativeWallThickness:
    def test_normal_rwt(self):
        # (0.8 + 0.8) / 5.0 = 0.32 → normal
        rwt = compute_relative_wall_thickness(0.8, 0.8, 5.0)
        assert abs(rwt - 0.32) < 0.01

    def test_elevated_rwt(self):
        # (1.2 + 1.2) / 4.5 ≈ 0.533 → elevated
        rwt = compute_relative_wall_thickness(1.2, 1.2, 4.5)
        assert rwt > 0.42

    def test_zero_lvidd_returns_zero(self):
        assert compute_relative_wall_thickness(1.0, 1.0, 0.0) == 0.0

    def test_zero_walls_returns_zero(self):
        assert compute_relative_wall_thickness(0.0, 0.0, 5.0) == 0.0

    def test_symmetric_walls(self):
        # IVSd == LVPWd should give RWT = 2*IVSd / LVIDd
        ivsd = 0.9
        lvidd = 4.8
        rwt = compute_relative_wall_thickness(ivsd, ivsd, lvidd)
        expected = round(2 * ivsd / lvidd, 3)
        assert abs(rwt - expected) < 0.001
