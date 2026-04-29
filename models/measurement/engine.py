"""
Measurement Engine — orchestrates all quantitative measurements from masks.
Returns a structured dict ready for the report generator.
"""
import numpy as np
from models.measurement.lvef import compute_lvef, mask_to_volume_ml
from models.measurement.wall_thickness import (
    compute_wall_thickness,
    compute_relative_wall_thickness,
)
from models.measurement.strain import compute_gls, classify_gls
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import NORMAL_RANGES, NORMAL_RANGES_MALE, NORMAL_RANGES_FEMALE


def _get_ranges(sex: str = "") -> dict:
    """Return normal ranges appropriate for sex ('M', 'F', or '' for generic)."""
    if sex == "M":
        return NORMAL_RANGES_MALE
    if sex == "F":
        return NORMAL_RANGES_FEMALE
    return NORMAL_RANGES


def classify_ef(ef: float) -> str:
    """Return clinical EF category per ASE/ESC guidelines."""
    if ef >= 53:
        return "Normal (HFpEF range)"
    elif ef >= 41:
        return "Mildly reduced (HFmrEF)"
    elif ef >= 30:
        return "Moderately reduced"
    else:
        return "Severely reduced (HFrEF)"


def flag_abnormal(key: str, value: float, sex: str = "") -> str | None:
    """Return 'LOW', 'HIGH', or None based on sex-specific normal ranges."""
    ranges = _get_ranges(sex)
    if key not in ranges:
        return None
    r = ranges[key]
    if value < r.get("min", -999):
        return "LOW"
    if value > r.get("max", 999):
        return "HIGH"
    return None


def _bsa(height_cm: float, weight_kg: float) -> float | None:
    """Body surface area via Mosteller formula: sqrt(H*W/3600). Returns None if inputs invalid."""
    if height_cm > 0 and weight_kg > 0:
        return round(float(np.sqrt(height_cm * weight_kg / 3600)), 2)
    return None


def _lv_mass_g(lvidd: float, ivsd: float, lvpwd: float) -> float:
    """ASE linear cubed formula: LVM = 0.8*(1.04*((d+s+pw)^3 - d^3)) + 0.6 grams."""
    if lvidd <= 0:
        return 0.0
    cube_outer = (lvidd + ivsd + lvpwd) ** 3
    cube_inner = lvidd ** 3
    return round(0.8 * (1.04 * (cube_outer - cube_inner)) + 0.6, 1)


