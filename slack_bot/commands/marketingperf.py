"""`/marketingperf`"""

from __future__ import annotations


def handle(operator_id: str) -> dict:
    from agents.campaign_review.agent import run

    return run(operator_id)
