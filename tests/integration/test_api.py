"""
Integration tests for the FastAPI REST API (integration/api/main.py).
Uses httpx.AsyncClient with ASGITransport — no real server needed.

Run with: python -m pytest tests/integration/test_api.py -v
"""
import sys
import io
import json
import struct
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import cv2
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from integration.api.main import app, _jobs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_avi_bytes(n_frames: int = 20, size: int = 112) -> bytes:
    """Return bytes of a minimal synthetic AVI file."""
    with tempfile.NamedTemporaryFile(suffix=".avi", delete=False) as f:
        path = f.name
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(path, fourcc, 25.0, (size, size), isColor=False)
    for i in range(n_frames):
        frame = np.zeros((size, size), dtype=np.uint8)
        r = 30 + int(10 * np.sin(2 * np.pi * i / n_frames))
        cv2.circle(frame, (56, 56), r, 200, -1)
        writer.write(frame)
    writer.release()
    with open(path, "rb") as f:
        data = f.read()
    Path(path).unlink(missing_ok=True)
    return data


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def avi_bytes():
    return _make_avi_bytes()


@pytest.fixture(autouse=True)
def clear_jobs():
    """Clear in-memory job store between tests."""
    _jobs.clear()
    yield
    _jobs.clear()


# ── Health endpoint ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health_ok():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "cuda_available" in data
    assert "active_jobs" in data


# ── Analyze endpoint ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analyze_returns_202(avi_bytes):
    with patch("integration.api.main.asyncio") as mock_asyncio:
        mock_loop = MagicMock()
        mock_asyncio.get_event_loop.return_value = mock_loop
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as client:
            r = await client.post(
                "/api/v1/analyze",
                files={"file": ("test.avi", avi_bytes, "video/avi")},
                data={"patient_name": "Test Patient", "device": "cpu"},
            )
    assert r.status_code == 202
    data = r.json()
    assert "study_id" in data
    assert data["status"] in ("pending", "processing")


@pytest.mark.anyio
async def test_analyze_invalid_format_422(avi_bytes):
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.post(
            "/api/v1/analyze",
            files={"file": ("test.mp4", avi_bytes, "video/mp4")},
        )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_analyze_creates_job(avi_bytes):
    with patch("integration.api.main.asyncio") as mock_asyncio:
        mock_loop = MagicMock()
        mock_asyncio.get_event_loop.return_value = mock_loop
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as client:
            r = await client.post(
                "/api/v1/analyze",
                files={"file": ("test.avi", avi_bytes, "video/avi")},
                data={"device": "cpu"},
            )
    study_id = r.json()["study_id"]
    assert study_id in _jobs


# ── Status endpoint ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_status_not_found():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/nonexistent-id/status")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_status_pending_after_submit(avi_bytes):
    with patch("integration.api.main.asyncio") as mock_asyncio:
        mock_loop = MagicMock()
        mock_asyncio.get_event_loop.return_value = mock_loop
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as client:
            r = await client.post(
                "/api/v1/analyze",
                files={"file": ("test.avi", avi_bytes, "video/avi")},
                data={"device": "cpu"},
            )
            study_id = r.json()["study_id"]
            r2 = await client.get(f"/api/v1/studies/{study_id}/status")
    assert r2.status_code == 200
    assert r2.json()["study_id"] == study_id
    assert r2.json()["status"] in ("pending", "processing", "done", "failed")


# ── Results endpoint (pre-seeded jobs) ────────────────────────────────────────

@pytest.mark.anyio
async def test_results_not_found():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/no-such-id")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_results_still_processing():
    _jobs["proc-id"] = {"status": "processing", "created_at": "2026-03-28T00:00:00"}
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/proc-id")
    assert r.status_code == 202


@pytest.mark.anyio
async def test_results_failed():
    _jobs["fail-id"] = {"status": "failed", "created_at": "2026-03-28T00:00:00",
                        "error": "Something went wrong"}
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/fail-id")
    assert r.status_code == 500


@pytest.mark.anyio
async def test_results_done_returns_analysis():
    _jobs["done-id"] = {
        "status": "done",
        "created_at": "2026-03-28T00:00:00",
        "completed_at": "2026-03-28T00:01:00",
        "mode": "segmentation",
        "view": {"view": "A4C", "confidence": 0.95, "trained": True},
        "measurements": {"LVEF": {"value": 60.0, "unit": "%", "flag": None}},
        "diseases": {"heart_failure": {"flag": False}},
        "report_path": "/tmp/report.pdf",
        "fhir_json": None,
    }
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/done-id")
    assert r.status_code == 200
    data = r.json()
    assert data["study_id"] == "done-id"
    assert data["mode"] == "segmentation"
    assert "measurements" in data
    assert "diseases" in data


# ── FHIR endpoint ─────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_fhir_not_found():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/no-such-id/fhir")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_fhir_still_processing():
    _jobs["fhir-proc"] = {"status": "processing", "created_at": "2026-03-28T00:00:00"}
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/fhir-proc/fhir")
    assert r.status_code == 202


@pytest.mark.anyio
async def test_fhir_returns_bundle():
    from reporting.fhir.exporter import build_fhir_bundle
    meas = {
        "LVEF": {"value": 60.0, "unit": "%", "flag": None},
        "EF_category": "Normal (HFpEF range)",
    }
    dis = {"heart_failure": {"flag": False}, "notes": []}
    bundle = build_fhir_bundle(meas, dis, None)
    fhir_json = bundle.model_dump_json()

    _jobs["fhir-done"] = {
        "status": "done",
        "created_at": "2026-03-28T00:00:00",
        "fhir_json": fhir_json,
    }
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/fhir-done/fhir")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/fhir+json")
    data = r.json()
    assert data["resourceType"] == "Bundle"
    assert data["type"] == "transaction"


@pytest.mark.anyio
async def test_fhir_no_bundle_404():
    _jobs["fhir-none"] = {
        "status": "done",
        "created_at": "2026-03-28T00:00:00",
        "fhir_json": None,
    }
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        r = await client.get("/api/v1/studies/fhir-none/fhir")
    assert r.status_code == 404
