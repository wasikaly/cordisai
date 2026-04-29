"""
Smoke tests for the HeartAI pipeline end-to-end.
Uses synthetic AVI files — no real echo data required.
Run with: python -m pytest tests/integration/test_pipeline_smoke.py -v

These tests verify the pipeline runs without crashing and returns
correctly structured output. They do NOT validate clinical accuracy.
"""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import cv2
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_synthetic_avi(path: str, n_frames: int = 20,
                         size: int = 112) -> None:
    """Write a synthetic 112×112 grayscale AVI with moving circle."""
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(path, fourcc, 25.0, (size, size), isColor=False)
    for i in range(n_frames):
        frame = np.zeros((size, size), dtype=np.uint8)
        # Pulsating circle to mimic cardiac motion
        r = 30 + int(10 * np.sin(2 * np.pi * i / n_frames))
        cv2.circle(frame, (size // 2, size // 2), r, 200, -1)
        writer.write(frame)
    writer.release()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPipelineSmoke:
    """
    End-to-end smoke tests using synthetic AVI input.
    Runs on CPU to avoid GPU dependency in CI.
    """

    @pytest.fixture(scope="class")
    def avi_path(self, tmp_path_factory):
        p = tmp_path_factory.mktemp("data") / "synthetic.avi"
        _write_synthetic_avi(str(p))
        return str(p)

    def test_pipeline_returns_dict(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        assert isinstance(result, dict)

    def test_pipeline_keys_present(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        for key in ("masks", "measurements", "diseases", "report_path", "mode", "view"):
            assert key in result, f"Missing key: {key}"

    def test_masks_shape(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        masks = result["masks"]
        assert masks.ndim == 3
        assert masks.shape[1] == 112
        assert masks.shape[2] == 112

    def test_measurements_ef_present(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        meas = result["measurements"]
        assert "LVEF" in meas
        ef = meas["LVEF"]["value"]
        assert isinstance(ef, float)
        assert 0.0 <= ef <= 100.0

    def test_measurements_volumes_present(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        meas = result["measurements"]
        assert "LVEDV" in meas
        assert "LVESV" in meas

    def test_diseases_dict_structure(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        dis = result["diseases"]
        for key in ("heart_failure", "lv_hypertrophy", "lv_dilatation",
                    "la_enlargement", "amyloidosis_suspicion", "notes"):
            assert key in dis

    def test_pdf_report_created(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        report_path = result["report_path"]
        assert report_path is not None
        assert Path(report_path).exists()
        assert Path(report_path).suffix == ".pdf"
        assert Path(report_path).stat().st_size > 1000   # non-empty PDF

    def test_mode_is_valid_string(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        assert result["mode"] in ("segmentation", "ef_regressor", "random_weights")

    def test_view_result_structure(self, avi_path):
        from pipeline import run_pipeline
        result = run_pipeline(avi_path, device="cpu")
        view = result["view"]
        assert "view" in view
        assert "confidence" in view
        assert "trained" in view
        assert isinstance(view["trained"], bool)

    def test_patient_info_forwarded_to_report(self, avi_path):
        from pipeline import run_pipeline
        patient = {"name": "Test Patient", "id": "TP001",
                   "dob": "1970-01-01", "study_date": "2026-03-28"}
        result = run_pipeline(avi_path, patient_info=patient, device="cpu")
        assert result["report_path"] is not None
