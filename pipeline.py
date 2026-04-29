"""
HeartAI — Main inference pipeline.

Takes an echo video (AVI / DICOM) or a CAMUS NIfTI study and returns:
  - segmentation masks
  - measurements dict
  - disease detection dict
  - PDF report path

Two modes:
  1. Segmentation mode (default when checkpoints/segmentation.pt exists):
     video -> U-Net -> masks -> LVEF (Simpson's rule) + wall thickness
  2. Direct EF mode (fallback when seg checkpoint not available):
     video -> EFRegressor -> LVEF only (limited measurements)

Accepted inputs:
  - .avi  — EchoNet-Dynamic grayscale AVI
  - .dcm  — DICOM single-file multi-frame cine loop
  - dir   — CAMUS NIfTI patient directory OR DICOM series directory
"""
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

import torch
import cv2
from data.loaders.video_loader import load_video
from data.loaders.nifti_loader import load_camus_patient, normalize_image
from data.loaders.dicom_loader import load_dicom_video, load_dicom_series, get_dicom_metadata
from models.segmentation.inference import segment_video, has_checkpoint
from models.view_classifier.classifier import classify_view
from models.measurement.engine import run_measurements
from models.disease_detection.classifier import detect_diseases
from reporting.pdf.generator import generate_report
from reporting.fhir.exporter import build_fhir_bundle
from reporting.dicom_sr.generator import generate_dicom_sr
from config import DEVICE, EF_CHECKPOINT, IMG_SIZE


