"""`/deepdive` — delegates to agents.deepdive.agent.run with SSM data"""

from __future__ import annotations


def handle(text: str, operator_id: str) -> dict:
    """Run deep-dive analysis. Text can optionally specify a data directory path."""
    from agents.deepdive.agent import run

    data_dir = text.strip() if text.strip() else None
    return run(operator_id=operator_id, data_dir=data_dir)
