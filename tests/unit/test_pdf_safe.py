"""
Unit tests for reporting/pdf/generator.py — _safe() sanitiser.

With МЗ РК-compliant generator, _safe() is a pass-through when a Unicode TTF
font is registered (Cyrillic support); otherwise it strips to latin-1 for
the bundled fpdf2 Helvetica core font.

Run with: python -m pytest tests/unit/test_pdf_safe.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import reporting.pdf.generator as gen
from reporting.pdf.generator import _safe


class TestSafeAscii:
    """ASCII input must always round-trip identically regardless of font mode."""

    def test_ascii_passthrough(self):
        assert _safe("Hello World") == "Hello World"

    def test_empty_string(self):
        assert _safe("") == ""

    def test_numbers_and_punctuation(self):
        s = "EF=65.3% | IVSd=1.20 cm"
        assert _safe(s) == s


class TestSafeUnicodeMode:
    """When Unicode font is available, _safe() preserves non-ASCII characters."""

    def test_cyrillic_preserved(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", True)
        assert _safe("Протокол") == "Протокол"

    def test_em_dash_preserved(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", True)
        assert _safe("a\u2014b") == "a\u2014b"


class TestSafeLatin1Fallback:
    """When no Unicode font is available, _safe() strips to latin-1."""

    def test_em_dash_replaced(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", False)
        assert "\u2014" not in _safe("a\u2014b")
        assert "--" in _safe("a\u2014b")

    def test_en_dash_replaced(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", False)
        assert "\u2013" not in _safe("a\u2013b")

    def test_squared_replaced(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", False)
        result = _safe("cm\u00b2")
        assert "\u00b2" not in result
        assert "2" in result

    def test_bullet_replaced(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", False)
        assert "\u2022" not in _safe("\u2022 item")

    def test_arrow_replaced(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", False)
        result = _safe("a \u2192 b")
        assert "\u2192" not in result
        assert "->" in result

    def test_output_encodable_as_latin1(self, monkeypatch):
        monkeypatch.setattr(gen, "_HAS_UNICODE_FONT", False)
        ugly = "cm\u00b2 \u2013 \u2014 \u2022 \u2192 \u2190 \u2191 \u2193"
        _safe(ugly).encode("latin-1")  # must not raise