def _predict_ef_direct(video: np.ndarray, device: str) -> float:
    """
    Fallback: predict LVEF directly using EFRegressor if checkpoint exists.
    Returns predicted EF (%) or None if no checkpoint.
    """
    if not EF_CHECKPOINT.exists():
        return None

    from models.measurement.ef_regressor import EFRegressor
    model = EFRegressor(pretrained=False).to(device)
    state = torch.load(EF_CHECKPOINT, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.eval()

    # Sample max 32 evenly-spaced frames
    T = video.shape[0]
    indices = np.linspace(0, T - 1, min(T, 32), dtype=int)
    frames = video[indices]                              # (32, H, W)
    tensor = torch.from_numpy(frames).unsqueeze(1)      # (32, 1, H, W)
    tensor = tensor.unsqueeze(0).to(device)             # (1, 32, 1, H, W)

    with torch.no_grad():
        ef = model(tensor).item()

    return round(float(ef), 1)


def run_pipeline(
    input_path: str | Path,
    patient_info: dict | None = None,
    output_pdf: str | Path | None = None,
    device: str = DEVICE,
) -> dict:
    """
    End-to-end HeartAI analysis pipeline.

    Args:
        input_path:   Path to .avi video, .dcm DICOM file, or patient directory.
        patient_info: Optional patient metadata dict (auto-filled from DICOM if None).
        output_pdf:   Where to write the PDF (auto-named if None).
        device:       'cuda' or 'cpu'.

    Returns:
        {
          'masks':        (T, H, W) segmentation masks,
          'measurements': measurements dict,
          'diseases':     disease detection dict,
          'report_path':  Path to PDF,
          'mode':         'segmentation' | 'ef_regressor' | 'random_weights',
        }
    """
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    input_path = Path(input_path)

    # ── 1. Load video ────────────────────────────────────────────────────────
    dicom_meta = {}
    suffix = input_path.suffix.lower()

    if suffix == ".avi":
        print(f"[Pipeline] Loading AVI: {input_path.name}")
        video = load_video(input_path)                   # (T, H, W) float32

    elif suffix == ".dcm":
        print(f"[Pipeline] Loading DICOM: {input_path.name}")
        video = load_dicom_video(input_path)             # (T, H, W) float32
        try:
            dicom_meta = get_dicom_metadata(input_path)
            if patient_info is None:
                patient_info = {
                    "name":       dicom_meta.get("patient_name", "N/A"),
                    "id":         dicom_meta.get("patient_id", "N/A"),
                    "dob":        dicom_meta.get("patient_dob", "N/A"),
                    "study_date": dicom_meta.get("study_date", "N/A"),
                }
        except Exception:
            pass

    elif input_path.is_dir():
        # Try DICOM series first, fall back to CAMUS NIfTI
        dcm_files = list(input_path.glob("*.dcm"))
        if dcm_files:
            print(f"[Pipeline] Loading DICOM series: {input_path.name} ({len(dcm_files)} files)")
            video = load_dicom_series(input_path)        # (T, H, W) float32
        else:
            print(f"[Pipeline] Loading CAMUS patient: {input_path.name}")
            data = load_camus_patient(input_path, view="4CH")
            seq = data.get("sequence")
            if seq is None:
                raise ValueError("No sequence found in CAMUS patient dir.")
            if seq.ndim == 3 and seq.shape[0] > seq.shape[-1]:
                video = seq
            else:
                video = seq.transpose(2, 0, 1)
            video = normalize_image(video).astype(np.float32)
    else:
        raise ValueError(f"Unsupported input: {input_path}")

    # Resize frames to model input size if needed; track effective pixel size
    T, H_orig, W_orig = video.shape
    pixel_size_cm = 0.1   # default: 1 mm/px (reasonable for 112-px EchoNet frames)

    if suffix == ".dcm" and dicom_meta:
        spacing = dicom_meta.get("pixel_spacing", [0.0, 0.0])
        if spacing and spacing[0] > 0:
            # DICOM PixelSpacing is in mm; average row/col spacing → cm/px
            orig_spacing_cm = (float(spacing[0]) + float(spacing[1])) / 2 / 10.0
            # After resize H_orig → IMG_SIZE, physical pixel size scales proportionally
            pixel_size_cm = round(orig_spacing_cm * H_orig / IMG_SIZE, 4)
            print(f"[Pipeline] DICOM pixel spacing: {spacing} mm → "
                  f"effective {pixel_size_cm:.4f} cm/px after resize")

    if H_orig != IMG_SIZE or W_orig != IMG_SIZE:
        resized = np.stack(
            [cv2.resize(video[i], (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)
             for i in range(T)],
            axis=0,
        )
        video = resized

    print(f"[Pipeline] Video shape: {video.shape}, device: {device}")

    # ── 1b. View classification ───────────────────────────────────────────────
    view_result = classify_view(video, device=device)
    print(f"[Pipeline] View: {view_result['view']} "
          f"(confidence={view_result['confidence']:.2f}, "
          f"trained={view_result['trained']})")

    # ── 2. Segmentation ──────────────────────────────────────────────────────
    print("[Pipeline] Running segmentation...")
    masks = segment_video(video, device=device)          # (T, H, W) int
    seg_ready = has_checkpoint()
    mode = "segmentation" if seg_ready else "random_weights"

    # ── 3. Measurements ──────────────────────────────────────────────────────
    print("[Pipeline] Computing measurements...")
    measurements = run_measurements(masks, pixel_size_cm=pixel_size_cm,
                                    patient_info=patient_info)

    # ── 3b. EF override from direct regressor (if seg not trained yet) ───────
    if not seg_ready:
        ef_direct = _predict_ef_direct(video, device)
        if ef_direct is not None:
            print(f"[Pipeline] EF Regressor override: {ef_direct}%")
            measurements["LVEF"]["value"] = ef_direct
            from models.measurement.engine import classify_ef, flag_abnormal
            measurements["LVEF"]["flag"] = flag_abnormal("LVEF", ef_direct)
            measurements["EF_category"] = classify_ef(ef_direct)
            mode = "ef_regressor"

    # ── 4. Disease detection ──────────────────────────────────────────────────
    print("[Pipeline] Detecting conditions...")
    diseases = detect_diseases(measurements)

    # ── 5. Report ─────────────────────────────────────────────────────────────
    print("[Pipeline] Generating PDF report...")
    report_path = generate_report(
        measurements=measurements,
        diseases=diseases,
        patient_info=patient_info,
        output_path=output_pdf,
    )
    print(f"[Pipeline] Report saved: {report_path}")

    # ── 6. FHIR R4 bundle ─────────────────────────────────────────────────────
    fhir_bundle = build_fhir_bundle(measurements, diseases, patient_info)

    # ── 7. DICOM Structured Report ────────────────────────────────────────────
    print("[Pipeline] Generating DICOM SR...")
    try:
        dicom_sr_path = generate_dicom_sr(measurements, diseases, patient_info)
        print(f"[Pipeline] DICOM SR saved: {dicom_sr_path}")
    except Exception as exc:
        print(f"[Pipeline] DICOM SR generation failed (non-fatal): {exc}")
        dicom_sr_path = None

    return {
        "video":          video,
        "masks":          masks,
        "measurements":   measurements,
        "diseases":       diseases,
        "report_path":    report_path,
        "dicom_sr_path":  dicom_sr_path,
        "fhir_bundle":    fhir_bundle,
        "mode":           mode,
        "view":           view_result,
    }
