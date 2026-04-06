"""MarketingReco agent — reads DeepDive JSON from disk; writes marketing plan JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config.settings import data_root
from shared.models.report import DeepDiveReport, MarketingPlan

from .approval_handler import apply_command
from .plan_generator import generate_plan


def _deepdive_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "deepdive.json"


def _plan_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "marketing_plan.json"


def run(
    operator_id: str,
    *,
    deepdive_report: dict[str, Any] | None = None,
    operator_profile: dict[str, Any] | None = None,
    budget_cap: float | None = None,
    campaign_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = operator_profile
    _ = campaign_history
    if deepdive_report is None:
        raw = _deepdive_path(operator_id).read_text(encoding="utf-8")
        dd = DeepDiveReport.model_validate_json(raw)
    else:
        dd = DeepDiveReport.model_validate(deepdive_report)
    plan = generate_plan(dd, budget_cap=budget_cap)
    path = _plan_path(operator_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return json.loads(plan.model_dump_json())


def approve(operator_id: str, command: str, notes: str = "") -> dict[str, Any]:
    path = _plan_path(operator_id)
    plan = MarketingPlan.model_validate_json(path.read_text(encoding="utf-8"))
    if command not in ("approve", "reject", "modify"):
        raise ValueError("command must be approve|reject|modify")
    apply_command(plan, command, notes)  # type: ignore[arg-type]
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return json.loads(plan.model_dump_json())


if __name__ == "__main__":
    import sys

    oid = sys.argv[1] if len(sys.argv) > 1 else "dev_operator"
    print(json.dumps(run(oid), indent=2))
