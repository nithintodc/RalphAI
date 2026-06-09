"""Builds review actions from campaign_performance blob (legacy contract)."""

from __future__ import annotations

from typing import Any

from .contract_rules import default_action_for_metrics


def evaluate(operator_id: str, campaign_performance: dict[str, Any]) -> list[dict[str, Any]]:
    _ = operator_id
    actions: list[dict[str, Any]] = []
    campaigns = campaign_performance.get("campaigns")
    if isinstance(campaigns, list):
        for c in campaigns:
            cid = c.get("campaign_id") or c.get("id")
            m = c.get("metrics") or {}
            act = default_action_for_metrics(m)
            actions.append({"campaign_id": str(cid) if cid is not None else None, "action": act})
    if not actions:
        actions.append({"campaign_id": None, "action": "new", "reason": "no_prior_campaigns"})
    return actions
