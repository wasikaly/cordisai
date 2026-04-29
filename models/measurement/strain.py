"""
GLS (Global Longitudinal Strain) estimation from 2D LV segmentation masks.

Method: endocardial contour length change from ED to ES.
  GLS = (L_ES - L_ED) / L_ED * 100%

Rationale: In apical views (A4C) the LV is elongated along the long axis, so
the endocardial perimeter is dominated by the longitudinal direction. Contour-
length strain is validated as a mask-based proxy for speckle-tracking GLS
(see CAMUS challenge papers, Leclerc et al. 2019).

Normal GLS (ASE 2015): <= -16%  (more negative = better systolic function)
Values > -14%  → impaired; values > -8% → severe impairment.
Values < -30%  → likely artefact / measurement error.
"""
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter1d


# ── Low-level helpers ──────────────────────────────────────────────────────────

def _contour_perimeter_px(mask: np.ndarray, label: int = 1) -> float:
    """
    Return the total endocardial contour perimeter (pixels) for a given label.
    Uses the largest connected component if multiple exist.
    """
    region = (mask == label).astype(np.uint8)
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return 0.0
    cnt = max(contours, key=cv2.contourArea)
    if len(cnt) < 3:
        return 0.0
    return float(cv2.arcLength(cnt, closed=True))


def _lv_area_px(mask: np.ndarray) -> int:
    """Number of LV cavity pixels (label=1)."""
    return int((mask == 1).sum())


# ── Main GLS function ──────────────────────────────────────────────────────────

def compute_gls(masks: np.ndarray,
                ed_idx: int,
                es_idx: int,
                pixel_size_cm: float = 0.1,
                min_lv_area_px: int = 200) -> dict:
    """
    Estimate Global Longitudinal Strain (GLS) from per-frame LV cavity masks.

    Args:
        masks:           (T, H, W) int segmentation masks (label 1 = LV cavity).
        ed_idx:          End-diastole frame index.
        es_idx:          End-systole frame index.
        pixel_size_cm:   Physical pixel size in cm.
        min_lv_area_px:  Minimum LV area (pixels) at ED required for a valid
                         estimate. Below this the mask is considered empty/noisy.

    Returns:
        {
          'GLS':          float (%) — negative in normal hearts; None if invalid,
          'GLS_category': str — clinical category string,
          'GLS_curve':    np.ndarray (T,) — per-frame strain relative to ED
                          (smoothed with Gaussian sigma=1 for display),
          'GLS_curve_raw':np.ndarray (T,) — unsmoothed per-frame strain,
          'L_ED':         float (cm) — endocardial contour length at ED,
          'L_ES':         float (cm) — endocardial contour length at ES,
          'reliable':     bool — False if quality checks failed,
        }
    """
    _empty = {
        "GLS": None,
        "GLS_category": "Not computed",
        "GLS_curve": np.zeros(len(masks)),
        "GLS_curve_raw": np.zeros(len(masks)),
        "L_ED": 0.0,
        "L_ES": 0.0,
        "reliable": False,
    }

    # ── Quality gate ────────────────────────────────────────────────────────
    lv_area_ed = _lv_area_px(masks[ed_idx])
    if lv_area_ed < min_lv_area_px:
        return _empty

    l_ed_px = _contour_perimeter_px(masks[ed_idx])
    l_es_px = _contour_perimeter_px(masks[es_idx])

    l_ed = l_ed_px * pixel_size_cm
    l_es = l_es_px * pixel_size_cm

    # Require a plausible LV contour (>= 4 cm perimeter at ED)
    if l_ed < 4.0:
        return _empty

    # ES perimeter must be smaller than ED (systolic contraction)
    if l_es >= l_ed:
        # Masks may be degenerate — still compute but mark unreliable
        gls = round((l_es - l_ed) / l_ed * 100.0, 1)
        reliable = False
    else:
        gls = round((l_es - l_ed) / l_ed * 100.0, 1)
        reliable = True

    # ── Per-frame strain curve ───────────────────────────────────────────────
    curve_raw = np.array([
        round((_contour_perimeter_px(masks[i]) * pixel_size_cm - l_ed) / l_ed * 100.0, 2)
        for i in range(len(masks))
    ])

    # Light smoothing (sigma=1 frame) to reduce segmentation noise
    curve_smooth = gaussian_filter1d(curve_raw.astype(float), sigma=1)

    return {
        "GLS": gls,
        "GLS_category": classify_gls(gls),
        "GLS_curve": curve_smooth,
        "GLS_curve_raw": curve_raw,
        "L_ED": round(l_ed, 2),
        "L_ES": round(l_es, 2),
        "reliable": reliable,
    }


# ── Clinical classification ────────────────────────────────────────────────────

def classify_gls(gls: float | None) -> str:
    """
    Clinical GLS category per ASE/EAE consensus (Lang et al. 2015,
    Marwick et al. 2015).

    Note: these thresholds apply to speckle-tracking GLS; mask-based estimates
    may be ~1-2% less negative than true GLS. Interpret with caution.
    """
    if gls is None:
        return "Not computed"
    if gls <= -20:
        return "Normal (excellent)"
    elif gls <= -16:
        return "Normal"
    elif gls <= -12:
        return "Mildly impaired"
    elif gls <= -8:
        return "Moderately impaired"
    else:
        return "Severely impaired"
