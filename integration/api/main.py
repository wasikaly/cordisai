"""
HeartAI REST API — FastAPI server for PACS / EMR integration.

Endpoints:
  POST /api/v1/analyze               — submit video/DICOM for analysis
  GET  /api/v1/studies/{study_id}    — get full results JSON
  GET  /api/v1/studies/{study_id}/report  — download PDF report
  GET  /api/v1/studies/{study_id}/status — get processing status
  GET  /api/v1/health                — liveness check

Usage:
    uvicorn integration.api.main:app --host 0.0.0.0 --port 8000 --reload
    # or from project root:
    python -m uvicorn integration.api.main:app --port 8000
"""
import sys
import uuid
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import REPORTS_DIR, DEVICE

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HeartAI API",
    description="Automated echocardiography analysis — AI-powered cardiac measurements.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store (replace with Redis/PostgreSQL for production) ─────────

_jobs: dict[str, dict] = {}           # study_id → job state
_executor = ThreadPoolExecutor(max_workers=2)

# Temp directory for uploaded files
_UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────────────

class StudyStatus(BaseModel):
    study_id: str
    status: str          # pending | processing | done | failed
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class AnalysisResult(BaseModel):
    study_id: str
    status: str
    mode: str
    view: dict
    measurements: dict
    diseases: dict
    report_path: Optional[str] = None
    frame_count: int = 0


# ── Background worker ─────────────────────────────────────────────────────────

def _save_overlay_frames(video: 'np.ndarray', masks: 'np.ndarray',
                         out_dir: Path) -> int:
    """Render original + segmentation overlay as PNG per frame."""
    import cv2
    import numpy as np

    # Color map for mask classes (BGR for cv2): LV=red, Myo=yellow, LA=blue
    COLORS = {
        1: np.array([60,  60,  220], dtype=np.uint8),   # LV  → red
        2: np.array([40,  200, 220], dtype=np.uint8),    # Myo → yellow
        3: np.array([220, 160, 60],  dtype=np.uint8),    # LA  → blue
    }
    ALPHA = 0.35

    count = min(len(video), len(masks))
    for i in range(count):
        # Grayscale frame → 3-channel
        frame = video[i]
        if frame.max() <= 1.0:
            frame = (frame * 255).astype(np.uint8)
        else:
            frame = frame.astype(np.uint8)
        rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        # Blend overlay
        overlay = rgb.copy()
        for label, color in COLORS.items():
            region = masks[i] == label
            overlay[region] = color
        blended = cv2.addWeighted(overlay, ALPHA, rgb, 1 - ALPHA, 0)

        # Upscale to 448×448 for crisp display
        blended = cv2.resize(blended, (448, 448), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(out_dir / f"{i:04d}.jpg"), blended, [cv2.IMWRITE_JPEG_QUALITY, 90])

    return count


def _run_analysis(study_id: str, file_path: Path, patient_info: dict):
    """Run pipeline in a thread (CPU/GPU bound work off the event loop)."""
    _jobs[study_id]["status"] = "processing"
    try:
        from pipeline import run_pipeline
        result = run_pipeline(
            input_path=file_path,
            patient_info=patient_info,
            device=DEVICE,
        )
        # Convert numpy arrays/scalars to serialisable types (recursive)
        import numpy as np

        def _to_python(obj):
            if isinstance(obj, dict):
                return {k: _to_python(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_to_python(i) for i in obj]
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            return obj

        video = result.pop("video", None)       # (T, H, W) float32
        masks = result.pop("masks", None)       # (T, H, W) int — class labels

        # Save overlay frames for frontend viewer
        frame_dir = _UPLOAD_DIR / study_id / "frames"
        frame_count = 0
        if video is not None and masks is not None:
            frame_dir.mkdir(parents=True, exist_ok=True)
            frame_count = _save_overlay_frames(video, masks, frame_dir)
        result["measurements"] = _to_python(result.get("measurements", {}))
        result["diseases"]     = _to_python(result.get("diseases", {}))
        result["view"]         = _to_python(result.get("view", {}))

        # Serialise FHIR bundle to JSON string for storage
        fhir_bundle = result.get("fhir_bundle")
        fhir_json = fhir_bundle.model_dump_json() if fhir_bundle is not None else None

        _jobs[study_id].update({
            "status":       "done",
            "completed_at": datetime.utcnow().isoformat(),
            "mode":         result.get("mode", ""),
            "view":         result.get("view", {}),
            "measurements": result.get("measurements", {}),
            "diseases":     result.get("diseases", {}),
            "report_path":  str(result.get("report_path", "")),
            "fhir_json":    fhir_json,
            "frame_count":  frame_count,
            "frame_dir":    str(frame_dir),
        })
    except Exception as exc:
        _jobs[study_id].update({
            "status":       "failed",
            "completed_at": datetime.utcnow().isoformat(),
            "error":        str(exc),
        })
    finally:
        # Clean up uploaded file
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health():
    import torch
    return {
        "status": "ok",
        "cuda_available": torch.cuda.is_available(),
        "active_jobs": sum(1 for j in _jobs.values() if j["status"] == "processing"),
    }


@app.post("/api/v1/analyze", response_model=StudyStatus, status_code=202)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Echo video (.avi or .dcm)"),
    patient_name: str   = Form(default="Anonymous"),
    patient_id:   str   = Form(default="N/A"),
    patient_dob:  str   = Form(default="N/A"),
    study_date:   str   = Form(default=""),
    sex:          str   = Form(default=""),           # "M" | "F" | ""
    height_cm:    float = Form(default=0.0),
    weight_kg:    float = Form(default=0.0),
    heart_rate:   int   = Form(default=0),
    device:       str   = Form(default=DEVICE),
):
    """
    Submit an echo video for analysis.
    Returns immediately with a study_id; poll /status for completion.
    """
    # Validate file type
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".avi", ".dcm"):
        raise HTTPException(status_code=422,
                            detail="Only .avi and .dcm files are supported.")

    study_id = str(uuid.uuid4())
    upload_path = _UPLOAD_DIR / f"{study_id}{suffix}"

    # Save upload to disk
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    patient_info = {
        "name":       patient_name,
        "id":         patient_id,
        "dob":        patient_dob,
        "study_date": study_date or datetime.utcnow().strftime("%Y-%m-%d"),
        "sex":        sex.upper() if sex in ("M", "F", "m", "f") else "",
        "height_cm":  height_cm if height_cm > 0 else None,
        "weight_kg":  weight_kg if weight_kg > 0 else None,
        "heart_rate": heart_rate if heart_rate > 0 else None,
    }

    _jobs[study_id] = {
        "status":     "pending",
        "created_at": datetime.utcnow().isoformat(),
        "file":       str(upload_path),
    }

    # Submit to thread pool
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_analysis, study_id, upload_path, patient_info)

    return StudyStatus(
        study_id=study_id,
        status="pending",
        created_at=_jobs[study_id]["created_at"],
    )


