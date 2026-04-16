"""RalphAI — Campaign Setup agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from shared.config.constants import REVIEW_DELAY_DAYS
from shared.config.settings import data_root
from shared.models.report import CampaignSetupResult, MarketingPlan
from shared.utils.date_helpers import review_scheduled_at_from_now, utc_now_iso

from .ads_flow import run_ads
from .browser_controller import BrowserController
from .offers_flow import run_offers
from .verification import verify_campaign


def _plan_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "marketing_plan.json"


def _setup_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "campaigns" / "setup.json"


def run(
    operator_id: str,
    *,
    campaign_type: Literal["offers", "ads"],
    marketing_plan: dict[str, Any] | None = None,
    store_ids: list[str] | None = None,
) -> dict[str, Any]:
    store_ids = store_ids or []
    if marketing_plan is None:
        plan = MarketingPlan.model_validate_json(
            _plan_path(operator_id).read_text(encoding="utf-8")
        )
    else:
        plan = MarketingPlan.model_validate(marketing_plan)

    ctrl = BrowserController()
    ctrl.start()
    created_models = []
    for rc in plan.recommended_campaigns:
        frag = rc.model_dump()
        ctype = rc.campaign_type
        if campaign_type == "offers" and ctype in ("promo", "combo"):
            c = run_offers(store_ids=store_ids, plan_fragment=frag)
            verify_campaign(c)
            created_models.append(c)
        if campaign_type == "ads" and ctype == "sponsored_listing":
            c = run_ads(store_ids=store_ids, plan_fragment=frag)
            verify_campaign(c)
            created_models.append(c)
    ctrl.stop()

    setup = CampaignSetupResult(
        operator_id=operator_id,
        setup_date=utc_now_iso(),
        campaigns_created=created_models,
        setup_summary=f"Created {len(created_models)} campaign(s) via {campaign_type}.",
        review_scheduled_at=review_scheduled_at_from_now(REVIEW_DELAY_DAYS),
    )
    out_path = _setup_path(operator_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(setup.model_dump_json(indent=2), encoding="utf-8")
    return json.loads(setup.model_dump_json())


if __name__ == "__main__":
    import sys

    oid = sys.argv[1] if len(sys.argv) > 1 else "dev_operator"
    ctype_raw = sys.argv[2] if len(sys.argv) > 2 else "ads"
    if ctype_raw not in ("offers", "ads"):
        raise SystemExit("usage: agent.py <operator_id> [offers|ads]")
    print(json.dumps(run(oid, campaign_type=ctype_raw), indent=2))
