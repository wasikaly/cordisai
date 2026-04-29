"""
Unit tests for reporting/dicom_sr/generator.py
Run with: python -m pytest tests/unit/test_dicom_sr.py -v
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import pydicom

from reporting.dicom_sr.generator import generate_dicom_sr


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _measurements():
    return {
        "LVEF":    {"value": 60.0, "unit": "%",   "flag": None},
        "LVEDV":   {"value": 90.0, "unit": "mL",  "flag": None},
        "LVESV":   {"value": 36.0, "unit": "mL",  "flag": None},
        "IVSd":    {"value": 0.9,  "unit": "cm",  "flag": None},
        "LVIDd":   {"value": 4.8,  "unit": "cm",  "flag": None},
        "LVPWd":   {"value": 0.9,  "unit": "cm",  "flag": None},
        "RWT":     {"value": 0.37, "unit": "",     "flag": None},
        "LA_area": {"value": 16.0, "unit": "cm2", "flag": None},
        "EF_category": "Normal (HFpEF range)",
    }


def _no_disease():
    return {
        "heart_failure":        {"flag": False},
        "lv_hypertrophy":       {"flag": False},
        "lv_dilatation":        {"flag": False},
        "la_enlargement":       {"flag": False},
        "amyloidosis_suspicion":{"flag": False},
    }


def _all_disease():
    return {
        "heart_failure":        {"flag": True, "type": "HFrEF (EF < 40%)"},
        "lv_hypertrophy":       {"flag": True, "type": "Concentric LVH"},
        "lv_dilatation":        {"flag": True},
        "la_enlargement":       {"flag": True},
        "amyloidosis_suspicion":{"flag": True},
    }


def _patient_info():
    return {"name": "Jane Doe", "id": "P999",
            "dob": "1980-06-15", "study_date": "2026-03-28"}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGenerateDicomSR:
    def test_returns_path(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        assert isinstance(out, Path)

    def test_file_exists(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        assert out.exists()

    def test_valid_dicom(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert ds is not None

    def test_modality_is_sr(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert ds.Modality == "SR"

    def test_patient_name(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert "Doe" in str(ds.PatientName)

    def test_patient_id(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert ds.PatientID == "P999"

    def test_study_date(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert ds.StudyDate == "20260328"

    def test_sop_class_uid_is_enhanced_sr(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert ds.SOPClassUID == "1.2.840.10008.5.1.4.1.1.88.33"

    def test_content_sequence_present(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert hasattr(ds, "ContentSequence")
        assert len(ds.ContentSequence) > 0

    def test_numeric_items_present(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        num_items = [item for item in ds.ContentSequence
                     if item.ValueType == "NUM"]
        assert len(num_items) == 8  # 8 numeric measurements

    def test_ef_value_correct(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        ef_items = [item for item in ds.ContentSequence
                    if item.ValueType == "NUM" and
                    item.ConceptNameCodeSequence[0].CodeValue == "10230-1"]
        assert len(ef_items) == 1
        assert float(ef_items[0].MeasuredValueSequence[0].NumericValue) == 60.0

    def test_no_disease_no_finding_codes(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        finding_items = [item for item in ds.ContentSequence
                         if item.ValueType == "CODE"]
        assert len(finding_items) == 0

    def test_all_diseases_produce_findings(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _all_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        finding_items = [item for item in ds.ContentSequence
                         if item.ValueType == "CODE"]
        assert len(finding_items) == 5

    def test_verification_flag_unverified(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        assert ds.VerificationFlag == "UNVERIFIED"

    def test_no_patient_info_still_works(self, tmp_path):
        out = generate_dicom_sr(_measurements(), _no_disease(), None,
                                output_path=tmp_path / "test.dcm")
        assert out.exists()
        ds = pydicom.dcmread(str(out))
        assert ds.Modality == "SR"

    def test_missing_measurement_skipped(self, tmp_path):
        meas = _measurements()
        del meas["LVEDV"]
        del meas["LVESV"]
        out = generate_dicom_sr(meas, _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        num_items = [item for item in ds.ContentSequence
                     if item.ValueType == "NUM"]
        assert len(num_items) == 6  # 8 - 2 skipped

    def test_high_flag_adds_concept_mod(self, tmp_path):
        meas = _measurements()
        meas["LVEDV"]["flag"] = "HIGH"
        out = generate_dicom_sr(meas, _no_disease(), _patient_info(),
                                output_path=tmp_path / "test.dcm")
        ds = pydicom.dcmread(str(out))
        lvedv_items = [item for item in ds.ContentSequence
                       if item.ValueType == "NUM" and
                       item.ConceptNameCodeSequence[0].CodeValue == "18026-6"]
        assert len(lvedv_items) == 1
        assert hasattr(lvedv_items[0], "ContentSequence")
        assert len(lvedv_items[0].ContentSequence) == 1
