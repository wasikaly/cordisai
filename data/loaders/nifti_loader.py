"""
NIfTI loader for CAMUS dataset.
Loads 2CH/4CH sequences and their segmentation masks.
"""
import numpy as np
from pathlib import Path

try:
    import SimpleITK as sitk
    _USE_SITK = True
except ImportError:
    import nibabel as nib
    _USE_SITK = False


def load_nifti(path: str | Path) -> np.ndarray:
    """Load a .nii.gz file and return (H, W) or (T, H, W) numpy array."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    if _USE_SITK:
        img = sitk.ReadImage(str(path))
        arr = sitk.GetArrayFromImage(img)   # (Z, Y, X) or (Y, X) for 2D
    else:
        img = nib.load(str(path))
        arr = img.get_fdata().T             # align axes

    return arr.astype(np.float32)


def load_camus_patient(patient_dir: str | Path, view: str = "4CH") -> dict:
    """
    Load all frames and masks for one CAMUS patient.

    Args:
        patient_dir: Path like '.../patient0001/'
        view:        '2CH' or '4CH'

    Returns:
        {
          'ED':      (H, W) ED image,
          'ES':      (H, W) ES image,
          'ED_gt':   (H, W) ED mask  (0=bg, 1=LVendo, 2=myocardium, 3=LA),
          'ES_gt':   (H, W) ES mask,
          'sequence':(T, H, W) full half-sequence,
        }
    """
    p = Path(patient_dir)
    pid = p.name                     # e.g. 'patient0001'
    v = view                         # '2CH' or '4CH'

    result = {}
    for key, suffix in [
        ("ED",        f"{pid}_{v}_ED.nii.gz"),
        ("ES",        f"{pid}_{v}_ES.nii.gz"),
        ("ED_gt",     f"{pid}_{v}_ED_gt.nii.gz"),
        ("ES_gt",     f"{pid}_{v}_ES_gt.nii.gz"),
        ("sequence",  f"{pid}_{v}_half_sequence.nii.gz"),
    ]:
        fpath = p / suffix
        if fpath.exists():
            arr = load_nifti(fpath)
            # NIfTI from CAMUS: (H, W) for single frames, (T, H, W) for sequence
            if arr.ndim == 3 and key not in ("sequence",):
                arr = arr[0]         # take first slice if 3D single frame
            result[key] = arr

    return result


def normalize_image(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize to [0, 1]."""
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-8:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)
