"""`/offers`"""

from __future__ import annotations


def handle(operator_id: str, *, doordash_email: str = "", doordash_password: str = "") -> dict:
    from agents.offers.agent import run

    return run(
        operator_id,
        doordash_email=doordash_email,
        doordash_password=doordash_password,
    )
