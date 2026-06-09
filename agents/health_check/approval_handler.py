"""Slack approval for review actions before RalphAI mutations."""

from __future__ import annotations

from shared.models.report import CampaignReviewReport


def mark_approved(report: CampaignReviewReport) -> CampaignReviewReport:
    report.approval_status = "approved"
    return report
