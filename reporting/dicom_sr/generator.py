"""
DICOM Structured Report (SR) Generator — TID 5200 (Echocardiography Procedure Report).

Produces a DICOM SR file that can be imported into any DICOM-compatible PACS or
viewer (OsiriX, Horos, 3D Slicer, DCM4CHEE, Orthanc, etc.).

Structure (TID 5200 subset):
  - Patient / Study / Series demographics
  - Procedure: Transthoracic Echocardiography
  - LV Measurements (LVEF, LVEDV, LVESV, wall thickness, LA area)
  - Disease flags (Heart Failure, LVH, Dilatation, LA Enlargement, Amyloidosis)
  - AI disclaimer note

Usage:
    from reporting.dicom_sr.generator import generate_dicom_sr
    sr_path = generate_dicom_sr(measurements, diseases, patient_info, output_path)
"""
import sys
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid, ExplicitVRLittleEndian


# ── DICOM / SNOMED concept tables ─────────────────────────────────────────────

_LOINC_PROC = ("59776-5", "LN", "Echocardiography procedure")

_MEASUREMENTS = {
    # (concept_name_code, coding_scheme, display_name, unit_code, unit_scheme)
    # LV systolic function
    "LVEF":    ("10230-1", "LN", "Left ventricular Ejection fraction",    "%",    "UCUM"),
    "LVEDV":   ("18026-6", "LN", "LV End-diastolic volume",               "mL",   "UCUM"),
    "LVESV":   ("18035-7", "LN", "LV End-systolic volume",                "mL",   "UCUM"),
    "LVSV":    ("90096-4", "LN", "LV Stroke volume",                      "mL",   "UCUM"),
    "LVEDVi":  ("77907-2", "LN", "LV End-diastolic volume index",         "mL/m2","UCUM"),
    "LVESVi":  ("77908-0", "LN", "LV End-systolic volume index",          "mL/m2","UCUM"),
    "GLS":     ("96567-5", "LN", "Global longitudinal strain",            "%",    "UCUM"),
    "CO":      ("8741-1",  "LN", "Cardiac output",                        "L/min","UCUM"),
    # LV dimensions & wall thickness
    "IVSd":    ("18086-0", "LN", "IVS thickness at end diastole",         "cm",   "UCUM"),
    "LVIDd":   ("18084-5", "LN", "LV internal dimension at end diastole", "cm",   "UCUM"),
    "LVIDs":   ("18085-2", "LN", "LV internal dimension at end systole",  "cm",   "UCUM"),
    "LVPWd":   ("18088-6", "LN", "LV posterior wall thickness",           "cm",   "UCUM"),
    "RWT":     ("79989-9", "LN", "Relative wall thickness",               "1",    "UCUM"),
    "LVIDd_index": ("18084-5", "LN", "LV internal dimension index (diastole)", "cm/m2", "UCUM"),
    "LVIDs_index": ("18085-2", "LN", "LV internal dimension index (systole)",  "cm/m2", "UCUM"),
    # LV mass
    "LVM":     ("10231-9", "LN", "Left ventricular mass",                 "g",    "UCUM"),
    "LVMi":    ("79990-7", "LN", "Left ventricular mass index",           "g/m2", "UCUM"),
    # Left atrium
    "LA_area": ("17341-9", "LN", "Left atrial area (2D)",                 "cm2",  "UCUM"),
    "LAV":     ("80028-5", "LN", "Left atrial volume",                    "mL",   "UCUM"),
    "LAVi":    ("80029-3", "LN", "Left atrial volume index",              "mL/m2","UCUM"),
    # Anthropometrics
    "BSA":     ("3140-1",  "LN", "Body surface area",                     "m2",   "UCUM"),
}

