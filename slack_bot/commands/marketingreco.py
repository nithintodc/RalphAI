"""`/marketingreco`"""

from __future__ import annotations


def handle(operator_id: str) -> dict:
    from agents.marketingreco.agent import run

    return run(operator_id)
