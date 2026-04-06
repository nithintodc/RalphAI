"""Post-setup verification — stub."""

from __future__ import annotations

from shared.models.campaign import CreatedCampaign


def verify_campaign(_: CreatedCampaign) -> bool:
    return True
