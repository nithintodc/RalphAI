"""Async browser-agent runs: logging, queue workers, job persistence."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from shared.agent_run_logging import agent_run_logging, tail_run_log, write_run_meta
from shared.browser_agent_jobs import (
    enqueue_browser_job,
    get_browser_agent_job,
    set_browser_agent_job,
)

ROOT = Path(__file__).resolve().parents[1]
OFFERS_RUNS_BASE = ROOT / "data" / "runs" / "offers"
ADS_RUNS_BASE = ROOT / "data" / "runs" / "ads"
STRATEGIST_RUNS_BASE = ROOT / "data" / "runs" / "strategist"

for _base in (OFFERS_RUNS_BASE, ADS_RUNS_BASE, STRATEGIST_RUNS_BASE):
    _base.mkdir(parents=True, exist_ok=True)


def agent_run_dir(agent: str, run_id: str) -> Path:
    mapping = {
        "offers": OFFERS_RUNS_BASE,
        "ads": ADS_RUNS_BASE,
        "strategist": STRATEGIST_RUNS_BASE,
    }
    base = mapping.get(agent)
    if base is None:
        raise ValueError(f"Unknown browser agent: {agent}")
    return base / run_id


def _finish_job(
    *,
    run_id: str,
    agent: str,
    run_dir: Path,
    t0: datetime,
    status: str,
    result: dict[str, Any] | None,
    error: str | None,
    operator_label: str,
    append_index: Callable[[dict], None],
    extra_meta: dict[str, Any] | None = None,
) -> None:
    duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
    if result is not None:
        (run_dir / "result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    meta = {
        "run_id": run_id,
        "agent": agent,
        "status": status,
        "started": t0.isoformat(),
        "operator": operator_label,
        "error": error,
        **(extra_meta or {}),
    }
    write_run_meta(run_dir, meta)
    set_browser_agent_job(
        run_id,
        {
            "run_id": run_id,
            "agent": agent,
            "status": status,
            "started": t0.isoformat(),
            "result": result,
            "error": error,
            "log_path": str(run_dir / "run.log"),
        },
    )
    append_index(
        {
            "id": run_id,
            "agent": agent,
            "operator": operator_label,
            "status": status,
            "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
            "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
        }
    )


def start_queued_browser_job(
    *,
    run_id: str,
    agent: str,
    operator_label: str,
    work: Callable[[], None],
    mode: str | None = None,
) -> int:
    run_dir = agent_run_dir(agent, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = datetime.now(timezone.utc)
    queue_position = enqueue_browser_job(
        run_id=run_id,
        agent=agent,
        label=operator_label,
        work=work,
    )
    set_browser_agent_job(
        run_id,
        {
            "run_id": run_id,
            "agent": agent,
            "status": "queued",
            "started": t0.isoformat(),
            "result": None,
            "error": None,
            "queue_position": queue_position,
            "mode": mode,
            "log_path": str(run_dir / "run.log"),
        },
    )
    write_run_meta(
        run_dir,
        {
            "run_id": run_id,
            "agent": agent,
            "status": "queued",
            "started": t0.isoformat(),
            "operator": operator_label,
            "queue_position": queue_position,
            "mode": mode,
        },
    )
    return queue_position


def run_offers_worker(
    *,
    run_id: str,
    t0: datetime,
    operator_id: str,
    operator_label: str,
    doordash_email: str,
    doordash_password: str,
    offers_sheet_path: str | None,
    mode: str,
    append_index: Callable[[dict], None],
) -> None:
    from agents.offers.agent import run as run_offers_agent

    run_dir = agent_run_dir("offers", run_id)
    downloads_dir = run_dir / "downloads"
    try:
        with agent_run_logging(run_dir, run_id=run_id, agent="offers"):
            result = run_offers_agent(
                operator_id,
                doordash_email=doordash_email,
                doordash_password=doordash_password,
                offers_sheet_path=offers_sheet_path,
                api_run_dir=downloads_dir,
            )
        status = str(result.get("status") or "success")
        _finish_job(
            run_id=run_id,
            agent="offers",
            run_dir=run_dir,
            t0=t0,
            status=status,
            result={**result, "run_id": run_id, "mode": mode},
            error=None,
            operator_label=operator_label,
            append_index=append_index,
            extra_meta={"mode": mode},
        )
    except Exception as exc:
        _finish_job(
            run_id=run_id,
            agent="offers",
            run_dir=run_dir,
            t0=t0,
            status="error",
            result=None,
            error=str(exc),
            operator_label=operator_label,
            append_index=append_index,
            extra_meta={"mode": mode},
        )


def run_ads_worker(
    *,
    run_id: str,
    t0: datetime,
    operator_id: str,
    operator_label: str,
    doordash_email: str,
    doordash_password: str,
    ads_sheet_path: str | None,
    mode: str,
    append_index: Callable[[dict], None],
) -> None:
    from agents.ads.agent import run as run_ads_agent

    run_dir = agent_run_dir("ads", run_id)
    downloads_dir = run_dir / "downloads"
    try:
        with agent_run_logging(run_dir, run_id=run_id, agent="ads"):
            result = run_ads_agent(
                operator_id,
                doordash_email=doordash_email,
                doordash_password=doordash_password,
                ads_sheet_path=ads_sheet_path,
                api_run_dir=downloads_dir,
            )
        status = str(result.get("status") or "success")
        _finish_job(
            run_id=run_id,
            agent="ads",
            run_dir=run_dir,
            t0=t0,
            status=status,
            result={**result, "run_id": run_id, "mode": mode},
            error=None,
            operator_label=operator_label,
            append_index=append_index,
            extra_meta={"mode": mode},
        )
    except Exception as exc:
        _finish_job(
            run_id=run_id,
            agent="ads",
            run_dir=run_dir,
            t0=t0,
            status="error",
            result=None,
            error=str(exc),
            operator_label=operator_label,
            append_index=append_index,
            extra_meta={"mode": mode},
        )


def run_strategist_auto_worker(
    *,
    run_id: str,
    t0: datetime,
    operator_ids: list[str],
    operator_label: str,
    append_index: Callable[[dict], None],
) -> None:
    from agents.strategist.agent import run as run_strategist

    run_dir = agent_run_dir("strategist", run_id)
    try:
        with agent_run_logging(run_dir, run_id=run_id, agent="strategist"):
            result = run_strategist(mode="auto", operator_ids=operator_ids)
        payload = {
            "status": "success",
            "run_id": run_id,
            "mode": "auto",
            "selected_operator_count": len(operator_ids),
            **result,
        }
        _finish_job(
            run_id=run_id,
            agent="strategist",
            run_dir=run_dir,
            t0=t0,
            status="success",
            result=payload,
            error=None,
            operator_label=operator_label,
            append_index=append_index,
            extra_meta={"mode": "auto"},
        )
    except Exception as exc:
        _finish_job(
            run_id=run_id,
            agent="strategist",
            run_dir=run_dir,
            t0=t0,
            status="error",
            result=None,
            error=str(exc),
            operator_label=operator_label,
            append_index=append_index,
            extra_meta={"mode": "auto"},
        )


def run_strategist_manual_worker(
    *,
    run_id: str,
    t0: datetime,
    operator_id: str,
    business_name: str,
    financial_path: Path | None = None,
    marketing_path: Path | None = None,
    register_path: Path | None = None,
    append_index: Callable[[dict], None],
    ralph_ads_upload_rows: Callable[[dict], list],
) -> None:
    from agents.strategist.agent import run as run_strategist

    run_dir = agent_run_dir("strategist", run_id)
    uploads_parent: Path | None = None
    if financial_path and financial_path.parent.is_dir():
        uploads_parent = financial_path.parent
    elif register_path and register_path.parent.is_dir():
        uploads_parent = register_path.parent
    try:
        with agent_run_logging(run_dir, run_id=run_id, agent="strategist"):
            if financial_path and financial_path.is_file():
                result = run_strategist(
                    mode="manual",
                    operator_id=operator_id,
                    financial_zip_path=str(financial_path),
                    marketing_zip_path=str(marketing_path) if marketing_path and marketing_path.is_file() else None,
                    business_name=business_name,
                )
            elif register_path and register_path.is_file():
                result = run_strategist(
                    mode="manual",
                    operator_id=operator_id,
                    register_report_path=str(register_path),
                    business_name=business_name,
                )
            else:
                raise ValueError("Manual Strategist requires financial_path or register_path")
        first = (result.get("results") or [{}])[0]
        ads_plan_payload = first.get("ads_plan") or {}
        downloads: dict[str, str] = {}
        campaigns_src = Path(first.get("combined_analysis") or first.get("campaigns_xlsx") or "")
        if campaigns_src.is_file():
            dest_name = campaigns_src.name if campaigns_src.name.startswith("combined_analysis_") else "combined_analysis.xlsx"
            shutil.copy2(campaigns_src, run_dir / dest_name)
            downloads["campaigns_excel"] = f"/api/runs/strategist/{run_id}/download/campaigns"
        slot_src = Path(first.get("slot_info_csv") or "")
        if slot_src.is_file():
            shutil.copy2(slot_src, run_dir / "slot_info.csv")
            downloads["slot_info_csv"] = f"/api/runs/strategist/{run_id}/download/slot-info"

        payload: dict[str, Any] = {
            "status": "success",
            "run_id": run_id,
            "mode": "manual",
            "selected_operator_count": 1,
            **result,
        }
        if downloads:
            payload["downloads"] = downloads
        payload["ads_upload_rows"] = ralph_ads_upload_rows(ads_plan_payload)
        payload.update({k: v for k, v in first.items() if k not in payload})

        _finish_job(
            run_id=run_id,
            agent="strategist",
            run_dir=run_dir,
            t0=t0,
            status="success",
            result=payload,
            error=None,
            operator_label=business_name,
            append_index=append_index,
            extra_meta={"mode": "manual"},
        )
    except Exception as exc:
        _finish_job(
            run_id=run_id,
            agent="strategist",
            run_dir=run_dir,
            t0=t0,
            status="error",
            result=None,
            error=str(exc),
            operator_label=business_name,
            append_index=append_index,
            extra_meta={"mode": "manual"},
        )
    finally:
        if uploads_parent is not None:
            shutil.rmtree(uploads_parent, ignore_errors=True)


def get_agent_job_payload(run_id: str) -> dict[str, Any] | None:
    return get_browser_agent_job(run_id)


def tail_agent_logs(agent: str, run_id: str, *, after_line: int = 0) -> dict[str, Any]:
    run_dir = agent_run_dir(agent, run_id)
    lines, total = tail_run_log(run_dir / "run.log", after_line=after_line)
    job = get_browser_agent_job(run_id) or {}
    return {
        "run_id": run_id,
        "agent": agent,
        "lines": lines,
        "line_count": total,
        "status": job.get("status"),
        "queue_position": job.get("queue_position"),
    }
