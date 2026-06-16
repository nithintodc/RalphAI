#!/usr/bin/env python3
"""DeepDive analyzer vs manual pandas pivots on bican sample data."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SAMPLE = ROOT / "sample_data" / "bican-sample-data"


def safe_sum(df: pd.DataFrame, col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())


def load_datasets() -> dict[str, pd.DataFrame]:
    ds: dict[str, pd.DataFrame] = {}
    fin = SAMPLE / "financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z"
    ds["financial_detailed"] = pd.read_csv(
        fin / "FINANCIAL_DETAILED_TRANSACTIONS_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv"
    )
    ds["financial_errors"] = pd.read_csv(
        fin / "FINANCIAL_ERROR_CHARGES_AND_ADJUSTMENTS_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv"
    )
    ds["financial_payouts"] = pd.read_csv(
        fin / "FINANCIAL_PAYOUT_SUMMARY_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv"
    )
    ds["sales_by_order"] = pd.read_csv(
        SAMPLE / "SALES_BY_ORDER_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.csv"
    )
    ds["sales_store_product"] = pd.read_csv(
        SAMPLE / "SALES_BY_STORE_2025-01-01_2026-06-03_NE9lv_2026-06-04T05-23-17Z.csv"
    )
    mkt = SAMPLE / "marketing_2025-01-01_2026-06-03_rdK2w_2026-06-04T05-23-55Z"
    ds["marketing_promotions"] = pd.read_csv(
        mkt / "MARKETING_PROMOTION_2025-01-01_2026-06-03_rdK2w_2026-06-04T05-23-55Z.csv"
    )
    ds["marketing_sponsored"] = pd.read_csv(
        mkt / "MARKETING_SPONSORED_LISTING_2025-01-01_2026-06-03_rdK2w_2026-06-04T05-23-55Z.csv"
    )
    ops = SAMPLE / "OPERATIONS_QUALITY_viewByStore_2025-01-01_2026-06-03_0KzEQ_2026-06-04T05-22-20Z"
    ds["ops_cancellations"] = pd.read_csv(
        ops / "OPERATIONS_QUALITY_viewByStore_cancellations_2025-01-01_2026-06-03_0KzEQ_2026-06-04T05-22-20Z.csv"
    )
    ds["ops_missing"] = pd.read_csv(
        ops / "OPERATIONS_QUALITY_viewByStore_missingAndIncorrect_2025-01-01_2026-06-03_0KzEQ_2026-06-04T05-22-20Z.csv"
    )
    return ds


def find_column(df: pd.DataFrame, variations: list[str]) -> str | None:
    for name in variations:
        if name in df.columns:
            return name
    lower_map = {c.strip().lower(): c for c in df.columns}
    for name in variations:
        hit = lower_map.get(name.strip().lower())
        if hit:
            return hit
    return None


def bool_true_count(df: pd.DataFrame, variations: list[str]) -> int:
    col = find_column(df, variations)
    if not col:
        return 0
    return int(df[col].astype(str).str.strip().str.lower().eq("true").sum())


def manual_financial(df: pd.DataFrame, payout_df: pd.DataFrame | None = None) -> dict:
    orders = df[df["Transaction type"] == "Order"].copy() if "Transaction type" in df.columns else df
    total_orders = len(orders)
    subtotal = safe_sum(orders, "Subtotal")
    net = safe_sum(payout_df, "Net total") if payout_df is not None and not payout_df.empty else safe_sum(df, "Net total")
    return {
        "total_orders": total_orders,
        "total_subtotal": round(subtotal, 2),
        "total_net_revenue": round(net, 2),
        "avg_order_value": round(subtotal / max(total_orders, 1), 2),
        "payout_ratio": round(net / max(subtotal, 0.01) * 100, 1),
    }


def manual_sales(df: pd.DataFrame) -> dict:
    n = len(df)
    cancelled = bool_true_count(df, ["Was Cancelled", "Is cancelled", "Is Cancelled", "Was cancelled"])
    dashpass = bool_true_count(df, ["Was Dashpass", "Was DashPass", "Is Dashpass", "Is DashPass", "DashPass"])
    missing = bool_true_count(df, [
        "Is Missing or Incorrect?", "Is missing or incorrect",
        "Is Missing or Incorrect", "Was Missing or Incorrect",
    ])
    subtotal = safe_sum(df, "Subtotal")
    return {
        "total_orders": n,
        "cancelled_orders": cancelled,
        "dashpass_orders": dashpass,
        "total_subtotal": round(subtotal, 2),
        "avg_order_value": round(subtotal / max(n, 1), 2),
        "cancellation_rate": round(cancelled / max(n, 1) * 100, 2),
        "dashpass_rate": round(dashpass / max(n, 1) * 100, 2),
        "missing_or_incorrect_count": missing,
        "error_rate": round(missing / max(n, 1) * 100, 2),
    }


def manual_marketing(promo: pd.DataFrame, sponsored: pd.DataFrame) -> dict:
    spend_col = "Customer discounts from marketing | (Funded by you)"
    promo_spend = abs(safe_sum(promo, spend_col))
    promo_sales = safe_sum(promo, "Sales")
    promo_orders = safe_sum(promo, "Orders")
    ad_spend = abs(safe_sum(sponsored, "Marketing fees | (including any applicable taxes)"))
    ad_sales = safe_sum(sponsored, "Sales")
    return {
        "promo_total_spend": round(promo_spend, 2),
        "promo_total_sales": round(promo_sales, 2),
        "promo_total_orders": round(promo_orders),
        "promo_roas": round(promo_sales / max(promo_spend, 0.01), 2),
        "sponsored_spend": round(ad_spend, 2),
        "sponsored_sales": round(ad_sales, 2),
        "combined_spend": round(promo_spend + ad_spend, 2),
    }


def compare(name: str, app_val, manual_val, tol: float = 0.01) -> dict:
    diff = round(float(app_val) - float(manual_val), 4)
    status = "DRIFT" if abs(diff) > tol else "OK"
    return {"name": name, "app": app_val, "manual": manual_val, "diff": diff, "status": status}


def main() -> None:
    from agents.deepdive.analyzer import analyze

    ds = load_datasets()
    result = analyze(ds, "bican")
    fin = result["sections"]["financial"]
    sales = result["sections"]["sales"]
    mkt = result["sections"]["marketing"]

    checks = []
    m_fin = manual_financial(ds["financial_detailed"], ds.get("financial_payouts"))
    for k in ["total_orders", "total_subtotal", "total_net_revenue", "avg_order_value", "payout_ratio"]:
        tol = 1 if "total" in k or "revenue" in k or "subtotal" in k else 0.1
        checks.append(compare(f"DeepDive financial {k}", fin.get(k, 0), m_fin[k], tol=tol))

    m_sales = manual_sales(ds["sales_by_order"])
    for k in [
        "total_orders",
        "cancelled_orders",
        "dashpass_orders",
        "total_subtotal",
        "avg_order_value",
        "cancellation_rate",
        "dashpass_rate",
        "missing_or_incorrect_count",
        "error_rate",
    ]:
        tol = 0.5 if "rate" in k else (1 if "total" in k or "subtotal" in k else 0)
        checks.append(compare(f"DeepDive sales {k}", sales.get(k, 0), m_sales[k], tol=tol))

    m_mkt = manual_marketing(ds["marketing_promotions"], ds["marketing_sponsored"])
    mkt_key_map = {
        "sponsored_spend": "sponsored_total_spend",
        "sponsored_sales": "sponsored_total_sales",
        "combined_spend": "combined_marketing_spend",
    }
    for k, v in m_mkt.items():
        app_key = mkt_key_map.get(k, k)
        checks.append(compare(f"DeepDive marketing {k}", mkt.get(app_key, 0), v, tol=1))

    fin = result["sections"]["financial"]
    if "financial_payouts" in ds:
        payout_net = float(ds["financial_payouts"]["Net total"].sum())
        checks.append(compare(
            "DeepDive financial total_net_revenue vs payout summary",
            fin.get("total_net_revenue", 0),
            payout_net,
            tol=0.01,
        ))

    # Ops: store cancellations sum
    ops_cancel = ds["ops_cancellations"]
    cancel_col = [c for c in ops_cancel.columns if "cancel" in c.lower() and "rate" not in c.lower()]
    if cancel_col:
        manual_cancels = safe_sum(ops_cancel, cancel_col[0])
        app_cancels = result["sections"]["operations"].get("total_cancellations", 0)
        checks.append(compare("DeepDive ops total_cancellations", app_cancels, manual_cancels, tol=10))

    out = {
        "checks": checks,
        "drift_count": sum(1 for c in checks if c["status"] == "DRIFT"),
        "ok_count": sum(1 for c in checks if c["status"] == "OK"),
    }
    out_path = SAMPLE / "CALC_AUDIT_DEEPDIVE.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