@app.get("/api/v1/studies/{study_id}/status", response_model=StudyStatus)
async def get_status(study_id: str):
    job = _jobs.get(study_id)
    if not job:
        raise HTTPException(status_code=404, detail="Study not found.")
    return StudyStatus(
        study_id=study_id,
        status=job["status"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )


@app.get("/api/v1/studies/{study_id}", response_model=AnalysisResult)
async def get_results(study_id: str):
    job = _jobs.get(study_id)
    if not job:
        raise HTTPException(status_code=404, detail="Study not found.")
    if job["status"] == "processing" or job["status"] == "pending":
        raise HTTPException(status_code=202, detail="Analysis still in progress.")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Unknown error."))

    return AnalysisResult(
        study_id=study_id,
        status=job["status"],
        mode=job.get("mode", ""),
        view=job.get("view", {}),
        measurements=job.get("measurements", {}),
        diseases=job.get("diseases", {}),
        report_path=job.get("report_path"),
        frame_count=job.get("frame_count", 0),
    )


@app.get("/api/v1/studies/{study_id}/report")
async def get_report(study_id: str):
    job = _jobs.get(study_id)
    if not job:
        raise HTTPException(status_code=404, detail="Study not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Report not ready yet.")

    report_path = Path(job.get("report_path", ""))
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="PDF report file not found.")

    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        filename=report_path.name,
    )


@app.get("/api/v1/studies/{study_id}/frames/{frame_num}")
async def get_frame(study_id: str, frame_num: int):
    """Return a single overlay frame (original + segmentation) as JPEG."""
    job = _jobs.get(study_id)
    if not job:
        raise HTTPException(status_code=404, detail="Study not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail="Frames not ready yet.")

    frame_dir = Path(job.get("frame_dir", ""))
    frame_file = frame_dir / f"{frame_num:04d}.jpg"
    if not frame_file.exists():
        raise HTTPException(status_code=404, detail=f"Frame {frame_num} not found.")

    return FileResponse(path=str(frame_file), media_type="image/jpeg")


@app.get("/api/v1/studies/{study_id}/fhir",
         response_class=JSONResponse,
         summary="FHIR R4 transaction Bundle")
async def get_fhir(study_id: str):
    """
    Return the FHIR R4 transaction Bundle for this study.
    Can be POSTed directly to any FHIR R4 server (HAPI FHIR, Azure Health Data
    Services, AWS HealthLake, Google Cloud Healthcare API).
    Content-Type: application/fhir+json
    """
    job = _jobs.get(study_id)
    if not job:
        raise HTTPException(status_code=404, detail="Study not found.")
    if job["status"] in ("pending", "processing"):
        raise HTTPException(status_code=202, detail="Analysis still in progress.")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Unknown error."))

    fhir_json = job.get("fhir_json")
    if not fhir_json:
        raise HTTPException(status_code=404, detail="FHIR bundle not available.")

    import json
    return JSONResponse(
        content=json.loads(fhir_json),
        media_type="application/fhir+json",
    )
