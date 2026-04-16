"""`/marketingperf`"""

from __future__ import annotations


def handle(operator_id: str, text: str = "") -> dict:
    from agents.campaign_review.agent import run

    raw = (text or "").strip()
    if not raw:
        return run(operator_id, mode="auto")
    # Usage:
    # /marketingperf manual /path/to/MARKETING_PROMOTION.csv /path/to/MARKETING_SPONSORED_LISTING.csv
    parts = raw.split()
    if parts[0].lower() == "manual":
        return run(operator_id, mode="manual", data_files=parts[1:])
    return run(operator_id, mode="auto", data_dir=raw)
