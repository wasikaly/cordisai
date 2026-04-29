"""
Orthanc REST API client.

Wraps the Orthanc-specific REST endpoints (not DICOMweb) for:
  - Uploading DICOM files
  - Querying patients / studies / series / instances
  - Downloading instances
  - Deleting studies

For standard DICOMweb (STOW/WADO/QIDO) use integration.pacs.dicomweb_client
with Orthanc's DICOMweb plugin enabled.

Usage:
    from integration.orthanc.client import OrthancClient

    oc = OrthancClient("http://localhost:8042", auth=("admin", "password"))
    instance_id = oc.upload(Path("study.dcm"))
    patients = oc.list_patients()
    data = oc.get_instance_dicom(instance_id)
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class OrthancError(Exception):
    """Raised when an Orthanc REST call fails."""


class OrthancClient:
    """
    Orthanc REST API client (non-DICOMweb endpoints).

    Args:
        base_url:  Orthanc base URL, e.g. "http://localhost:8042"
        auth:      (username, password) or None
        timeout:   Request timeout in seconds
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8042",
        auth: tuple[str, str] | None = ("admin", "password"),
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if auth:
            self.session.auth = auth
        self.timeout = timeout

    # ── System ─────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if Orthanc is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/system", timeout=5)
            return resp.ok
        except requests.RequestException:
            return False

    def system_info(self) -> dict:
        """Return Orthanc system info (version, DICOM AE title, etc.)."""
        return self._get("/system")

    # ── Upload ─────────────────────────────────────────────────────────────────

    def upload(self, dcm_path: Path) -> str:
        """
        Upload a DICOM file to Orthanc.

        Returns:
            The Orthanc instance ID (UUID string) of the uploaded instance.
        """
        data = Path(dcm_path).read_bytes()
        resp = self.session.post(
            f"{self.base_url}/instances",
            data=data,
            headers={"Content-Type": "application/dicom"},
            timeout=self.timeout,
        )
        self._raise_for_status(resp, f"upload {dcm_path.name}")
        return resp.json().get("ID", "")

    def upload_many(self, *dcm_paths: Path) -> list[str]:
        """Upload multiple DICOM files. Returns list of Orthanc instance IDs."""
        return [self.upload(p) for p in dcm_paths]

    # ── Query ──────────────────────────────────────────────────────────────────

    def list_patients(self) -> list[str]:
        """Return list of all patient IDs in Orthanc."""
        return self._get("/patients")

    def list_studies(self) -> list[str]:
        """Return list of all study IDs."""
        return self._get("/studies")

    def get_patient(self, patient_id: str) -> dict:
        """Return patient metadata dict."""
        return self._get(f"/patients/{patient_id}")

    def get_study(self, study_id: str) -> dict:
        """Return study metadata dict."""
        return self._get(f"/studies/{study_id}")

    def get_series(self, series_id: str) -> dict:
        return self._get(f"/series/{series_id}")

    def get_instance(self, instance_id: str) -> dict:
        """Return instance metadata (tags, parent IDs, etc.)."""
        return self._get(f"/instances/{instance_id}")

    def find(
        self,
        level: str = "Study",
        patient_id: str | None = None,
        patient_name: str | None = None,
        study_date: str | None = None,
        modality: str | None = None,
    ) -> list[str]:
        """
        Search Orthanc using /tools/find.

        Args:
            level:  "Patient", "Study", "Series", or "Instance"
            ...rest: DICOM tag filters (wildcards supported, e.g. "DOE*")

        Returns:
            List of matching Orthanc resource IDs.
        """
        query: dict = {}
        if patient_id:
            query["PatientID"] = patient_id
        if patient_name:
            query["PatientName"] = patient_name
        if study_date:
            query["StudyDate"] = study_date
        if modality:
            query["Modality"] = modality

        payload = {"Level": level, "Query": query}
        resp = self.session.post(
            f"{self.base_url}/tools/find",
            json=payload,
            timeout=self.timeout,
        )
        self._raise_for_status(resp, "find")
        return resp.json()

    # ── Download ───────────────────────────────────────────────────────────────

    def get_instance_dicom(self, instance_id: str) -> bytes:
        """Download a DICOM instance as raw bytes."""
        resp = self.session.get(
            f"{self.base_url}/instances/{instance_id}/file",
            timeout=self.timeout,
        )
        self._raise_for_status(resp, f"get instance {instance_id}")
        return resp.content

    def get_study_archive(self, study_id: str) -> bytes:
        """Download all instances in a study as a ZIP archive."""
        resp = self.session.get(
            f"{self.base_url}/studies/{study_id}/archive",
            timeout=self.timeout,
        )
        self._raise_for_status(resp, f"study archive {study_id}")
        return resp.content

    # ── Delete ─────────────────────────────────────────────────────────────────

    def delete_study(self, study_id: str) -> None:
        """Delete a study and all its series/instances from Orthanc."""
        resp = self.session.delete(
            f"{self.base_url}/studies/{study_id}",
            timeout=self.timeout,
        )
        self._raise_for_status(resp, f"delete study {study_id}")

    def delete_instance(self, instance_id: str) -> None:
        resp = self.session.delete(
            f"{self.base_url}/instances/{instance_id}",
            timeout=self.timeout,
        )
        self._raise_for_status(resp, f"delete instance {instance_id}")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get(self, path: str) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        self._raise_for_status(resp, f"GET {path}")
        return resp.json()

    def _raise_for_status(self, resp: requests.Response, op: str) -> None:
        if not resp.ok:
            raise OrthancError(
                f"{op} failed: HTTP {resp.status_code} — {resp.text[:200]}"
            )
