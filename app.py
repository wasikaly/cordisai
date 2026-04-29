"""
HeartAI — Streamlit Web Application (MVP UI)

Run with:
    streamlit run app.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import numpy as np
import tempfile, os

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HeartAI — Echo Analysis",
    page_icon="🫀",
    layout="wide",
)

# ── Inline CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 20px 30px;
        border-radius: 12px;
        margin-bottom: 24px;
    }
    .main-header h1 { color: #e94560; margin: 0; font-size: 2rem; }
    .main-header p  { color: #a8b2d8; margin: 4px 0 0; font-size: 1rem; }
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; }
    .metric-label { color: #a8b2d8; font-size: 0.85rem; }
    .flag-normal   { color: #a6e3a1; }
    .flag-abnormal { color: #f38ba8; }
    .disclaimer {
        background: #1e1e2e;
        border-left: 4px solid #fab387;
        padding: 12px 16px;
        border-radius: 6px;
        color: #cdd6f4;
        font-size: 0.82rem;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🫀 HeartAI</h1>
  <p>Automated Echocardiography Analysis Platform — AI-Powered MVP</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar — patient info ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔖 Patient Information")
    patient_name = st.text_input("Patient Name", "Anonymous")
    patient_id   = st.text_input("Patient ID",   "N/A")
    patient_dob  = st.text_input("Date of Birth","N/A")
    study_date   = st.date_input("Study Date")

    st.markdown("---")
    st.markdown("### 🧬 Anthropometrics")
    patient_sex    = st.selectbox("Sex", ["Unknown", "Male", "Female"])
    patient_height = st.number_input("Height (cm)", min_value=0, max_value=250,
                                     value=0, step=1,
                                     help="Required for BSA-indexed measurements")
    patient_weight = st.number_input("Weight (kg)", min_value=0, max_value=300,
                                     value=0, step=1,
                                     help="Required for BSA-indexed measurements")
    patient_hr     = st.number_input("Heart Rate (bpm)", min_value=0, max_value=300,
                                     value=0, step=1,
                                     help="Required for Cardiac Output calculation")

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    use_gpu = st.checkbox("Use GPU (CUDA)", value=True)
    device  = "cuda" if use_gpu else "cpu"

    st.markdown("---")
    st.markdown("""
    **HeartAI MVP**
    - LV Segmentation (U-Net)
    - LVEF · LVEDV · LVESV · LVSV
    - LV mass + indexed values
    - Wall thickness + LVIDs
    - LA volume (from mask)
    - Cardiac Output (with HR)
    - Gender-specific norms
    - Disease detection
    - PDF Report
    """)

_sex_code = {"Male": "M", "Female": "F"}.get(patient_sex, "")
patient_info = {
    "name":       patient_name,
    "id":         patient_id,
    "dob":        patient_dob,
    "study_date": str(study_date),
    "sex":        _sex_code,
    "height_cm":  patient_height if patient_height > 0 else None,
    "weight_kg":  patient_weight if patient_weight > 0 else None,
    "heart_rate": patient_hr     if patient_hr > 0     else None,
}

# ── Main area ──────────────────────────────────────────────────────────────────
col_upload, col_info = st.columns([3, 2])

with col_upload:
    st.markdown("### 📂 Upload Echo Video")
    uploaded = st.file_uploader(
        "Drop an echocardiography file (AVI or DICOM)",
        type=["avi", "dcm"],
        help="Upload an A4C apical 4-chamber echo video in AVI or DICOM format.",
    )

with col_info:
    st.markdown("### ℹ️ Supported Formats")
    st.info(
        "**AVI** — EchoNet-Dynamic format (112×112 px)\n\n"
        "**DICOM (.dcm)** — Multi-frame cine loop from echo machine\n\n"
        "Patient info is auto-extracted from DICOM headers."
    )

# ── Analysis ───────────────────────────────────────────────────────────────────
if uploaded is not None:
    file_suffix = ".dcm" if uploaded.name.lower().endswith(".dcm") else ".avi"
    with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as f:
        f.write(uploaded.read())
        tmp_video_path = f.name

    st.success(f"File uploaded: **{uploaded.name}** ({uploaded.size / 1024:.0f} KB)")

    if st.button("🔬 Run Analysis", type="primary", use_container_width=True):
        with st.spinner("Running HeartAI pipeline…"):
            try:
                from pipeline import run_pipeline
                result = run_pipeline(
                    input_path=tmp_video_path,
                    patient_info=patient_info,
                    device=device,
                )
                st.session_state["result"] = result
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                os.unlink(tmp_video_path)

# ── Show results ───────────────────────────────────────────────────────────────
if "result" in st.session_state:
    result = st.session_state["result"]
    meas   = result["measurements"]
    dis    = result["diseases"]
    masks  = result["masks"]

    st.markdown("---")
    st.markdown("## 📊 Analysis Results")

    # ── Mode / view badges ───────────────────────────────────────────────────
    view_info = result.get("view", {})
    col_mode, col_view = st.columns(2)
    with col_mode:
        mode = result.get("mode", "")
        mode_color = {"segmentation": "normal", "ef_regressor": "warning",
                      "random_weights": "error"}.get(mode, "info")
        getattr(st, mode_color)(f"Mode: **{mode}**")
    with col_view:
        vname = view_info.get("view", "Unknown")
        vconf = view_info.get("confidence", 0.0)
        trained = view_info.get("trained", False)
        conf_str = f" ({vconf:.0%})" if trained else " (heuristic)"
        st.info(f"View: **{vname}**{conf_str}")

    # ── Key metrics row ──────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    ef    = meas.get("LVEF",  {}).get("value", 0)
    lvedv = meas.get("LVEDV", {}).get("value", 0)
    lvesv = meas.get("LVESV", {}).get("value", 0)
    lvsv  = meas.get("LVSV",  {}).get("value", 0)
    ef_flag = meas.get("LVEF", {}).get("flag")

    def _metric_md(label, value, unit, flag=None):
        color_class = "flag-abnormal" if flag else "flag-normal"
        return f"""
        <div class="metric-card">
          <div class="metric-value {color_class}">{value}</div>
          <div class="metric-label">{label} {unit}</div>
        </div>"""

    gls_val  = meas.get("GLS",  {}).get("value")
    gls_flag = meas.get("GLS",  {}).get("flag")
    gls_str  = f"{gls_val:.1f}" if gls_val is not None else "N/A"

    c1.markdown(_metric_md("LVEF", f"{ef:.1f}", "%", ef_flag), unsafe_allow_html=True)
    c2.markdown(_metric_md("LVEDV", f"{lvedv:.1f}", "mL"), unsafe_allow_html=True)
    c3.markdown(_metric_md("LVESV", f"{lvesv:.1f}", "mL"), unsafe_allow_html=True)
    c4.markdown(_metric_md("GLS", gls_str, "%", gls_flag), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.caption(
        f"EF: **{meas.get('EF_category', '')}**  |  "
        f"GLS: **{meas.get('GLS_category', 'N/A')}**"
        + (" ⚠️ mask-based estimate" if mode == "segmentation" else "")
    )

    # ── BSA / indexed row (only if BSA available) ────────────────────────────
    bsa = meas.get("BSA")
    if bsa:
        st.markdown(f"**BSA:** {bsa:.2f} m²  |  Sex: **{meas.get('sex', '?')}**")
        ci1, ci2, ci3, ci4 = st.columns(4)
        lvedvi = meas.get("LVEDVi", {}).get("value")
        lvesvi = meas.get("LVESVi", {}).get("value")
        lvmi   = meas.get("LVMi",   {}).get("value")
        co     = meas.get("CO",     {}).get("value")
        ci1.metric("LVEDVi (mL/m²)", f"{lvedvi:.1f}" if lvedvi else "—",
                   delta=None)
        ci2.metric("LVESVi (mL/m²)", f"{lvesvi:.1f}" if lvesvi else "—")
        ci3.metric("LVM index (g/m²)", f"{lvmi:.1f}" if lvmi else "—",
                   help="Normal: men ≤115, women ≤95 g/m²")
        ci4.metric("CO (L/min)", f"{co:.2f}" if co else "—",
                   help="Cardiac Output = LVSV × HR / 1000")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Wall thickness ───────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 🧱 Wall Dimensions")
        wall_data = {
            "IVSd ED (cm)":  meas.get("IVSd",  {}).get("value", 0),
            "LVIDd (cm)":    meas.get("LVIDd", {}).get("value", 0),
            "LVPWd ED (cm)": meas.get("LVPWd", {}).get("value", 0),
            "LVIDs (cm)":    meas.get("LVIDs", {}).get("value", 0),
            "RWT":           meas.get("RWT",   {}).get("value", 0),
            "LV mass (g)":   meas.get("LVM",   {}).get("value", 0),
        }
        for k, v in wall_data.items():
            flag = None
            key_map = {"IVSd ED (cm)": "IVSd", "LVIDd (cm)": "LVIDd",
                       "LVPWd ED (cm)": "LVPWd", "LVIDs (cm)": "LVIDs",
                       "LV mass (g)": "LVM"}
            if k in key_map:
                flag = meas.get(key_map[k], {}).get("flag")
            delta_color = "inverse" if flag == "HIGH" else ("normal" if flag == "LOW" else "off")
            st.metric(k, f"{v:.2f}", delta=flag or "", delta_color=delta_color)
        st.caption(f"LV Geometry: **{meas.get('LV_geometry', 'N/A')}**")

    with col_b:
        st.markdown("#### 🫀 LA & Disease Detection")
        lav  = meas.get("LAV",  {}).get("value", 0)
        lavi = meas.get("LAVi", {}).get("value")
        la_str = f"{lav:.1f} mL"
        if lavi:
            la_str += f" (indexed: {lavi:.1f} mL/m²)"
        st.metric("LA Volume", la_str,
                  delta=meas.get("LAV", {}).get("flag") or "",
                  delta_color="inverse" if meas.get("LAV", {}).get("flag") == "HIGH" else "off")
        st.markdown("**Disease flags:**")
        conditions = [
            ("Heart Failure",         dis.get("heart_failure",        {}).get("flag"), dis.get("heart_failure",        {}).get("type", "")),
            ("LV Hypertrophy",        dis.get("lv_hypertrophy",       {}).get("flag"), dis.get("lv_hypertrophy",       {}).get("type", "")),
            ("LV Dilatation",         dis.get("lv_dilatation",        {}).get("flag"), ""),
            ("LA Enlargement",        dis.get("la_enlargement",       {}).get("flag"), ""),
            ("Amyloidosis suspicion", dis.get("amyloidosis_suspicion",{}).get("flag"), ""),
        ]
        for cond, flag, detail in conditions:
            icon = "🔴" if flag else "🟢"
            label = f"{icon} **{cond}**"
            if flag and detail:
                label += f" — {detail}"
            st.markdown(label)

    # ── LV area curve ────────────────────────────────────────────────────────
    lv_areas = meas.get("lv_areas")
    if lv_areas is not None:
        st.markdown("#### 📈 LV Area — Cardiac Cycle")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 3))
        ax.plot(lv_areas, color="#2962FF", linewidth=1.8)
        ax.axvline(meas.get("ed_frame", 0), color="green", linestyle="--",
                   linewidth=1.4, label="ED")
        ax.axvline(meas.get("es_frame", 0), color="red",   linestyle="--",
                   linewidth=1.4, label="ES")
        ax.set_xlabel("Frame")
        ax.set_ylabel("LV area (px)")
        ax.legend()
        ax.set_facecolor("#0e1117")
        fig.patch.set_facecolor("#0e1117")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    # ── GLS strain curve (segmentation mode only) ───────────────────────────
    if mode == "segmentation" and meas.get("GLS_reliable"):
        gls_curve = meas.get("GLS_curve")
        if gls_curve is not None and len(gls_curve) > 2:
            st.markdown("#### 📉 GLS Strain Curve — Cardiac Cycle")
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig2, ax2 = plt.subplots(figsize=(9, 3))
            ax2.plot(gls_curve, color="#f38ba8", linewidth=1.8, label="Strain (%)")
            ax2.axhline(0, color="#666", linewidth=0.8, linestyle=":")
            ax2.axhline(-16, color="#fab387", linewidth=1, linestyle="--",
                        label="Normal limit (-16%)")
            ax2.axvline(meas.get("ed_frame", 0), color="green", linestyle="--",
                        linewidth=1.4, label="ED")
            ax2.axvline(meas.get("es_frame", 0), color="red", linestyle="--",
                        linewidth=1.4, label="ES")
            ax2.set_xlabel("Frame")
            ax2.set_ylabel("Strain (%)")
            ax2.legend(fontsize=8)
            ax2.set_facecolor("#0e1117")
            fig2.patch.set_facecolor("#0e1117")
            ax2.tick_params(colors="white")
            ax2.xaxis.label.set_color("white")
            ax2.yaxis.label.set_color("white")
            for spine in ax2.spines.values():
                spine.set_edgecolor("#444")
            gls_display = meas.get("GLS", {}).get("value")
            gls_cat = meas.get("GLS_category", "")
            st.caption(
                f"GLS = **{gls_display:.1f}%**  |  {gls_cat}"
                "  |  Method: endocardial contour length (mask-based)"
            )
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)
    elif mode == "segmentation" and gls_val is None:
        st.info("GLS not computed — LV contour too small or not detected.")

    # ── Segmentation preview (only meaningful in segmentation mode) ───────────
    if mode == "segmentation":
        st.markdown("#### 🖼️ Segmentation Preview")
        import cv2
        ed_idx = meas.get("ed_frame", 0)
        ed_mask_preview = masks[ed_idx]
        h, w = ed_mask_preview.shape
        colour = np.zeros((h, w, 3), dtype=np.uint8)
        colour[ed_mask_preview == 1] = [41,  98,  255]
        colour[ed_mask_preview == 2] = [220, 50,  50]
        colour[ed_mask_preview == 3] = [30,  160, 80]
        bg = np.full((h, w, 3), 40, dtype=np.uint8)
        mask_any = (ed_mask_preview > 0)[..., None]
        preview = np.where(mask_any, colour, bg)
        st.image(preview, caption="ED frame — segmentation overlay (Blue=LV, Red=Myo, Green=LA)",
                 use_container_width=False, width=250)
    else:
        st.info("Segmentation preview not available in EF-regressor mode.")

    # ── Clinical notes ───────────────────────────────────────────────────────
    notes = dis.get("notes", [])
    if notes:
        st.markdown("#### 📝 Clinical Notes")
        for note in notes:
            st.warning(f"• {note}")

    # ── Download PDF ─────────────────────────────────────────────────────────
    st.markdown("---")
    report_path = result.get("report_path")
    if report_path and Path(report_path).exists():
        with open(report_path, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="📥 Download Full PDF Report",
            data=pdf_bytes,
            file_name=Path(report_path).name,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )

# ── Disclaimer ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
⚠️ <strong>Disclaimer:</strong> HeartAI is an AI-assisted analysis tool intended as a
clinical decision support aid only. All outputs are pre-populated drafts that must be
reviewed and signed off by a licensed clinician. HeartAI does not replace clinical judgement.
</div>
""", unsafe_allow_html=True)
