"""
FHIR R4 Exporter — converts CordisAI measurements to FHIR resources.

Produces:
  - One Observation per cardiac measurement (LOINC-coded)
  - One DiagnosticReport referencing all Observations
  - One Condition per detected disease (SNOMED-CT-coded)

All resources can be POSTed directly to any FHIR R4 server (HAPI FHIR,
Azure Health Data Services, AWS HealthLake, Google Cloud Healthcare API).

Usage:
    from reporting.fhir.exporter import build_fhir_bundle
    bundle = build_fhir_bundle(measurements, diseases, patient_info)
    json_str = bundle.json(indent=2)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uuid
from datetime import datetime, timezone
from typing import Optional

from fhir.resources.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.diagnosticreport import DiagnosticReport
from fhir.resources.observation import Observation
from fhir.resources.condition import Condition
from fhir.resources.annotation import Annotation
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.quantity import Quantity
from fhir.resources.reference import Reference
from fhir.resources.patient import Patient
from fhir.resources.humanname import HumanName
from fhir.resources.identifier import Identifier


# ── LOINC codes for echo measurements ────────────────────────────────────────
# Source: LOINC / ACC/AHA Echo Reporting Standard

_LOINC = {
    # LV systolic function
    "LVEF":    ("10230-1",  "Left ventricular Ejection fraction"),
    "LVEDV":   ("18026-6",  "Left ventricular End-diastolic volume"),
    "LVESV":   ("18035-7",  "Left ventricular End-systolic volume"),
    "LVSV":    ("90096-4",  "Left ventricular Stroke volume"),
    "LVEDVi":  ("77907-2",  "Left ventricular End-diastolic volume index"),
    "LVESVi":  ("77908-0",  "Left ventricular End-systolic volume index"),
    "GLS":     ("96567-5",  "Global longitudinal strain"),
    "CO":      ("8741-1",   "Cardiac output"),
    # LV dimensions & wall thickness
    "IVSd":    ("18086-0",  "Interventricular septum thickness at end diastole"),
    "LVIDd":   ("18084-5",  "Left ventricular internal dimension at end diastole"),
    "LVIDs":   ("18085-2",  "Left ventricular internal dimension at end systole"),
    "LVPWd":   ("18088-6",  "Left ventricular posterior wall thickness at end diastole"),
    "RWT":     ("79989-9",  "Relative wall thickness"),
    "LVIDd_index": ("18084-5", "Left ventricular internal dimension index (diastole)"),
    "LVIDs_index": ("18085-2", "Left ventricular internal dimension index (systole)"),
    # LV mass
    "LVM":     ("10231-9",  "Left ventricular mass"),
    "LVMi":    ("79990-7",  "Left ventricular mass index"),
    # Left atrium
    "LA_area": ("17341-9",  "Left atrial area"),
    "LAV":     ("80028-5",  "Left atrial volume"),
    "LAVi":    ("80029-3",  "Left atrial volume index"),
    # Anthropometrics
    "BSA":     ("3140-1",   "Body surface area"),
}

# ── UCUM units ─────────────────────────────────────────────────────────────────
_UNITS = {
    "LVEF":    ("%",      "%"),
    "LVEDV":   ("mL",     "mL"),
    "LVESV":   ("mL",     "mL"),
    "LVSV":    ("mL",     "mL"),
    "LVEDVi":  ("mL/m2",  "mL/m2"),
    "LVESVi":  ("mL/m2",  "mL/m2"),
    "GLS":     ("%",      "%"),
    "CO":      ("L/min",  "L/min"),
    "IVSd":    ("cm",     "cm"),
    "LVIDd":   ("cm",     "cm"),
    "LVIDs":   ("cm",     "cm"),
    "LVPWd":   ("cm",     "cm"),
    "RWT":     ("1",      "ratio"),
    "LVIDd_index": ("cm/m2", "cm/m2"),
    "LVIDs_index": ("cm/m2", "cm/m2"),
    "LVM":     ("g",      "g"),
    "LVMi":    ("g/m2",   "g/m2"),
    "LA_area": ("cm2",    "cm2"),
    "LAV":     ("mL",     "mL"),
    "LAVi":    ("mL/m2",  "mL/m2"),
    "BSA":     ("m2",     "m2"),
}

# ── SNOMED-CT disease codes ────────────────────────────────────────────────────
_SNOMED = {
    "heart_failure_HFrEF":  ("84114007", "Heart failure with reduced ejection fraction"),
    "heart_failure_HFmrEF": ("85232009", "Heart failure with mildly reduced ejection fraction"),
    "lv_hypertrophy":       ("55827005", "Left ventricular hypertrophy"),
    "lv_dilatation":        ("21470009", "Left ventricular dilatation"),
    "la_enlargement":       ("48724000", "Left atrial enlargement"),
    "amyloidosis_suspicion": ("17289003", "Amyloid heart disease"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _loinc_concept(code: str, display: str) -> CodeableConcept:
    return CodeableConcept(
        coding=[Coding(system="http://loinc.org", code=code, display=display)],
        text=display,
    )


def _snomed_concept(code: str, display: str) -> CodeableConcept:
    return CodeableConcept(
        coding=[Coding(
            system="http://snomed.info/sct", code=code, display=display,
        )],
        text=display,
    )


def _reference(resource_type: str, res_id: str) -> Reference:
    return Reference(reference=f"{resource_type}/{res_id}")


# ── Builders ──────────────────────────────────────────────────────────────────

def build_patient(patient_info: dict) -> Patient:
    pi = patient_info or {}
    name_text = pi.get("name", "Anonymous")
    parts = name_text.split(" ", 1)
    human_name = HumanName(
        text=name_text,
        family=parts[-1] if parts else "Anonymous",
        given=[parts[0]] if len(parts) > 1 else [],
    )
    identifiers = []
    if pi.get("id") and pi["id"] not in ("N/A", ""):
        identifiers.append(Identifier(value=pi["id"]))

    return Patient(
        id=_new_id(),
        identifier=identifiers or None,
        name=[human_name],
        birthDate=pi.get("dob") if pi.get("dob") not in (None, "N/A", "") else None,
    )


def build_observation(key: str, meas_entry: dict,
                      patient_ref: Reference,
                      study_date: str) -> Optional[Observation]:
    """Build one FHIR Observation for a single measurement."""
    if key not in _LOINC:
        return None
    value = meas_entry.get("value")
    if value is None:
        return None

    loinc_code, loinc_display = _LOINC[key]
    ucum_unit, unit_display = _UNITS[key]
    flag = meas_entry.get("flag")

    interpretation = None
    if flag == "HIGH":
        interpretation = CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                code="H", display="High",
            )]
        )
    elif flag == "LOW":
        interpretation = CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                code="L", display="Low",
            )]
        )

    obs = Observation(
        id=_new_id(),
        status="final",
        category=[CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/observation-category",
                code="imaging", display="Imaging",
            )]
        )],
        code=_loinc_concept(loinc_code, loinc_display),
        subject=patient_ref,
        effectiveDateTime=study_date,
        valueQuantity=Quantity(
            value=round(float(value), 2),
            unit=unit_display,
            system="http://unitsofmeasure.org",
            code=ucum_unit,
        ),
        interpretation=[interpretation] if interpretation else None,
    )
    return obs


def build_conditions(diseases: dict,
                     patient_ref: Reference,
                     study_date: str) -> list[Condition]:
    """Build FHIR Condition resources for detected diseases."""
    conditions = []

    hf = diseases.get("heart_failure", {})
    if hf.get("flag"):
        hf_type = hf.get("type", "")
        key = "heart_failure_HFrEF" if "HFrEF" in hf_type else "heart_failure_HFmrEF"
        code, display = _SNOMED[key]
        conditions.append(Condition(
            id=_new_id(),
            clinicalStatus=CodeableConcept(
                coding=[Coding(
                    system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                    code="active",
                )]
            ),
            verificationStatus=CodeableConcept(
                coding=[Coding(
                    system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    code="unconfirmed",
                )]
            ),
            code=_snomed_concept(code, display),
            subject=patient_ref,
            onsetDateTime=study_date,
            note=[{"text": "AI-assisted detection — requires clinical confirmation."}],
        ))

    for disease_key, snomed_key in [
        ("lv_hypertrophy",  "lv_hypertrophy"),
        ("lv_dilatation",   "lv_dilatation"),
        ("la_enlargement",  "la_enlargement"),
        ("amyloidosis_suspicion", "amyloidosis_suspicion"),
    ]:
        entry = diseases.get(disease_key, {})
        if entry.get("flag"):
            code, display = _SNOMED[snomed_key]
            conditions.append(Condition(
                id=_new_id(),
                clinicalStatus=CodeableConcept(
                    coding=[Coding(
                        system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                        code="active",
                    )]
                ),
                verificationStatus=CodeableConcept(
                    coding=[Coding(
                        system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        code="unconfirmed",
                    )]
                ),
                code=_snomed_concept(code, display),
                subject=patient_ref,
                onsetDateTime=study_date,
                note=[Annotation(text="AI-assisted detection — requires clinical confirmation.")],
            ))

    return conditions


def build_diagnostic_report(obs_refs: list[Reference],
                             condition_refs: list[Reference],
                             patient_ref: Reference,
                             study_date: str,
                             ef_category: str = "") -> DiagnosticReport:
    """Build the top-level DiagnosticReport."""
    conclusion = f"AI-assisted echocardiography analysis."
    if ef_category:
        conclusion += f" EF classification: {ef_category}."
    conclusion += " All findings require clinical review and sign-off."

    return DiagnosticReport(
        id=_new_id(),
        status="preliminary",       # must be signed off to become 'final'
        category=[CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/v2-0074",
                code="CUS", display="Cardiac Ultrasound",
            )]
        )],
        code=_loinc_concept("34552-0", "Echocardiography study"),
        subject=patient_ref,
        effectiveDateTime=study_date,
        issued=_now_iso(),
        result=obs_refs if obs_refs else None,
        conclusion=conclusion,
        conclusionCode=[_snomed_concept("168731009",
                                        "Standard echocardiogram")] if not condition_refs
                       else None,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def build_fhir_bundle(measurements: dict,
                      diseases: dict,
                      patient_info: dict | None = None) -> Bundle:
    """
    Build a FHIR R4 transaction Bundle containing:
      - Patient
      - Observations (one per measurement)
      - Conditions (one per detected disease)
      - DiagnosticReport

    Args:
        measurements:  Output of models.measurement.engine.run_measurements()
        diseases:      Output of models.disease_detection.classifier.detect_diseases()
        patient_info:  Optional {'name', 'id', 'dob', 'study_date'}

    Returns:
        fhir.resources.bundle.Bundle — ready for .json() serialisation or
        POST to a FHIR server endpoint.
    """
    pi = patient_info or {}
    study_date = pi.get("study_date", datetime.now().strftime("%Y-%m-%d"))

    # ── Patient ───────────────────────────────────────────────────────────────
    patient = build_patient(pi)
    patient_ref = _reference("Patient", patient.id)

    # ── Observations ──────────────────────────────────────────────────────────
    obs_list = []
    for key in ("LVEF", "LVEDV", "LVESV", "LVSV", "LVEDVi", "LVESVi",
                 "GLS", "CO",
                 "IVSd", "LVIDd", "LVIDs", "LVPWd", "RWT",
                 "LVIDd_index", "LVIDs_index",
                 "LVM", "LVMi",
                 "LA_area", "LAV", "LAVi",
                 "BSA"):
        entry = measurements.get(key)
        if isinstance(entry, dict):
            obs = build_observation(key, entry, patient_ref, study_date)
            if obs:
                obs_list.append(obs)

    obs_refs = [_reference("Observation", o.id) for o in obs_list]

    # ── Conditions ────────────────────────────────────────────────────────────
    conditions = build_conditions(diseases, patient_ref, study_date)
    condition_refs = [_reference("Condition", c.id) for c in conditions]

    # ── DiagnosticReport ──────────────────────────────────────────────────────
    report = build_diagnostic_report(
        obs_refs, condition_refs, patient_ref, study_date,
        ef_category=measurements.get("EF_category", ""),
    )

    # ── Bundle ────────────────────────────────────────────────────────────────
    entries = []

    def _entry(resource, resource_type: str) -> BundleEntry:
        return BundleEntry(
            fullUrl=f"urn:uuid:{resource.id}",
            resource=resource,
            request=BundleEntryRequest(
                method="POST",
                url=resource_type,
            ),
        )

    entries.append(_entry(patient, "Patient"))
    for obs in obs_list:
        entries.append(_entry(obs, "Observation"))
    for cond in conditions:
        entries.append(_entry(cond, "Condition"))
    entries.append(_entry(report, "DiagnosticReport"))

    return Bundle(
        id=_new_id(),
        type="transaction",
        timestamp=_now_iso(),
        entry=entries,
    )
