"""Build MarketingPlan from ads_planner slot tiers, promo mappings, and campaign history."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from shared.config.settings import data_root, deepdive_default_zip_dir
from shared.models.campaign import RecommendedCampaign
from shared.models.report import DeepDiveReport, MarketingPlan
from shared.utils.date_helpers import utc_now_iso

log = logging.getLogger(__name__)


def _find_financial_csv(operator_id: str) -> Path | None:
    """Return the most recent FINANCIAL_DETAILED CSV reachable for this operator.

    Search order:
    1. ``data/operators/<id>/raw/``           — per-operator download directory.
    2. ``data/TriArch/_extracted/``           — extracted from legacy shared zips.
    3. ``data/TriArch/``                      — direct CSV drop in legacy dir.
    """
    candidates: list[Path] = [
        data_root() / "operators" / operator_id / "raw",
        deepdive_default_zip_dir() / "_extracted",
        deepdive_default_zip_dir(),
    ]
    for root in candidates:
        if not root.is_dir():
            continue
        csvs = sorted(root.rglob("FINANCIAL_DETAILED*.csv"), reverse=True)
        if csvs:
            log.debug("Found FINANCIAL_DETAILED CSV for %s at %s", operator_id, csvs[0])
            return csvs[0]
    return None


def _schedule_tag(day_of_week: str, daypart: str) -> int | None:
    from agents.marketingreco.ralph_ads_excel import slot_table_row_to_schedule_tag

    return slot_table_row_to_schedule_tag(
        {"day_of_week": day_of_week, "daypart": daypart},
    )


def _weekly_budget(ads_plan: dict[str, Any] | None, store_id: Any, dow: str, daypart: str) -> float:
    if not ads_plan:
        return 0.0
    for row in ads_plan.get("slot_table") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("store_id")) != str(store_id):
            continue
        if str(row.get("day_of_week")) != str(dow):
            continue
        if str(row.get("daypart")) != str(daypart):
            continue
        return float(row.get("weekly_budget") or row.get("budget_estimate") or 0.0)
    return 0.0


def _promo_from_mappings(
    operator_id: str,
    mappings: list[dict[str, Any]],
) -> list[RecommendedCampaign]:
    campaigns: list[RecommendedCampaign] = []
    for m in mappings:
        tags_raw = m.get("slot_tags")
        if isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw if t is not None]
        else:
            tags = [t.strip() for t in str(tags_raw or "").replace("，", ",").split(",") if t.strip()]
        campaigns.append(
            RecommendedCampaign(
                campaign_type="promo",
                campaign_name=m.get("campaign_name", "Campaign"),
                budget=0.0,
                start_date=utc_now_iso(),
                duration_days=7,
                target_day_parts=tags,
                store_id=str(m.get("store_id") or ""),
                rationale=(
                    f"Promo mapping for store {m.get('store_id') or 'unknown'} "
                    f"(min subtotal {m.get('min_subtotal')}, slots {tags or m.get('slot_tags')}, "
                    f"status {m.get('status', 'Pending')})."
                )[:500],
            )
        )
    return campaigns


def _ads_from_ads_plan(
    operator_id: str,
    ads_plan: dict[str, Any],
) -> list[RecommendedCampaign]:
    campaigns: list[RecommendedCampaign] = []
    for c in ads_plan.get("campaigns") or []:
        if not isinstance(c, dict):
            continue
        tier = str(c.get("tier") or "").upper()
        if tier == "SKIP":
            continue

        store_id = c.get("store_id")
        dow = str(c.get("day_of_week") or "")
        daypart = str(c.get("daypart") or "")
        tag = _schedule_tag(dow, daypart)
        slot_tags = [str(tag)] if tag is not None else []

        budget = _weekly_budget(ads_plan, store_id, dow, daypart)
        if budget <= 0 and c.get("allocation_pct"):
            budget = round(float(c.get("allocation_pct") or 0) * 10, 2)

        rationale = str(c.get("rationale") or c.get("metrics", ""))
        if c.get("history_note"):
            rationale = f"{c.get('history_note')}. {rationale}"

        campaigns.append(
            RecommendedCampaign(
                campaign_type="sponsored_listing",
                campaign_name=str(c.get("campaign_name") or f"{store_id}_{dow}_{daypart}_{tier}"),
                budget=round(budget, 2),
                start_date=str(c.get("start_date") or utc_now_iso()),
                duration_days=28,
                target_day_parts=slot_tags,
                store_id=str(store_id or ""),
                day_of_week=dow,
                daypart=daypart,
                tier=tier,
                slot_tags=slot_tags,
                bid_strategy=str(c.get("bid_strategy") or ""),
                bid_amount=c.get("bid_amount"),
                target_audience=str(c.get("target_audience") or ""),
                rationale=rationale[:500],
            )
        )
    return campaigns


def generate_plan_from_sources(
    operator_id: str,
    *,
    mappings: list[dict[str, Any]] | None = None,
    ads_plan: dict[str, Any] | None = None,
    deepdive_report: DeepDiveReport | None = None,
    campaign_history: dict[str, Any] | None = None,
    budget_cap: float | None = None,
) -> MarketingPlan:
    """
    Slot-level thesis end-to-end:
    - Promos from combined-analysis Campaign Mappings
    - Sponsored listings from ads_planner DEFEND/GROW/HARVEST (post history adjustment)
    - DeepDive seed only when no slot-level ads exist
    """
    _ = campaign_history
    _ = budget_cap

    recommended: list[RecommendedCampaign] = []
    recommended.extend(_promo_from_mappings(operator_id, mappings or []))
    recommended.extend(_ads_from_ads_plan(operator_id, ads_plan or {}))

    if not recommended and deepdive_report is not None:
        return generate_plan(deepdive_report, budget_cap=budget_cap)

    if not recommended:
        recommended.append(
            RecommendedCampaign(
                campaign_type="promo",
                campaign_name="No slot recommendations",
                budget=0.0,
                start_date=utc_now_iso(),
                duration_days=7,
                rationale="No campaign mappings or ads_plan slot campaigns were produced.",
            )
        )

    notes = ""
    if campaign_history:
        slot_count = len(campaign_history.get("slots") or {})
        notes = f"Applied campaign_history from review ({slot_count} slot records)."
    if ads_plan:
        tiers = ads_plan.get("tier_summary") or {}
        notes = (
            f"{notes} Ads tiers: DEFEND={tiers.get('DEFEND', 0)}, "
            f"GROW={tiers.get('GROW', 0)}, HARVEST={tiers.get('HARVEST', 0)}."
        ).strip()

    return MarketingPlan(
        operator_id=operator_id,
        plan_date=utc_now_iso(),
        recommended_campaigns=recommended,
        approval_status="pending",
        approver_notes=notes,
    )


def generate_plan(
    deepdive_report: DeepDiveReport,
    *,
    budget_cap: float | None = None,
    campaign_history: dict[str, Any] | None = None,
) -> MarketingPlan:
    """Build a slot-level MarketingPlan for the operator.

    Primary path — tries to locate a FINANCIAL_DETAILED CSV and run
    ``ads_planner.build_ads_plan()`` to produce granular DEFEND/GROW/HARVEST
    sponsored-listing campaigns per store × day-of-week × daypart.

    Fallback path — used when no CSV is found or the planner raises (e.g. all
    Order rows have null ``Order received local time``): returns two baseline
    campaigns so the pipeline never stalls.
    """
    # --- primary: slot-level plan from FINANCIAL_DETAILED ---
    financial_csv = _find_financial_csv(deepdive_report.operator_id)
    if financial_csv is not None:
        try:
            from .ads_planner import build_ads_plan
            ads_plan = build_ads_plan(str(financial_csv))
            if ads_plan.get("campaigns"):
                log.info(
                    "Slot-level plan for operator %s: %d campaigns, tiers=%s",
                    deepdive_report.operator_id,
                    ads_plan.get("total_campaigns", 0),
                    ads_plan.get("tier_summary", {}),
                )
                return generate_plan_from_sources(
                    deepdive_report.operator_id,
                    ads_plan=ads_plan,
                    deepdive_report=deepdive_report,
                    campaign_history=campaign_history,
                    budget_cap=budget_cap,
                )
        except ValueError as exc:
            # Common cause: no delivered rows with non-null Order received local time.
            log.warning(
                "ads_planner skipped for operator %s (%s) — using DeepDive seed fallback",
                deepdive_report.operator_id,
                exc,
            )
        except Exception as exc:
            log.warning(
                "Unexpected ads_planner error for operator %s (%s) — using fallback",
                deepdive_report.operator_id,
                exc,
            )
    else:
        log.info(
            "No FINANCIAL_DETAILED CSV found for operator %s — using DeepDive seed fallback",
            deepdive_report.operator_id,
        )

    # --- fallback: seed-based campaigns from DeepDive report ---
    seed = deepdive_report.recommendations_seed or "Grow traffic and protect margin."
    history_note = ""
    if campaign_history:
        slots = campaign_history.get("slots") or {}
        winners = [
            k for k, v in slots.items()
            if str(v.get("recommendation")) in ("/keep", "/new") and float(v.get("roas_delta") or 0) > 0
        ]
        if winners:
            history_note = f" Prior review winners: {', '.join(winners[:5])}."

    campaigns = [
        RecommendedCampaign(
            campaign_type="sponsored_listing",
            campaign_name="Weekend traffic test",
            budget=150.0,
            start_date=utc_now_iso(),
            duration_days=14,
            target_day_parts=["Dinner", "Late night"],
            rationale=(seed[:480] + history_note)[:500],
        ),
        RecommendedCampaign(
            campaign_type="promo",
            campaign_name="AOV lift — spend threshold",
            budget=0.0,
            start_date=utc_now_iso(),
            duration_days=7,
            target_day_parts=["Lunch"],
            discount_pct=15.0,
            rationale="Pair with listing test; tune discount from DeepDive AOV.",
        ),
    ]
    return MarketingPlan(
        operator_id=deepdive_report.operator_id,
        plan_date=utc_now_iso(),
        recommended_campaigns=campaigns,
        approval_status="pending",
        approver_notes=(
            "Slot-level plan unavailable — FINANCIAL_DETAILED CSV not found or contained "
            "no deliverable Order rows with timestamps. Using baseline recommendations."
            + history_note
        ).strip(),
    )
