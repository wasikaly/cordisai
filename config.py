"""
HeartAI — Global configuration
"""
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── Dataset paths ──────────────────────────────────────────────────────────────
ECHONET_DIR = BASE_DIR / "EchoNet-Dynamic"
ECHONET_VIDEOS = ECHONET_DIR / "Videos"
ECHONET_FILELIST = ECHONET_DIR / "FileList.csv"
ECHONET_TRACINGS = ECHONET_DIR / "VolumeTracings.csv"

CAMUS_DIR = BASE_DIR / "CAMUS_public" / "CAMUS_public"
CAMUS_NIFTI = CAMUS_DIR / "database_nifti"
CAMUS_SPLIT = CAMUS_DIR / "database_split"

# ── Model checkpoint paths ─────────────────────────────────────────────────────
CHECKPOINTS_DIR = BASE_DIR / "checkpoints"
CHECKPOINTS_DIR.mkdir(exist_ok=True)

SEG_CHECKPOINT = CHECKPOINTS_DIR / "segmentation.pt"
EF_CHECKPOINT = CHECKPOINTS_DIR / "ef_prediction.pt"

# ── Inference settings ─────────────────────────────────────────────────────────
DEVICE = "cuda"          # will fall back to cpu if unavailable
IMG_SIZE = 112           # EchoNet standard frame size
BATCH_SIZE = 8
NUM_WORKERS = 0          # 0 = main process (safe on Windows)

# ── Report output ──────────────────────────────────────────────────────────────
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── Normal ranges — sex-agnostic fallback (ASE 2015) ──────────────────────────
NORMAL_RANGES = {
    "LVEF": {"min": 53, "max": 73, "unit": "%", "critical_low": 40},
    "LVEDV": {"min": 56, "max": 104, "unit": "mL"},
    "LVESV": {"min": 19, "max": 49, "unit": "mL"},
    "GLS":  {"min": -30, "max": -16, "unit": "%"},  # HIGH=impaired(>-16%), LOW=artefact(<-30%)
}

# ── Gender-specific normal ranges (ASE 2015, Table 3) ─────────────────────────
NORMAL_RANGES_MALE = {
    "LVEF":   {"min": 52,  "max": 72,  "unit": "%",     "critical_low": 40},
    "LVEDV":  {"min": 62,  "max": 150, "unit": "mL"},
    "LVESV":  {"min": 21,  "max": 61,  "unit": "mL"},
    "LVIDd":  {"min": 4.2, "max": 5.9, "unit": "cm"},
    "LVIDs":  {"min": 2.5, "max": 4.0, "unit": "cm"},
    "IVSd":   {"min": 0.6, "max": 1.0, "unit": "cm"},
    "LVPWd":  {"min": 0.6, "max": 1.0, "unit": "cm"},
    "LVM":    {"min": 88,  "max": 224, "unit": "g"},
    "LVMi":   {"min": 49,  "max": 115, "unit": "g/m2"},
    "LVEDVi": {"min": 34,  "max": 74,  "unit": "mL/m2"},
    "LVESVi": {"min": 11,  "max": 31,  "unit": "mL/m2"},
    "LVSV":   {"min": 35,  "max": 95,  "unit": "mL"},
    "LVIDd_index": {"min": 2.2, "max": 3.1, "unit": "cm/m2"},
    "LVIDs_index": {"min": 1.2, "max": 2.1, "unit": "cm/m2"},
    "LAV":    {"min": 0,   "max": 58,  "unit": "mL"},
    "LAVi":   {"min": 0,   "max": 34,  "unit": "mL/m2"},
    "CO":     {"min": 4.0, "max": 8.0, "unit": "L/min"},
    "GLS":    {"min": -30, "max": -16, "unit": "%"},
}

NORMAL_RANGES_FEMALE = {
    "LVEF":   {"min": 54,  "max": 74,  "unit": "%",     "critical_low": 40},
    "LVEDV":  {"min": 46,  "max": 106, "unit": "mL"},
    "LVESV":  {"min": 14,  "max": 42,  "unit": "mL"},
    "LVIDd":  {"min": 3.9, "max": 5.3, "unit": "cm"},
    "LVIDs":  {"min": 2.2, "max": 3.5, "unit": "cm"},
    "IVSd":   {"min": 0.6, "max": 0.9, "unit": "cm"},
    "LVPWd":  {"min": 0.6, "max": 0.9, "unit": "cm"},
    "LVM":    {"min": 67,  "max": 162, "unit": "g"},
    "LVMi":   {"min": 43,  "max": 95,  "unit": "g/m2"},
    "LVEDVi": {"min": 29,  "max": 61,  "unit": "mL/m2"},
    "LVESVi": {"min": 8,   "max": 24,  "unit": "mL/m2"},
    "LVSV":   {"min": 30,  "max": 80,  "unit": "mL"},
    "LVIDd_index": {"min": 2.0, "max": 2.9, "unit": "cm/m2"},
    "LVIDs_index": {"min": 1.1, "max": 1.9, "unit": "cm/m2"},
    "LAV":    {"min": 0,   "max": 52,  "unit": "mL"},
    "LAVi":   {"min": 0,   "max": 34,  "unit": "mL/m2"},
    "CO":     {"min": 4.0, "max": 8.0, "unit": "L/min"},
    "GLS":    {"min": -30, "max": -16, "unit": "%"},
}
