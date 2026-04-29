"""
PDF Report Generator — МЗ РК-compliant echocardiography protocol.

Produces a standardized echocardiography report following:
  • Клинический протокол диагностики и лечения МЗ РК (Приказ МЗ РК)
  • Стандарт оказания кардиологической помощи
  • Рекомендации ASE 2015 / ESC 2021

Key МЗ РК requirements implemented:
  • Bilingual labels (RU primary, EN in brackets)
  • Паспортные данные пациента (ФИО, ИИН, пол, возраст, рост, вес, ППТ)
  • Стандартные разделы: ЛЖ / ЛП / ПЖ / Клапаны / Перикард / Заключение
  • Заключение + Рекомендации врача
  • Блок подписи врача + печать организации + лицензия
  • Ссылки на приказ МЗ РК и клинические протоколы
"""
from fpdf import FPDF, XPos, YPos
from datetime import datetime
from pathlib import Path
import numpy as np
import tempfile, os, platform

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import REPORTS_DIR, NORMAL_RANGES


# ── Colour palette ─────────────────────────────────────────────────────────────
BRAND_BLUE  = (41, 98, 255)
BRAND_DARK  = (30, 30, 30)
RED         = (220, 50, 50)
GREEN       = (30, 160, 80)
ORANGE      = (230, 130, 0)
LIGHT_GRAY  = (245, 247, 250)
MID_GRAY    = (180, 180, 180)
BORDER_GRAY = (210, 210, 215)


