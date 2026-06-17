"""Campaign-level Week-over-Week metrics (Promo + Ads) for Health Check."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Same metrics as Super App marketing summary / App2.0 campaign tables.
CAMPAIGN_METRICS = [
    "Orders",
    "Sales",
    "Spend",
    "ROAS",
    "Cost per Order",
    "Promo AOV",
    "Check After Promo",
]

CAMPAIGN_HTML_KEYS = {
    "Orders": "orders",
    "Sales": "sales",
    "Spend": "spend",
    "ROAS": "roas",
    "Cost per Order": "cpo",
    "Promo AOV": "promoAov",
    "Check After Promo": "check",
}

WOW_MERGE_KEYS = ["Campaign Type", "Campaign Name", "Store ID"]


def _safe_ratio(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return float(num) / float(den)


def _finite_float(val: Any, default: float = 0.0) -> float:
    """Coerce to float; NaN/inf/missing → default (``float(nan) or 0`` is still NaN)."""
    v = pd.to_numeric(val, errors="coerce")
    if pd.isna(v):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):  # NaN or inf
        return default
    return f


def _metric_int(val: Any) -> int:
    return int(round(_finite_float(val, 0.0)))


def derive_campaign_metrics(orders: float, sales: float, spend: float) -> dict[str, float]:
    """Compute derived marketing metrics from summed Orders / Sales / Spend."""
    orders = _finite_float(orders, 0.0)
    sales = _finite_float(sales, 0.0)
    spend = abs(_finite_float(spend, 0.0))
    promo_aov = _safe_ratio(sales, orders)
    cpo = _safe_ratio(spend, orders)
    return {
        "Orders": round(orders),
        "Sales": round(sales, 2),
        "Spend": round(spend, 2),
        "ROAS": round(_safe_ratio(sales, spend), 2),
        "Cost per Order": round(cpo, 2),
        "Promo AOV": round(promo_aov, 2),
        "Check After Promo": round(promo_aov - cpo, 2),
    }


def _week_label(start: date, end: date) -> str:
    return f"{start.month}/{start.day}-{end.month}/{end.day}"


def _wow_pct(delta: float, prior: float) -> Optional[float]:
    if prior == 0:
        return None
    return round(delta / abs(prior) * 100, 1)


def _campaign_status(sales_delta: float, roas_delta: float) -> tuple[str, str, str]:
    if sales_delta > 0 and roas_delta > 0:
        return "Improving", "Sales up and ROAS up", "No"
    if sales_delta < 0 and roas_delta < 0:
        return "Declining", "Sales down and ROAS down", "Yes"
    if sales_delta > 0 and roas_delta < 0:
        return "Mixed", "Sales up but ROAS down", "Yes"
    if sales_delta < 0 and roas_delta > 0:
        return "Mixed", "Sales down but ROAS up", "Yes"
    return "Flat", "Mixed or unchanged trend", "No"


def build_campaigns_wow_csv(
    week1_campaigns_csv: Path,
    week2_campaigns_csv: Path,
    week1_start: date,
    week1_end: date,
    week2_start: date,
    week2_end: date,
    output_path: Path,
    *,
    campaign_types: list[str] | None = None,
) -> Optional[Path]:
    """
    WoW per campaign (store × campaign). Outer-joins weeks so campaigns only in one week still appear.
    """
    w1 = pd.read_csv(week1_campaigns_csv)
    w2 = pd.read_csv(week2_campaigns_csv)
    if w1.empty and w2.empty:
        return None

    for frame in (w1, w2):
        for k in WOW_MERGE_KEYS + ["Store Name", "Promotion Type", "Self Serve", "Campaign Owner"]:
            if k not in frame.columns:
                frame[k] = ""
        for m in CAMPAIGN_METRICS:
            if m not in frame.columns:
                frame[m] = 0

    if campaign_types:
        w1 = w1[w1["Campaign Type"].isin(campaign_types)]
        w2 = w2[w2["Campaign Type"].isin(campaign_types)]

    merged = w2.merge(w1, on=WOW_MERGE_KEYS, how="outer", suffixes=("_week2", "_week1"))
    if merged.empty:
        return None

    w1_label = _week_label(week1_start, week1_end)
    w2_label = _week_label(week2_start, week2_end)

    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        out: dict[str, Any] = {
            "Campaign Type": row.get("Campaign Type", ""),
            "Campaign Name": row.get("Campaign Name", ""),
            "Store ID": row.get("Store ID", ""),
            "Store Name": row.get("Store Name_week2") or row.get("Store Name_week1") or "",
            "Promotion Type": row.get("Promotion Type_week2") or row.get("Promotion Type_week1") or "",
            "Campaign Owner": row.get("Campaign Owner_week2") or row.get("Campaign Owner_week1") or "",
        }

        sales_delta = 0.0
        roas_delta = 0.0
        for m in CAMPAIGN_METRICS:
            v2 = _finite_float(row.get(f"{m}_week2"), 0.0)
            v1 = _finite_float(row.get(f"{m}_week1"), 0.0)
            d = round(v2 - v1, 2)
            p = _wow_pct(d, v1)
            if m == "Sales":
                sales_delta = d
            elif m == "ROAS":
                roas_delta = d
            out[f"{m} ({w2_label})"] = round(v2, 2) if m != "Orders" else _metric_int(v2)
            out[f"{m} ({w1_label})"] = round(v1, 2) if m != "Orders" else _metric_int(v1)
            out[f"{m} WoW Δ"] = d if m != "Orders" else _metric_int(d)
            out[f"{m} WoW %"] = p

        status, reason, review = _campaign_status(sales_delta, roas_delta)
        out["Status"] = status
        out["Reason"] = reason
        out["Needs Review"] = review
        rows.append(out)

    if not rows:
        return None

    result = pd.DataFrame(rows)
    result = result.sort_values(
        by=["Campaign Type", "Sales WoW Δ"],
        ascending=[True, False],
        na_position="last",
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    logger.info("Campaign WoW CSV written: %s (%d rows)", output_path, len(result))
    return output_path


def _rollup_campaigns_by_name(df: pd.DataFrame) -> pd.DataFrame:
    rollup_keys = ["Campaign Type", "Campaign Name", "Promotion Type", "Self Serve", "Campaign Owner"]
    for k in rollup_keys + ["Orders", "Sales", "Spend"]:
        if k not in df.columns:
            df[k] = 0 if k in ("Orders", "Sales", "Spend") else ""

    rows = []
    for keys, grp in df.groupby(rollup_keys, dropna=False):
        key_map = dict(zip(rollup_keys, keys)) if isinstance(keys, tuple) else {rollup_keys[0]: keys}
        metrics = derive_campaign_metrics(
            float(grp["Orders"].sum()),
            float(grp["Sales"].sum()),
            float(grp["Spend"].sum()),
        )
        rows.append({**key_map, "Store ID": "ALL", "Store Name": "All stores", **metrics})
    return pd.DataFrame(rows)


def build_campaigns_wow_by_name_csv(
    week1_campaigns_csv: Path,
    week2_campaigns_csv: Path,
    week1_start: date,
    week1_end: date,
    week2_start: date,
    week2_end: date,
    output_path: Path,
) -> Optional[Path]:
    """Roll up store-level campaign CSVs to campaign-name totals, then WoW."""
    import tempfile

    w1 = pd.read_csv(week1_campaigns_csv)
    w2 = pd.read_csv(week2_campaigns_csv)
    if w1.empty or w2.empty:
        return None

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        w1_path = td_path / "w1.csv"
        w2_path = td_path / "w2.csv"
        _rollup_campaigns_by_name(w1).to_csv(w1_path, index=False)
        _rollup_campaigns_by_name(w2).to_csv(w2_path, index=False)
        return build_campaigns_wow_csv(
            w1_path,
            w2_path,
            week1_start,
            week1_end,
            week2_start,
            week2_end,
            output_path,
        )


def build_all_campaign_wow_outputs(
    week1_campaigns_csv: Path,
    week2_campaigns_csv: Path,
    week1_start: date,
    week1_end: date,
    week2_start: date,
    week2_end: date,
    output_dir: Path,
) -> dict[str, Optional[str]]:
    """Write combined, promo-only, ads-only, and by-name WoW CSVs."""
    output_dir = Path(output_dir)
    w1_tag = _week_label(week1_start, week1_end).replace("/", "")
    w2_tag = _week_label(week2_start, week2_end).replace("/", "")
    stem = f"wow_campaigns_{w1_tag}_vs_{w2_tag}"

    paths: dict[str, Optional[str]] = {}
    combined = build_campaigns_wow_csv(
        week1_campaigns_csv,
        week2_campaigns_csv,
        week1_start,
        week1_end,
        week2_start,
        week2_end,
        output_dir / f"{stem}.csv",
    )
    paths["wow_campaigns"] = str(combined) if combined else None

    promo = build_campaigns_wow_csv(
        week1_campaigns_csv,
        week2_campaigns_csv,
        week1_start,
        week1_end,
        week2_start,
        week2_end,
        output_dir / f"{stem}_promo.csv",
        campaign_types=["Promo"],
    )
    paths["wow_campaigns_promo"] = str(promo) if promo else None

    ads = build_campaigns_wow_csv(
        week1_campaigns_csv,
        week2_campaigns_csv,
        week1_start,
        week1_end,
        week2_start,
        week2_end,
        output_dir / f"{stem}_ads.csv",
        campaign_types=["Ads"],
    )
    paths["wow_campaigns_ads"] = str(ads) if ads else None

    by_name = build_campaigns_wow_by_name_csv(
        week1_campaigns_csv,
        week2_campaigns_csv,
        week1_start,
        week1_end,
        week2_start,
        week2_end,
        output_dir / f"{stem}_by_name.csv",
    )
    paths["wow_campaigns_by_name"] = str(by_name) if by_name else None
    return paths


def _load_wow_csv(path: Path | None) -> pd.DataFrame:
    if not path or not Path(path).is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


def build_campaign_slack_summary(
    *,
    promo_wow_csv: Path | None,
    ads_wow_csv: Path | None,
    week1_label: str,
    week2_label: str,
    operator_name: str,
    top_n: int = 5,
) -> str:
    """Compact Slack block for campaign WoW (top movers by sales Δ)."""
    lines = [f"*Campaign WoW — {operator_name}*", f"_{week1_label} → {week2_label}_"]

    for label, csv_path in (("Promo", promo_wow_csv), ("Ads", ads_wow_csv)):
        df = _load_wow_csv(csv_path)
        if df.empty:
            lines.append(f"\n*{label}:* no campaign data")
            continue
        delta_col = "Sales WoW Δ"
        if delta_col not in df.columns:
            continue
        df = df.copy()
        df[delta_col] = pd.to_numeric(df[delta_col], errors="coerce").fillna(0)
        up = df.nlargest(top_n, delta_col)
        down = df.nsmallest(top_n, delta_col)
        lines.append(f"\n*{label}* ({len(df)} campaigns)")
        if not up.empty:
            lines.append(f"Top {min(top_n, len(up))} sales ↑:")
            for _, r in up.iterrows():
                name = str(r.get("Campaign Name", ""))[:48]
                d = r.get(delta_col, 0)
                roas = r.get("ROAS WoW Δ", "—")
                lines.append(f"  • {name}: sales Δ {d:+,} | ROAS Δ {roas}")
        if not down.empty:
            lines.append(f"Top {min(top_n, len(down))} sales ↓:")
            for _, r in down.iterrows():
                name = str(r.get("Campaign Name", ""))[:48]
                d = r.get(delta_col, 0)
                lines.append(f"  • {name}: sales Δ {d:+,}")

    return "\n".join(lines)


def campaign_wow_for_html(
    promo_wow_csv: Path | None,
    ads_wow_csv: Path | None,
    *,
    top_n: int | None = None,
) -> dict[str, Any]:
    """Serialize campaign WoW rows for embedded HTML (all campaigns by default)."""
    out: dict[str, Any] = {"promo": [], "ads": [], "metrics": CAMPAIGN_METRICS}

    for platform_key, csv_path in (("promo", promo_wow_csv), ("ads", ads_wow_csv)):
        df = _load_wow_csv(csv_path)
        if df.empty:
            continue
        delta_col = "Sales WoW Δ"
        if delta_col not in df.columns:
            continue
        df = df.copy()
        df[delta_col] = pd.to_numeric(df[delta_col], errors="coerce").fillna(0)
        status_rank = {"Declining": 0, "Mixed": 1, "Flat": 2, "Improving": 3}
        df["_status_rank"] = df["Status"].map(lambda s: status_rank.get(str(s).strip(), 1.5))
        df = df.sort_values(by=["_status_rank", delta_col], ascending=[True, True])
        subset = df if top_n is None else df.head(top_n)
        rows = []
        for _, r in subset.iterrows():
            row = {
                "name": str(r.get("Campaign Name", "")),
                "storeId": str(r.get("Store ID", "")),
                "owner": str(r.get("Campaign Owner", "")),
                "status": str(r.get("Status", "")),
            }
            for m in CAMPAIGN_METRICS:
                metric_key = CAMPAIGN_HTML_KEYS[m]
                delta = pd.to_numeric(r.get(f"{m} WoW Δ"), errors="coerce")
                row[f"{metric_key}Delta"] = 0.0 if pd.isna(delta) else float(delta)
                row[f"{metric_key}Pct"] = r.get(f"{m} WoW %")
            rows.append(row)
        out[platform_key] = rows
    return out