_DISEASE_CODES = {
    "heart_failure":        ("84114007", "SCT", "Heart failure"),
    "lv_hypertrophy":       ("55827005", "SCT", "Left ventricular hypertrophy"),
    "lv_dilatation":        ("21470009", "SCT", "Left ventricular dilatation"),
    "la_enlargement":       ("48724000", "SCT", "Left atrial enlargement"),
    "amyloidosis_suspicion":("17289003", "SCT", "Amyloid heart disease"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_uid() -> str:
    return str(generate_uid())


def _dicom_date(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' to DICOM date 'YYYYMMDD'. Tolerates bad input."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y%m%d")
    except Exception:
        return datetime.utcnow().strftime("%Y%m%d")


def _dicom_time() -> str:
    return datetime.utcnow().strftime("%H%M%S.%f")[:13]


def _code_sq(code: str, scheme: str, meaning: str) -> Sequence:
    """Return a one-item CodeSequence dataset."""
    ds = Dataset()
    ds.CodeValue = code
    ds.CodingSchemeDesignator = scheme
    ds.CodeMeaning = meaning
    return Sequence([ds])


def _numeric_content(concept_code, concept_scheme, concept_meaning,
                     value: float, unit_code: str, unit_scheme: str,
                     unit_meaning: str) -> Dataset:
    item = Dataset()
    item.RelationshipType = "CONTAINS"
    item.ValueType = "NUM"
    item.ConceptNameCodeSequence = _code_sq(concept_code, concept_scheme, concept_meaning)

    meas_ds = Dataset()
    meas_ds.NumericValue = pydicom.valuerep.DSfloat(round(value, 4))
    meas_ds.MeasurementUnitsCodeSequence = _code_sq(unit_code, unit_scheme, unit_meaning)
    item.MeasuredValueSequence = Sequence([meas_ds])
    return item


def _text_content(concept_code: str, concept_scheme: str,
                  concept_meaning: str, text: str) -> Dataset:
    item = Dataset()
    item.RelationshipType = "CONTAINS"
    item.ValueType = "TEXT"
    item.ConceptNameCodeSequence = _code_sq(concept_code, concept_scheme, concept_meaning)
    item.TextValue = text
    return item


def _code_content(rel_type: str, concept_code: str, concept_scheme: str,
                  concept_meaning: str, val_code: str, val_scheme: str,
                  val_meaning: str) -> Dataset:
    item = Dataset()
    item.RelationshipType = rel_type
    item.ValueType = "CODE"
    item.ConceptNameCodeSequence = _code_sq(concept_code, concept_scheme, concept_meaning)
    item.ConceptCodeSequence = _code_sq(val_code, val_scheme, val_meaning)
    return item


# ── Main builder ──────────────────────────────────────────────────────────────

def generate_dicom_sr(
    measurements: dict,
    diseases: dict,
    patient_info: dict | None = None,
    output_path: str | Path | None = None,
) -> Path:
    """
    Generate a DICOM Structured Report for a CordisAI echo analysis.

    Args:
        measurements:  Output of models.measurement.engine.run_measurements()
        diseases:      Output of models.disease_detection.classifier.detect_diseases()
        patient_info:  Optional {'name', 'id', 'dob', 'study_date'}
        output_path:   Destination .dcm path (auto-named if None)

    Returns:
        Path to the generated DICOM SR file.
    """
    pi = patient_info or {}
    study_date_str = pi.get("study_date") or datetime.utcnow().strftime("%Y-%m-%d")
    study_date = _dicom_date(study_date_str)
    now_time = _dicom_time()

    # ── File meta ─────────────────────────────────────────────────────────────
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID    = "1.2.840.10008.5.1.4.1.1.88.33"  # Enhanced SR
    file_meta.MediaStorageSOPInstanceUID = _new_uid()
    file_meta.TransferSyntaxUID          = ExplicitVRLittleEndian

    # ── Main dataset ──────────────────────────────────────────────────────────
    ds = FileDataset(None, {}, file_meta=file_meta, preamble=b"\0" * 128)

    # Patient module
    name_text = pi.get("name", "Anonymous")
    parts = name_text.split(" ", 1)
    if len(parts) == 2:
        dicom_name = f"{parts[1]}^{parts[0]}"
    else:
        dicom_name = name_text
    ds.PatientName = dicom_name
    ds.PatientID   = pi.get("id", "N/A")
    dob = pi.get("dob", "")
    ds.PatientBirthDate = _dicom_date(dob) if dob and dob not in ("N/A", "") else ""
    ds.PatientSex  = ""

    # General study module
    ds.StudyInstanceUID = _new_uid()
    ds.StudyDate        = study_date
    ds.StudyTime        = now_time
    ds.AccessionNumber  = ""
    ds.ReferringPhysicianName = ""
    ds.StudyID          = "1"

    # SR Document Series module
    ds.Modality            = "SR"
    ds.SeriesInstanceUID   = _new_uid()
    ds.SeriesNumber        = "1"
    ds.SeriesDate          = study_date
    ds.SeriesTime          = now_time

    # SR Document module
    ds.SOPClassUID         = "1.2.840.10008.5.1.4.1.1.88.33"  # Enhanced SR
    ds.SOPInstanceUID      = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber      = "1"
    ds.ContentDate         = study_date
    ds.ContentTime         = now_time
    ds.VerificationFlag    = "UNVERIFIED"
    ds.CompletionFlag      = "COMPLETE"

    # Document title
    ds.ConceptNameCodeSequence = _code_sq(*_LOINC_PROC)

    # ── Content sequence ──────────────────────────────────────────────────────
    content_items = []

    # Procedure description
    content_items.append(
        _text_content(
            "121065", "DCM", "Procedure Description",
            "AI-assisted transthoracic echocardiography analysis (CordisAI). "
            "All findings require clinical review and sign-off by a cardiologist.",
        )
    )

    # EF category if present
    ef_cat = measurements.get("EF_category")
    if ef_cat and isinstance(ef_cat, str):
        content_items.append(
            _text_content("10230-1", "LN", "EF Classification", ef_cat)
        )

    # ── Measurements ──────────────────────────────────────────────────────────
    for key, (code, scheme, display, unit_code, unit_scheme) in _MEASUREMENTS.items():
        entry = measurements.get(key)
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        if value is None:
            continue
        try:
            float_val = float(value)
        except (TypeError, ValueError):
            continue

        # Unit display strings (human-readable meaning for UCUM codes)
        unit_meaning = {
            "%": "Percent", "mL": "Milliliter", "cm": "Centimeter",
            "cm2": "Square centimeter", "1": "No units",
            "mL/m2": "mL per square meter", "g": "Gram",
            "g/m2": "Gram per square meter", "cm/m2": "cm per square meter",
            "L/min": "Liter per minute", "m2": "Square meter",
        }.get(unit_code, unit_code)

        num_item = _numeric_content(
            code, scheme, display,
            float_val, unit_code, unit_scheme, unit_meaning,
        )

        # Add abnormal flag as child TEXT item if present
        flag = entry.get("flag")
        if flag in ("HIGH", "LOW"):
            flag_item = Dataset()
            flag_item.RelationshipType = "HAS CONCEPT MOD"
            flag_item.ValueType = "CODE"
            flag_item.ConceptNameCodeSequence = _code_sq(
                "121401", "DCM", "Derivation"
            )
            flag_item.ConceptCodeSequence = _code_sq(
                "H" if flag == "HIGH" else "L",
                "HL7V3",
                "High" if flag == "HIGH" else "Low",
            )
            num_item.ContentSequence = Sequence([flag_item])

        content_items.append(num_item)

    # ── Disease findings ──────────────────────────────────────────────────────
    for disease_key, (code, scheme, display) in _DISEASE_CODES.items():
        entry = diseases.get(disease_key, {})
        if not isinstance(entry, dict) or not entry.get("flag"):
            continue
        content_items.append(
            _code_content(
                "CONTAINS",
                "121071", "DCM", "Finding",
                code, scheme, display,
            )
        )
        # Include sub-type if present
        sub_type = entry.get("type", "")
        if sub_type:
            content_items.append(
                _text_content("121071", "DCM", f"Finding detail ({display})", sub_type)
            )

    # AI disclaimer
    content_items.append(
        _text_content(
            "121106", "DCM", "Conclusions",
            "AUTOMATED ANALYSIS — NOT FOR CLINICAL USE WITHOUT PHYSICIAN REVIEW. "
            "Generated by CordisAI v0.1. Findings are preliminary.",
        )
    )

    ds.ContentSequence = Sequence(content_items)

    # ── Output path ───────────────────────────────────────────────────────────
    if output_path is None:
        from config import REPORTS_DIR
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        patient_id = pi.get("id", "unknown")
        output_path = REPORTS_DIR / f"SR_{patient_id}_{ts}.dcm"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pydicom.dcmwrite(str(output_path), ds)
    return output_path
