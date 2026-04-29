"""
Unit tests for infrastructure/aws/healthlake_client.py
All AWS/boto3 calls are mocked — no real AWS credentials needed.
Run with: python -m pytest tests/unit/test_healthlake_client.py -v
"""
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from infrastructure.aws.healthlake_client import HealthLakeClient, HealthLakeError


# ── Fixture data ──────────────────────────────────────────────────────────────

def _bundle_json():
    return json.dumps({
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "resource": {"resourceType": "Patient", "id": "p1"},
                "request": {"method": "POST", "url": "Patient"},
            }
        ],
    })


def _mock_ok_response(json_data=None, status=200):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = status
    data = json_data or {}
    resp.content = json.dumps(data).encode()
    resp.json.return_value = data
    resp.text = json.dumps(data)
    return resp


def _mock_err_response(status=400, text="Bad Request"):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status
    resp.text = text
    resp.content = text.encode()
    return resp


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHealthLakeClient:
    def setup_method(self):
        self.client = HealthLakeClient(
            datastore_id="abc123def456",
            region="us-east-1",
        )

    def _patch_request(self, response):
        """Patch the internal _request call via boto3/requests mock chain."""
        return patch.object(self.client, "_request", return_value=response)

    def test_fhir_base_url_correct(self):
        assert "healthlake.us-east-1.amazonaws.com" in self.client.fhir_base
        assert "abc123def456" in self.client.fhir_base
        assert "/r4" in self.client.fhir_base

    def test_custom_endpoint_overrides_base(self):
        c = HealthLakeClient("abc", endpoint_url="http://localhost:8080/r4")
        assert c.fhir_base == "http://localhost:8080/r4"

    def test_post_bundle_str(self):
        with self._patch_request({"resourceType": "Bundle"}) as mock_req:
            result = self.client.post_bundle(_bundle_json())
        mock_req.assert_called_once()
        args = mock_req.call_args[0]
        assert args[0] == "POST"
        assert args[1] == "/"

    def test_post_bundle_dict(self):
        bundle = json.loads(_bundle_json())
        with self._patch_request({"resourceType": "Bundle"}) as mock_req:
            self.client.post_bundle(bundle)
        body_arg = mock_req.call_args[0][2]
        assert isinstance(body_arg, str)  # dict was serialised

    def test_post_pipeline_result_with_bundle(self):
        mock_bundle = MagicMock()
        mock_bundle.model_dump_json.return_value = _bundle_json()
        pipeline_result = {"fhir_bundle": mock_bundle, "mode": "segmentation"}
        with self._patch_request({"resourceType": "Bundle"}) as mock_req:
            result = self.client.post_pipeline_result(pipeline_result)
        assert result == {"resourceType": "Bundle"}

    def test_post_pipeline_result_no_bundle_returns_none(self):
        pipeline_result = {"fhir_bundle": None, "mode": "segmentation"}
        result = self.client.post_pipeline_result(pipeline_result)
        assert result is None

    def test_get_resource_calls_get(self):
        expected = {"resourceType": "Patient", "id": "p1"}
        with self._patch_request(expected) as mock_req:
            result = self.client.get_resource("Patient", "p1")
        args = mock_req.call_args[0]
        assert args[0] == "GET"
        assert "/Patient/p1" in args[1]

    def test_search_appends_params(self):
        with self._patch_request({"resourceType": "Bundle", "entry": []}) as mock_req:
            self.client.search("Observation", params={"code": "10230-1"})
        path = mock_req.call_args[0][1]
        assert "Observation" in path
        assert "10230-1" in path

    def test_search_no_params(self):
        with self._patch_request({"resourceType": "Bundle"}) as mock_req:
            self.client.search("Patient")
        path = mock_req.call_args[0][1]
        assert path == "/Patient"

    def test_delete_resource(self):
        with self._patch_request({}) as mock_req:
            self.client.delete_resource("Observation", "obs-1")
        args = mock_req.call_args[0]
        assert args[0] == "DELETE"
        assert "/Observation/obs-1" in args[1]

    def test_request_raises_on_http_error(self):
        """_request should raise HealthLakeError on non-ok responses."""
        with patch("boto3.Session") as mock_session, \
             patch("requests.request", return_value=_mock_err_response(400)):
            # Setup mock credentials chain
            mock_creds = MagicMock()
            mock_creds.get_frozen_credentials.return_value = MagicMock(
                access_key="AKIA_TEST",
                secret_key="secret",
                token=None,
            )
            mock_session.return_value.get_credentials.return_value = mock_creds
            with patch("botocore.auth.SigV4Auth.add_auth"):
                with pytest.raises(HealthLakeError, match="failed"):
                    self.client._request("POST", "/", "{}")

    def test_describe_datastore_calls_boto3(self):
        mock_boto_client = MagicMock()
        mock_boto_client.describe_fhir_datastore.return_value = {
            "DatastoreProperties": {"DatastoreStatus": "ACTIVE", "DatastoreId": "abc123def456"}
        }
        with patch.object(self.client, "_boto3_client", return_value=mock_boto_client):
            info = self.client.describe_datastore()
        assert info["DatastoreStatus"] == "ACTIVE"

    def test_datastore_status_active(self):
        with patch.object(self.client, "describe_datastore",
                          return_value={"DatastoreStatus": "ACTIVE"}):
            assert self.client.datastore_status() == "ACTIVE"
