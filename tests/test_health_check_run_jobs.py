"""Health-check job persistence across API reload."""

import json

import shared.health_check_run_jobs as jobs_mod
from shared.health_check_run_jobs import (
    get_health_check_job,
    reconcile_stale_running_jobs,
    set_health_check_job,
)


class TestHealthCheckRunJobs:
    def setup_method(self):
        jobs_mod._mem.clear()
        for path in jobs_mod.JOBS_DIR.glob("*.json"):
            path.unlink()

    def test_persist_and_reload_from_disk(self):
        run_id = "test-run-001"
        set_health_check_job(
            run_id,
            {"run_id": run_id, "status": "running", "started": "2026-01-01T00:00:00Z"},
        )
        jobs_mod._mem.clear()
        job = get_health_check_job(run_id)
        assert job is not None
        assert job["status"] == "running"

    def test_reconcile_marks_stale_running_interrupted(self):
        run_id = "stale-run-002"
        path = jobs_mod._job_path(run_id)
        path.write_text(
            json.dumps({"run_id": run_id, "status": "running", "started": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )
        reconcile_stale_running_jobs()
        job = get_health_check_job(run_id)
        assert job is not None
        assert job["status"] == "interrupted"
        assert "restarted" in str(job.get("error") or "").lower()
