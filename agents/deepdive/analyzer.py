"""
DeepDive analyzer — processes all SSM dataset categories into structured insights.

Produces a dict-of-dicts result with:
  - executive_summary
  - financial (revenue, payouts, commissions, fees, daily trends)
  - sales (by order, by store, by time, product mix, customer segments)
  - marketing (promotions, sponsored listings, corporate vs TODC, ROAS)
  - operations (avoidable wait, cancellations, missing/incorrect items)
  - support (refund analysis, reasons breakdown)
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import numpy as np


def analyze(datasets: dict[str, pd.DataFrame], operator_id: str) -> dict[str, Any]:
    """Run all analysis modules and return consolidated results."""
    result: dict[str, Any] = {"operator_id": operator_id, "sections": {}}

    result["sections"]["financial"] = _analyze_financial(datasets)
    result["sections"]["sales"] = _analyze_sales(datasets)
    result["sections"]["marketing"] = _analyze_marketing(datasets)
    result["sections"]["operations"] = _analyze_operations(datasets)
    result["sections"]["support"] = _analyze_support(datasets)
    result["sections"]["executive_summary"] = _build_executive_summary(result["sections"])

    return result


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------

def _analyze_financial(ds: dict[str, pd.DataFrame]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # Detailed transactions
    df = ds.get("financial_detailed")
    if df is not None and not df.empty:
        df = df.copy()
        if "Timestamp local date" in df.columns:
            df["date"] = pd.to_datetime(df["Timestamp local date"], errors="coerce")
        orders = df[df["Transaction type"] == "Order"].copy() if "Transaction type" in df.columns else df

        result["total_orders"] = len(orders)
        result["total_subtotal"] = _safe_sum(orders, "Subtotal")
        result["total_net_revenue"] = _safe_sum(orders, "Net total")
        result["total_commission"] = _safe_sum(orders, "Commission")
        result["total_marketing_fees"] = _safe_sum(orders, "Marketing fees | (including any applicable taxes)")
        result["total_customer_discounts_funded_by_you"] = _safe_sum(orders, "Customer discounts from marketing | (funded by you)")
        result["avg_order_value"] = round(result["total_subtotal"] / max(result["total_orders"], 1), 2)
        result["avg_net_per_order"] = round(result["total_net_revenue"] / max(result["total_orders"], 1), 2)
        result["payout_ratio"] = round(result["total_net_revenue"] / max(result["total_subtotal"], 0.01) * 100, 1)

        # Daily revenue trend
        if "date" in orders.columns:
            daily = orders.groupby("date").agg(
                orders_count=("Subtotal", "count"),
                subtotal=("Subtotal", "sum"),
                net_total=("Net total", "sum"),
            ).reset_index().sort_values("date")
            daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
            result["daily_trend"] = daily.to_dict("records")

        # By store
        if "Store name" in orders.columns:
            store_agg = orders.groupby("Store name").agg(
                orders=("Subtotal", "count"),
                subtotal=("Subtotal", "sum"),
                net_total=("Net total", "sum"),
                commission=("Commission", "sum"),
            ).reset_index().sort_values("subtotal", ascending=False)
            store_agg["aov"] = (store_agg["subtotal"] / store_agg["orders"].clip(lower=1)).round(2)
            result["by_store"] = store_agg.to_dict("records")

        # By channel
        if "Channel" in orders.columns:
            channel = orders.groupby("Channel").agg(
                orders=("Subtotal", "count"),
                subtotal=("Subtotal", "sum"),
            ).reset_index().sort_values("subtotal", ascending=False)
            result["by_channel"] = channel.to_dict("records")

        # Monthly breakdown
        if "date" in orders.columns:
            orders["month"] = orders["date"].dt.to_period("M").astype(str)
            monthly = orders.groupby("month").agg(
                orders=("Subtotal", "count"),
                subtotal=("Subtotal", "sum"),
                net_total=("Net total", "sum"),
            ).reset_index()
            result["monthly_breakdown"] = monthly.to_dict("records")

    # Error charges & adjustments
    df_err = ds.get("financial_errors")
    if df_err is not None and not df_err.empty:
        result["total_error_charges"] = _safe_sum(df_err, "Error charges")
        result["total_adjustments"] = _safe_sum(df_err, "Adjustments")
        result["error_adjustment_count"] = len(df_err)
        if "Store name" in df_err.columns:
            err_by_store = df_err.groupby("Store name").agg(
                count=("Error charges", "count"),
                error_charges=("Error charges", "sum"),
                adjustments=("Adjustments", "sum"),
            ).reset_index().sort_values("error_charges", ascending=True)
            result["errors_by_store"] = err_by_store.to_dict("records")

    # Payout summary
    df_pay = ds.get("financial_payouts")
    if df_pay is not None and not df_pay.empty:
        result["payout_summary"] = {
            "total_net_payout": _safe_sum(df_pay, "Net total"),
            "total_commission": _safe_sum(df_pay, "Commission"),
            "total_marketing_fees": _safe_sum(df_pay, "Marketing fees | (including any applicable taxes)"),
            "payout_count": len(df_pay),
        }

    return result


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------

def _analyze_sales(ds: dict[str, pd.DataFrame]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # Sales by Order
    df = ds.get("sales_by_order")
    if df is not None and not df.empty:
        df = df.copy()
        result["total_orders"] = len(df)
        result["cancelled_orders"] = int(df["Was Cancelled"].astype(str).str.lower().eq("true").sum()) if "Was Cancelled" in df.columns else 0
        result["pickup_orders"] = int(df["Was Pickup"].astype(str).str.lower().eq("true").sum()) if "Was Pickup" in df.columns else 0
        result["dashpass_orders"] = int(df["Was Dashpass"].astype(str).str.lower().eq("true").sum()) if "Was Dashpass" in df.columns else 0
        result["total_subtotal"] = _safe_sum(df, "Subtotal")
        result["avg_order_value"] = round(result["total_subtotal"] / max(len(df), 1), 2)
        result["missing_or_incorrect_count"] = int(df["Is Missing or Incorrect?"].astype(str).str.lower().eq("true").sum()) if "Is Missing or Incorrect?" in df.columns else 0
        result["cancellation_rate"] = round(result["cancelled_orders"] / max(len(df), 1) * 100, 2)
        result["dashpass_rate"] = round(result["dashpass_orders"] / max(len(df), 1) * 100, 2)
        result["error_rate"] = round(result["missing_or_incorrect_count"] / max(len(df), 1) * 100, 2)

        # Rating distribution
        if "Rating" in df.columns:
            ratings = pd.to_numeric(df["Rating"], errors="coerce").dropna()
            if len(ratings) > 0:
                result["avg_rating"] = round(ratings.mean(), 2)
                result["rating_distribution"] = ratings.value_counts().sort_index().to_dict()
                result["rated_orders_pct"] = round(len(ratings) / len(df) * 100, 1)

        # By store
        if "Store Name" in df.columns:
            store = df.groupby("Store Name").agg(
                orders=("Subtotal", "count"),
                subtotal=("Subtotal", "sum"),
                total_commission=("Commission", "sum"),
            ).reset_index().sort_values("subtotal", ascending=False)
            store["aov"] = (store["subtotal"] / store["orders"].clip(lower=1)).round(2)
            result["by_store"] = store.to_dict("records")

        # Daily order volume
        if "Order Placed Date" in df.columns:
            df["date"] = pd.to_datetime(df["Order Placed Date"], errors="coerce")
            daily = df.groupby("date").agg(
                orders=("Subtotal", "count"),
                subtotal=("Subtotal", "sum"),
            ).reset_index().sort_values("date")
            daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
            result["daily_orders"] = daily.to_dict("records")

        # Day of week pattern
        if "date" in df.columns:
            df["dow"] = df["date"].dt.day_name()
            dow = df.groupby("dow").agg(orders=("Subtotal", "count"), subtotal=("Subtotal", "sum")).reset_index()
            dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dow["sort"] = dow["dow"].map({d: i for i, d in enumerate(dow_order)})
            dow = dow.sort_values("sort").drop(columns=["sort"])
            result["day_of_week"] = dow.to_dict("records")

    # Sales by Store (aggregate view)
    df_store = ds.get("sales_store_product")
    if df_store is not None and not df_store.empty:
        cols = ["Store Name", "Merchant Supplied ID", "Gross Sales", "Total Orders Including Cancelled Orders",
                "Total Delivered or Picked Up Orders", "AOV", "Total Commission",
                "Dashpass Sales", "Dashpass Orders", "Marketplace Classic Sales", "Marketplace Classic Orders"]
        available = [c for c in cols if c in df_store.columns]
        result["store_performance"] = df_store[available].to_dict("records")

    # Sales by Store - Customer counts
    df_cust = ds.get("sales_store_customers")
    if df_cust is not None and not df_cust.empty:
        cols = ["Store Name", "Merchant Supplied ID", "Gross Sales", "Total Delivered or Picked Up Orders",
                "New Customer Count", "Existing Customer Count",
                "Dashpass Customer Count", "Non-Dashpass Customer Count"]
        available = [c for c in cols if c in df_cust.columns]
        result["store_customers"] = df_cust[available].to_dict("records")

    # Sales by Time - daily aggregate
    df_time = ds.get("sales_time_product")
    if df_time is not None and not df_time.empty:
        df_time = df_time.copy()
        if "Start Date" in df_time.columns:
            df_time["date"] = pd.to_datetime(df_time["Start Date"], errors="coerce")
            time_data = df_time.sort_values("date")
            result["time_series_sales"] = time_data[["Start Date", "Gross Sales", "Total Orders Including Cancelled Orders",
                                                       "Total Delivered or Picked Up Orders", "AOV"]].to_dict("records") if all(c in time_data.columns for c in ["Gross Sales", "Total Orders Including Cancelled Orders"]) else []

    # Customer counts over time
    df_tc = ds.get("sales_time_customers")
    if df_tc is not None and not df_tc.empty:
        cols = ["Start Date", "Gross Sales", "New Customer Count", "Existing Customer Count",
                "Dashpass Customer Count", "Non-Dashpass Customer Count"]
        available = [c for c in cols if c in df_tc.columns]
        result["time_series_customers"] = df_tc[available].to_dict("records")

    return result


# ---------------------------------------------------------------------------
# Marketing
# ---------------------------------------------------------------------------

def _analyze_marketing(ds: dict[str, pd.DataFrame]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # Promotions
    df = ds.get("marketing_promotions")
    if df is not None and not df.empty:
        df = df.copy()
        result["promo_total_orders"] = _safe_sum(df, "Orders")
        result["promo_total_sales"] = _safe_sum(df, "Sales")
        spend_col = "Customer discounts from marketing | (Funded by you)"
        result["promo_total_spend"] = abs(_safe_sum(df, spend_col))
        result["promo_new_customers"] = _safe_sum(df, "New customers acquired")
        result["promo_existing_customers"] = _safe_sum(df, "Existing customers acquired")
        result["promo_roas"] = round(result["promo_total_sales"] / max(result["promo_total_spend"], 0.01), 2)
        result["promo_cost_per_order"] = round(result["promo_total_spend"] / max(result["promo_total_orders"], 1), 2)
        result["promo_cost_per_new_customer"] = round(result["promo_total_spend"] / max(result["promo_new_customers"], 1), 2)

        # Corporate vs TODC
        if "Is self serve campaign" in df.columns:
            df["segment"] = df["Is self serve campaign"].astype(str).str.lower().map(
                {"false": "Corporate", "true": "TODC"}
            ).fillna("Unknown")
            seg = df.groupby("segment").agg(
                orders=("Orders", "sum"),
                sales=("Sales", "sum"),
                spend=(spend_col, lambda x: abs(x.sum())),
                new_customers=("New customers acquired", "sum"),
            ).reset_index()
            seg["roas"] = (seg["sales"] / seg["spend"].clip(lower=0.01)).round(2)
            seg["cost_per_order"] = (seg["spend"] / seg["orders"].clip(lower=1)).round(2)
            result["corporate_vs_todc_promos"] = seg.to_dict("records")

        # By campaign
        if "Campaign name" in df.columns:
            camp = df.groupby("Campaign name").agg(
                orders=("Orders", "sum"),
                sales=("Sales", "sum"),
                spend=(spend_col, lambda x: abs(x.sum())),
                new_customers=("New customers acquired", "sum"),
            ).reset_index().sort_values("sales", ascending=False)
            camp["roas"] = (camp["sales"] / camp["spend"].clip(lower=0.01)).round(2)
            result["top_promo_campaigns"] = camp.head(15).to_dict("records")

        # Monthly promo trend
        if "Date" in df.columns:
            df["date"] = pd.to_datetime(df["Date"], errors="coerce")
            df["month"] = df["date"].dt.to_period("M").astype(str)
            monthly = df.groupby("month").agg(
                orders=("Orders", "sum"),
                sales=("Sales", "sum"),
                spend=(spend_col, lambda x: abs(x.sum())),
                new_customers=("New customers acquired", "sum"),
            ).reset_index()
            monthly["roas"] = (monthly["sales"] / monthly["spend"].clip(lower=0.01)).round(2)
            result["promo_monthly_trend"] = monthly.to_dict("records")

    # Sponsored Listings
    df_sp = ds.get("marketing_sponsored")
    if df_sp is not None and not df_sp.empty:
        df_sp = df_sp.copy()
        spend_col_sp = "Marketing fees | (including any applicable taxes)"
        result["sponsored_total_orders"] = _safe_sum(df_sp, "Orders")
        result["sponsored_total_sales"] = _safe_sum(df_sp, "Sales")
        result["sponsored_total_spend"] = abs(_safe_sum(df_sp, spend_col_sp))
        result["sponsored_impressions"] = _safe_sum(df_sp, "Impressions")
        result["sponsored_clicks"] = _safe_sum(df_sp, "Clicks")
        result["sponsored_roas"] = round(result["sponsored_total_sales"] / max(result["sponsored_total_spend"], 0.01), 2)
        result["sponsored_ctr"] = round(result["sponsored_clicks"] / max(result["sponsored_impressions"], 1) * 100, 2)
        result["sponsored_conversion_rate"] = round(result["sponsored_total_orders"] / max(result["sponsored_clicks"], 1) * 100, 2)

        # Corporate vs TODC for sponsored
        if "Is self serve campaign" in df_sp.columns:
            df_sp["segment"] = df_sp["Is self serve campaign"].astype(str).str.lower().map(
                {"false": "Corporate", "true": "TODC"}
            ).fillna("Unknown")
            seg_sp = df_sp.groupby("segment").agg(
                orders=("Orders", "sum"),
                sales=("Sales", "sum"),
                spend=(spend_col_sp, lambda x: abs(x.sum())),
                impressions=("Impressions", "sum"),
                clicks=("Clicks", "sum"),
            ).reset_index()
            seg_sp["roas"] = (seg_sp["sales"] / seg_sp["spend"].clip(lower=0.01)).round(2)
            seg_sp["ctr"] = (seg_sp["clicks"] / seg_sp["impressions"].clip(lower=1) * 100).round(2)
            result["corporate_vs_todc_sponsored"] = seg_sp.to_dict("records")

    # Combined marketing totals
    result["combined_marketing_spend"] = result.get("promo_total_spend", 0) + result.get("sponsored_total_spend", 0)
    result["combined_marketing_sales"] = result.get("promo_total_sales", 0) + result.get("sponsored_total_sales", 0)
    result["combined_marketing_roas"] = round(
        result["combined_marketing_sales"] / max(result["combined_marketing_spend"], 0.01), 2
    )

    return result


# ---------------------------------------------------------------------------
# Operations / Quality
# ---------------------------------------------------------------------------

def _analyze_operations(ds: dict[str, pd.DataFrame]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # Avoidable wait
    df_wait = ds.get("ops_avoidable_wait")
    if df_wait is not None and not df_wait.empty:
        result["total_orders_with_wait_data"] = len(df_wait)
        result["avg_avoidable_wait_min"] = round(pd.to_numeric(df_wait.get("Avoidable Wait Time", pd.Series(dtype=float)), errors="coerce").mean(), 2)
        result["avg_delivery_time_min"] = round(pd.to_numeric(df_wait.get("Total Delivery Time (ASAP Time)", pd.Series(dtype=float)), errors="coerce").mean(), 2)

        # By store
        if "Store Name" in df_wait.columns:
            wait_num = pd.to_numeric(df_wait["Avoidable Wait Time"], errors="coerce")
            delivery_num = pd.to_numeric(df_wait["Total Delivery Time (ASAP Time)"], errors="coerce")
            store_wait = df_wait.assign(
                wait=wait_num,
                delivery=delivery_num,
            ).groupby("Store Name").agg(
                orders=("wait", "count"),
                avg_wait=("wait", "mean"),
                avg_delivery=("delivery", "mean"),
                p90_wait=("wait", lambda x: x.quantile(0.9)),
            ).reset_index().round(2).sort_values("avg_wait", ascending=False)
            result["wait_by_store"] = store_wait.to_dict("records")

        # Wait time distribution (buckets)
        wait_vals = pd.to_numeric(df_wait.get("Avoidable Wait Time", pd.Series(dtype=float)), errors="coerce").dropna()
        if len(wait_vals) > 0:
            bins = [0, 2, 5, 10, 15, 20, float("inf")]
            labels = ["0-2min", "2-5min", "5-10min", "10-15min", "15-20min", "20+min"]
            dist = pd.cut(wait_vals, bins=bins, labels=labels).value_counts().sort_index()
            result["wait_distribution"] = dist.to_dict()

    # Cancellations
    df_cancel = ds.get("ops_cancelled")
    if df_cancel is not None and not df_cancel.empty:
        result["total_cancellations"] = len(df_cancel)

        if "Cancellation Category - Short" in df_cancel.columns:
            cat = df_cancel["Cancellation Category - Short"].value_counts()
            result["cancellation_reasons"] = cat.to_dict()

        if "Paid" in df_cancel.columns:
            paid = df_cancel["Paid"].astype(str).str.lower().eq("true").sum()
            result["cancellations_paid"] = int(paid)
            result["cancellations_unpaid"] = len(df_cancel) - int(paid)

        if "Store Name" in df_cancel.columns:
            by_store = df_cancel.groupby("Store Name").size().reset_index(name="cancellations").sort_values("cancellations", ascending=False)
            result["cancellations_by_store"] = by_store.to_dict("records")

    # Missing / Incorrect
    df_mi = ds.get("ops_missing_incorrect")
    if df_mi is not None and not df_mi.empty:
        result["total_error_items"] = len(df_mi)
        result["total_error_charges"] = _safe_sum(df_mi, "Error Charge")

        if "Error Category" in df_mi.columns:
            cats = df_mi["Error Category"].value_counts()
            result["error_categories"] = cats.to_dict()

        if "Menu Category" in df_mi.columns:
            menu = df_mi.groupby("Menu Category").agg(
                count=("Error Charge", "count"),
                total_charge=("Error Charge", "sum"),
            ).reset_index().sort_values("count", ascending=False)
            result["errors_by_menu_category"] = menu.head(15).to_dict("records")

        if "Item Name" in df_mi.columns:
            items = df_mi.groupby("Item Name").agg(
                count=("Error Charge", "count"),
                total_charge=("Error Charge", "sum"),
            ).reset_index().sort_values("count", ascending=False)
            result["top_error_items"] = items.head(15).to_dict("records")

        if "Store Name" in df_mi.columns:
            store_err = df_mi.groupby("Store Name").agg(
                error_count=("Error Charge", "count"),
                total_charge=("Error Charge", "sum"),
            ).reset_index().sort_values("error_count", ascending=False)
            result["errors_by_store"] = store_err.to_dict("records")

    return result


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------

def _analyze_support(ds: dict[str, pd.DataFrame]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    df = ds.get("support")
    if df is None or df.empty:
        return result

    result["total_support_cases"] = len(df)

    if "Primary reason" in df.columns:
        primary = df["Primary reason"].value_counts()
        result["primary_reasons"] = primary.to_dict()

    if "Secondary reason" in df.columns:
        secondary = df["Secondary reason"].value_counts()
        result["secondary_reasons"] = secondary.head(10).to_dict()

    if "Party responsible for refund" in df.columns:
        party = df["Party responsible for refund"].value_counts()
        result["responsible_party"] = party.to_dict()

    if "Original order value" in df.columns:
        result["total_original_order_value"] = _safe_sum(df, "Original order value")
    if "$ Order value to refund to customer" in df.columns:
        result["total_refund_to_customer"] = _safe_sum(df, "$ Order value to refund to customer")
    if "Total refund to store" in df.columns:
        result["total_refund_to_store"] = _safe_sum(df, "Total refund to store")

    if "Full order refund to customer?" in df.columns:
        full_refunds = df["Full order refund to customer?"].astype(str).str.lower().eq("yes").sum()
        result["full_refund_pct"] = round(full_refunds / max(len(df), 1) * 100, 1)

    if "Store name" in df.columns:
        store = df.groupby("Store name").size().reset_index(name="cases").sort_values("cases", ascending=False)
        result["support_by_store"] = store.to_dict("records")

    # Monthly trend
    if "Refund creation date" in df.columns:
        df = df.copy()
        df["date"] = pd.to_datetime(df["Refund creation date"], errors="coerce")
        df["month"] = df["date"].dt.to_period("M").astype(str)
        monthly = df.groupby("month").size().reset_index(name="cases")
        result["monthly_support_trend"] = monthly.to_dict("records")

    return result


# ---------------------------------------------------------------------------
# Executive Summary
# ---------------------------------------------------------------------------

def _build_executive_summary(sections: dict[str, Any]) -> dict[str, Any]:
    fin = sections.get("financial", {})
    sales = sections.get("sales", {})
    mkt = sections.get("marketing", {})
    ops = sections.get("operations", {})
    sup = sections.get("support", {})

    summary: dict[str, Any] = {}

    # Key headline numbers
    summary["total_revenue"] = fin.get("total_subtotal", 0)
    summary["total_net_payout"] = fin.get("total_net_revenue", 0)
    summary["total_orders"] = fin.get("total_orders", 0)
    summary["avg_order_value"] = fin.get("avg_order_value", 0)
    summary["payout_ratio_pct"] = fin.get("payout_ratio", 0)

    summary["dashpass_rate_pct"] = sales.get("dashpass_rate", 0)
    summary["cancellation_rate_pct"] = sales.get("cancellation_rate", 0)
    summary["error_rate_pct"] = sales.get("error_rate", 0)

    summary["total_marketing_spend"] = mkt.get("combined_marketing_spend", 0)
    summary["marketing_roas"] = mkt.get("combined_marketing_roas", 0)
    summary["new_customers_acquired"] = mkt.get("promo_new_customers", 0)

    summary["total_cancellations"] = ops.get("total_cancellations", 0)
    summary["avg_avoidable_wait_min"] = ops.get("avg_avoidable_wait_min", 0)
    summary["total_support_cases"] = sup.get("total_support_cases", 0)

    # Insights
    insights = []
    if summary["payout_ratio_pct"] > 0:
        insights.append(f"Net payout ratio is {summary['payout_ratio_pct']}% — every $1 in sales yields ${summary['payout_ratio_pct']/100:.2f} net.")
    if summary["dashpass_rate_pct"] > 50:
        insights.append(f"DashPass orders dominate at {summary['dashpass_rate_pct']}% — loyalty base is strong.")
    elif summary["dashpass_rate_pct"] > 0:
        insights.append(f"DashPass penetration is {summary['dashpass_rate_pct']}% — room to grow subscription orders.")
    if summary["cancellation_rate_pct"] > 3:
        insights.append(f"Cancellation rate of {summary['cancellation_rate_pct']}% is elevated — investigate root causes.")
    if summary["marketing_roas"] > 0:
        insights.append(f"Combined marketing ROAS is {summary['marketing_roas']}x — ${summary['total_marketing_spend']:,.0f} spend drove ${mkt.get('combined_marketing_sales', 0):,.0f} in sales.")
    if summary["avg_avoidable_wait_min"] and summary["avg_avoidable_wait_min"] > 5:
        insights.append(f"Average avoidable wait is {summary['avg_avoidable_wait_min']} min — consider prep workflow improvements.")
    if summary["total_support_cases"] > 0:
        insights.append(f"{summary['total_support_cases']} support/refund cases in period.")

    summary["insights"] = insights
    return summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_sum(df: pd.DataFrame, col: str) -> float:
    if col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").sum())


# Legacy compatibility
def analyze_rows(rows: list[dict], operator_id: str):
    """Legacy stub — kept for backwards compat with old import."""
    from shared.models.report import DeepDiveReport, OrderBreakdown, RevenueMetrics
    from shared.utils.date_helpers import utc_now_iso
    return DeepDiveReport(
        operator_id=operator_id,
        analysis_date=utc_now_iso(),
        order_breakdown=OrderBreakdown(),
        revenue_metrics=RevenueMetrics(),
        recommendations_seed="Use analyze() with SSM datasets for full analysis.",
    )
