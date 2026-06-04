"""Headless Cloud Run Job worker for large-file analysis."""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from google.cloud import storage

from export_functions import (
    build_financial_summary_table,
    create_bucketing_export,
    create_date_export_from_master_files,
)


@dataclass(frozen=True)
class JobEnv:
    job_id: str
    dd_input_uri: str
    ue_input_uri: str
    marketing_input_uri: str
    pre_start_date: str
    pre_end_date: str
    post_start_date: str
    post_end_date: str
    operator_name: str
    excluded_dates: list[str]
    output_uri: str


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {uri}")
    without_prefix = uri[5:]
    if "/" not in without_prefix:
        return without_prefix, ""
    bucket, blob = without_prefix.split("/", 1)
    return bucket, blob


def _download_blob(client: storage.Client, uri: str, destination: Path) -> Path:
    bucket_name, blob_name = _parse_gs_uri(uri)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(destination))
    return destination


def _download_prefix(client: storage.Client, uri_prefix: str, destination_dir: Path) -> list[Path]:
    bucket_name, prefix = _parse_gs_uri(uri_prefix)
    bucket = client.bucket(bucket_name)
    destination_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for blob in client.list_blobs(bucket, prefix=prefix):
        if blob.name.endswith("/"):
            continue
        relative = blob.name[len(prefix):].lstrip("/")
        if not relative:
            relative = Path(blob.name).name
        target = destination_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target))
        downloaded.append(target)
    return downloaded


def _upload_bytes(client: storage.Client, destination_uri: str, payload: bytes, content_type: str) -> str:
    bucket_name, blob_name = _parse_gs_uri(destination_uri)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(payload, content_type=content_type)
    return destination_uri


def _upload_json(client: storage.Client, destination_uri: str, payload: dict) -> str:
    blob_payload = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    return _upload_bytes(client, destination_uri, blob_payload, "application/json")


def _read_env() -> JobEnv:
    excluded_raw = os.getenv("EXCLUDED_DATES", "").strip()
    excluded_dates = [item.strip() for item in excluded_raw.split(",") if item.strip()]
    return JobEnv(
        job_id=os.getenv("JOB_ID", "analysis-job"),
        dd_input_uri=os.getenv("DD_INPUT_URI", "").strip(),
        ue_input_uri=os.getenv("UE_INPUT_URI", "").strip(),
        marketing_input_uri=os.getenv("MARKETING_INPUT_URI", "").strip(),
        pre_start_date=os.getenv("PRE_START_DATE", "").strip(),
        pre_end_date=os.getenv("PRE_END_DATE", "").strip(),
        post_start_date=os.getenv("POST_START_DATE", "").strip(),
        post_end_date=os.getenv("POST_END_DATE", "").strip(),
        operator_name=os.getenv("OPERATOR_NAME", "").strip(),
        excluded_dates=excluded_dates,
        output_uri=os.getenv("OUTPUT_URI", "").strip(),
    )


def _validate_env(env: JobEnv) -> None:
    required = {
        "DD_INPUT_URI": env.dd_input_uri,
        "UE_INPUT_URI": env.ue_input_uri,
        "PRE_START_DATE": env.pre_start_date,
        "PRE_END_DATE": env.pre_end_date,
        "POST_START_DATE": env.post_start_date,
        "POST_END_DATE": env.post_end_date,
        "OUTPUT_URI": env.output_uri,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing required job environment values: {', '.join(missing)}")


def _normalize_output_prefix(output_uri: str) -> str:
    return output_uri.rstrip("/")


def main() -> int:
    env = _read_env()
    _validate_env(env)
    client = storage.Client()

    started_at = datetime.now(timezone.utc).isoformat()
    output_prefix = _normalize_output_prefix(env.output_uri)

    with TemporaryDirectory(prefix="todc-job-") as temp_dir:
        temp_root = Path(temp_dir)
        dd_local = temp_root / "inputs" / "dd-data.csv"
        ue_local = temp_root / "inputs" / "ue-data.csv"
        marketing_local = temp_root / "inputs" / "marketing_data"

        artifacts: list[dict[str, str]] = []
        try:
            _download_blob(client, env.dd_input_uri, dd_local)
            _download_blob(client, env.ue_input_uri, ue_local)
            if env.marketing_input_uri:
                _download_prefix(client, env.marketing_input_uri, marketing_local)

            date_bytes, date_filename = create_date_export_from_master_files(
                dd_data_path=dd_local,
                ue_data_path=ue_local,
                pre_start_date=env.pre_start_date,
                pre_end_date=env.pre_end_date,
                post_start_date=env.post_start_date,
                post_end_date=env.post_end_date,
                excluded_dates=env.excluded_dates,
                operator_name=env.operator_name or None,
            )
            if date_bytes and date_filename:
                date_uri = f"{output_prefix}/{date_filename}"
                _upload_bytes(
                    client,
                    date_uri,
                    date_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                artifacts.append({"name": "date_export", "uri": date_uri})

            bucket_bytes, bucket_filename = create_bucketing_export(
                dd_data_path=dd_local,
                operator_name=env.operator_name or None,
                pre_start_date=env.pre_start_date,
                pre_end_date=env.pre_end_date,
                post_start_date=env.post_start_date,
                post_end_date=env.post_end_date,
                excluded_dates=env.excluded_dates,
            )
            if bucket_bytes and bucket_filename:
                bucket_uri = f"{output_prefix}/{bucket_filename}"
                _upload_bytes(
                    client,
                    bucket_uri,
                    bucket_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                artifacts.append({"name": "bucketing_export", "uri": bucket_uri})

            financial_df = build_financial_summary_table(
                dd_data_path=dd_local,
                ue_data_path=ue_local,
                pre_start=env.pre_start_date,
                pre_end=env.pre_end_date,
                post_start=env.post_start_date,
                post_end=env.post_end_date,
                excluded_dates=env.excluded_dates,
            )
            if financial_df is not None and not financial_df.empty:
                summary_csv = financial_df.to_csv(index=False).encode("utf-8")
                summary_uri = f"{output_prefix}/financial_summary.csv"
                _upload_bytes(client, summary_uri, summary_csv, "text/csv")
                artifacts.append({"name": "financial_summary_csv", "uri": summary_uri})

            completed_at = datetime.now(timezone.utc).isoformat()
            status_payload = {
                "job_id": env.job_id,
                "status": "succeeded",
                "started_at_utc": started_at,
                "completed_at_utc": completed_at,
                "artifacts": artifacts,
                "inputs": {
                    "dd_input_uri": env.dd_input_uri,
                    "ue_input_uri": env.ue_input_uri,
                    "marketing_input_uri": env.marketing_input_uri,
                },
                "filters": {
                    "pre_start_date": env.pre_start_date,
                    "pre_end_date": env.pre_end_date,
                    "post_start_date": env.post_start_date,
                    "post_end_date": env.post_end_date,
                    "excluded_dates": env.excluded_dates,
                },
            }
            _upload_json(client, f"{output_prefix}/status.json", status_payload)
            return 0
        except Exception as exc:
            failed_at = datetime.now(timezone.utc).isoformat()
            error_payload = {
                "job_id": env.job_id,
                "status": "failed",
                "started_at_utc": started_at,
                "failed_at_utc": failed_at,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }
            _upload_json(client, f"{output_prefix}/status.json", error_payload)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
