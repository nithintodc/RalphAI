"""Campaign Review agent (`/marketingperf`)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config.constants import NEXT_REVIEW_INTERVAL_DAYS
from shared.config.settings import data_root
from shared.models.report import CampaignReviewItem, CampaignReviewReport
from shared.utils.date_helpers import review_scheduled_at_from_now, utc_now_iso

from .comparator import compare
from .recommender import recommend


def _setup_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "campaigns" / "setup.json"


def _review_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "campaign_review.json"


def run(
    operator_id: str,
    *,
    active_campaigns: dict[str, Any] | None = None,
    post_campaign_data: list[str] | None = None,
    pre_campaign_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = post_campaign_data
    if active_campaigns is None:
        active_campaigns = json.loads(_setup_path(operator_id).read_text(encoding="utf-8"))
    pre = pre_campaign_baseline or {}
    post: dict[str, Any] = {}
    reviews: list[CampaignReviewItem] = []
    for c in active_campaigns.get("campaigns_created", []):
        cid = c.get("campaign_id", "")
        name = c.get("campaign_name", "")
        aov_l, vol_l, rev_d = compare(pre, post)
        rec = recommend(pre, post)
        reviews.append(
            CampaignReviewItem(
                campaign_id=cid,
                campaign_name=name,
                pre_metrics=pre,
                post_metrics=post,
                aov_lift_pct=aov_l,
                order_volume_lift_pct=vol_l,
                net_revenue_delta=rev_d,
                recommendation=rec,
                update_params={},
                rationale="Stub review — wire post_campaign_data parsers.",
            )
        )
    report = CampaignReviewReport(
        operator_id=operator_id,
        review_date=utc_now_iso(),
        campaign_reviews=reviews,
        approval_status="pending",
        next_review_date=review_scheduled_at_from_now(NEXT_REVIEW_INTERVAL_DAYS),
    )
    path = _review_path(operator_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return json.loads(report.model_dump_json())


if __name__ == "__main__":
    import sys

    oid = sys.argv[1] if len(sys.argv) > 1 else "dev_operator"
    print(json.dumps(run(oid), indent=2))
