"""
DICOMweb client for PACS integration.

Implements:
  - STOW-RS  (Store): POST studies       — send DICOM SR / images to PACS
  - WADO-RS  (Retrieve): GET instances   — pull DICOM files from PACS
  - QIDO-RS  (Query): GET studies        — search for studies / series

Compatible with:
  - Orthanc (with DICOMweb plugin)
  - DCM4CHEE
  - Google Cloud Healthcare API
  - Azure API for DICOM

Usage:
    from integration.pacs.dicomweb_client import DICOMwebClient

    client = DICOMwebClient("http://orthanc:8042/dicom-web", auth=("admin", "password"))

    # Store a DICOM file
    client.stow(Path("report.dcm"))

    # Query studies for a patient
    studies = client.qido_studies(patient_id="P999")

    # Retrieve a DICOM instance as bytes
    data = client.wado_instance(study_uid, series_uid, instance_uid)
"""
from __future__ import annotations

import sys
import json
import uuid
import email.generator
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class DICOMwebError(Exception):
    """Raised when a DICOMweb request fails."""


class DICOMwebClient:
    """
    Minimal DICOMweb (STOW-RS / WADO-RS / QIDO-RS) client.

    Args:
        base_url:  DICOMweb base URL, e.g. "http://orthanc:8042/dicom-web"
        auth:      (username, password) tuple, or None for unauthenticated
        timeout:   Request timeout in seconds (default 30)
    """

    def __init__(
        self,
        base_url: str,
        auth: tuple[str, str] | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
        self.timeout = timeout

    # ── STOW-RS ────────────────────────────────────────────────────────────────

    def stow(self, *dcm_paths: Path, study_uid: str | None = None) -> dict:
        """
        Store one or more DICOM files using STOW-RS.

        Args:
            *dcm_paths:  Paths to .dcm files to upload.
            study_uid:   Optional study UID to scope the endpoint.

        Returns:
            Parsed JSON response from the server.

        Raises:
            DICOMwebError on HTTP errors.
        """
        if not dcm_paths:
            raise ValueError("At least one DICOM file path is required.")

        boundary = uuid.uuid4().hex
        url = f"{self.base_url}/studies"
        if study_uid:
            url = f"{self.base_url}/studies/{study_uid}"

        # Build multipart/related body manually (requests doesn't support
        # content-type per part natively)
        parts = []
        for path in dcm_paths:
            data = Path(path).read_bytes()
            parts.append(
                f"--{boundary}\r\n"
                f"Content-Type: application/dicom\r\n"
                f"\r\n".encode() + data + b"\r\n"
            )
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()

        headers = {
            "Content-Type": f'multipart/related; type="application/dicom"; boundary="{boundary}"',
            "Accept": "application/dicom+json",
        }
        resp = self.session.post(url, data=body, headers=headers,
                                 timeout=self.timeout)
        self._raise_for_status(resp, "STOW-RS")
        try:
            return resp.json()
        except Exception:
            return {"status": resp.status_code}

    # ── WADO-RS ────────────────────────────────────────────────────────────────

    def wado_instance(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
    ) -> bytes:
        """
        Retrieve a single DICOM instance as raw bytes (WADO-RS).

        Raises:
            DICOMwebError if the instance is not found or the request fails.
        """
        url = (
            f"{self.base_url}/studies/{study_uid}"
            f"/series/{series_uid}"
            f"/instances/{instance_uid}"
        )
        resp = self.session.get(
            url,
            headers={"Accept": "application/dicom"},
            timeout=self.timeout,
        )
        self._raise_for_status(resp, "WADO-RS")
        # Response may be multipart — return raw bytes, caller can parse
        return resp.content

    def wado_series(self, study_uid: str, series_uid: str) -> bytes:
        """Retrieve all instances of a series as raw multipart bytes."""
        url = f"{self.base_url}/studies/{study_uid}/series/{series_uid}"
        resp = self.session.get(
            url,
            headers={"Accept": "multipart/related; type=application/dicom"},
            timeout=self.timeout,
        )
        self._raise_for_status(resp, "WADO-RS (series)")
        return resp.content

    # ── QIDO-RS ────────────────────────────────────────────────────────────────

    def qido_studies(
        self,
        patient_id: str | None = None,
        patient_name: str | None = None,
        study_date: str | None = None,
        modality: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        Query for DICOM studies (QIDO-RS).

        Returns a list of study result dicts (DICOMweb JSON format).
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if patient_id:
            params["00100020"] = patient_id    # PatientID tag
        if patient_name:
            params["00100010"] = patient_name  # PatientName tag
        if study_date:
            params["00080020"] = study_date    # StudyDate tag
        if modality:
            params["00080060"] = modality      # Modality tag

        resp = self.session.get(
            f"{self.base_url}/studies",
            params=params,
            headers={"Accept": "application/dicom+json"},
            timeout=self.timeout,
        )
        self._raise_for_status(resp, "QIDO-RS (studies)")
        return resp.json() if resp.content else []

    def qido_series(self, study_uid: str) -> list[dict]:
        """Query all series in a study."""
        resp = self.session.get(
            f"{self.base_url}/studies/{study_uid}/series",
            headers={"Accept": "application/dicom+json"},
            timeout=self.timeout,
        )
        self._raise_for_status(resp, "QIDO-RS (series)")
        return resp.json() if resp.content else []

    def qido_instances(self, study_uid: str, series_uid: str) -> list[dict]:
        """Query all instances in a series."""
        resp = self.session.get(
            f"{self.base_url}/studies/{study_uid}/series/{series_uid}/instances",
            headers={"Accept": "application/dicom+json"},
            timeout=self.timeout,
        )
        self._raise_for_status(resp, "QIDO-RS (instances)")
        return resp.json() if resp.content else []

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _raise_for_status(self, resp: requests.Response, operation: str) -> None:
        if not resp.ok:
            raise DICOMwebError(
                f"{operation} failed: HTTP {resp.status_code} — {resp.text[:200]}"
            )
