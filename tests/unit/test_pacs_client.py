"""
Unit tests for integration/pacs/dicomweb_client.py and integration/orthanc/client.py
Uses unittest.mock to avoid requiring a real PACS server.
Run with: python -m pytest tests/unit/test_pacs_client.py -v
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from integration.pacs.dicomweb_client import DICOMwebClient, DICOMwebError
from integration.orthanc.client import OrthancClient, OrthancError


# ── DICOMwebClient ─────────────────────────────────────────────────────────────

class TestDICOMwebClient:
    def setup_method(self):
        self.client = DICOMwebClient("http://pacs:8080/dicom-web",
                                     auth=("user", "pass"))

    def _mock_ok(self, json_data=None, status=200):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = status
        resp.content = json.dumps(json_data or {}).encode()
        resp.json.return_value = json_data or {}
        return resp

    def _mock_err(self, status=404, text="Not found"):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = status
        resp.text = text
        return resp

    def test_stow_posts_to_studies(self, tmp_path):
        dcm = tmp_path / "test.dcm"
        dcm.write_bytes(b"DICM" + b"\x00" * 128)
        with patch.object(self.client.session, "post",
                          return_value=self._mock_ok({"00081190": "uid"})) as mock_post:
            result = self.client.stow(dcm)
        assert mock_post.called
        url = mock_post.call_args[0][0]
        assert "/studies" in url

    def test_stow_no_files_raises(self):
        with pytest.raises(ValueError):
            self.client.stow()

    def test_stow_http_error_raises(self, tmp_path):
        dcm = tmp_path / "test.dcm"
        dcm.write_bytes(b"DICM")
        with patch.object(self.client.session, "post",
                          return_value=self._mock_err(500, "Server error")):
            with pytest.raises(DICOMwebError, match="STOW-RS failed"):
                self.client.stow(dcm)

    def test_wado_instance_returns_bytes(self):
        with patch.object(self.client.session, "get",
                          return_value=self._mock_ok()) as mock_get:
            mock_get.return_value.content = b"DICM_DATA"
            data = self.client.wado_instance("study1", "series1", "inst1")
        assert data == b"DICM_DATA"

    def test_wado_instance_error_raises(self):
        with patch.object(self.client.session, "get",
                          return_value=self._mock_err(404)):
            with pytest.raises(DICOMwebError, match="WADO-RS failed"):
                self.client.wado_instance("s", "r", "i")

    def test_qido_studies_returns_list(self):
        studies = [{"00200010": {"Value": ["S001"]}}]
        with patch.object(self.client.session, "get",
                          return_value=self._mock_ok(studies)):
            result = self.client.qido_studies(patient_id="P001")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_qido_empty_response_returns_empty_list(self):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        resp.content = b""
        resp.json.return_value = []
        with patch.object(self.client.session, "get", return_value=resp):
            result = self.client.qido_studies()
        assert result == []

    def test_qido_passes_patient_id_param(self):
        with patch.object(self.client.session, "get",
                          return_value=self._mock_ok([])) as mock_get:
            self.client.qido_studies(patient_id="P999")
        params = mock_get.call_args[1]["params"]
        assert params["00100020"] == "P999"

    def test_qido_series_hits_correct_url(self):
        with patch.object(self.client.session, "get",
                          return_value=self._mock_ok([])) as mock_get:
            self.client.qido_series("study-uid-123")
        url = mock_get.call_args[0][0]
        assert "study-uid-123/series" in url


# ── OrthancClient ──────────────────────────────────────────────────────────────

class TestOrthancClient:
    def setup_method(self):
        self.client = OrthancClient("http://orthanc:8042",
                                    auth=("admin", "password"))

    def _mock_ok(self, json_data=None, status=200):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = status
        resp.content = json.dumps(json_data or {}).encode()
        resp.json.return_value = json_data or {}
        return resp

    def _mock_err(self, status=500, text="error"):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = status
        resp.text = text
        return resp

    def test_ping_true_when_ok(self):
        with patch.object(self.client.session, "get",
                          return_value=self._mock_ok({"Version": "1.12.0"})):
            assert self.client.ping() is True

    def test_ping_false_on_connection_error(self):
        import requests
        with patch.object(self.client.session, "get",
                          side_effect=requests.RequestException("conn refused")):
            assert self.client.ping() is False

    def test_upload_returns_instance_id(self, tmp_path):
        dcm = tmp_path / "test.dcm"
        dcm.write_bytes(b"DICM")
        with patch.object(self.client.session, "post",
                          return_value=self._mock_ok({"ID": "abc-123", "Status": "Success"})):
            result = self.client.upload(dcm)
        assert result == "abc-123"

    def test_upload_error_raises(self, tmp_path):
        dcm = tmp_path / "test.dcm"
        dcm.write_bytes(b"DICM")
        with patch.object(self.client.session, "post",
                          return_value=self._mock_err(400)):
            with pytest.raises(OrthancError):
                self.client.upload(dcm)

    def test_list_patients_returns_list(self):
        with patch.object(self.client.session, "get",
                          return_value=self._mock_ok(["p1", "p2"])):
            result = self.client.list_patients()
        assert result == ["p1", "p2"]

    def test_find_posts_to_tools_find(self):
        with patch.object(self.client.session, "post",
                          return_value=self._mock_ok(["id1"])) as mock_post:
            result = self.client.find(level="Study", patient_id="P999")
        url = mock_post.call_args[0][0]
        assert "/tools/find" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["Level"] == "Study"
        assert payload["Query"]["PatientID"] == "P999"

    def test_get_instance_dicom_returns_bytes(self):
        resp = MagicMock()
        resp.ok = True
        resp.content = b"DICM_DATA"
        with patch.object(self.client.session, "get", return_value=resp):
            data = self.client.get_instance_dicom("inst-123")
        assert data == b"DICM_DATA"

    def test_delete_study_calls_delete(self):
        resp = MagicMock()
        resp.ok = True
        resp.status_code = 200
        with patch.object(self.client.session, "delete",
                          return_value=resp) as mock_del:
            self.client.delete_study("study-999")
        url = mock_del.call_args[0][0]
        assert "studies/study-999" in url
