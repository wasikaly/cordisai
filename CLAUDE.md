# CordisAI — Developer Guide

## Project Overview

AI-powered echocardiography analysis platform (us2.ai-style MVP).
Echo video (.avi/.dcm/.nii) → U-Net segmentation → 25+ measurements → 7+ disease detections → clinical recommendations → PDF/FHIR/DICOM SR report.
**Rebranded HeartAI → CordisAI** (2026-03-29). Dark theme frontend. Landing website in `website/`.

## Architecture

```
input (AVI / DICOM / CAMUS NIfTI)
  → data/loaders/              video_loader / dicom_loader / nifti_loader
  → models/segmentation/       U-Net 2D → masks (0=bg, 1=LV, 2=Myo, 3=LA)
  → models/measurement/        25+ params: LVEF, volumes, wall thickness, LV mass, LAV, GLS, indexed
  → models/disease_detection/  rule-based flags + clinical recommendations (7+ conditions)
  → reporting/pdf/             fpdf2 PDF report with recommendations
  → reporting/fhir/            FHIR R4 bundle (21 observations + conditions + DiagnosticReport)
  → reporting/dicom_sr/        DICOM SR TID 5200 (21 measurements, pydicom 3.x)
  → pipeline.py                orchestrates all steps
  → app.py                     Streamlit UI → localhost:8501
  → integration/api/main.py    FastAPI REST → localhost:8002
  → frontend/                  React 18 + Vite + Tailwind → localhost:3000
  → website/                   Static landing site (index.html + mvp.MOV)
```

## Environment

- Python 3.11, PyTorch 2.5.1+cu124, CUDA 12.4, RTX 4050 (6 GB VRAM)
- Windows 11, shell = bash (Unix-style paths)

## Key Commands

```bash
python -m uvicorn integration.api.main:app --host 0.0.0.0 --port 8002   # API
cd frontend && npm run dev                                                # Frontend → :3000
python -m pytest                                                          # 199 tests
python training/train_ef_regressor.py --resume --epochs 30 --batch 8 --max_frames 32  # EF resume
```

## Datasets

| Dataset | Location | Used for |
|---------|----------|----------|
| EchoNet-Dynamic | `EchoNet-Dynamic/` | EF regressor + view classifier (A4C) |
| CAMUS | `CAMUS_public/CAMUS_public/database_nifti/` | U-Net segmentation + view classifier |

## Model Checkpoints

| File | Model | Status |
|------|-------|--------|
| `checkpoints/segmentation.pt` | U-Net 2D | DONE — val LV Dice 0.9153 |
| `checkpoints/ef_prediction.pt` | EF Regressor (EfficientNet-B0) | PAUSED — MAE 5.60%, epoch 11/30 |
| `checkpoints/view_classifier.pt` | View Classifier | DONE — 93.3% val acc |

## Measurements (25+ parameters, 21 implemented)

**LV Systolic**: LVEF, LVEDV, LVESV, LVSV, LVEDVi, LVESVi, GLS, CO
**LV Dimensions**: IVSd, LVPWd, LVIDd, LVIDs, LVIDd_index, LVIDs_index, RWT
**LV Mass**: LVM, LVMi
**Left Atrium**: LA_area, LAV, LAVi
**Other**: BSA, EF_category, LV_geometry, GLS_category
**Planned (Doppler/Phase 2)**: E/A, E/e', DT, Peak TRV, TAPSE, PASP, RV area, FAC

## Disease Detection (7+ conditions)

Heart Failure (HFrEF/HFmrEF), LV Hypertrophy, LV Dilatation, LA Enlargement,
Amyloidosis Suspicion, Diastolic Dysfunction Risk, Valvular Disease Risk.
Each generates AI clinical recommendations (GDMT, imaging referrals, screening).

## Gender-Specific Normal Ranges (ASE 2015)

`config.py`: `NORMAL_RANGES`, `NORMAL_RANGES_MALE`, `NORMAL_RANGES_FEMALE` — 21 params each.

