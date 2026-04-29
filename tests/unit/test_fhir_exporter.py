"""
Unit tests for reporting/fhir/exporter.py
Run with: python -m pytest tests/unit/test_fhir_exporter.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import pytest

from reporting.fhir.exporter import (
    build_fhir_bundle,
    build_patient,
    build_observation,
    build_conditions,
    build_diagnostic_report,
    _reference,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

def _normal_measurements():
    return {
        "LVEF":    {"value": 60.0, "unit": "%",   "flag": None},
        "LVEDV":   {"value": 90.0, "unit": "mL",  "flag": None},
        "LVESV":   {"value": 36.0, "unit": "mL",  "flag": None},
        "IVSd":    {"value": 0.9,  "unit": "cm",  "flag": None},
        "LVIDd":   {"value": 4.8,  "unit": "cm",  "flag": None},
        "LVPWd":   {"value": 0.9,  "unit": "cm",  "flag": None},
        "RWT":     {"value": 0.37, "unit": "",    "flag": None},
        "LA_area": {"value": 16.0, "unit": "cm2", "flag": None},
        "EF_category": "Normal (HFpEF range)",
    }


def _no_disease():
    return {
        "heart_failure": {"flag": False, "type": ""},
        "lv_hypertrophy": {"flag": False, "type": ""},
        "lv_dilatation": {"flag": False},
        "la_enlargement": {"flag": False},
        "amyloidosis_suspicion": {"flag": False},
        "notes": [],
    }


def _all_disease():
    return {
        "heart_failure": {"flag": True, "type": "HFrEF (EF < 40%)"},
        "lv_hypertrophy": {"flag": True, "type": "Concentric LVH"},
        "lv_dilatation": {"flag": True},
        "la_enlargement": {"flag": True},
        "amyloidosis_suspicion": {"flag": True},
        "notes": ["note"],
    }


def _patient_info():
    return {"name": "Jane Doe", "id": "P999",
            "dob": "1980-06-15", "study_date": "2026-03-28"}


# ── build_patient ─────────────────────────────────────────────────────────────

class TestBuildPatient:
    def test_resource_type(self):
        p = build_patient(_patient_info())
        assert type(p).__name__ == "Patient"

    def test_name_present(self):
        p = build_patient(_patient_info())
        assert p.name[0].text == "Jane Doe"

    def test_identifier_set(self):
        p = build_patient(_patient_info())
        assert p.identifier[0].value == "P999"

    def test_anonymous_no_identifier(self):
        p = build_patient({"name": "Anonymous", "id": "N/A"})
        assert p.identifier is None

    def test_empty_info(self):
        p = build_patient({})
        assert p.name[0].family == "Anonymous"


# ── build_observation ─────────────────────────────────────────────────────────

class TestBuildObservation:
    def setup_method(self):
        self.pat_ref = _reference("Patient", "test-id")

    def test_lvef_observation(self):
        obs = build_observation(
            "LVEF", {"value": 60.0, "flag": None},
            self.pat_ref, "2026-03-28",
        )
        assert obs is not None
        assert type(obs).__name__ == "Observation"
        assert obs.status == "final"
        assert obs.valueQuantity.value == 60.0
        assert obs.valueQuantity.unit == "%"

    def test_loinc_code_present(self):
        obs = build_observation(
            "LVEF", {"value": 60.0, "flag": None},
            self.pat_ref, "2026-03-28",
        )
        assert obs.code.coding[0].system == "http://loinc.org"
        assert obs.code.coding[0].code == "10230-1"

    def test_high_flag_interpretation(self):
        obs = build_observation(
            "LVEDV", {"value": 120.0, "flag": "HIGH"},
            self.pat_ref, "2026-03-28",
        )
        assert obs.interpretation[0].coding[0].code == "H"

    def test_low_flag_interpretation(self):
        obs = build_observation(
            "LVEF", {"value": 35.0, "flag": "LOW"},
            self.pat_ref, "2026-03-28",
        )
        assert obs.interpretation[0].coding[0].code == "L"

    def test_normal_no_interpretation(self):
        obs = build_observation(
            "LVEF", {"value": 60.0, "flag": None},
            self.pat_ref, "2026-03-28",
        )
        assert obs.interpretation is None

    def test_unknown_key_returns_none(self):
        obs = build_observation(
            "UNKNOWN_KEY", {"value": 1.0, "flag": None},
            self.pat_ref, "2026-03-28",
        )
        assert obs is None

    def test_missing_value_returns_none(self):
        obs = build_observation(
            "LVEF", {"flag": None},
            self.pat_ref, "2026-03-28",
        )
        assert obs is None


# ── build_conditions ──────────────────────────────────────────────────────────

class TestBuildConditions:
    def setup_method(self):
        self.pat_ref = _reference("Patient", "test-id")

    def test_no_disease_empty_list(self):
        conds = build_conditions(_no_disease(), self.pat_ref, "2026-03-28")
        assert conds == []

    def test_all_diseases_five_conditions(self):
        conds = build_conditions(_all_disease(), self.pat_ref, "2026-03-28")
        assert len(conds) == 5

    def test_hfref_snomed_code(self):
        dis = _no_disease()
        dis["heart_failure"] = {"flag": True, "type": "HFrEF (EF < 40%)"}
        conds = build_conditions(dis, self.pat_ref, "2026-03-28")
        assert len(conds) == 1
        assert conds[0].code.coding[0].code == "84114007"

    def test_hfmref_snomed_code(self):
        dis = _no_disease()
        dis["heart_failure"] = {"flag": True, "type": "HFmrEF (EF 40-49%)"}
        conds = build_conditions(dis, self.pat_ref, "2026-03-28")
        assert conds[0].code.coding[0].code == "85232009"

    def test_conditions_unconfirmed_status(self):
        dis = _no_disease()
        dis["lv_hypertrophy"] = {"flag": True, "type": "Concentric LVH"}
        conds = build_conditions(dis, self.pat_ref, "2026-03-28")
        assert conds[0].verificationStatus.coding[0].code == "unconfirmed"

    def test_conditions_have_ai_note(self):
        dis = _no_disease()
        dis["la_enlargement"] = {"flag": True}
        conds = build_conditions(dis, self.pat_ref, "2026-03-28")
        assert "AI-assisted" in conds[0].note[0].text


# ── build_fhir_bundle ─────────────────────────────────────────────────────────

class TestBuildFhirBundle:
    def test_bundle_type(self):
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), _patient_info())
        assert type(b).__name__ == "Bundle"
        assert b.type == "transaction"

    def test_entry_count_normal_no_disease(self):
        # 1 Patient + 8 Observations + 0 Conditions + 1 DiagnosticReport = 10
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), _patient_info())
        assert len(b.entry) == 10

    def test_entry_count_all_diseases(self):
        # 1 Patient + 8 Obs + 5 Conditions + 1 DiagnosticReport = 15
        b = build_fhir_bundle(_normal_measurements(), _all_disease(), _patient_info())
        assert len(b.entry) == 15

    def test_all_entries_have_post_request(self):
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), _patient_info())
        for entry in b.entry:
            assert entry.request.method == "POST"

    def test_bundle_serialises_to_json(self):
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), _patient_info())
        data = json.loads(b.model_dump_json())
        assert data["resourceType"] == "Bundle"

    def test_diagnostic_report_is_preliminary(self):
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), _patient_info())
        reports = [e for e in b.entry
                   if type(e.resource).__name__ == "DiagnosticReport"]
        assert len(reports) == 1
        assert reports[0].resource.status == "preliminary"

    def test_observations_reference_patient(self):
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), _patient_info())
        obs_entries = [e for e in b.entry
                       if type(e.resource).__name__ == "Observation"]
        for e in obs_entries:
            assert e.resource.subject.reference.startswith("Patient/")

    def test_no_patient_info_still_works(self):
        b = build_fhir_bundle(_normal_measurements(), _no_disease(), None)
        assert b is not None
        assert len(b.entry) >= 2
