"""
AWS HealthLake FHIR R4 client.

Posts HeartAI FHIR bundles to an AWS HealthLake datastore, enabling
downstream analytics, CDS Hooks integration, and EMR interoperability.

Prerequisites:
    pip install boto3
    AWS credentials configured (aws configure, IAM role, or env vars)

Usage:
    from infrastructure.aws.healthlake_client import HealthLakeClient

    client = HealthLakeClient(
        datastore_id="abc123...",
        region="us-east-1",
    )

    # Post a FHIR transaction bundle
    result = client.post_bundle(fhir_bundle_json_str)

    # Convenience: pull bundle from HeartAI pipeline result and post it
    result = client.post_pipeline_result(pipeline_result)

    # Search FHIR resources
    obs = client.search("Observation", params={"subject": "Patient/abc", "code": "10230-1"})
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class HealthLakeError(Exception):
    """Raised when an AWS HealthLake request fails."""


class HealthLakeClient:
    """
    Client for AWS HealthLake FHIR R4 datastore.

    Uses boto3's healthlake client for management operations and
    requests with SigV4 signing for FHIR REST API calls.

    Args:
        datastore_id:  HealthLake datastore ID (40-char hex string)
        region:        AWS region, e.g. "us-east-1"
        endpoint_url:  Override for local testing (e.g. LocalStack)
    """

    FHIR_ENDPOINT_TEMPLATE = (
        "https://healthlake.{region}.amazonaws.com"
        "/datastore/{datastore_id}/r4"
    )

    def __init__(
        self,
        datastore_id: str,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
    ):
        self.datastore_id = datastore_id
        self.region = region
        self.fhir_base = (
            endpoint_url or
            self.FHIR_ENDPOINT_TEMPLATE.format(
                region=region, datastore_id=datastore_id
            )
        ).rstrip("/")
        self._session = None   # lazy-init to avoid boto3 import at module load

    # ── FHIR REST operations ───────────────────────────────────────────────────

    def post_bundle(self, fhir_json: str | dict) -> dict:
        """
        POST a FHIR transaction Bundle to HealthLake.

        Args:
            fhir_json:  JSON string or dict representing a FHIR R4 Bundle.

        Returns:
            Parsed JSON response dict from HealthLake.

        Raises:
            HealthLakeError on HTTP errors.
        """
        if isinstance(fhir_json, dict):
            body = json.dumps(fhir_json)
        else:
            body = fhir_json

        resp = self._request("POST", "/", body,
                             content_type="application/fhir+json")
        return resp

    def post_pipeline_result(self, pipeline_result: dict) -> dict | None:
        """
        Extract FHIR bundle from a pipeline result dict and post it.

        Args:
            pipeline_result: Return value of pipeline.run_pipeline()

        Returns:
            HealthLake response dict, or None if no FHIR bundle present.
        """
        fhir_bundle = pipeline_result.get("fhir_bundle")
        if fhir_bundle is None:
            return None
        fhir_json = fhir_bundle.model_dump_json()
        return self.post_bundle(fhir_json)

    def get_resource(self, resource_type: str, resource_id: str) -> dict:
        """Read a single FHIR resource by type + ID."""
        return self._request("GET", f"/{resource_type}/{resource_id}")

    def search(
        self,
        resource_type: str,
        params: dict[str, str] | None = None,
    ) -> dict:
        """
        Search FHIR resources.

        Args:
            resource_type:  e.g. "Observation", "Patient", "DiagnosticReport"
            params:         FHIR search parameters, e.g. {"code": "10230-1"}

        Returns:
            FHIR Bundle (searchset) response dict.
        """
        import urllib.parse
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(params)
        return self._request("GET", f"/{resource_type}{query}")

    def delete_resource(self, resource_type: str, resource_id: str) -> None:
        """Delete a FHIR resource."""
        self._request("DELETE", f"/{resource_type}/{resource_id}")

    # ── Datastore management (boto3) ──────────────────────────────────────────

    def describe_datastore(self) -> dict:
        """Return HealthLake datastore description via boto3."""
        client = self._boto3_client()
        resp = client.describe_fhir_datastore(DatastoreId=self.datastore_id)
        return resp.get("DatastoreProperties", {})

    def datastore_status(self) -> str:
        """Return datastore status string (ACTIVE, CREATING, DELETED, etc.)."""
        return self.describe_datastore().get("DatastoreStatus", "UNKNOWN")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: str | None = None,
        content_type: str = "application/fhir+json",
    ) -> dict:
        """Sign and execute a FHIR REST request using SigV4."""
        import boto3
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        import requests as req_lib

        session = boto3.Session()
        credentials = session.get_credentials().get_frozen_credentials()
        url = self.fhir_base + path

        aws_request = AWSRequest(
            method=method,
            url=url,
            data=body.encode() if body else b"",
            headers={"Content-Type": content_type},
        )
        SigV4Auth(credentials, "healthlake", self.region).add_auth(aws_request)

        http_resp = req_lib.request(
            method=method,
            url=url,
            data=body.encode() if body else None,
            headers=dict(aws_request.headers),
            timeout=60,
        )
        if not http_resp.ok:
            raise HealthLakeError(
                f"HealthLake {method} {path} failed: "
                f"HTTP {http_resp.status_code} — {http_resp.text[:300]}"
            )
        if http_resp.content:
            try:
                return http_resp.json()
            except Exception:
                return {"raw": http_resp.text}
        return {}

    def _boto3_client(self):
        import boto3
        return boto3.client("healthlake", region_name=self.region)
