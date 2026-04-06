"""`/ads`"""

from __future__ import annotations


def handle(operator_id: str) -> dict:
    from agents.campaign_setup.agent import run

    return run(operator_id, campaign_type="ads")