# ── Unicode font discovery (Cyrillic support) ─────────────────────────────────
def _find_unicode_font() -> tuple[str | None, str | None, str | None]:
    """Return (regular, bold, italic) TTF paths with Cyrillic support, or (None,)*3."""
    candidates = [
        (r"C:\Windows\Fonts\arial.ttf",
         r"C:\Windows\Fonts\arialbd.ttf",
         r"C:\Windows\Fonts\ariali.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
        ("/Library/Fonts/Arial.ttf",
         "/Library/Fonts/Arial Bold.ttf",
         "/Library/Fonts/Arial Italic.ttf"),
    ]
    for reg, bold, italic in candidates:
        if Path(reg).exists():
            return (reg,
                    bold if Path(bold).exists() else reg,
                    italic if Path(italic).exists() else reg)
    return None, None, None


_FONT_REG, _FONT_BOLD, _FONT_ITALIC = _find_unicode_font()
_HAS_UNICODE_FONT = _FONT_REG is not None
FONT = "Unicode" if _HAS_UNICODE_FONT else "Helvetica"


def _safe(text: str) -> str:
    """Pass-through if Unicode font available, otherwise strip to latin-1."""
    if _HAS_UNICODE_FONT:
        return str(text)
    replacements = {
        "\u2013": "-", "\u2014": "--", "\u2022": "*", "\u2019": "'",
        "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2264": "<=",
        "\u2265": ">=", "\u2260": "!=", "\u00b0": "deg", "\u00b2": "2",
        "\u00b3": "3", "\u00b5": "u", "\u03bc": "u", "\u03b1": "a",
        "\u2713": "OK", "\u2714": "[+]", "\u2715": "[-]",
        "\u2192": "->", "\u2190": "<-", "\u2191": "^", "\u2193": "v",
        "№": "No.",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class MoHReport(FPDF):
    """Custom FPDF subclass with МЗ РК-compliant header/footer."""

    def header(self):
        self.set_fill_color(*BRAND_BLUE)
        self.rect(0, 0, 210, 16, "F")
        self.set_text_color(255, 255, 255)
        self.set_font(FONT, "B", 11)
        self.set_xy(8, 3)
        self.cell(0, 5, _safe("ПРОТОКОЛ ЭХОКАРДИОГРАФИЧЕСКОГО ИССЛЕДОВАНИЯ"),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font(FONT, "", 8)
        self.set_x(8)
        self.cell(0, 4, _safe("CordisAI  |  AI-Assisted Echocardiography Report  |  Соответствует требованиям МЗ РК"),
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*BRAND_DARK)
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font(FONT, "I", 7.5)
        self.set_text_color(*MID_GRAY)
        self.cell(
            0, 4,
            _safe("AI-сгенерированный черновик — требует проверки и подписи врача-кардиолога. "
                  "Соответствует клиническому протоколу МЗ РК по эхокардиографии."),
            align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        self.cell(0, 4, _safe(f"Страница {self.page_no()} / {{nb}}"), align="C")


# ── Helper plots ───────────────────────────────────────────────────────────────

def _save_area_curve(lv_areas: np.ndarray, ed_idx: int, es_idx: int,
                     out_path: str) -> bool:
    if not _HAS_MPL or lv_areas is None:
        return False
    fig, ax = plt.subplots(figsize=(5, 2.2))
    ax.plot(lv_areas, color="#2962FF", linewidth=1.8)
    ax.axvline(ed_idx, color="green",  linestyle="--", linewidth=1.2, label="ED")
    ax.axvline(es_idx, color="red",    linestyle="--", linewidth=1.2, label="ES")
    ax.set_xlabel("Frame", fontsize=8)
    ax.set_ylabel("LV area (px)", fontsize=8)
    ax.set_title("LV Area Over Cardiac Cycle", fontsize=9, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return True


def _save_gls_curve(gls_curve: np.ndarray, ed_idx: int, es_idx: int,
                    gls_val: float, out_path: str) -> bool:
    if not _HAS_MPL or gls_curve is None or len(gls_curve) < 3:
        return False
    fig, ax = plt.subplots(figsize=(5, 2.2))
    ax.plot(gls_curve, color="#e94560", linewidth=1.8, label="Strain (%)")
    ax.axhline(0,   color="#888", linewidth=0.7, linestyle=":")
    ax.axhline(-16, color="#f4a261", linewidth=1.0, linestyle="--",
               label="Normal limit (-16%)")
    ax.axvline(ed_idx, color="green", linestyle="--", linewidth=1.2, label="ED")
    ax.axvline(es_idx, color="red",   linestyle="--", linewidth=1.2, label="ES")
    ax.set_xlabel("Frame", fontsize=8)
    ax.set_ylabel("Strain (%)", fontsize=8)
    ax.set_title(f"GLS Strain Curve  (GLS = {gls_val:.1f}%)", fontsize=9, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    plt.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return True


# ── Main generator ─────────────────────────────────────────────────────────────

def generate_report(
    measurements: dict,
    diseases: dict,
    patient_info: dict | None = None,
    output_path: str | Path | None = None,
    organization: dict | None = None,
) -> Path:
    """
    Generate МЗ РК-compliant echocardiography PDF protocol.

    Args:
        measurements:  Output of measurement engine (21 params).
        diseases:      Output of disease classifier + recommendations.
        patient_info:  {'name', 'dob', 'id', 'iin', 'study_date', 'sex',
                        'height_cm', 'weight_kg', 'bp', 'hr', 'referrer',
                        'indication', 'card_number'}
        output_path:   Where to save the PDF (auto-named if None).
        organization:  {'name', 'address', 'license', 'doctor_name',
                        'doctor_position', 'doctor_license'}
    """
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = REPORTS_DIR / f"CordisAI_MoH_Report_{ts}.pdf"
    output_path = Path(output_path)

    pdf = MoHReport(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)

    # Register Unicode font if found
    if _HAS_UNICODE_FONT:
        pdf.add_font("Unicode", "", _FONT_REG)
        pdf.add_font("Unicode", "B", _FONT_BOLD)
        pdf.add_font("Unicode", "I", _FONT_ITALIC)

    pdf.alias_nb_pages()
    pdf.add_page()

    pi  = patient_info or {}
    org = organization or {}

    # ── Organization header ─────────────────────────────────────────────────
    org_name    = org.get("name",    "Медицинская организация: _________________________________")
    org_address = org.get("address", "Адрес: _________________________________________________")
    org_license = org.get("license", "Лицензия МЗ РК № _______________________________________")

    pdf.set_font(FONT, "B", 9.5)
    pdf.set_text_color(*BRAND_DARK)
    pdf.set_x(8)
    pdf.multi_cell(194, 4.5, _safe(org_name), align="C")
    pdf.set_font(FONT, "", 8)
    pdf.set_x(8)
    pdf.multi_cell(194, 4, _safe(org_address), align="C")
    pdf.set_x(8)
    pdf.multi_cell(194, 4, _safe(org_license), align="C")
    pdf.ln(2)

    # Horizontal line
    pdf.set_draw_color(*BORDER_GRAY)
    pdf.line(8, pdf.get_y(), 202, pdf.get_y())
    pdf.ln(3)

    # ── Protocol number & date ──────────────────────────────────────────────
    study_date = pi.get("study_date", datetime.now().strftime("%d.%m.%Y"))
    proto_no   = pi.get("protocol_no", datetime.now().strftime("%Y%m%d-%H%M"))
    pdf.set_font(FONT, "B", 10)
    pdf.set_x(8)
    pdf.cell(0, 5, _safe(f"Протокол № {proto_no}   от {study_date}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # ── ПАСПОРТНЫЕ ДАННЫЕ ПАЦИЕНТА ─────────────────────────────────────────
    _section_title(pdf, "ПАСПОРТНЫЕ ДАННЫЕ ПАЦИЕНТА  (Patient Identification)")

    sex_code  = measurements.get("sex") or pi.get("sex", "")
    sex_label = ("Мужской (M)" if sex_code == "M"
                 else "Женский (F)" if sex_code == "F"
                 else "Не указан")
    bsa = measurements.get("BSA") or pi.get("bsa")
    bsa_str = f"{bsa:.2f} м²" if bsa else pi.get("bsa_str", "—")

    _kv_row(pdf, [("Ф.И.О.:", pi.get("name", "Анонимно")),
                  ("Дата рожд.:", pi.get("dob", "—"))])
    _kv_row(pdf, [("Пол:", sex_label),
                  ("ИИН:", pi.get("iin", "—"))])
    _kv_row(pdf, [("Рост:", f"{pi.get('height_cm', '—')} см" if pi.get('height_cm') else "—"),
                  ("Вес:", f"{pi.get('weight_kg', '—')} кг" if pi.get('weight_kg') else "—")])
    _kv_row(pdf, [("ППТ (BSA):", bsa_str),
                  ("АД / ЧСС:", f"{pi.get('bp', '—')} / {pi.get('hr', '—')} уд/мин")])
    _kv_row(pdf, [("№ карты / ист. болезни:", pi.get("card_number") or pi.get("id", "—")),
                  ("Направлен:", pi.get("referrer", "—"))])
    pdf.set_x(12)
    pdf.set_font(FONT, "", 9)
    pdf.multi_cell(190, 5, _safe(f"Показание к исследованию: {pi.get('indication', '—')}"))
    pdf.ln(2)

    # ── РЕЖИМ ИССЛЕДОВАНИЯ ─────────────────────────────────────────────────
    _section_title(pdf, "РЕЖИМ ИССЛЕДОВАНИЯ  (Scan Modality)")
    pdf.set_font(FONT, "", 9)
    pdf.set_x(12)
    pdf.multi_cell(190, 5, _safe(
        "Двумерная (2D) эхокардиография с автоматическим AI-анализом (CordisAI U-Net). "
        "Доступы: апикальный 4-камерный (A4C). Доплеровское исследование: не проводилось."
    ))
    pdf.ln(2)

    # ── ЛЕВЫЙ ЖЕЛУДОЧЕК ─────────────────────────────────────────────────────
    _section_title(pdf, "ЛЕВЫЙ ЖЕЛУДОЧЕК — СИСТОЛИЧЕСКАЯ ФУНКЦИЯ  (LV Systolic Function)")

    ef_ref  = ("52–72%" if sex_code == "M" else "54–74%" if sex_code == "F" else "53–73%")
    edv_ref = ("62–150 мл" if sex_code == "M" else "46–106 мл" if sex_code == "F" else "56–104 мл")
    esv_ref = ("21–61 мл" if sex_code == "M" else "14–42 мл"  if sex_code == "F" else "19–49 мл")

    rows = [
        ("ФВ ЛЖ (LVEF)",      measurements.get("LVEF",  {}).get("value"), "%",
                              measurements.get("LVEF",  {}).get("flag"),
                              f"Норма {ef_ref}"),
        ("КДО (LVEDV)",       measurements.get("LVEDV", {}).get("value"), "мл",
                              measurements.get("LVEDV", {}).get("flag"),
                              f"Норма {edv_ref}"),
        ("КСО (LVESV)",       measurements.get("LVESV", {}).get("value"), "мл",
                              measurements.get("LVESV", {}).get("flag"),
                              f"Норма {esv_ref}"),
        ("УО (SV)",           measurements.get("LVSV",  {}).get("value"), "мл",
                              measurements.get("LVSV",  {}).get("flag"),
                              "Норма 35–95 мл (М) / 30–80 мл (Ж)"),
    ]
    if bsa:
        rows += [
            ("Индекс КДО (LVEDVi)",  measurements.get("LVEDVi", {}).get("value"), "мл/м²",
                                     measurements.get("LVEDVi", {}).get("flag"),
                                     "Норма: М 34–74, Ж 29–61 мл/м²"),
            ("Индекс КСО (LVESVi)",  measurements.get("LVESVi", {}).get("value"), "мл/м²",
                                     measurements.get("LVESVi", {}).get("flag"),
                                     "Норма: М 11–31, Ж 8–24 мл/м²"),
        ]
    co_val = measurements.get("CO", {}).get("value")
    if co_val is not None:
        rows.append(("Сердечный выброс (CO)", co_val, "л/мин",
                     measurements.get("CO", {}).get("flag"),
                     "Норма 4.0–8.0 л/мин"))
    gls_val = measurements.get("GLS", {}).get("value")
    if gls_val is not None:
        rows.append(("ГЛС (GLS, mask-based)", gls_val, "%",
                     measurements.get("GLS", {}).get("flag"),
                     "Норма ≤ −16%"))
    _measurement_table(pdf, rows)

    ef_cat  = measurements.get("EF_category", "")
    gls_cat = measurements.get("GLS_category", "")
    pdf.set_font(FONT, "I", 9)
    pdf.set_x(12)
    pdf.cell(0, 5, _safe(f"Категория ФВ: {ef_cat}    |    Категория ГЛС: {gls_cat}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # ── РАЗМЕРЫ И ТОЛЩИНА СТЕНОК ЛЖ ───────────────────────────────────────
    _section_title(pdf, "ЛЖ — РАЗМЕРЫ И ТОЛЩИНА СТЕНОК  (LV Dimensions & Walls)")
    lvm_ref  = ("Норма М 88–224 г, Ж 67–162 г" if sex_code in ("M", "F")
                else "Норма ~88–224 г (зависит от пола)")
    lvmi_ref = ("Норма М ≤ 115, Ж ≤ 95 г/м²" if sex_code in ("M", "F")
                else "Норма ≤ 115 г/м² (зависит от пола)")

    _measurement_table(pdf, [
        ("ТМЖПд (IVSd)",      measurements.get("IVSd",  {}).get("value"), "см",
                              measurements.get("IVSd",  {}).get("flag"),  "Норма 0.6–1.0 см"),
        ("КДР ЛЖ (LVIDd)",    measurements.get("LVIDd", {}).get("value"), "см",
                              measurements.get("LVIDd", {}).get("flag"),
                              "Норма М 4.2–5.9, Ж 3.9–5.3 см"),
        ("ТЗСЛЖд (LVPWd)",    measurements.get("LVPWd", {}).get("value"), "см",
                              measurements.get("LVPWd", {}).get("flag"),  "Норма 0.6–1.0 см"),
        ("КСР ЛЖ (LVIDs)",    measurements.get("LVIDs", {}).get("value"), "см",
                              measurements.get("LVIDs", {}).get("flag"),
                              "Норма М 2.5–4.0, Ж 2.2–3.5 см"),
        ("ОТС (RWT)",         measurements.get("RWT",   {}).get("value"), "",
                              measurements.get("RWT",   {}).get("flag"),  "Норма < 0.42"),
        ("ММЛЖ (LV mass)",    measurements.get("LVM",   {}).get("value"), "г",
                              measurements.get("LVM",   {}).get("flag"),  lvm_ref),
    ])
    if bsa:
        _measurement_table(pdf, [
            ("ИММЛЖ (LVMi)", measurements.get("LVMi", {}).get("value"), "г/м²",
             measurements.get("LVMi", {}).get("flag"), lvmi_ref),
        ])
    geo = measurements.get("LV_geometry", "—")
    pdf.set_font(FONT, "I", 9)
    pdf.set_x(12)
    pdf.cell(0, 5, _safe(f"Геометрия ЛЖ (LV Geometry): {geo}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # ── ЛЕВОЕ ПРЕДСЕРДИЕ ───────────────────────────────────────────────────
    _section_title(pdf, "ЛЕВОЕ ПРЕДСЕРДИЕ  (Left Atrium)")
    la_rows = [("Объём ЛП (LAV)", measurements.get("LAV", {}).get("value"), "мл",
                measurements.get("LAV", {}).get("flag"),
                "Норма М ≤ 58 мл, Ж ≤ 52 мл")]
    if bsa:
        la_rows.append(
            ("ИОЛП (LAVi)", measurements.get("LAVi", {}).get("value"), "мл/м²",
             measurements.get("LAVi", {}).get("flag"),
             "Норма ≤ 34 мл/м² (оба пола)"),
        )
    _measurement_table(pdf, la_rows)
    pdf.ln(1)

    # ── ПРАВЫЕ ОТДЕЛЫ (не оценивались) ─────────────────────────────────────
    _section_title(pdf, "ПРАВЫЕ ОТДЕЛЫ СЕРДЦА  (Right Heart)")
    pdf.set_font(FONT, "I", 9)
    pdf.set_x(12)
    pdf.multi_cell(190, 5, _safe(
        "В данном AI-анализе не оценивались (требуется ручная оценка врачом): "
        "размер ПЖ, ТАПСЕ, FAC, систолическое давление в ЛА (PASP)."
    ))
    pdf.ln(1)

    # ── КЛАПАНЫ / ПЕРИКАРД / ДОПЛЕР ────────────────────────────────────────
    _section_title(pdf, "КЛАПАННЫЙ АППАРАТ, ПЕРИКАРД, ДОППЛЕР  (Valves / Pericardium / Doppler)")
    pdf.set_font(FONT, "I", 9)
    pdf.set_x(12)
    pdf.multi_cell(190, 5, _safe(
        "Доплеровское исследование (E/A, E/e', DT, Peak TRV) и визуальная оценка клапанов "
        "и перикарда в данном AI-анализе не проводились. Требуется очное заключение "
        "врача-кардиолога."
    ))
    pdf.ln(2)

    # ── AI-ЗАКЛЮЧЕНИЕ ──────────────────────────────────────────────────────
    _section_title(pdf, "AI-ВЫЯВЛЕННЫЕ СОСТОЯНИЯ  (AI-Assisted Findings)")
    _disease_table(pdf, diseases)
    pdf.ln(1)

    # ── Графики (если есть) ────────────────────────────────────────────────
    lv_areas = measurements.get("lv_areas")
    if lv_areas is not None and _HAS_MPL:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name
        if _save_area_curve(lv_areas,
                            measurements.get("ed_frame", 0),
                            measurements.get("es_frame", 0),
                            tmp_path):
            _section_title(pdf, "ПЛОЩАДЬ ЛЖ — СЕРДЕЧНЫЙ ЦИКЛ  (LV Area Cycle)")
            pdf.image(tmp_path, x=12, w=130)
            pdf.ln(3)
            os.unlink(tmp_path)

    gls_curve = measurements.get("GLS_curve")
    gls_reliable = measurements.get("GLS_reliable", False)
    if gls_reliable and gls_curve is not None and _HAS_MPL:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_gls = f.name
        if _save_gls_curve(gls_curve,
                           measurements.get("ed_frame", 0),
                           measurements.get("es_frame", 0),
                           measurements.get("GLS", {}).get("value", 0.0),
                           tmp_gls):
            _section_title(pdf, "КРИВАЯ ГЛС (GLS Strain Curve)")
            pdf.image(tmp_gls, x=12, w=130)
            pdf.set_font(FONT, "I", 8)
            pdf.set_text_color(*MID_GRAY)
            pdf.set_x(12)
            pdf.multi_cell(190, 4.5, _safe(
                "Примечание: ГЛС рассчитан на основе изменения длины эндокардиального контура; "
                "не эквивалентен speckle-tracking GLS."
            ))
            pdf.ln(2)
            pdf.set_text_color(*BRAND_DARK)
            os.unlink(tmp_gls)

    # ── КЛИНИЧЕСКИЕ ЗАМЕТКИ ───────────────────────────────────────────────
    notes = diseases.get("notes", [])
    if notes:
        _section_title(pdf, "КЛИНИЧЕСКИЕ ЗАМЕТКИ  (Clinical Notes)")
        pdf.set_font(FONT, "", 9)
        pdf.set_text_color(*BRAND_DARK)
        for note in notes:
            pdf.set_x(14)
            pdf.multi_cell(188, 5, _safe(f"•  {note}"))
        pdf.ln(2)

    # ── РЕКОМЕНДАЦИИ ──────────────────────────────────────────────────────
    recs = diseases.get("recommendations", [])
    if recs:
        _section_title(pdf, "AI-РЕКОМЕНДАЦИИ  (AI-Assisted Clinical Recommendations)")
        pdf.set_font(FONT, "", 9)
        pdf.set_text_color(*BRAND_DARK)
        for i, rec in enumerate(recs, 1):
            pdf.set_x(14)
            pdf.multi_cell(188, 5, _safe(f"{i}. {rec}"))
            pdf.ln(0.5)
        pdf.ln(2)

    # ── ЗАКЛЮЧЕНИЕ ВРАЧА (пустое поле) ─────────────────────────────────────
    _section_title(pdf, "ЗАКЛЮЧЕНИЕ ВРАЧА  (Physician's Conclusion)")
    pdf.set_font(FONT, "I", 9)
    pdf.set_text_color(*MID_GRAY)
    pdf.set_x(12)
    pdf.multi_cell(190, 5, _safe(
        "Заполняется врачом-кардиологом после верификации AI-данных. "
        "Диагноз по МКБ-10: _______________________________________________________"
    ))
    pdf.ln(1)
    # Empty lines for handwritten conclusion
    for _ in range(4):
        pdf.set_x(12)
        pdf.set_draw_color(*BORDER_GRAY)
        y = pdf.get_y() + 5
        pdf.line(12, y, 200, y)
        pdf.ln(6)
    pdf.ln(1)

    # ── ПОДПИСЬ ВРАЧА ──────────────────────────────────────────────────────
    _section_title(pdf, "ПОДПИСЬ ВРАЧА  (Physician's Signature)")
    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*BRAND_DARK)
    doctor_name     = org.get("doctor_name", "_____________________________________")
    doctor_position = org.get("doctor_position", "Врач-кардиолог / Специалист УЗД")
    doctor_license  = org.get("doctor_license", "____________________________")

    pdf.set_x(12)
    pdf.cell(0, 5, _safe(f"Должность: {doctor_position}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(12)
    pdf.cell(0, 5, _safe(f"Ф.И.О.:    {doctor_name}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(12)
    pdf.cell(0, 5, _safe(f"№ сертификата / лицензии: {doctor_license}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    pdf.set_x(12)
    pdf.cell(70, 5, _safe("Подпись: _____________________"), border=0)
    pdf.cell(60, 5, _safe(f"Дата: {study_date}"), border=0)
    pdf.cell(0,  5, _safe("М.П."), border=0,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # ── Соответствие нормативам ───────────────────────────────────────────
    pdf.set_font(FONT, "B", 8.5)
    pdf.set_text_color(*BRAND_BLUE)
    pdf.set_x(8)
    pdf.cell(0, 4, _safe("СООТВЕТСТВИЕ НОРМАТИВНЫМ ТРЕБОВАНИЯМ:"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(FONT, "", 8)
    pdf.set_text_color(*BRAND_DARK)
    for line in [
        "•  Клинический протокол диагностики и лечения МЗ РК по эхокардиографии",
        "•  Стандарт оказания кардиологической помощи взрослому населению (МЗ РК)",
        "•  ASE Recommendations for Cardiac Chamber Quantification (2015)",
        "•  ESC Guidelines for the Diagnosis and Treatment of Heart Failure (2021)",
        "•  ISO 27001 / HIPAA compliance (data security)",
    ]:
        pdf.set_x(10)
        pdf.multi_cell(192, 4, _safe(line))
    pdf.ln(2)

    # ── DISCLAIMER ────────────────────────────────────────────────────────
    pdf.set_font(FONT, "I", 7.5)
    pdf.set_text_color(*MID_GRAY)
    pdf.multi_cell(
        0, 4,
        _safe(
            "DISCLAIMER / ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ: Данный протокол сформирован программным "
            "обеспечением CordisAI на основе автоматического анализа эхокардиографического видео "
            "с применением искусственного интеллекта и представляет собой предварительный "
            "черновик. Все измерения и заключения подлежат обязательной проверке, верификации "
            "и подписи лицензированным врачом-кардиологом до клинического использования. "
            "CordisAI не заменяет клиническое суждение врача и не является медицинским изделием "
            "в смысле законодательства РК о медицинских изделиях."
        ),
    )

    pdf.output(str(output_path))
    return output_path


# ── Internal helpers ───────────────────────────────────────────────────────────

def _section_title(pdf: MoHReport, title: str) -> None:
    pdf.set_fill_color(*BRAND_BLUE)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(FONT, "B", 9.5)
    pdf.set_x(8)
    pdf.cell(194, 6, _safe(f"  {title}"), fill=True,
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    pdf.set_text_color(*BRAND_DARK)


def _kv_row(pdf: MoHReport, pairs: list[tuple[str, str]]) -> None:
    """Two-column key/value row inside patient card."""
    pdf.set_x(12)
    pdf.set_font(FONT, "B", 8.5)
    k1, v1 = pairs[0]
    pdf.cell(35, 5, _safe(k1), border=0)
    pdf.set_font(FONT, "", 8.5)
    pdf.cell(60, 5, _safe(str(v1)), border=0)
    if len(pairs) > 1:
        k2, v2 = pairs[1]
        pdf.set_font(FONT, "B", 8.5)
        pdf.cell(30, 5, _safe(k2), border=0)
        pdf.set_font(FONT, "", 8.5)
        pdf.cell(0, 5, _safe(str(v2)), border=0)
    pdf.ln(5)


def _flag_color(flag: str | None):
    if flag == "LOW":
        return ORANGE
    if flag == "HIGH":
        return RED
    return GREEN


def _flag_ru(flag: str | None) -> str:
    if flag == "LOW":
        return "Снижен"
    if flag == "HIGH":
        return "Повышен"
    return "Норма"


def _measurement_table(pdf: MoHReport, rows: list) -> None:
    """rows: list of (name, value, unit, flag, reference) tuples."""
    col_w   = [50, 24, 16, 22, 82]
    headers = ["Параметр", "Значение", "Ед.", "Статус", "Референсный диапазон"]

    pdf.set_fill_color(*BRAND_DARK)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(FONT, "B", 8)
    pdf.set_x(8)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 5.5, _safe(f"  {h}"), fill=True, border=0)
    pdf.ln()

    for i, (name, value, unit, flag, ref) in enumerate(rows):
        fill_rgb = LIGHT_GRAY if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_rgb)
        pdf.set_text_color(*BRAND_DARK)
        pdf.set_font(FONT, "", 8.5)
        pdf.set_x(8)

        val_str = f"{value:.1f}" if isinstance(value, float) else str(value or "—")

        pdf.cell(col_w[0], 5.5, _safe(f"  {name}"), fill=True)
        pdf.cell(col_w[1], 5.5, _safe(f"  {val_str}"), fill=True)
        pdf.cell(col_w[2], 5.5, _safe(f"  {unit}"), fill=True)

        pdf.set_text_color(*_flag_color(flag))
        pdf.set_font(FONT, "B", 8.5)
        pdf.cell(col_w[3], 5.5, _safe(f"  {_flag_ru(flag)}"), fill=True)

        pdf.set_text_color(*BRAND_DARK)
        pdf.set_font(FONT, "", 8)
        pdf.cell(col_w[4], 5.5, _safe(f"  {ref}"), fill=True)
        pdf.ln()

    pdf.ln(1)


def _disease_table(pdf: MoHReport, diseases: dict) -> None:
    checks = [
        ("Сердечная недостаточность (Heart Failure)",
         diseases.get("heart_failure", {}).get("flag"),
         diseases.get("heart_failure", {}).get("type", "")),
        ("Гипертрофия ЛЖ (LV Hypertrophy)",
         diseases.get("lv_hypertrophy", {}).get("flag"),
         diseases.get("lv_hypertrophy", {}).get("type", "")),
        ("Дилатация ЛЖ (LV Dilatation)",
         diseases.get("lv_dilatation", {}).get("flag"), ""),
        ("Увеличение ЛП (LA Enlargement)",
         diseases.get("la_enlargement", {}).get("flag"), ""),
        ("Подозрение на амилоидоз (Amyloidosis)",
         diseases.get("amyloidosis_suspicion", {}).get("flag"),
         diseases.get("amyloidosis_suspicion", {}).get("confidence", "")),
    ]

    pdf.set_x(8)
    for i, (cond, flag, detail) in enumerate(checks):
        fill_rgb = LIGHT_GRAY if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*fill_rgb)

        marker = "[+]" if flag else "[-]"
        color = RED if flag else GREEN

        pdf.set_text_color(*color)
        pdf.set_font(FONT, "B", 9)
        pdf.set_x(8)
        pdf.cell(10, 5.5, _safe(marker), fill=True)

        pdf.set_text_color(*BRAND_DARK)
        pdf.set_font(FONT, "B" if flag else "", 9)
        pdf.cell(95, 5.5, _safe(cond), fill=True)

        pdf.set_font(FONT, "I", 8.5)
        pdf.cell(0, 5.5, _safe(detail or ("Выявлено" if flag else "Не выявлено")),
                 fill=True)
        pdf.ln()

    pdf.ln(1)
