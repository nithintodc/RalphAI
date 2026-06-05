"""Deterministic analysis for legacy contract pipeline — swap for LLM + metrics."""

from __future__ import annotations

from typing import Any


def _df_has_data(data: dict[str, Any], key: str) -> bool:
    """Return True if ``data[key]`` is a non-empty DataFrame or non-empty list."""
    val = data.get(key)
    if val is None:
        return False
    try:
        import pandas as pd
        if isinstance(val, pd.DataFrame):
            return not val.empty
    except ImportError:
        pass
    # Legacy list-of-dict or __dataframe serialised payload
    if isinstance(val, dict) and val.get("__dataframe"):
        return bool(val.get("records"))
    try:
        return len(val) > 0
    except TypeError:
        return False


def analyze_performance(data: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Return (insights, problems, opportunities).

    Handles two payload formats:
    - **New format**: ``data`` keys are DoorDash export category names
      (``financial_detailed``, ``marketing_promotions``, …) with ``pd.DataFrame`` values,
      as returned by ``doordash_client.fetch_operator_window``.
    - **Legacy format**: ``data`` keys are ``orders`` / ``revenue`` / ``ads`` / ``menu``
      as list-of-dict (the old stub shape, kept for backward-compat with old contracts).
    """
    insights: list[str] = []
    problems: list[str] = []
    opportunities: list[str] = []

    # --- detect which format we received ---
    has_financial = _df_has_data(data, "financial_detailed")
    has_marketing = _df_has_data(data, "marketing_promotions") or _df_has_data(data, "marketing_sponsored")
    has_sales = _df_has_data(data, "sales_by_order") or _df_has_data(data, "sales_by_time")
    # legacy
    has_legacy_orders = _df_has_data(data, "orders")
    has_legacy_revenue = _df_has_data(data, "revenue")

    has_any = has_financial or has_marketing or has_sales or has_legacy_orders or has_legacy_revenue

    if not has_any:
        insights.append("Insufficient recent order volume in window — prioritize traffic diagnostics.")
        problems.append("Low or missing transactional data for deep segmentation.")
        opportunities.append("Enable full export sync to unlock cohort and time-of-day analysis.")
        return insights, problems, opportunities

    # --- new-format analysis: derive KPIs from FINANCIAL_DETAILED ---
    if has_financial:
        try:
            import pandas as pd
            fin = data["financial_detailed"]
            if isinstance(fin, pd.DataFrame) and not fin.empty:
                order_mask = (
                    fin["Transaction type"] == "Order"
                    if "Transaction type" in fin.columns
                    else pd.Series(True, index=fin.index)
                )
                orders_df = fin.loc[order_mask]
                n_orders = len(orders_df)
                subtotal = (
                    pd.to_numeric(orders_df["Subtotal"], errors="coerce").sum()
                    if "Subtotal" in orders_df.columns
                    else 0.0
                )
                net = (
                    pd.to_numeric(orders_df["Net total"], errors="coerce").sum()
                    if "Net total" in orders_df.columns
                    else 0.0
                )
                aov = round(float(subtotal) / n_orders, 2) if n_orders > 0 else 0.0
                payout_ratio = round(float(net) / float(subtotal) * 100, 1) if float(subtotal) > 0 else 0.0

                insights.append(
                    f"Performance baseline: {n_orders:,} orders, AOV ${aov:.2f}, "
                    f"payout ratio {payout_ratio}%."
                )
                if payout_ratio > 0 and payout_ratio < 65:
                    problems.append(
                        f"Payout ratio {payout_ratio:.1f}% is below the 65% floor — "
                        "review commission structure and outstanding error charges."
                    )
                if payout_ratio >= 72:
                    opportunities.append(
                        "Payout ratio above 72% — headroom exists to scale sponsored listings "
                        "without margin risk."
                    )
            else:
                insights.append("Performance baseline established from ingested window.")
        except Exception:
            insights.append("Performance baseline established from ingested window.")
    else:
        insights.append("Performance baseline established from ingested window.")

    if not has_marketing:
        opportunities.append(
            "No active marketing campaigns detected — slot-level sponsored listings "
            "can grow new-customer acquisition."
        )
    else:
        insights.append("Active marketing campaigns detected. Run campaign_review to measure slot-level ROAS.")

    if has_sales:
        opportunities.append(
            "Sales-by-order data available — slot-level analysis can pinpoint peak acquisition windows "
            "for precise daypart targeting."
        )

    opportunities.append("Scale winning dayparts once slot-level campaign data stabilises.")
    return insights, problems, opportunities
