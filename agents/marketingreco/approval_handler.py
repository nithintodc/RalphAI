"""Slack approval workflow — maps /approve /reject /modify to plan status."""

from __future__ import annotations

from typing import Literal

from shared.models.report import MarketingPlan

Command = Literal["approve", "reject", "modify"]


def apply_command(plan: MarketingPlan, command: Command, notes: str = "") -> MarketingPlan:
    if command == "approve":
        plan.approval_status = "approved"
    elif command == "reject":
        plan.approval_status = "rejected"
    else:
        plan.approval_status = "modified"
    plan.approver_notes = notes
    return plan
