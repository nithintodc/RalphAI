"""Campaign review logic (pre/post metrics, recommendations) — part of Health Check."""

from __future__ import annotations

import json
import math
import zipfile
from numbers import Integral
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from shared.config.constants import NEXT_REVIEW_INTERVAL_DAYS
from shared.config.settings import data_root, deepdive_default_zip_dir
from shared.models.report import CampaignReviewItem, CampaignReviewReport
from shared.utils.date_helpers import review_scheduled_at_from_now, utc_now_iso

from shared.campaign_history import build_campaign_history_from_review
from shared.slot_campaign_keys import parse_slot_campaign_name, slot_key

from .comparator import compare
from .recommender import recommend

CampaignReviewMode = Literal["auto", "manual"]


def _setup_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "campaigns" / "setup.json"


def _marketing_plan_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "marketing_plan.json"


def _review_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "campaign_review.json"


def _safe_num(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def _sanitize_for_json(obj: Any) -> Any:
    """Replace NaN/Inf and numpy scalars so output is strict JSON (FastAPI-safe)."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, Integral) and not isinstance(obj, bool):
        return int(obj)
    if isinstance(obj, float):
        return 0.0 if not math.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(x) for x in obj]
    if isinstance(obj, tuple):
        return [_sanitize_for_json(x) for x in obj]
    if hasattr(obj, "dtype") and getattr(obj, "shape", ()) == ():
        try:
            return _sanitize_for_json(obj.item())
        except (ValueError, AttributeError, TypeError):
            return obj
    try:
        x = float(obj)
        return x if math.isfinite(x) else 0.0
    except (TypeError, ValueError):
        return obj


def to_json_safe(value: Any) -> Any:
    """Normalize nested structures for strict JSON (FastAPI, json.dumps with allow_nan=False)."""
    return _sanitize_for_json(value)


def _finalize_marketing_metrics(
    orders: float,
    sales: float,
    spend: float,
    views: float,
    clicks: float,
    new_customers: float = 0.0,
    *,
    channel: str = "",
) -> dict[str, Any]:
    avg_order_value = sales / orders if orders > 0 else 0.0
    cpo = round(spend / orders, 2) if orders > 0 else 0.0
    out: dict[str, Any] = {
        "orders": round(orders, 2),
        "sales": round(sales, 2),
        "spend": round(spend, 2),
        "new_customers": round(new_customers, 2),
        "views": round(views, 2),
        "clicks": round(clicks, 2),
        "roas": round(sales / spend, 2) if spend > 0 else 0.0,
        "ctr_pct": round(clicks / views * 100, 2) if views > 0 else 0.0,
        "conversion_rate_pct": round(orders / clicks * 100, 2) if clicks > 0 else 0.0,
        "cost_per_order": cpo,
        "cost_per_new_customer": round(spend / new_customers, 2) if new_customers > 0 else 0.0,
        "cost_per_click": round(spend / clicks, 2) if clicks > 0 else 0.0,
        "avg_order_value": round(avg_order_value, 2),
        "cpa": cpo,
    }
    if channel:
        out["channel"] = channel
    return out


def _combine_metric_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    if not a:
        return dict(b) if b else {}
    if not b:
        return dict(a)
    orders = _safe_num(a.get("orders")) + _safe_num(b.get("orders"))
    sales = _safe_num(a.get("sales")) + _safe_num(b.get("sales"))
    spend = _safe_num(a.get("spend")) + _safe_num(b.get("spend"))
    views = _safe_num(a.get("views")) + _safe_num(b.get("views"))
    clicks = _safe_num(a.get("clicks")) + _safe_num(b.get("clicks"))
    nc = _safe_num(a.get("new_customers")) + _safe_num(b.get("new_customers"))
    ch_a, ch_b = str(a.get("channel", "")), str(b.get("channel", ""))
    channel = "combined" if ch_a and ch_b and ch_a != ch_b else (ch_a or ch_b)
    return _finalize_marketing_metrics(orders, sales, spend, views, clicks, nc, channel=channel)


def _rollup_from_frame(g: pd.DataFrame, spend_col: str, channel: str = "") -> dict[str, Any]:
    if g is None or g.empty:
        return _finalize_marketing_metrics(0, 0, 0, 0, 0, 0, channel=channel)
    orders = _safe_num(pd.to_numeric(g.get("Orders"), errors="coerce").sum())
    sales = _safe_num(pd.to_numeric(g.get("Sales"), errors="coerce").sum())
    spend_raw = g.get(spend_col)
    spend = abs(_safe_num(pd.to_numeric(spend_raw, errors="coerce").sum())) if spend_raw is not None else 0.0
    views = _safe_num(pd.to_numeric(g.get("Impressions"), errors="coerce").sum()) if "Impressions" in g.columns else 0.0
    clicks = _safe_num(pd.to_numeric(g.get("Clicks"), errors="coerce").sum()) if "Clicks" in g.columns else 0.0
    nc = (
        _safe_num(pd.to_numeric(g.get("New customers acquired"), errors="coerce").sum())
        if "New customers acquired" in g.columns
        else 0.0
    )
    return _finalize_marketing_metrics(orders, sales, spend, views, clicks, nc, channel=channel)


def _enriched_campaign_pre_post(
    df: pd.DataFrame | None, spend_col: str, channel: str
) -> dict[str, dict[str, Any]]:
    if df is None or df.empty or "Campaign name" not in df.columns:
        return {}
    required = ("Date", "Campaign start date", "Campaign end date")
    if not all(c in df.columns for c in required) or spend_col not in df.columns:
        return {}

    tmp = df.copy()
    for c in required:
        tmp[c] = pd.to_datetime(tmp[c], errors="coerce")

    out: dict[str, dict[str, Any]] = {}
    for name, g in tmp.groupby("Campaign name", dropna=True):
        key = str(name).strip()
        if not key:
            continue
        post_start = g["Campaign start date"].dropna().min()
        post_end = g["Campaign end date"].dropna().max()
        if pd.isna(post_start) or pd.isna(post_end):
            continue
        post_start_ts = pd.Timestamp(post_start).normalize()
        post_end_ts = pd.Timestamp(post_end).normalize()
        if post_end_ts < post_start_ts:
            post_end_ts = post_start_ts
        post_days = int((post_end_ts - post_start_ts).days + 1)
        pre_end_ts = post_start_ts - pd.Timedelta(days=1)
        pre_start_ts = post_start_ts - pd.Timedelta(days=post_days)

        dr = pd.to_datetime(g["Date"], errors="coerce")
        post_mask = (dr >= post_start_ts) & (dr <= post_end_ts)
        pre_mask = (dr >= pre_start_ts) & (dr <= pre_end_ts)
        post_g = g.loc[post_mask]
        pre_g = g.loc[pre_mask]

        post_metrics = _rollup_from_frame(post_g, spend_col, channel)
        pre_metrics = _rollup_from_frame(pre_g, spend_col, channel)

        pre_dates = pd.to_datetime(pre_g["Date"], errors="coerce").dropna().dt.normalize().unique()
        pre_hit = len(pre_dates)
        coverage = round(min(100.0, pre_hit / post_days * 100.0), 2) if post_days > 0 else 0.0

        out[key] = {
            "pre_metrics": pre_metrics,
            "post_metrics": post_metrics,
            "post_window_days": post_days,
            "pre_window_days": post_days,
            "pre_data_coverage_pct": coverage,
            "pre_period_start": pre_start_ts.strftime("%Y-%m-%d"),
            "pre_period_end": pre_end_ts.strftime("%Y-%m-%d"),
            "post_period_start": post_start_ts.strftime("%Y-%m-%d"),
            "post_period_end": post_end_ts.strftime("%Y-%m-%d"),
        }
    return out


def _merge_enriched_by_name(
    promo_e: dict[str, dict[str, Any]],
    sponsored_e: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    names = set(promo_e) | set(sponsored_e)
    out: dict[str, dict[str, Any]] = {}
    for name in names:
        a = promo_e.get(name)
        b = sponsored_e.get(name)
        if a and b:
            cov = round(min(a["pre_data_coverage_pct"], b["pre_data_coverage_pct"]), 2)
            out[name] = {
                "pre_metrics": _combine_metric_dicts(a["pre_metrics"], b["pre_metrics"]),
                "post_metrics": _combine_metric_dicts(a["post_metrics"], b["post_metrics"]),
                "post_window_days": max(int(a["post_window_days"]), int(b["post_window_days"])),
                "pre_window_days": max(int(a["pre_window_days"]), int(b["pre_window_days"])),
                "pre_data_coverage_pct": cov,
                "pre_period_start": min(str(a["pre_period_start"]), str(b["pre_period_start"])),
                "pre_period_end": max(str(a["pre_period_end"]), str(b["pre_period_end"])),
                "post_period_start": min(str(a["post_period_start"]), str(b["post_period_start"])),
                "post_period_end": max(str(a["post_period_end"]), str(b["post_period_end"])),
            }
        elif a:
            out[name] = dict(a)
        elif b:
            out[name] = dict(b)
    return out


def _fill_enriched_fallback(
    enriched: dict[str, dict[str, Any]],
    campaign_name_metrics: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out = dict(enriched)
    for name, post in campaign_name_metrics.items():
        if name in out:
            continue
        out[name] = {
            "pre_metrics": {},
            "post_metrics": dict(post),
            "post_window_days": 0,
            "pre_window_days": 0,
            "pre_data_coverage_pct": 0.0,
            "pre_period_start": "",
            "pre_period_end": "",
            "post_period_start": "",
            "post_period_end": "",
            "pre_window_note": "Export missing Date / campaign window columns; using totals only (no equal-length pre window).",
        }
    return out


def _effective_pre_metrics(campaign_pre: dict[str, Any], global_pre: dict[str, Any] | None) -> dict[str, Any]:
    gpre = global_pre or {}
    if not campaign_pre:
        return dict(gpre)
    idle = (
        _safe_num(campaign_pre.get("orders")) == 0
        and _safe_num(campaign_pre.get("sales")) == 0
        and _safe_num(campaign_pre.get("spend")) == 0
        and _safe_num(campaign_pre.get("clicks")) == 0
        and _safe_num(campaign_pre.get("views")) == 0
    )
    if idle and gpre:
        return dict(gpre)
    return dict(campaign_pre)


def _fold_enriched_pre_post(enriched: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    pre: dict[str, Any] = {}
    post: dict[str, Any] = {}
    for row in enriched.values():
        pre = _combine_metric_dicts(pre, row.get("pre_metrics") or {})
        post = _combine_metric_dicts(post, row.get("post_metrics") or {})
    return pre, post


def _campaign_comparison_table(enriched: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, e in enriched.items():
        pm = e.get("post_metrics") or {}
        pr = e.get("pre_metrics") or {}
        rows.append(
            {
                "campaign_name": name,
                "post_window_days": e.get("post_window_days", 0),
                "pre_window_days": e.get("pre_window_days", 0),
                "pre_data_coverage_pct": e.get("pre_data_coverage_pct", 0.0),
                "post_roas": pm.get("roas", 0.0),
                "pre_roas": pr.get("roas", 0.0),
                "roas_delta": round(_safe_num(pm.get("roas")) - _safe_num(pr.get("roas")), 2),
                "post_sales": pm.get("sales", 0.0),
                "pre_sales": pr.get("sales", 0.0),
                "post_spend": pm.get("spend", 0.0),
                "pre_spend": pr.get("spend", 0.0),
                "post_orders": pm.get("orders", 0.0),
                "pre_orders": pr.get("orders", 0.0),
                "post_ctr_pct": pm.get("ctr_pct", 0.0),
                "pre_ctr_pct": pr.get("ctr_pct", 0.0),
                "post_conversion_rate_pct": pm.get("conversion_rate_pct", 0.0),
                "pre_conversion_rate_pct": pr.get("conversion_rate_pct", 0.0),
                "post_avg_order_value": pm.get("avg_order_value", 0.0),
                "pre_avg_order_value": pr.get("avg_order_value", 0.0),
            }
        )
    rows.sort(
        key=lambda r: (_safe_num(r.get("post_roas")), _safe_num(r.get("post_sales"))),
        reverse=True,
    )
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def _classify_csv(filename: str) -> str:
    name = filename.upper()
    if "MARKETING_PROMOTION" in name:
        return "marketing_promotions"
    if "MARKETING_SPONSORED_LISTING" in name:
        return "marketing_sponsored"
    return "unknown"


def _load_manual_csvs(data_files: list[str | Path]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for p0 in data_files:
        p = Path(p0)
        if not p.exists():
            continue
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p, "r") as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".csv"):
                        continue
                    k = _classify_csv(Path(name).name)
                    if k == "unknown":
                        continue
                    with zf.open(name) as fp:
                        out[k] = pd.read_csv(fp, low_memory=False)
            continue
        if p.suffix.lower() == ".csv":
            k = _classify_csv(p.name)
            if k == "unknown":
                continue
            out[k] = pd.read_csv(p, low_memory=False)
    return out


def _load_auto_from_triarch(data_dir: str | Path | None) -> dict[str, pd.DataFrame]:
    from agents.deepdive.data_loader import load_ssm_zips

    path = Path(data_dir) if data_dir else deepdive_default_zip_dir()
    if not path.is_dir():
        return {}
    return load_ssm_zips(path)


def _promo_metrics(df: pd.DataFrame | None) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    spend_col = "Customer discounts from marketing | (Funded by you)"
    if spend_col not in df.columns:
        spend_col = "Customer discounts from marketing | (funded by you)"
    orders = _safe_num(pd.to_numeric(df.get("Orders"), errors="coerce").sum())
    sales = _safe_num(pd.to_numeric(df.get("Sales"), errors="coerce").sum())
    spend = abs(_safe_num(pd.to_numeric(df.get(spend_col), errors="coerce").sum()))
    new_customers = _safe_num(pd.to_numeric(df.get("New customers acquired"), errors="coerce").sum())
    views = _safe_num(pd.to_numeric(df.get("Impressions"), errors="coerce").sum())
    clicks = _safe_num(pd.to_numeric(df.get("Clicks"), errors="coerce").sum())
    avg_order_value = sales / orders if orders > 0 else 0.0
    return {
        "channel": "promo",
        "orders": round(orders, 2),
        "sales": round(sales, 2),
        "spend": round(spend, 2),
        "new_customers": round(new_customers, 2),
        "views": round(views, 2),
        "clicks": round(clicks, 2),
        "roas": round(sales / spend, 2) if spend > 0 else 0.0,
        "ctr_pct": round(clicks / views * 100, 2) if views > 0 else 0.0,
        "conversion_rate_pct": round(orders / clicks * 100, 2) if clicks > 0 else 0.0,
        "cost_per_order": round(spend / orders, 2) if orders > 0 else 0.0,
        "cost_per_new_customer": round(spend / new_customers, 2) if new_customers > 0 else 0.0,
        "cost_per_click": round(spend / clicks, 2) if clicks > 0 else 0.0,
        "avg_order_value": round(avg_order_value, 2),
    }


def _sponsored_metrics(df: pd.DataFrame | None) -> dict[str, Any]:
    if df is None or df.empty:
        return {}
    spend_col = "Marketing fees | (including any applicable taxes)"
    orders = _safe_num(pd.to_numeric(df.get("Orders"), errors="coerce").sum())
    sales = _safe_num(pd.to_numeric(df.get("Sales"), errors="coerce").sum())
    spend = abs(_safe_num(pd.to_numeric(df.get(spend_col), errors="coerce").sum()))
    views = _safe_num(pd.to_numeric(df.get("Impressions"), errors="coerce").sum())
    clicks = _safe_num(pd.to_numeric(df.get("Clicks"), errors="coerce").sum())
    avg_order_value = sales / orders if orders > 0 else 0.0
    return {
        "channel": "sponsored_listing",
        "orders": round(orders, 2),
        "sales": round(sales, 2),
        "spend": round(spend, 2),
        "new_customers": 0.0,
        "views": round(views, 2),
        "clicks": round(clicks, 2),
        "roas": round(sales / spend, 2) if spend > 0 else 0.0,
        "ctr_pct": round(clicks / views * 100, 2) if views > 0 else 0.0,
        "conversion_rate_pct": round(orders / clicks * 100, 2) if clicks > 0 else 0.0,
        "cost_per_order": round(spend / orders, 2) if orders > 0 else 0.0,
        "cost_per_new_customer": 0.0,
        "cost_per_click": round(spend / clicks, 2) if clicks > 0 else 0.0,
        "avg_order_value": round(avg_order_value, 2),
    }


def _combined_metrics(promo: dict[str, Any], sponsored: dict[str, Any]) -> dict[str, Any]:
    orders = _safe_num(promo.get("orders")) + _safe_num(sponsored.get("orders"))
    sales = _safe_num(promo.get("sales")) + _safe_num(sponsored.get("sales"))
    spend = _safe_num(promo.get("spend")) + _safe_num(sponsored.get("spend"))
    views = _safe_num(promo.get("views")) + _safe_num(sponsored.get("views"))
    clicks = _safe_num(promo.get("clicks")) + _safe_num(sponsored.get("clicks"))
    new_customers = _safe_num(promo.get("new_customers"))
    return {
        "channel": "combined",
        "orders": round(orders, 2),
        "sales": round(sales, 2),
        "spend": round(spend, 2),
        "new_customers": round(new_customers, 2),
        "views": round(views, 2),
        "clicks": round(clicks, 2),
        "roas": round(sales / spend, 2) if spend > 0 else 0.0,
        "ctr_pct": round(clicks / views * 100, 2) if views > 0 else 0.0,
        "conversion_rate_pct": round(orders / clicks * 100, 2) if clicks > 0 else 0.0,
        "cost_per_order": round(spend / orders, 2) if orders > 0 else 0.0,
        "cost_per_new_customer": round(spend / new_customers, 2) if new_customers > 0 else 0.0,
        "cost_per_click": round(spend / clicks, 2) if clicks > 0 else 0.0,
        "avg_order_value": round(sales / orders, 2) if orders > 0 else 0.0,
    }


def _campaign_name_metrics(df: pd.DataFrame | None, spend_col: str) -> dict[str, dict[str, Any]]:
    if df is None or df.empty or "Campaign name" not in df.columns:
        return {}
    tmp = df.copy()
    tmp["Orders"] = pd.to_numeric(tmp.get("Orders"), errors="coerce")
    tmp["Sales"] = pd.to_numeric(tmp.get("Sales"), errors="coerce")
    tmp[spend_col] = pd.to_numeric(tmp.get(spend_col), errors="coerce")
    if "Impressions" in tmp.columns:
        tmp["Impressions"] = pd.to_numeric(tmp["Impressions"], errors="coerce")
    else:
        tmp["Impressions"] = 0
    if "Clicks" in tmp.columns:
        tmp["Clicks"] = pd.to_numeric(tmp["Clicks"], errors="coerce")
    else:
        tmp["Clicks"] = 0
    if "New customers acquired" in tmp.columns:
        tmp["New customers acquired"] = pd.to_numeric(tmp["New customers acquired"], errors="coerce")
    else:
        tmp["New customers acquired"] = 0

    out: dict[str, dict[str, Any]] = {}
    for name, g in tmp.groupby("Campaign name", dropna=True):
        key = str(name).strip()
        if not key:
            continue
        orders = _safe_num(g["Orders"].sum())
        sales = _safe_num(g["Sales"].sum())
        spend = abs(_safe_num(g[spend_col].sum()))
        views = _safe_num(g["Impressions"].sum())
        clicks = _safe_num(g["Clicks"].sum())
        new_customers = _safe_num(g["New customers acquired"].sum())
        out[key] = {
            "orders": round(orders, 2),
            "sales": round(sales, 2),
            "spend": round(spend, 2),
            "views": round(views, 2),
            "clicks": round(clicks, 2),
            "new_customers": round(new_customers, 2),
            "roas": round(sales / spend, 2) if spend > 0 else 0.0,
            "ctr_pct": round(clicks / views * 100, 2) if views > 0 else 0.0,
            "conversion_rate_pct": round(orders / clicks * 100, 2) if clicks > 0 else 0.0,
            "cost_per_order": round(spend / orders, 2) if orders > 0 else 0.0,
            "cost_per_new_customer": round(spend / new_customers, 2) if new_customers > 0 else 0.0,
            "cost_per_click": round(spend / clicks, 2) if clicks > 0 else 0.0,
            "avg_order_value": round(sales / orders, 2) if orders > 0 else 0.0,
        }
    return out


def _load_active_campaigns(operator_id: str, active_campaigns: dict[str, Any] | None) -> dict[str, Any]:
    if active_campaigns is not None:
        return active_campaigns
    setup = _setup_path(operator_id)
    if setup.is_file():
        return json.loads(setup.read_text(encoding="utf-8"))
    return {"campaigns_created": []}


def _load_marketing_plan(operator_id: str) -> dict[str, Any]:
    path = _marketing_plan_path(operator_id)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _slot_attribution_table(
    *,
    active_campaigns: dict[str, Any],
    enriched_by_name: dict[str, dict[str, Any]],
    reviews: list[CampaignReviewItem],
    marketing_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Slot-level attribution: store × day × daypart tied to review metrics."""
    plan_by_name = {
        str(c.get("campaign_name", "")).strip(): c
        for c in marketing_plan.get("recommended_campaigns") or []
        if str(c.get("campaign_name", "")).strip()
    }
    review_by_name = {r.campaign_name: r for r in reviews if r.campaign_name}

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _append_row(
        *,
        name: str,
        store_id: str,
        dow: str,
        daypart: str,
        tier: str,
        slot_tags: list[str],
        enriched: dict[str, Any] | None,
        review: CampaignReviewItem | None,
    ) -> None:
        key = slot_key(store_id, dow, daypart)
        if key in seen:
            return
        seen.add(key)
        post = (enriched or {}).get("post_metrics") or (review.post_metrics if review else {})
        pre = (enriched or {}).get("pre_metrics") or (review.pre_metrics if review else {})
        rows.append(
            {
                "campaign_name": name,
                "store_id": store_id,
                "day_of_week": dow,
                "daypart": daypart,
                "tier": tier,
                "slot_tags": slot_tags,
                "slot_key": key,
                "recommendation": review.recommendation if review else "",
                "post_roas": post.get("roas", 0.0),
                "pre_roas": pre.get("roas", 0.0),
                "roas_delta": round(_safe_num(post.get("roas")) - _safe_num(pre.get("roas")), 2),
                "post_sales": post.get("sales", 0.0),
                "pre_sales": pre.get("sales", 0.0),
                "post_spend": post.get("spend", 0.0),
                "aov_lift_pct": review.aov_lift_pct if review else 0.0,
                "order_volume_lift_pct": review.order_volume_lift_pct if review else 0.0,
            }
        )

    for c in active_campaigns.get("campaigns_created", []) or []:
        name = str(c.get("campaign_name") or "").strip()
        store_id = str(c.get("store_id") or "")
        dow = str(c.get("day_of_week") or "")
        daypart = str(c.get("daypart") or "")
        tier = str(c.get("tier") or "")
        slot_tags = [str(t) for t in (c.get("slot_tags") or [])]
        if not dow or not daypart:
            parsed = parse_slot_campaign_name(name)
            if parsed:
                store_id = store_id or parsed.get("store_id", "")
                dow = dow or parsed.get("day_of_week", "")
                daypart = daypart or parsed.get("daypart", "")
                tier = tier or parsed.get("tier", "")
        plan_frag = plan_by_name.get(name) or {}
        if not slot_tags:
            slot_tags = [str(t) for t in (plan_frag.get("slot_tags") or plan_frag.get("target_day_parts") or [])]
        if not tier:
            tier = str(plan_frag.get("tier") or "")
        _append_row(
            name=name,
            store_id=store_id,
            dow=dow,
            daypart=daypart,
            tier=tier,
            slot_tags=slot_tags,
            enriched=enriched_by_name.get(name),
            review=review_by_name.get(name),
        )

    for name, plan_frag in plan_by_name.items():
        if plan_frag.get("campaign_type") != "sponsored_listing":
            continue
        store_id = str(plan_frag.get("store_id") or "")
        dow = str(plan_frag.get("day_of_week") or "")
        daypart = str(plan_frag.get("daypart") or "")
        if not dow and not daypart:
            parsed = parse_slot_campaign_name(name)
            if parsed:
                store_id = store_id or parsed.get("store_id", "")
                dow = parsed.get("day_of_week", "")
                daypart = parsed.get("daypart", "")
        if not dow or not daypart:
            continue
        slot_tags = [str(t) for t in (plan_frag.get("slot_tags") or plan_frag.get("target_day_parts") or [])]
        _append_row(
            name=name,
            store_id=store_id,
            dow=dow,
            daypart=daypart,
            tier=str(plan_frag.get("tier") or ""),
            slot_tags=slot_tags,
            enriched=enriched_by_name.get(name),
            review=review_by_name.get(name),
        )

    rows.sort(key=lambda r: (r.get("store_id", ""), r.get("day_of_week", ""), r.get("daypart", "")))
    return rows


def _load_planned_budget_by_name(operator_id: str) -> dict[str, float]:
    path = _marketing_plan_path(operator_id)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out: dict[str, float] = {}
    for c in raw.get("recommended_campaigns", []):
        name = str(c.get("campaign_name", "")).strip()
        if not name:
            continue
        out[name] = _safe_num(c.get("budget"))
    return out


def _build_review_items(
    *,
    active_campaigns: dict[str, Any],
    pre_campaign_baseline: dict[str, Any] | None,
    enriched_by_name: dict[str, dict[str, Any]],
    campaign_name_metrics: dict[str, dict[str, Any]],
    by_type: dict[str, dict[str, Any]],
) -> list[CampaignReviewItem]:
    reviews: list[CampaignReviewItem] = []
    global_pre = pre_campaign_baseline or {}
    campaigns = active_campaigns.get("campaigns_created", []) or []
    if not campaigns:
        if enriched_by_name:
            pre_c, post_c = _fold_enriched_pre_post(enriched_by_name)
            pre_eff = _effective_pre_metrics(pre_c, global_pre)
            aov_l, vol_l, rev_d = compare(pre_eff, post_c)
            rec = recommend(pre_eff, post_c)
            cov_avg = (
                round(
                    sum(_safe_num(e.get("pre_data_coverage_pct")) for e in enriched_by_name.values())
                    / max(len(enriched_by_name), 1),
                    2,
                )
                if enriched_by_name
                else 0.0
            )
            reviews.append(
                CampaignReviewItem(
                    campaign_id="summary",
                    campaign_name="Combined marketing summary",
                    pre_metrics=pre_eff,
                    post_metrics=post_c,
                    post_window_days=0,
                    pre_window_days=0,
                    pre_data_coverage_pct=cov_avg,
                    aov_lift_pct=aov_l,
                    order_volume_lift_pct=vol_l,
                    net_revenue_delta=rev_d,
                    recommendation=rec,
                    update_params={},
                    rationale=(
                        "No active campaign setup; rolled up all campaigns with equal-length pre windows where "
                        f"export dates allow (avg pre-date coverage {cov_avg}%). "
                        f"ROAS post={post_c.get('roas', 0)} vs pre={pre_eff.get('roas', 0)}; "
                        f"CTR={post_c.get('ctr_pct', 0)}%."
                    ),
                )
            )
        else:
            post = by_type.get("combined", {})
            pre_eff = global_pre
            aov_l, vol_l, rev_d = compare(pre_eff, post)
            rec = recommend(pre_eff, post)
            reviews.append(
                CampaignReviewItem(
                    campaign_id="summary",
                    campaign_name="Combined marketing summary",
                    pre_metrics=pre_eff,
                    post_metrics=post,
                    post_window_days=0,
                    pre_window_days=0,
                    pre_data_coverage_pct=0.0,
                    aov_lift_pct=aov_l,
                    order_volume_lift_pct=vol_l,
                    net_revenue_delta=rev_d,
                    recommendation=rec,
                    update_params={},
                    rationale="No active campaign setup found; recommendation is based on combined marketing metrics.",
                )
            )
        return reviews

    for c in campaigns:
        cid = str(c.get("campaign_id") or "")
        name = str(c.get("campaign_name") or "")
        ctype = str(c.get("campaign_type") or "")
        enriched = enriched_by_name.get(name)
        if enriched:
            raw_pre = enriched.get("pre_metrics") or {}
            post = dict(enriched.get("post_metrics") or {})
            pre_eff = _effective_pre_metrics(raw_pre, global_pre)
            p_days = int(enriched.get("post_window_days") or 0)
            pre_days = int(enriched.get("pre_window_days") or 0)
            cov = float(enriched.get("pre_data_coverage_pct") or 0.0)
            note = str(enriched.get("pre_window_note") or "")
        else:
            post = campaign_name_metrics.get(name)
            if post is None:
                if ctype in ("promo", "combo"):
                    post = by_type.get("promo", {})
                elif ctype == "sponsored_listing":
                    post = by_type.get("sponsored_listing", {})
                else:
                    post = by_type.get("combined", {})
            post = dict(post or {})
            pre_eff = dict(global_pre)
            p_days, pre_days, cov = 0, 0, 0.0
            note = "No per-campaign row in marketing export for this setup name."

        aov_l, vol_l, rev_d = compare(pre_eff, post)
        rec = recommend(pre_eff, post)
        reviews.append(
            CampaignReviewItem(
                campaign_id=cid,
                campaign_name=name or cid or "unknown",
                pre_metrics=pre_eff,
                post_metrics=post,
                post_window_days=p_days,
                pre_window_days=pre_days,
                pre_data_coverage_pct=cov,
                aov_lift_pct=aov_l,
                order_volume_lift_pct=vol_l,
                net_revenue_delta=rev_d,
                recommendation=rec,
                update_params={},
                rationale=(
                    (f"{note} " if note else "")
                    + f"Post window {p_days}d (pre compare window {pre_days}d, pre export coverage {cov}%). "
                    f"ROAS post={post.get('roas', 0)} vs pre={pre_eff.get('roas', 0)}; "
                    f"CTR={post.get('ctr_pct', 0)}%; CVR={post.get('conversion_rate_pct', 0)}%; "
                    f"CPC={post.get('cost_per_click', 0)}; CPA/CPO={post.get('cost_per_order', 0)}."
                ),
            )
        )
    return reviews


def run(
    operator_id: str,
    *,
    mode: CampaignReviewMode = "auto",
    data_dir: str | Path | None = None,
    data_files: list[str | Path] | None = None,
    active_campaigns: dict[str, Any] | None = None,
    post_campaign_data: list[str] | None = None,  # legacy alias for data_files
    pre_campaign_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    files = data_files or post_campaign_data or []
    if mode == "manual":
        datasets = _load_manual_csvs(files)
    else:
        datasets = _load_auto_from_triarch(data_dir)

    promo_df = datasets.get("marketing_promotions")
    sponsored_df = datasets.get("marketing_sponsored")
    promo_metrics = _promo_metrics(promo_df)
    sponsored_metrics = _sponsored_metrics(sponsored_df)
    combined_metrics = _combined_metrics(promo_metrics, sponsored_metrics)

    spend_col_promo = (
        "Customer discounts from marketing | (Funded by you)"
        if promo_df is not None and "Customer discounts from marketing | (Funded by you)" in promo_df.columns
        else "Customer discounts from marketing | (funded by you)"
    )
    promo_by_name = _campaign_name_metrics(promo_df, spend_col_promo) if promo_df is not None else {}
    sponsored_by_name = (
        _campaign_name_metrics(sponsored_df, "Marketing fees | (including any applicable taxes)")
        if sponsored_df is not None
        else {}
    )
    campaign_name_metrics = {**promo_by_name, **sponsored_by_name}

    promo_enriched = _enriched_campaign_pre_post(promo_df, spend_col_promo, "promo") if promo_df is not None else {}
    sponsored_enriched = (
        _enriched_campaign_pre_post(
            sponsored_df, "Marketing fees | (including any applicable taxes)", "sponsored_listing"
        )
        if sponsored_df is not None
        else {}
    )
    enriched_by_name = _merge_enriched_by_name(promo_enriched, sponsored_enriched)
    enriched_by_name = _fill_enriched_fallback(enriched_by_name, campaign_name_metrics)
    campaign_comparison = _campaign_comparison_table(enriched_by_name)

    active = _load_active_campaigns(operator_id, active_campaigns)
    marketing_plan = _load_marketing_plan(operator_id)
    by_type = {
        "promo": promo_metrics,
        "sponsored_listing": sponsored_metrics,
        "combined": combined_metrics,
    }
    reviews = _build_review_items(
        active_campaigns=active,
        pre_campaign_baseline=pre_campaign_baseline,
        enriched_by_name=enriched_by_name,
        campaign_name_metrics=campaign_name_metrics,
        by_type=by_type,
    )

    slot_attribution = _slot_attribution_table(
        active_campaigns=active,
        enriched_by_name=enriched_by_name,
        reviews=reviews,
        marketing_plan=marketing_plan,
    )

    planned_budget_by_name = _load_planned_budget_by_name(operator_id)
    for r in reviews:
        planned = _safe_num(planned_budget_by_name.get(r.campaign_name, 0.0))
        spend = _safe_num(r.post_metrics.get("spend"))
        budget_utilization_pct = round(spend / planned * 100, 2) if planned > 0 else 0.0
        if not math.isfinite(budget_utilization_pct):
            budget_utilization_pct = 0.0
        r.post_metrics["planned_budget"] = round(planned, 2)
        r.post_metrics["budget_utilization_pct"] = budget_utilization_pct

    summary = {
        "promo": promo_metrics,
        "sponsored_listing": sponsored_metrics,
        "combined": combined_metrics,
        "datasets_loaded": sorted(datasets.keys()),
        "campaign_metrics_by_name": campaign_name_metrics,
        "campaign_comparison": campaign_comparison,
        "campaign_windows_by_name": {
            k: {
                "post_window_days": v.get("post_window_days", 0),
                "pre_window_days": v.get("pre_window_days", 0),
                "pre_data_coverage_pct": v.get("pre_data_coverage_pct", 0.0),
                "pre_period_start": v.get("pre_period_start", ""),
                "pre_period_end": v.get("pre_period_end", ""),
                "post_period_start": v.get("post_period_start", ""),
                "post_period_end": v.get("post_period_end", ""),
                "pre_window_note": v.get("pre_window_note", ""),
            }
            for k, v in enriched_by_name.items()
        },
        "slot_attribution": slot_attribution,
    }

    if not reviews:
        reviews = [
            CampaignReviewItem(
                campaign_id="summary",
                campaign_name="Combined marketing summary",
                pre_metrics=pre_campaign_baseline or {},
                post_metrics=combined_metrics,
                aov_lift_pct=0.0,
                order_volume_lift_pct=0.0,
                net_revenue_delta=0.0,
                recommendation="/new",
                update_params={},
                rationale="No review rows could be built; verify campaign setup and uploaded files.",
            )
        ]

    notes = (
        f"mode={mode}; metrics include ROAS, CTR (click-through rate), conversion rate, CPC, CPA/CPO, "
        "CAC (promo), AOV, and pre/post lift where equal-length pre windows exist in the export."
    )
    if mode == "manual" and not files:
        notes += " Manual mode received no files."
    if mode == "auto" and not datasets:
        notes += " Auto mode found no loadable datasets."

    next_review = review_scheduled_at_from_now(NEXT_REVIEW_INTERVAL_DAYS)
    # Sanitize nested metric dicts before building the report — Pydantic v2 model_dump_json()
    # raises on NaN/Inf ("Out of range float values are not JSON compliant").
    for r in reviews:
        r.pre_metrics = _sanitize_for_json(dict(r.pre_metrics or {}))
        r.post_metrics = _sanitize_for_json(dict(r.post_metrics or {}))

    report = CampaignReviewReport(
        operator_id=operator_id,
        review_date=utc_now_iso(),
        campaign_reviews=reviews,
        approval_status="pending",
        next_review_date=next_review,
    )
    out = _sanitize_for_json(report.model_dump(mode="python"))
    out["summary_metrics"] = _sanitize_for_json(summary)
    out["slot_attribution"] = _sanitize_for_json(slot_attribution)
    out["campaign_history"] = _sanitize_for_json(build_campaign_history_from_review(out))
    out["mode"] = mode
    out["notes"] = notes
    out["next_review_date"] = next_review

    out = _sanitize_for_json(out)

    path = _review_path(operator_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, allow_nan=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    oid = sys.argv[1] if len(sys.argv) > 1 else "dev_operator"
    print(json.dumps(run(oid), indent=2))
