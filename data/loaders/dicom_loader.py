"""
DICOM loader for echocardiography studies.
Handles single-frame, multi-frame (Enhanced DICOM), and DICOM sequences.

Returns (T, H, W) float32 grayscale frames normalized to [0, 1].
"""
import numpy as np
from pathlib import Path

try:
    import pydicom
    _HAS_PYDICOM = True
except ImportError:
    _HAS_PYDICOM = False


def _require_pydicom():
    if not _HAS_PYDICOM:
        raise ImportError("pydicom not installed. Run: pip install pydicom")


def load_dicom_video(path: str | Path) -> np.ndarray:
    """
    Load a DICOM file and return (T, H, W) float32 grayscale frames.

    Supports:
    - Multi-frame DICOM (NumberOfFrames > 1)  — echocardiography cine loops
    - Single-frame DICOM                       — returns (1, H, W)

    Args:
        path: Path to .dcm file.

    Returns:
        np.ndarray of shape (T, H, W), float32, values in [0, 1].
    """
    _require_pydicom()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    ds = pydicom.dcmread(str(path))
    pixels = ds.pixel_array  # raw pixels; shape depends on modality

    # Apply DICOM LUT / window if present (best-effort)
    try:
        from pydicom.pixels import apply_modality_lut, apply_voi_lut
        pixels = apply_modality_lut(pixels, ds)
        pixels = apply_voi_lut(pixels, ds)
    except Exception:
        pass  # fall back to raw pixels

    pixels = pixels.astype(np.float32)

    # Shape normalisation → (T, H, W)
    if pixels.ndim == 2:
        pixels = pixels[np.newaxis]                    # single frame → (1, H, W)
    elif pixels.ndim == 3:
        n = int(getattr(ds, "NumberOfFrames", 1))
        if n > 1:
            pass                                        # already (T, H, W)
        else:
            # Could be (H, W, 3) RGB — convert to gray
            if pixels.shape[-1] in (3, 4):
                pixels = (pixels[..., 0] * 0.299 +
                          pixels[..., 1] * 0.587 +
                          pixels[..., 2] * 0.114).astype(np.float32)
                pixels = pixels[np.newaxis]
            else:
                pixels = pixels[np.newaxis]
    elif pixels.ndim == 4:
        # (T, H, W, C) — RGB cine loop; convert to gray
        pixels = (pixels[..., 0] * 0.299 +
                  pixels[..., 1] * 0.587 +
                  pixels[..., 2] * 0.114).astype(np.float32)

    # Normalise to [0, 1]
    mn, mx = pixels.min(), pixels.max()
    if mx - mn > 1e-8:
        pixels = (pixels - mn) / (mx - mn)
    else:
        pixels = np.zeros_like(pixels)

    return pixels


def load_dicom_series(series_dir: str | Path) -> np.ndarray:
    """
    Load a directory of single-frame DICOM files as a video sequence.
    Files are sorted by InstanceNumber (or filename as fallback).

    Returns:
        (T, H, W) float32 grayscale video.
    """
    _require_pydicom()
    series_dir = Path(series_dir)
    dcm_files = sorted(series_dir.glob("*.dcm"))
    if not dcm_files:
        raise FileNotFoundError(f"No .dcm files in {series_dir}")

    # Sort by InstanceNumber if available
    def sort_key(f):
        try:
            ds = pydicom.dcmread(str(f), stop_before_pixels=True)
            return int(getattr(ds, "InstanceNumber", 0))
        except Exception:
            return 0

    dcm_files.sort(key=sort_key)
    frames = []
    for f in dcm_files:
        single = load_dicom_video(f)     # (1, H, W)
        frames.append(single[0])        # (H, W)

    return np.stack(frames, axis=0)     # (T, H, W)


def get_dicom_metadata(path: str | Path) -> dict:
    """
    Extract key DICOM metadata relevant to echocardiography analysis.

    Returns:
        dict with patient info, modality, dimensions, etc.
    """
    _require_pydicom()
    ds = pydicom.dcmread(str(path), stop_before_pixels=True)

    def _get(tag, default="N/A"):
        return str(getattr(ds, tag, default))

    return {
        "patient_name":   _get("PatientName"),
        "patient_id":     _get("PatientID"),
        "patient_dob":    _get("PatientBirthDate"),
        "study_date":     _get("StudyDate"),
        "modality":       _get("Modality"),
        "manufacturer":   _get("Manufacturer"),
        "rows":           int(getattr(ds, "Rows", 0)),
        "columns":        int(getattr(ds, "Columns", 0)),
        "num_frames":     int(getattr(ds, "NumberOfFrames", 1)),
        "frame_rate":     float(getattr(ds, "RecommendedDisplayFrameRate",
                                        getattr(ds, "CineRate", 0))),
        "pixel_spacing":  list(getattr(ds, "PixelSpacing", [0.0, 0.0])),
        "institution":    _get("InstitutionName"),
    }