def run_measurements(masks: np.ndarray,
                     ed_mask: np.ndarray | None = None,
                     pixel_size_cm: float = 0.1,
                     patient_info: dict | None = None) -> dict:
    """
    Run all measurements on segmentation output.

    Args:
        masks:          (T, H, W) int segmentation masks for full video.
        ed_mask:        (H, W) ED frame mask (optional; derived automatically).
        pixel_size_cm:  Physical pixel size in cm.
        patient_info:   Optional dict with keys: sex ('M'/'F'/''), height_cm,
                        weight_kg, heart_rate.

    Returns:
        Nested dict with all measurements, flags, and clinical interpretation.
    """
    pi = patient_info or {}
    sex_raw = str(pi.get("sex", "")).strip().upper()
    sex = sex_raw[:1] if sex_raw[:1] in ("M", "F") else ""
    height_cm = float(pi.get("height_cm") or 0)
    weight_kg = float(pi.get("weight_kg") or 0)
    heart_rate = float(pi.get("heart_rate") or 0)
    bsa = _bsa(height_cm, weight_kg)

    # ── LVEF & volumes ──────────────────────────────────────────────────────
    lvef_result = compute_lvef(masks, pixel_size_cm)
    ef = lvef_result["LVEF"]
    lvedv = lvef_result["LVEDV"]
    lvesv = lvef_result["LVESV"]

    # ── Wall thickness on ED frame ──────────────────────────────────────────
    if ed_mask is None:
        ed_mask = masks[lvef_result["ed_frame"]]
    wt_ed = compute_wall_thickness(ed_mask, pixel_size_cm)
    rwt = compute_relative_wall_thickness(wt_ed["IVSd"], wt_ed["LVPWd"], wt_ed["LVIDd"])

    # ── LVIDs — wall thickness on ES frame ─────────────────────────────────
    es_mask = masks[lvef_result["es_frame"]]
    wt_es = compute_wall_thickness(es_mask, pixel_size_cm)
    lv_ids = wt_es["LVIDd"]   # LV internal diameter at systole

    # ── LV mass (ASE cubed formula) ─────────────────────────────────────────
    lvm = _lv_mass_g(wt_ed["LVIDd"], wt_ed["IVSd"], wt_ed["LVPWd"])

    # ── Stroke volume & cardiac output ──────────────────────────────────────
    lvsv = round(lvedv - lvesv, 1)
    co = round(lvsv * heart_rate / 1000.0, 2) if heart_rate > 0 and lvsv > 0 else None

    # ── Indexed values (require BSA) ────────────────────────────────────────
    lvedvi = round(lvedv / bsa, 1) if bsa else None
    lvesvi = round(lvesv / bsa, 1) if bsa else None
    lvmi   = round(lvm / bsa, 1)   if bsa and lvm > 0 else None
    lvidd_idx = round(wt_ed["LVIDd"] / bsa, 2) if bsa else None
    lvids_idx = round(lv_ids / bsa, 2) if bsa else None

    # ── GLS ─────────────────────────────────────────────────────────────────
    gls_result = compute_gls(masks, lvef_result["ed_frame"], lvef_result["es_frame"],
                             pixel_size_cm)
    gls_val = gls_result["GLS"]

    # ── LA area & volume ────────────────────────────────────────────────────
    la_pixels = (ed_mask == 3).sum()
    la_area_cm2 = round(la_pixels * pixel_size_cm ** 2, 1)
    lav = round(mask_to_volume_ml(ed_mask, pixel_size_cm, label=3), 1)
    lavi = round(lav / bsa, 1) if bsa and lav > 0 else None

    # ── LV geometry (ASE 4-pattern classification) ──────────────────────────
    lvm_threshold = (115 if sex == "M" else 95 if sex == "F" else 200)
    lvm_indexed_threshold = (115 if sex == "M" else 95 if sex == "F" else None)
    lvm_elevated = (
        (lvmi > lvm_indexed_threshold if lvmi is not None and lvm_indexed_threshold else False)
        or (lvm > lvm_threshold if lvmi is None else False)
    )

    if rwt > 0.42 and lvm_elevated:
        lv_geometry = "Concentric LVH"
    elif rwt > 0.42:
        lv_geometry = "Concentric remodelling"
    elif lvm_elevated:
        lv_geometry = "Eccentric LVH"
    else:
        lv_geometry = "Normal geometry"

    # ── Build structured result ─────────────────────────────────────────────
    measurements = {
        # LV Function
        "LVEF":  {"value": ef,    "unit": "%",  "flag": flag_abnormal("LVEF",  ef,    sex)},
        "GLS":   {"value": gls_val, "unit": "%",
                  "flag": flag_abnormal("GLS", gls_val, sex) if gls_val is not None else None},
        "GLS_category":  gls_result["GLS_category"],
        "GLS_curve":     gls_result["GLS_curve"],
        "GLS_curve_raw": gls_result["GLS_curve_raw"],
        "GLS_L_ED":      gls_result["L_ED"],
        "GLS_L_ES":      gls_result["L_ES"],
        "GLS_reliable":  gls_result["reliable"],
        "LVEDV": {"value": lvedv, "unit": "mL", "flag": flag_abnormal("LVEDV", lvedv, sex)},
        "LVESV": {"value": lvesv, "unit": "mL", "flag": flag_abnormal("LVESV", lvesv, sex)},
        "LVSV":  {"value": lvsv,  "unit": "mL", "flag": flag_abnormal("LVSV",  lvsv,  sex)},
        "EF_category": classify_ef(ef),

        # Wall dimensions (ED)
        "IVSd":  {"value": wt_ed["IVSd"],  "unit": "cm", "flag": flag_abnormal("IVSd",  wt_ed["IVSd"],  sex)},
        "LVIDd": {"value": wt_ed["LVIDd"], "unit": "cm", "flag": flag_abnormal("LVIDd", wt_ed["LVIDd"], sex)},
        "LVPWd": {"value": wt_ed["LVPWd"], "unit": "cm", "flag": flag_abnormal("LVPWd", wt_ed["LVPWd"], sex)},
        "LVIDs": {"value": lv_ids,          "unit": "cm", "flag": flag_abnormal("LVIDs", lv_ids,         sex)},
        "RWT":   {"value": rwt, "unit": "", "flag": "HIGH" if rwt > 0.42 else None},
        "LVIDd_index": {"value": lvidd_idx, "unit": "cm/m2", "flag": flag_abnormal("LVIDd_index", lvidd_idx, sex) if lvidd_idx is not None else None},
        "LVIDs_index": {"value": lvids_idx, "unit": "cm/m2", "flag": flag_abnormal("LVIDs_index", lvids_idx, sex) if lvids_idx is not None else None},

        # LV mass
        "LVM":   {"value": lvm,   "unit": "g",    "flag": flag_abnormal("LVM",  lvm,   sex)},
        "LVMi":  {"value": lvmi,  "unit": "g/m2", "flag": flag_abnormal("LVMi", lvmi,  sex) if lvmi is not None else None},

        # Indexed volumes (None when BSA unavailable)
        "LVEDVi": {"value": lvedvi, "unit": "mL/m2", "flag": flag_abnormal("LVEDVi", lvedvi, sex) if lvedvi is not None else None},
        "LVESVi": {"value": lvesvi, "unit": "mL/m2", "flag": flag_abnormal("LVESVi", lvesvi, sex) if lvesvi is not None else None},

        # Cardiac output
        "CO":    {"value": co, "unit": "L/min", "flag": flag_abnormal("CO", co, sex) if co is not None else None},

        # LA
        "LA_area": {"value": la_area_cm2, "unit": "cm2", "flag": None},
        "LAV":     {"value": lav,  "unit": "mL",    "flag": flag_abnormal("LAV",  lav,  sex)},
        "LAVi":    {"value": lavi, "unit": "mL/m2", "flag": flag_abnormal("LAVi", lavi, sex) if lavi is not None else None},

        # Anthropometrics
        "BSA": bsa,
        "sex": sex,

        # Frame info
        "ed_frame":  lvef_result["ed_frame"],
        "es_frame":  lvef_result["es_frame"],
        "lv_areas":  lvef_result["lv_areas"],
        "LV_geometry": lv_geometry,
    }

    return measurements
