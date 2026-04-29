"""
Unit tests for models/disease_detection/classifier.py
Run with: python -m pytest tests/unit/test_disease_detection.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from models.disease_detection.classifier import detect_diseases


# ── Helpers ───────────────────────────────────────────────────────────────────

def _meas(ef=60.0, ivsd=0.8, lvpwd=0.8, lvidd=4.5, rwt=0.35, la_area=16.0):
    """Construct a minimal measurements dict with normal defaults."""
    return {
        "LVEF":    {"value": ef},
        "IVSd":    {"value": ivsd},
        "LVPWd":   {"value": lvpwd},
        "LVIDd":   {"value": lvidd},
        "RWT":     {"value": rwt},
        "LA_area": {"value": la_area},
    }


# ── Heart Failure ─────────────────────────────────────────────────────────────

class TestHeartFailure:
    def test_normal_ef_no_hf(self):
        result = detect_diseases(_meas(ef=60.0))
        assert result["heart_failure"]["flag"] is False

    def test_ef_50_boundary_no_hf(self):
        result = detect_diseases(_meas(ef=50.0))
        assert result["heart_failure"]["flag"] is False

    def test_ef_49_hf_mref(self):
        result = detect_diseases(_meas(ef=49.0))
        hf = result["heart_failure"]
        assert hf["flag"] is True
        assert "HFmrEF" in hf["type"]

    def test_ef_39_hfref(self):
        result = detect_diseases(_meas(ef=39.0))
        hf = result["heart_failure"]
        assert hf["flag"] is True
        assert "HFrEF" in hf["type"]

    def test_hfref_note_present(self):
        result = detect_diseases(_meas(ef=35.0))
        assert any("HFrEF" in n or "Severely" in n for n in result["notes"])


# ── LV Hypertrophy ────────────────────────────────────────────────────────────

class TestLvHypertrophy:
    def test_normal_walls_no_hypertrophy(self):
        result = detect_diseases(_meas(ivsd=0.9, lvpwd=0.9))
        assert result["lv_hypertrophy"]["flag"] is False

    def test_thick_ivsd_hypertrophy(self):
        result = detect_diseases(_meas(ivsd=1.3, lvpwd=0.9))
        assert result["lv_hypertrophy"]["flag"] is True

    def test_thick_lvpwd_hypertrophy(self):
        result = detect_diseases(_meas(ivsd=0.9, lvpwd=1.3))
        assert result["lv_hypertrophy"]["flag"] is True

    def test_concentric_pattern(self):
        # RWT > 0.42 + no dilation → concentric LVH
        result = detect_diseases(_meas(ivsd=1.3, rwt=0.50, lvidd=4.5))
        hyp = result["lv_hypertrophy"]
        assert hyp["flag"] is True
        assert "Concentric" in hyp["type"]

    def test_eccentric_pattern(self):
        # RWT <= 0.42 or dilated LV → eccentric LVH
        result = detect_diseases(_meas(ivsd=1.3, rwt=0.30, lvidd=6.0))
        hyp = result["lv_hypertrophy"]
        assert hyp["flag"] is True
        assert "Eccentric" in hyp["type"]


# ── LV Dilatation ─────────────────────────────────────────────────────────────

class TestLvDilatation:
    def test_normal_size_no_dilatation(self):
        result = detect_diseases(_meas(lvidd=5.0))
        assert result["lv_dilatation"]["flag"] is False

    def test_dilated(self):
        result = detect_diseases(_meas(lvidd=6.0))
        assert result["lv_dilatation"]["flag"] is True

    def test_boundary_59_not_dilated(self):
        # ASE 2015 male upper normal limit = 5.9 cm (used for unknown sex)
        result = detect_diseases(_meas(lvidd=5.9))
        assert result["lv_dilatation"]["flag"] is False

    def test_boundary_above_59_dilated(self):
        result = detect_diseases(_meas(lvidd=6.0))
        assert result["lv_dilatation"]["flag"] is True

    def test_female_threshold_53(self):
        # Female threshold is 5.3 cm
        meas = _meas(lvidd=5.4)
        meas["sex"] = "F"
        result = detect_diseases(meas)
        assert result["lv_dilatation"]["flag"] is True


# ── LA Enlargement ────────────────────────────────────────────────────────────

class TestLaEnlargement:
    def test_normal_la(self):
        result = detect_diseases(_meas(la_area=18.0))
        assert result["la_enlargement"]["flag"] is False

    def test_normal_la_boundary(self):
        result = detect_diseases(_meas(la_area=20.0))
        assert result["la_enlargement"]["flag"] is False

    def test_enlarged_la(self):
        result = detect_diseases(_meas(la_area=24.0))
        assert result["la_enlargement"]["flag"] is True


# ── Amyloidosis suspicion ─────────────────────────────────────────────────────

class TestAmyloidosisSuspicion:
    def test_classic_pattern_suspected(self):
        # LVH + preserved EF + concentric (RWT > 0.42)
        result = detect_diseases(_meas(ef=58.0, ivsd=1.4, lvpwd=1.4, rwt=0.55))
        assert result["amyloidosis_suspicion"]["flag"] is True

    def test_low_ef_not_suspected(self):
        # Amyloidosis pattern requires preserved EF
        result = detect_diseases(_meas(ef=35.0, ivsd=1.4, rwt=0.55))
        assert result["amyloidosis_suspicion"]["flag"] is False

    def test_no_lvh_not_suspected(self):
        result = detect_diseases(_meas(ef=60.0, ivsd=0.9, lvpwd=0.9, rwt=0.55))
        assert result["amyloidosis_suspicion"]["flag"] is False

    def test_normal_rwt_not_suspected(self):
        result = detect_diseases(_meas(ef=60.0, ivsd=1.4, rwt=0.30))
        assert result["amyloidosis_suspicion"]["flag"] is False


# ── Output structure ──────────────────────────────────────────────────────────

class TestOutputStructure:
    def test_all_keys_present(self):
        result = detect_diseases(_meas())
        for key in ("heart_failure", "lv_hypertrophy", "lv_dilatation",
                    "la_enlargement", "amyloidosis_suspicion", "notes"):
            assert key in result

    def test_notes_is_list(self):
        result = detect_diseases(_meas())
        assert isinstance(result["notes"], list)

    def test_normal_case_no_notes(self):
        result = detect_diseases(_meas())
        assert result["notes"] == []
