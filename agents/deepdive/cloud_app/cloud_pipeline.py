"""Cloud pipeline helpers for GCS uploads and Cloud Run Job execution."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.cloud import storage
from googleapiclient.discovery import build


@dataclass(frozen=True)
class CloudPipelineConfig:
    project_id: str
    region: str
    bucket: str
    job_name: str
    output_prefix: str

    @property
    def enabled(self) -> bool:
        return all(
            [
                self.project_id,
                self.region,
                self.bucket,
                self.job_name,
            ]
        )


def load_cloud_config() -> CloudPipelineConfig:
    """Load cloud pipeline settings from environment variables."""
    return CloudPipelineConfig(
        project_id=os.getenv("GCP_PROJECT_ID", "").strip(),
        region=os.getenv("GCP_REGION", "us-central1").strip(),
        bucket=os.getenv("GCS_UPLOAD_BUCKET", "").strip(),
        job_name=os.getenv("CLOUD_RUN_ANALYSIS_JOB", "").strip(),
        output_prefix=os.getenv("ANALYSIS_OUTPUT_PREFIX", "analysis-results").strip(),
    )


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def upload_bytes_to_gcs(
    payload: bytes,
    bucket_name: str,
    destination: str,
    content_type: str = "text/csv",
) -> str:
    """Upload bytes to GCS and return gs:// URI."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination)
    blob.upload_from_string(payload, content_type=content_type)
    return f"gs://{bucket_name}/{destination}"


def upload_local_file_to_gcs(path: Path, bucket_name: str, destination: str) -> str:
    """Upload an existing local file to GCS and return gs:// URI."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination)
    blob.upload_from_filename(str(path))
    return f"gs://{bucket_name}/{destination}"


def build_upload_object_path(job_id: str, logical_name: str, filename: str) -> str:
    """Build a stable GCS object path for an uploaded source file."""
    safe_name = Path(filename).name.replace(" ", "_")
    return f"uploads/{job_id}/{logical_name}/{safe_name}"


def trigger_cloud_run_job(
    *,
    config: CloudPipelineConfig,
    job_id: str,
    dd_uri: str,
    ue_uri: str,
    marketing_uri: str,
    pre_start: str,
    pre_end: str,
    post_start: str,
    post_end: str,
    operator_name: str,
    excluded_dates: list[str],
) -> dict[str, Any]:
    """Trigger a Cloud Run Job and return execution metadata."""
    if not config.enabled:
        raise ValueError("Cloud pipeline is not configured.")

    run_service = build("run", "v2")
    parent = f"projects/{config.project_id}/locations/{config.region}/jobs/{config.job_name}"
    output_uri = f"gs://{config.bucket}/{config.output_prefix}/{job_id}"

    env_vars = [
        {"name": "JOB_ID", "value": job_id},
        {"name": "DD_INPUT_URI", "value": dd_uri},
        {"name": "UE_INPUT_URI", "value": ue_uri},
        {"name": "MARKETING_INPUT_URI", "value": marketing_uri},
        {"name": "PRE_START_DATE", "value": pre_start},
        {"name": "PRE_END_DATE", "value": pre_end},
        {"name": "POST_START_DATE", "value": post_start},
        {"name": "POST_END_DATE", "value": post_end},
        {"name": "OPERATOR_NAME", "value": operator_name or ""},
        {"name": "EXCLUDED_DATES", "value": ",".join(excluded_dates)},
        {"name": "OUTPUT_URI", "value": output_uri},
    ]

    request_body = {
        "overrides": {
            "containerOverrides": [
                {
                    "env": env_vars,
                }
            ]
        }
    }

    response = run_service.projects().locations().jobs().run(name=parent, body=request_body).execute()
    return {
        "job_id": job_id,
        "operation_name": response.get("name", ""),
        "output_uri": output_uri,
        "submitted_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def get_cloud_run_operation_status(config: CloudPipelineConfig, operation_name: str) -> dict[str, Any]:
    """Check status of a long-running Cloud Run job run operation."""
    if not operation_name:
        return {"done": False}
    run_service = build("run", "v2")
    operation = run_service.projects().locations().operations().get(name=operation_name).execute()
    metadata = operation.get("metadata", {})
    return {
        "name": operation.get("name", ""),
        "done": bool(operation.get("done", False)),
        "error": operation.get("error"),
        "metadata": metadata,
    }


def new_job_id(prefix: str = "analysis") -> str:
    """Generate a compact, traceable job id."""
    return f"{prefix}-{_timestamp_slug()}-{uuid.uuid4().hex[:8]}"


def list_gcs_objects(bucket_name: str, prefix: str = "", suffix: str = "") -> list[str]:
    """List gs:// URIs for objects in a bucket."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uris: list[str] = []
    for blob in client.list_blobs(bucket, prefix=prefix or None):
        if blob.name.endswith("/"):
            continue
        if suffix and not blob.name.endswith(suffix):
            continue
        uris.append(f"gs://{bucket_name}/{blob.name}")
    return sorted(uris)
