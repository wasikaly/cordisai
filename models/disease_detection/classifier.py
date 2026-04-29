"""
Rule-based + threshold disease detection for MVP.
Consumes the measurements dict from the Measurement Engine and applies
guideline-based criteria to flag potential conditions.

For the MVP this is deterministic (no separate ML model needed).
Post-MVP: replace with trained EfficientNet + temporal attention heads.
"""


def detect_diseases(measurements: dict) -> dict:
    """
    Apply guideline-based rules to flag potential cardiac conditions.

    Args:
        measurements: Output dict from models.measurement.engine.run_measurements()

    Returns:
        {
          'heart_failure': {'flag': bool, 'type': str, 'confidence': str},
          'lv_hypertrophy': {'flag': bool, 'type': str},
          'lv_dilatation': {'flag': bool},
          'la_enlargement': {'flag': bool},
          'amyloidosis_suspicion': {'flag': bool, 'confidence': str},
          'diastolic_dysfunction_risk': {'flag': bool, 'risk_factors': list},
          'valvular_disease_risk': {'flag': bool, 'indicators': list},
          'recommendations': [str, ...],
          'notes': [str, ...]
        }
    """
    results = {}
    notes = []
    recommendations = []

    sex   = measurements.get("sex", "")

    def _val(key, default=None):
        e = measurements.get(key)
        return e.get("value", default) if isinstance(e, dict) else default

    ef    = _val("LVEF", 55.0)
    ivsd  = _val("IVSd", 0.0)
    lvpwd = _val("LVPWd", 0.0)
    lvidd = _val("LVIDd", 0.0)
    lvids  = _val("LVIDs")
    rwt    = _val("RWT", 0.0)
    la_area = _val("LA_area", 0.0)
    lav    = _val("LAV", 0.0) or 0.0
    lavi   = _val("LAVi")
    lvmi   = _val("LVMi")
    lvm    = _val("LVM")
    lvsv   = _val("LVSV")
    lvedv  = _val("LVEDV")
    lvesv  = _val("LVESV")
    lvedvi = _val("LVEDVi")
    lvesvi = _val("LVESVi")
    gls   = _val("GLS")
    co    = _val("CO")
    bsa   = _val("BSA")

    # ── Heart Failure ────────────────────────────────────────────────────────
    hf_flag = ef < 50
    hf_type = ""
    if ef < 30:
        hf_type = "HFrEF (EF < 30%) - severe"
        notes.append("Severely reduced EF (<30%) -- urgent HFrEF work-up required.")
        recommendations.append(
            "URGENT: EF < 30%. Recommend cardiology consultation, "
            "NT-proBNP / BNP, renal function panel, consider ICD evaluation "
            "per ESC/AHA guidelines."
        )
    elif ef < 40:
        hf_type = "HFrEF (EF < 40%)"
        notes.append("Severely reduced EF -- consider HFrEF work-up.")
        recommendations.append(
            "EF < 40% (HFrEF). Recommend initiation/optimization of GDMT: "
            "ACEi/ARNi + beta-blocker + MRA + SGLT2i. "
            "Consider cardiac MRI for etiology assessment."
        )
    elif ef < 50:
        hf_type = "HFmrEF (EF 40-49%)"
        notes.append("Mildly reduced EF -- consider HFmrEF evaluation.")
        recommendations.append(
            "EF 40-49% (HFmrEF). Recommend NT-proBNP, "
            "echocardiographic follow-up in 3-6 months, "
            "consider diuretics if symptomatic."
        )

    results["heart_failure"] = {
        "flag": hf_flag,
        "type": hf_type,
        "confidence": "rule-based",
    }

    # ── LV Hypertrophy ───────────────────────────────────────────────────────
    lvh_threshold = 1.3 if sex == "M" else 1.2
    lv_hypertrophy = (ivsd > lvh_threshold or lvpwd > lvh_threshold)

    lvmi_threshold = (115 if sex == "M" else 95 if sex == "F" else None)
    if lvmi is not None and lvmi_threshold is not None and lvmi > lvmi_threshold:
        lv_hypertrophy = True

    hyp_type = ""
    if lv_hypertrophy:
        if rwt > 0.42 and lvidd < (5.9 if sex == "M" else 5.3):
            hyp_type = "Concentric LVH"
            notes.append("Concentric LVH pattern -- consider hypertension, "
                         "HCM, or amyloidosis.")
            recommendations.append(
                "Concentric LVH detected. Recommend: "
                "1) Blood pressure assessment and 24h ambulatory monitoring, "
                "2) ECG for voltage criteria and strain pattern, "
                "3) If IVSd > 1.5 cm: consider cardiac MRI to exclude HCM/amyloidosis, "
                "4) Serum/urine immunofixation if amyloidosis suspected."
            )
        else:
            hyp_type = "Eccentric LVH"
            notes.append("Eccentric LVH -- consider volume overload or DCM.")
            recommendations.append(
                "Eccentric LVH pattern. Evaluate for: "
                "volume overload (valvular regurgitation, anemia, thyrotoxicosis), "
                "dilated cardiomyopathy. Consider cardiac MRI with late gadolinium enhancement."
            )

    results["lv_hypertrophy"] = {
        "flag": lv_hypertrophy,
        "type": hyp_type,
    }

    # ── LV Dilatation ────────────────────────────────────────────────────────
    dil_threshold = 5.3 if sex == "F" else 5.9
    lv_dilated = lvidd > dil_threshold
    if lv_dilated:
        notes.append("LV cavity enlarged -- consider DCM or volume overload.")
        recommendations.append(
            "LV dilatation present. Recommend evaluation for: "
            "dilated cardiomyopathy, significant valvular regurgitation (MR/AR), "
            "ischemic etiology (coronary angiography if risk factors present). "
            "Serial echo in 6 months to assess progression."
        )

    results["lv_dilatation"] = {"flag": lv_dilated}

    # ── LA Enlargement ───────────────────────────────────────────────────────
    if lavi is not None:
        la_enlarged = lavi > 34
    elif lav > 0:
        la_enlarged = lav > (58 if sex == "M" else 52 if sex == "F" else 55)
    else:
        la_enlarged = la_area > 20
    if la_enlarged:
        notes.append("Left atrium enlarged -- consider AF risk, diastolic "
                     "dysfunction, or mitral valve disease.")
        recommendations.append(
            "LA enlargement detected. Recommend: "
            "1) ECG/Holter to screen for atrial fibrillation, "
            "2) Assess diastolic function (E/A, E/e' if Doppler available), "
            "3) Evaluate mitral valve for structural abnormalities, "
            "4) CHA2DS2-VASc score if AF confirmed."
        )

    results["la_enlargement"] = {"flag": la_enlarged}

    # ── Amyloidosis suspicion (simple pattern) ───────────────────────────────
    amy_suspect = (lv_hypertrophy and ef >= 50 and rwt > 0.42)
    # Strengthen suspicion if severe wall thickening
    high_suspicion = (amy_suspect and (ivsd > 1.5 or lvpwd > 1.5))
    if amy_suspect:
        if high_suspicion:
            notes.append(
                "Significant wall thickening (>1.5 cm) with preserved EF -- "
                "cardiac amyloidosis should be actively excluded."
            )
            recommendations.append(
                "HIGH SUSPICION for cardiac amyloidosis. Recommend: "
                "1) Tc-99m PYP/DPD bone scintigraphy (ATTR screening), "
                "2) Serum free light chains + immunofixation (AL screening), "
                "3) Cardiac MRI with T1 mapping if available, "
                "4) Referral to amyloidosis center."
            )
        else:
            notes.append(
                "Wall thickening with preserved EF -- consider cardiac amyloidosis "
                "or hypertrophic cardiomyopathy (further evaluation required)."
            )
            recommendations.append(
                "LVH with preserved EF pattern. Differential: HCM vs cardiac amyloidosis. "
                "Consider cardiac MRI and genetic testing if HCM suspected, "
                "or Tc-99m PYP scintigraphy if amyloidosis suspected."
            )

    results["amyloidosis_suspicion"] = {
        "flag": amy_suspect,
        "confidence": "high (rule-based)" if high_suspicion else "low (rule-based screening only)",
    }

    # ── Diastolic Dysfunction Risk ───────────────────────────────────────────
    dd_risk_factors = []
    if la_enlarged:
        dd_risk_factors.append("LA enlargement")
    if lv_hypertrophy:
        dd_risk_factors.append("LV hypertrophy")
    if ef >= 50 and lv_hypertrophy and la_enlarged:
        dd_risk_factors.append("HFpEF pattern (preserved EF + LVH + LA enlargement)")
    if gls is not None and gls > -16:
        dd_risk_factors.append("Impaired GLS (subclinical systolic dysfunction)")

    dd_flag = len(dd_risk_factors) >= 2
    if dd_flag:
        recommendations.append(
            "Multiple risk factors for diastolic dysfunction identified: "
            + ", ".join(dd_risk_factors) + ". "
            "Recommend Doppler assessment (E/A ratio, tissue Doppler e', E/e') "
            "for definitive grading per ASE/EACVI 2016 guidelines."
        )

    results["diastolic_dysfunction_risk"] = {
        "flag": dd_flag,
        "risk_factors": dd_risk_factors,
    }

    # ── Valvular Disease Risk Assessment ─────────────────────────────────────
    valve_indicators = []
    if la_enlarged and lv_dilated:
        valve_indicators.append("LA + LV enlargement -- evaluate for significant MR")
    if la_enlarged and not lv_dilated and lv_hypertrophy:
        valve_indicators.append("LA enlargement + LVH -- evaluate for aortic stenosis or MR")
    if lv_dilated and not lv_hypertrophy:
        valve_indicators.append("Isolated LV dilatation -- evaluate for AR or MR")

    valve_flag = len(valve_indicators) > 0
    if valve_flag:
        recommendations.append(
            "Structural pattern suggests possible valvular disease: "
            + "; ".join(valve_indicators) + ". "
            "Recommend comprehensive Doppler evaluation of all valves."
        )

    results["valvular_disease_risk"] = {
        "flag": valve_flag,
        "indicators": valve_indicators,
    }

    # ── GLS-based Early Detection ────────────────────────────────────────────
    if gls is not None:
        if gls > -12:
            recommendations.append(
                "Severely impaired GLS (> -12%). This indicates significant "
                "subclinical or overt myocardial dysfunction even if EF is preserved. "
                "Recommend comprehensive cardiology evaluation and cardiac MRI."
            )
        elif gls > -16:
            recommendations.append(
                "Mildly-moderately impaired GLS (-16% to -12%). "
                "May indicate early/subclinical myocardial dysfunction. "
                "Recommend echocardiographic follow-up in 6-12 months."
            )

    # ── Volume Status Assessment ─────────────────────────────────────────────
    if lvedvi is not None:
        if lvedvi > 74:
            recommendations.append(
                "Elevated LVEDVi (volume overload). Evaluate for: "
                "significant valvular regurgitation, high-output states, "
                "or fluid overload. Consider volume status optimization."
            )
    if lvesvi is not None:
        if lvesvi > 31:
            recommendations.append(
                "Elevated LVESVi indicating impaired contractile reserve. "
                "Consider coronary evaluation if ischemic etiology suspected."
            )

    # ── Cardiac Output Assessment ────────────────────────────────────────────
    if co is not None:
        if co < 4.0:
            recommendations.append(
                "Low cardiac output (<4.0 L/min). Assess for cardiogenic shock "
                "signs/symptoms. Verify heart rate input is accurate."
            )
        elif co > 8.0:
            recommendations.append(
                "Elevated cardiac output (>8.0 L/min). Consider high-output states: "
                "anemia, thyrotoxicosis, AV fistula, sepsis, severe AR."
            )

    # ── LV Mass Assessment ───────────────────────────────────────────────────
    if lvmi is not None:
        severe_lvmi = (200 if sex == "M" else 150)
        if lvmi > severe_lvmi:
            recommendations.append(
                "Severe LV mass elevation (LVMi > %d g/m2). "
                "High risk for arrhythmias and sudden cardiac death. "
                "Consider cardiac MRI for tissue characterization, "
                "Holter monitoring, and electrophysiology consultation." % severe_lvmi
            )

    # ── General Follow-up Recommendations ────────────────────────────────────
    if not hf_flag and not lv_hypertrophy and not lv_dilated and not la_enlarged:
        if ef >= 53:
            recommendations.append(
                "No structural abnormalities detected by 2D analysis. "
                "If clinical suspicion remains, consider Doppler assessment "
                "for diastolic function and valvular evaluation."
            )

    # ── BSA Warning ──────────────────────────────────────────────────────────
    if bsa is None or bsa == 0:
        recommendations.append(
            "Note: Height/weight not provided. Indexed measurements "
            "(LVEDVi, LVESVi, LVMi, LAVi) unavailable. "
            "Provide patient anthropometrics for complete assessment."
        )

    results["recommendations"] = recommendations
    results["notes"] = notes
    return results
