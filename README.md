# CordisAI

> AI-powered echocardiography analysis platform — echo video to МЗ РК-compliant clinical report in 60 seconds.

[![Tests](https://img.shields.io/badge/tests-199%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11-blue)]()
[![PyTorch](https://img.shields.io/badge/pytorch-2.5.1%2Bcu124-orange)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

CordisAI ingests echocardiography video (AVI / DICOM / NIfTI), segments cardiac chambers with a U-Net (val LV Dice **0.9153**), computes 21 clinical measurements (LVEF, LVEDV, LVMi, GLS, ...), detects 7+ pathological conditions (HFrEF, LV hypertrophy, amyloidosis suspicion, ...) and generates a **standardized МЗ РК-compliant report** in PDF, FHIR R4 and DICOM SR formats — ready for physician sign-off and import into hospital MIS.

## Pipeline

```
input (AVI / DICOM / NIfTI)
  → data/loaders/             video / dicom / nifti
  → models/segmentation/      U-Net 2D — masks (bg, LV, Myo, LA)
  → models/measurement/       21 parameters (ASE 2015 / ESC 2021)
  → models/disease_detection/ 7+ conditions + AI-assisted recommendations
  → reporting/pdf/            МЗ РК PDF protocol with signature block
  → reporting/fhir/           FHIR R4 bundle (LOINC + SNOMED-CT)
  → reporting/dicom_sr/       DICOM SR TID 5200
```

## Quick start

```bash
# Backend API
python -m uvicorn integration.api.main:app --host 0.0.0.0 --port 8002

# Frontend (React 18 + Vite + Tailwind)
cd frontend && npm install && npm run dev   # → http://localhost:3000

# Tests
python -m pytest                             # 199 tests
```

**Requirements:** Python 3.11, PyTorch 2.5.1+cu124, CUDA 12.4 (RTX 4050 6 GB tested), Node 18+

## Project layout

```
cordisai/
├── data/loaders/              # AVI / DICOM / NIfTI loaders
├── models/
│   ├── segmentation/          # U-Net 2D
│   ├── measurement/           # 21-parameter engine
│   ├── disease_detection/     # 7+ condition classifier + recs
│   └── view_classifier/       # A4C view detection (93.3% acc)
├── reporting/
│   ├── pdf/                   # МЗ РК-compliant PDF (Cyrillic)
│   ├── fhir/                  # FHIR R4 bundle exporter
│   └── dicom_sr/              # DICOM SR TID 5200
├── integration/
│   ├── api/                   # FastAPI (port 8002)
│   ├── pacs/                  # DICOMweb client
│   └── orthanc/               # Orthanc REST client
├── infrastructure/
│   ├── aws/                   # AWS HealthLake FHIR
│   └── k8s/                   # Kubernetes manifests
├── frontend/                  # React 18 + Vite + Tailwind (dark theme)
├── website/                   # Static landing site
├── tests/                     # 199 tests
└── training/                  # Training scripts (EF regressor, etc.)
```

## Datasets (downloaded separately)

| Dataset | Used for | Source |
|---|---|---|
| EchoNet-Dynamic | EF regressor + view classifier | https://echonet.github.io/dynamic/ |
| CAMUS | U-Net segmentation + view classifier | https://www.creatis.insa-lyon.fr/Challenge/camus/ |

Place datasets at `EchoNet-Dynamic/` and `CAMUS_public/CAMUS_public/database_nifti/` (excluded from git).

## Model checkpoints

Released separately (not in git due to size). Drop into `checkpoints/`:

| File | Model | Status |
|---|---|---|
| `segmentation.pt` | U-Net 2D | DONE — val LV Dice 0.9153 |
| `view_classifier.pt` | View classifier | DONE — 93.3% val acc |
| `ef_prediction.pt` | EF regressor (EfficientNet-B0) | PAUSED — MAE 5.60% (epoch 11/30) |

## Key features

- **21 measurements** — LVEF, LVEDV, LVESV, LVSV, LVEDVi, LVESVi, GLS, CO, IVSd, LVPWd, LVIDd, LVIDs, RWT, LVM, LVMi, LAV, LAVi, BSA + categorizations
- **7+ disease detections** — HFrEF/HFmrEF, LV hypertrophy, LV dilatation, LA enlargement, amyloidosis suspicion, diastolic dysfunction risk, valvular disease risk
- **МЗ РК-compliant PDF** — Cyrillic, patient identification block, gender-specific reference ranges (ASE 2015), physician signature block, references to MoH KZ orders
- **FHIR R4 export** — 21 LOINC-coded observations + SNOMED-CT conditions + DiagnosticReport
- **DICOM SR** — TID 5200 with LOINC + UCUM coding
- **Gender-specific normal ranges** — separate male/female thresholds for all 21 parameters
- **Clinical recommendations** — auto-generated GDMT suggestions, imaging referrals, screening flags

## Documentation

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — 1-page project summary
- [DOCUMENTATION.md](DOCUMENTATION.md) — full technical documentation
- [CLAUDE.md](CLAUDE.md) — developer guide
- [PITCH_DECK.md](PITCH_DECK.md) — investor pitch
- [BUSINESS_MODEL.md](BUSINESS_MODEL.md) — financial model + go-to-market

## Roadmap

**Phase 1 (DONE)** — MVP, 21 parameters, PDF/FHIR/DICOM SR, dark-theme frontend
**Phase 2 (Q3–Q4 2026)** — Doppler (E/A, E/e'), RV segmentation, real-time USG stream, ISO 27001 + МЗ РК class IIa certification
**Phase 3 (2027+)** — Pediatric echo, edge mode, multilingual reports (KZ/RU/EN), CIS → EU → FDA expansion

## Disclaimer

CordisAI is an AI assistant — it does **not** replace clinical judgment. All AI-generated measurements and findings require verification and sign-off by a licensed cardiologist before clinical use. Not currently registered as a medical device under МЗ РК / FDA / CE — for research and pilot use only.

## License

Proprietary. All rights reserved. Contact igrobzor974@gmail.com for licensing inquiries.

---

**Status:** MVP ready, seeking pre-seed and clinical pilot partners.
**Contact:** igrobzor974@gmail.com
