"""
Wall thickness measurements from segmentation masks.
Computes IVS (interventricular septum) and LVPW (posterior wall) thickness.
Works on PLAX-view masks or approximated from A4C myocardium label.

Label convention: 1 = LV cavity, 2 = myocardium, 3 = LA
"""
import numpy as np


def compute_wall_thickness(mask: np.ndarray,
                           pixel_size_cm: float = 0.1) -> dict:
    """
    Estimate wall thicknesses from a 2D segmentation mask.

    Method: At mid-LV level (50% of LV long axis), scan left→right:
    - IVSd: thickness of myocardium on the septal (left) side
    - LVIDd: inner diameter of LV cavity at mid level
    - LVPWd: thickness of myocardium on the posterior (right) side

    Args:
        mask:           (H, W) int array. 1=LV_endo, 2=myocardium, 3=LA.
        pixel_size_cm:  Physical pixel size in cm.

    Returns:
        {
          'IVSd':  float (cm),
          'LVIDd': float (cm),
          'LVPWd': float (cm),
        }
        All values 0.0 if LV not found.
    """
    lv = (mask == 1)
    myo = (mask == 2)

    rows = np.where(lv.any(axis=1))[0]
    if len(rows) < 4:
        return {"IVSd": 0.0, "LVIDd": 0.0, "LVPWd": 0.0}

    # Sample at 50% of LV long axis
    mid_row = rows[len(rows) // 2]

    lv_row = lv[mid_row]
    myo_row = myo[mid_row]

    lv_cols = np.where(lv_row)[0]
    if len(lv_cols) < 2:
        return {"IVSd": 0.0, "LVIDd": 0.0, "LVPWd": 0.0}

    lv_left = lv_cols[0]
    lv_right = lv_cols[-1]
    lvid_px = lv_right - lv_left + 1

    # Septal wall: myocardium pixels immediately left of LV cavity
    septal_cols = np.where(myo_row[:lv_left])[0]
    ivs_px = len(septal_cols)

    # Posterior wall: myocardium pixels immediately right of LV cavity
    post_cols = np.where(myo_row[lv_right:])[0]
    lvpw_px = len(post_cols)

    return {
        "IVSd":  round(ivs_px * pixel_size_cm, 2),
        "LVIDd": round(lvid_px * pixel_size_cm, 2),
        "LVPWd": round(lvpw_px * pixel_size_cm, 2),
    }


def compute_relative_wall_thickness(ivsd: float, lvpwd: float,
                                    lvidd: float) -> float:
    """
    RWT = (IVSd + LVPWd) / LVIDd
    Normal < 0.42.  Elevated → concentric geometry.
    """
    if lvidd <= 0:
        return 0.0
    return round((ivsd + lvpwd) / lvidd, 3)
