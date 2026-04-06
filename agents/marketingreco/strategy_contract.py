"""Maps insights to campaign_plan items — legacy contract pipeline."""

from __future__ import annotations


def build_campaign_plan(operator_id: str, insights: list[str]) -> list[dict]:
    _ = operator_id
    plan: list[dict] = []
    text = " ".join(insights).lower()
    if "weekend" in text or "traffic" in text:
        plan.append(
            {
                "type": "ads",
                "budget": 100,
                "target": "weekend traffic",
            }
        )
    if "aov" in text or "order" in text:
        plan.append(
            {
                "type": "offers",
                "discount": "20%",
                "condition": "above $30",
            }
        )
    if not plan:
        plan.append({"type": "ads", "budget": 50, "target": "lunch daypart"})
    return plan
