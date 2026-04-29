"""
LVEF & Volume calculation — Modified Simpson's Biplane Method (ASE standard).

Given per-frame LV cavity masks (from segmentation), the engine:
1. Detects End-Diastole (ED) and End-Systole (ES) frames.
2. Applies the disk-summation formula to compute LVEDV and LVESV.
3. Computes LVEF = (LVEDV - LVESV) / LVEDV * 100.
"""
import numpy as np
from typing import Tuple


# ── Frame selection ────────────────────────────────────────────────────────────

def compute_lv_areas(masks: np.ndarray) -> np.ndarray:
    """
    Compute LV cavity area (pixel count) per frame.

    Args:
        masks: (T, H, W) int array, label 1 = LV cavity.
    Returns:
        areas: (T,) float array of pixel counts.
    """
    return (masks == 1).sum(axis=(1, 2)).astype(float)


def find_ed_es_frames(masks: np.ndarray,
                      areas: np.ndarray | None = None) -> Tuple[int, int]:
    """
    Identify end-diastole (max LV area) and end-systole (min LV area) frames.

    Args:
        masks:  (T, H, W) int array. Used only if areas is None.
        areas:  Pre-computed LV area array (T,). Pass to avoid recomputation.

    Returns:
        (ed_idx, es_idx)
    """
    if areas is None:
        areas = compute_lv_areas(masks)
    ed_idx = int(np.argmax(areas))
    es_idx = int(np.argmin(areas))
    return ed_idx, es_idx


# ── Volume estimation ──────────────────────────────────────────────────────────

def mask_to_volume_ml(mask: np.ndarray, pixel_size_cm: float = 0.1,
                      label: int = 1) -> float:
    """
    Estimate chamber volume (mL) from a 2D segmentation mask using the
    area-length disk-summation approximation (monoplane simplified form).

    The chamber is modelled as a stack of N=20 circular disks of equal height,
    where each disk radius is derived from the local mask width.

    Args:
        mask:           (H, W) segmentation mask.
        pixel_size_cm:  Physical size of one pixel in cm.
        label:          Segmentation label to extract (1=LV cavity, 3=LA).

    Returns:
        volume in mL (cm³).
    """
    lv_mask = (mask == label).astype(np.uint8)
    if lv_mask.sum() == 0:
        return 0.0

    # Find LV bounding box rows
    rows = np.where(lv_mask.any(axis=1))[0]
    if len(rows) < 2:
        return 0.0

    row_min, row_max = rows[0], rows[-1]
    L = (row_max - row_min) * pixel_size_cm   # LV long-axis length (cm)
    if L <= 0:
        return 0.0

    # 20-disk model
    N = 20
    row_indices = np.linspace(row_min, row_max, N, dtype=int)
    disk_height = L / N   # cm

    volume_cm3 = 0.0
    for row in row_indices:
        cols = np.where(lv_mask[row] == 1)[0]
        if len(cols) == 0:
            continue
        width_px = cols[-1] - cols[0] + 1
        # Diameter of disk = width; assume circular cross-section
        d = width_px * pixel_size_cm   # cm
        r = d / 2
        volume_cm3 += np.pi * r ** 2 * disk_height

    return volume_cm3  # 1 cm³ = 1 mL


# ── Main LVEF computation ──────────────────────────────────────────────────────

def compute_lvef(masks: np.ndarray,
                 pixel_size_cm: float = 0.1) -> dict:
    """
    Compute LVEF and volumes from segmentation masks.

    Args:
        masks:          (T, H, W) int array, label 1 = LV cavity.
        pixel_size_cm:  Physical pixel size in cm.

    Returns:
        {
          'LVEF':   float (%),
          'LVEDV':  float (mL),
          'LVESV':  float (mL),
          'ed_frame': int,
          'es_frame': int,
          'lv_areas': np.ndarray (T,)
        }
    """
    areas = compute_lv_areas(masks)
    ed_idx, es_idx = find_ed_es_frames(masks, areas=areas)

    lvedv = mask_to_volume_ml(masks[ed_idx], pixel_size_cm)
    lvesv = mask_to_volume_ml(masks[es_idx], pixel_size_cm)

    lvef = (lvedv - lvesv) / lvedv * 100.0 if lvedv > 0 else 0.0

    return {
        "LVEF": round(lvef, 1),
        "LVEDV": round(lvedv, 1),
        "LVESV": round(lvesv, 1),
        "ed_frame": ed_idx,
        "es_frame": es_idx,
        "lv_areas": areas,
    }