## Reporting

- **PDF** (`reporting/pdf/generator.py`): CordisAI branded, fpdf2, recommendations section
- **FHIR R4** (`reporting/fhir/exporter.py`): 21 LOINC Observations + SNOMED-CT Conditions
- **DICOM SR** (`reporting/dicom_sr/generator.py`): TID 5200, LOINC+UCUM coded

## Frontend (React 18 + Vite + Tailwind)

- **Dark theme**: surface levels #0a0a0e→#22222e, red/white brand, backdrop-blur header
- Port: **3000** (not 3001)
- Pages: Dashboard, Upload, StudiesPage, StudyStatus, ResultsPage
- DiseaseFlags: 7+ condition cards + clinical notes (slate theme) + AI recommendations (blue)
- EchoViewer: Canvas-based, frame preloading, autoplay at 50% loaded
- `tsconfig.json`: no project references, `include: ["src"]`

## Landing Website (`website/`)

Static site — open `website/index.html` directly in browser (no server needed).
- `index.html` — full landing page (Hero + ECG animation + Features + Stats + How It Works + Measurements + Use Cases + Comparison table + Tech Stack + Demo form + Footer)
- `mvp.MOV` — embedded MVP demo video
- Dark theme, Space Grotesk + Inter fonts, scroll animations, animated counters
- Logo as text: **CORDIS** (white) **AI** (red)

## Infrastructure

- `integration/pacs/` — DICOMweb client
- `integration/orthanc/` — Orthanc REST client
- `infrastructure/aws/` — AWS HealthLake FHIR R4
- `infrastructure/k8s/` — K8s manifests
- `Dockerfile` — CPU-only, non-root, uvicorn

## Code Conventions

- `print()` ASCII only (Windows cp1251)
- `flag_abnormal()` reads from `NORMAL_RANGES` — no inline thresholds
- `sys.path.insert(0, ...)` in submodules — intentional
- `weights_only=True` on `torch.load()`
- `fpdf2` Helvetica/latin-1 — `_safe()` wrapper
- `NUM_WORKERS=0` on Windows
- `sample_mode="evenly"` for EF training
- `_val()` helper in disease detection for safe dict access
- `_to_python()` in API for numpy types
- Frontend localStorage: `cordisai_recent_studies`
- Frontend API: `http://localhost:8002`

## Roadmap (updated 2026-04-21)

### Phase 1 — DONE (2026-04-02)
- BSA + indexed measurements, LV Mass, LAV, gender norms, FHIR/DICOM SR, clinical recommendations

### Phase 2 — Next (Q3-Q4 2026)
- Doppler: E/A, E/e', DT, Peak TRV, PASP
- RV segmentation (label=4), TAPSE, FAC, RA area
- Real-time USG device connection (DICOM stream / video capture)
- AI scanning assistant (probe positioning, auto-capture ED/ES)
- EF Regressor resume to epoch 30

### Phase 3 — Scale (2027+)
- Pediatric echo norms, offline/edge mode, multilingual reports (RU/KZ/EN), telemedicine

## Business Documents

- `PITCH_DECK.md` — investor pitch (18 slides + business model with LTV/CAC=25x in MoonAI-style format)
- `BUSINESS_MODEL.md` — full financial model: TAM/SAM/SOM, B2B+B2G strategy, revenue forecast 2026–2030 ($80K → $5.5M), unit economics, B2G tier breakdown ($40K–$500K/year)
- Pre-seed ask: **$50–80K** (realistic for MVP stage — pilots in 1–2 clinics, edge servers, regulatory)
- Strategy: **B2B (private clinics) → B2G (gov hospitals)**, no B2C
- Pricing: **CordisAI Clinic $499/мес** + **Enterprise $1 499/мес** + B2G tiered contracts
- Real-time USG = competitive differentiator (DICOM stream / capture card → edge GPU server in clinic)

## Test Suite — 199 tests, all passing

```bash
python -m pytest
```
