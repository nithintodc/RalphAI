"""
Headless runner for DeepDive analysis — 3-month financial + marketing pivot analysis.
Reuses cloud_app CSV parsing modules via dummy-streamlit pattern (same approach as ralph_runner.py).
"""

from __future__ import annotations

import importlib
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Dummy Streamlit (cloud_app modules import `streamlit` at module level)
# Duplicated from ralph_runner.py to avoid cross-agent imports.
# ---------------------------------------------------------------------------

_STREAMLIT_DUMMY: Any | None = None


class _SessionState(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item) from None

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _build_dummy_streamlit_module() -> Any:
    import types
    from contextlib import contextmanager

    dummy = types.SimpleNamespace()
    dummy.session_state = _SessionState()
    dummy.secrets = {}

    def _no_op(*_a: Any, **_k: Any) -> None:
        return None

    dummy.error = _no_op
    dummy.warning = _no_op
    dummy.success = _no_op
    dummy.info = _no_op
    dummy.markdown = _no_op
    dummy.write = _no_op
    dummy.code = _no_op

    def cache_data_decorator(func=None, **_kwargs):
        if func is None:
            return lambda f: f
        return func

    dummy.cache_data = cache_data_decorator

    @contextmanager
    def spinner(_text: str):
        yield

    dummy.spinner = spinner
    dummy.set_page_config = _no_op
    dummy.sidebar = types.SimpleNamespace()
    dummy.expander = lambda *_a, **_k: types.SimpleNamespace(
        __enter__=lambda s: s, __exit__=lambda *_: False
    )
    dummy.multiselect = lambda *_a, **_k: []
    dummy.button = lambda *_a, **_k: False
    dummy.rerun = _no_op
    return dummy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_to_records(df: pd.DataFrame | None, max_rows: int = 400) -> dict[str, Any]:
    if df is None or (hasattr(df, "empty") and df.empty):
        return {"columns": [], "rows": []}
    d = df.reset_index()
    if len(d) > max_rows:
        d = d.head(max_rows)
    cols = [str(c) for c in d.columns]
    rows: list[dict[str, Any]] = []
    for _, row in d.iterrows():
        rec: dict[str, Any] = {}
        for c in d.columns:
            v = row[c]
            if pd.isna(v):
                rec[str(c)] = None
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[str(c)] = None
            else:
                rec[str(c)] = v.item() if hasattr(v, "item") else v
        rows.append(rec)
    return {"columns": cols, "rows": rows}


def _parse_date_range(date_range: str) -> tuple[str, str]:
    if not date_range or not str(date_range).strip():
        raise ValueError("Invalid date range format. Expected MM/DD/YYYY-MM/DD/YYYY")
    s = str(date_range).strip()
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})", s)
    if not m:
        raise ValueError("Invalid date range format. Expected MM/DD/YYYY-MM/DD/YYYY")
    start, end = m.group(1).strip(), m.group(2).strip()
    start_dt = datetime.strptime(start, "%m/%d/%Y")
    end_dt = datetime.strptime(end, "%m/%d/%Y")
    if start_dt > end_dt:
        raise ValueError("Start date must be <= end date")
    return start_dt.strftime("%m/%d/%Y"), end_dt.strftime("%m/%d/%Y")


def _parse_excluded_dates(excluded_dates_text: str) -> list:
    if not excluded_dates_text or not excluded_dates_text.strip():
        return []
    dates = []
    for p in [x.strip() for x in excluded_dates_text.split(",") if x.strip()]:
        dt = datetime.strptime(p, "%m/%d/%Y")
        dates.append(dt.date())
    return dates


def _resolve_marketing_folder(base: Path) -> Path:
    def _has_marketing_subdirs(p: Path) -> bool:
        if not p.is_dir():
            return False
        return any(x.is_dir() and x.name.startswith("marketing_") for x in p.iterdir())

    if _has_marketing_subdirs(base):
        return base
    for child in sorted(base.iterdir()):
        if child.is_dir() and _has_marketing_subdirs(child):
            return child
    return base


def _cloud_app_dir() -> Path:
    return Path(__file__).resolve().parent / "cloud_app"


# ---------------------------------------------------------------------------
# Normalize raw data into a common schema
# ---------------------------------------------------------------------------


def _normalize_dd_raw(df: pd.DataFrame, utils_mod: Any) -> pd.DataFrame:
    """Normalize DoorDash raw DataFrame to: Date, Store ID, Sales, Payouts, Order_ID, Platform."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    # Find date column
    date_col = utils_mod.find_date_column(df, utils_mod.DD_DATE_COLUMN_VARIATIONS)
    if date_col is None:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    # Store ID
    store_col = "Merchant store ID" if "Merchant store ID" in df.columns else "Store ID"
    if store_col not in df.columns:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    # Sales
    sales_col = "Subtotal"
    if sales_col not in df.columns:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    # Payouts
    payout_col = None
    if "Net total" in df.columns:
        payout_col = "Net total"
    elif "Net total (for historical reference only)" in df.columns:
        payout_col = "Net total (for historical reference only)"

    # Order ID
    order_col = "DoorDash order ID" if "DoorDash order ID" in df.columns else None

    out = pd.DataFrame()
    out["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    out["Store ID"] = df[store_col].astype(str)
    out["Sales"] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    out["Payouts"] = pd.to_numeric(df[payout_col], errors="coerce").fillna(0) if payout_col else 0
    out["Order_ID"] = df[order_col].astype(str) if order_col else ""
    out["Platform"] = "DoorDash"
    return out.dropna(subset=["Date"])


def _normalize_ue_raw(df: pd.DataFrame, utils_mod: Any) -> pd.DataFrame:
    """Normalize UberEats raw DataFrame to: Date, Store ID, Sales, Payouts, Order_ID, Platform."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    # Date is already parsed by filter_master_file_by_date_range (column index 8)
    # Find the actual date column (the one that was parsed)
    date_col = None
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            date_col = c
            break
    if date_col is None and len(df.columns) > 8:
        date_col = df.columns[8]

    if date_col is None:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    # Store ID
    df_norm, store_col = utils_mod.normalize_store_id_column(df)
    if store_col is None:
        return pd.DataFrame(columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"])

    sales_col = "Sales (excl. tax)" if "Sales (excl. tax)" in df_norm.columns else None
    payout_col = "Total payout" if "Total payout" in df_norm.columns else None
    order_col = "Order ID" if "Order ID" in df_norm.columns else None

    out = pd.DataFrame()
    out["Date"] = pd.to_datetime(df_norm[date_col], errors="coerce")
    out["Store ID"] = df_norm[store_col].astype(str)
    out["Sales"] = pd.to_numeric(df_norm[sales_col], errors="coerce").fillna(0) if sales_col else 0
    out["Payouts"] = pd.to_numeric(df_norm[payout_col], errors="coerce").fillna(0) if payout_col else 0
    out["Order_ID"] = df_norm[order_col].astype(str) if order_col else ""
    out["Platform"] = "UberEats"
    return out.dropna(subset=["Date"])


# ---------------------------------------------------------------------------
# Pivot analyses
# ---------------------------------------------------------------------------


def _daily_trend(combined: pd.DataFrame) -> pd.DataFrame:
    """Sales, payouts, orders by date."""
    if combined.empty:
        return pd.DataFrame(columns=["Date", "Sales", "Payouts", "Orders"])
    daily = combined.groupby(combined["Date"].dt.date).agg(
        Sales=("Sales", "sum"),
        Payouts=("Payouts", "sum"),
        Orders=("Order_ID", "nunique"),
    ).reset_index()
    daily["Date"] = pd.to_datetime(daily["Date"])
    return daily.sort_values("Date")


def _weekly_trend(combined: pd.DataFrame) -> pd.DataFrame:
    """Sales, payouts, orders aggregated by ISO week."""
    if combined.empty:
        return pd.DataFrame(columns=["Week", "Sales", "Payouts", "Orders"])
    df = combined.copy()
    df["Week"] = df["Date"].dt.isocalendar().week.astype(int)
    df["Year"] = df["Date"].dt.isocalendar().year.astype(int)
    weekly = df.groupby(["Year", "Week"]).agg(
        Sales=("Sales", "sum"),
        Payouts=("Payouts", "sum"),
        Orders=("Order_ID", "nunique"),
    ).reset_index()
    weekly["Week_Label"] = weekly["Year"].astype(str) + "-W" + weekly["Week"].astype(str).str.zfill(2)
    return weekly.sort_values(["Year", "Week"]).drop(columns=["Year", "Week"]).rename(columns={"Week_Label": "Week"})


def _day_of_week_avg(daily: pd.DataFrame) -> pd.DataFrame:
    """Average performance by day of week."""
    if daily.empty:
        return pd.DataFrame(columns=["Day", "Avg_Sales", "Avg_Payouts", "Avg_Orders"])
    df = daily.copy()
    df["DayNum"] = pd.to_datetime(df["Date"]).dt.dayofweek
    df["Day"] = pd.to_datetime(df["Date"]).dt.day_name()
    agg = df.groupby(["DayNum", "Day"]).agg(
        Avg_Sales=("Sales", "mean"),
        Avg_Payouts=("Payouts", "mean"),
        Avg_Orders=("Orders", "mean"),
    ).reset_index().sort_values("DayNum").drop(columns=["DayNum"])
    agg["Avg_Sales"] = agg["Avg_Sales"].round(2)
    agg["Avg_Payouts"] = agg["Avg_Payouts"].round(2)
    agg["Avg_Orders"] = agg["Avg_Orders"].round(1)
    return agg


def _store_ranking(combined: pd.DataFrame) -> pd.DataFrame:
    """Stores ranked by total sales."""
    if combined.empty:
        return pd.DataFrame(columns=["Store ID", "Platform", "Sales", "Payouts", "Orders"])
    ranked = combined.groupby(["Store ID", "Platform"]).agg(
        Sales=("Sales", "sum"),
        Payouts=("Payouts", "sum"),
        Orders=("Order_ID", "nunique"),
    ).reset_index().sort_values("Sales", ascending=False)
    ranked["Sales"] = ranked["Sales"].round(2)
    ranked["Payouts"] = ranked["Payouts"].round(2)
    return ranked


def _monthly_comparison(combined: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month totals with deltas."""
    if combined.empty:
        return pd.DataFrame(columns=["Month", "Sales", "Payouts", "Orders", "Sales_Delta", "Sales_Delta_Pct"])
    df = combined.copy()
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    monthly = df.groupby("Month").agg(
        Sales=("Sales", "sum"),
        Payouts=("Payouts", "sum"),
        Orders=("Order_ID", "nunique"),
    ).reset_index().sort_values("Month")

    monthly["Sales_Delta"] = monthly["Sales"].diff()
    monthly["Sales_Delta_Pct"] = monthly["Sales"].pct_change().mul(100).round(1)
    monthly["Payouts_Delta"] = monthly["Payouts"].diff()
    monthly["Orders_Delta"] = monthly["Orders"].diff()
    monthly["Sales"] = monthly["Sales"].round(2)
    monthly["Payouts"] = monthly["Payouts"].round(2)
    monthly["Sales_Delta"] = monthly["Sales_Delta"].round(2)
    monthly["Payouts_Delta"] = monthly["Payouts_Delta"].round(2)
    return monthly


def _marketing_breakdown(
    data_root: Path,
    start_date: str,
    end_date: str,
    excluded_dates: list,
    marketing_analysis: Any,
) -> pd.DataFrame | None:
    """Corporate vs TODC marketing breakdown using promotion + sponsored data."""
    mkt_folder = _resolve_marketing_folder(data_root)
    try:
        _, _, combined_table = marketing_analysis.create_corporate_vs_todc_table(
            excluded_dates=excluded_dates,
            pre_start_date=start_date,
            pre_end_date=end_date,
            post_start_date=start_date,
            post_end_date=end_date,
            marketing_folder_path=mkt_folder,
        )
        if combined_table is not None and not combined_table.empty:
            # Rename index values for clarity
            rename_map = {True: "TODC", False: "Corporate", "True": "TODC", "False": "Corporate"}
            combined_table.index = [rename_map.get(idx, idx) for idx in combined_table.index]
        return combined_table
    except Exception:
        return None


def _new_customer_trend(
    data_root: Path,
    start_date: str,
    end_date: str,
    excluded_dates: list,
    marketing_analysis: Any,
) -> pd.DataFrame:
    """New customers acquired by month from promotion CSVs."""
    mkt_folder = _resolve_marketing_folder(data_root)
    try:
        marketing_dirs = marketing_analysis.find_marketing_folders(mkt_folder)
    except Exception:
        return pd.DataFrame(columns=["Month", "New_Customers"])

    all_data: list[pd.DataFrame] = []
    for mdir in marketing_dirs:
        promo_file = marketing_analysis.get_marketing_file_path(mdir, "PROMOTION")
        if not promo_file or not promo_file.exists():
            continue
        try:
            df = pd.read_csv(promo_file, encoding="utf-8-sig")
            df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]

            # Find new customers column (case-insensitive)
            nc_col = None
            for c in df.columns:
                if "new customers acquired" in c.lower():
                    nc_col = c
                    break
            if nc_col is None:
                continue

            # Find date column
            date_col = None
            for c in df.columns:
                if c.lower() in ("date", "day"):
                    date_col = c
                    break
            if date_col is None:
                continue

            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])
            df[nc_col] = pd.to_numeric(df[nc_col], errors="coerce").fillna(0)

            # Filter to date range
            s = pd.to_datetime(start_date, format="%m/%d/%Y")
            e = pd.to_datetime(end_date, format="%m/%d/%Y")
            df = df[(df[date_col] >= s) & (df[date_col] <= e)]

            if not df.empty:
                sub = pd.DataFrame({"Date": df[date_col], "New_Customers": df[nc_col]})
                all_data.append(sub)
        except Exception:
            continue

    if not all_data:
        return pd.DataFrame(columns=["Month", "New_Customers"])

    combined = pd.concat(all_data, ignore_index=True)
    combined["Month"] = combined["Date"].dt.to_period("M").astype(str)
    monthly = combined.groupby("Month")["New_Customers"].sum().reset_index().sort_values("Month")
    monthly["New_Customers"] = monthly["New_Customers"].astype(int)
    return monthly


# ---------------------------------------------------------------------------
# Insights generation
# ---------------------------------------------------------------------------


def _generate_insights(
    daily: pd.DataFrame,
    stores: pd.DataFrame,
    dow: pd.DataFrame,
    monthly: pd.DataFrame,
    marketing: pd.DataFrame | None,
    nc_trend: pd.DataFrame,
) -> list[str]:
    insights: list[str] = []

    # 1. Overall trend direction
    if len(daily) >= 7:
        try:
            x = np.arange(len(daily))
            slope = np.polyfit(x, daily["Sales"].values, 1)[0]
            direction = "upward" if slope > 0 else "downward"
            insights.append(f"Overall sales trend is {direction} (${slope:+,.0f}/day over {len(daily)} days).")
        except Exception:
            pass

    # 2. Total period summary
    if not daily.empty:
        total_sales = daily["Sales"].sum()
        total_orders = daily["Orders"].sum()
        avg_daily_sales = daily["Sales"].mean()
        insights.append(
            f"Period totals: ${total_sales:,.0f} sales across {total_orders:,} orders "
            f"(avg ${avg_daily_sales:,.0f}/day)."
        )

    # 3. Top / bottom stores
    if len(stores) >= 2:
        top = stores.head(3)
        top_names = [f"{r['Store ID']} (${r['Sales']:,.0f})" for _, r in top.iterrows()]
        insights.append(f"Top stores by sales: {', '.join(top_names)}.")
        if len(stores) >= 4:
            bottom = stores.tail(3)
            bottom_names = [f"{r['Store ID']} (${r['Sales']:,.0f})" for _, r in bottom.iterrows()]
            insights.append(f"Bottom stores by sales: {', '.join(bottom_names)}.")

    # 4. Best / worst days of week
    if not dow.empty and "Avg_Sales" in dow.columns:
        best_row = dow.loc[dow["Avg_Sales"].idxmax()]
        worst_row = dow.loc[dow["Avg_Sales"].idxmin()]
        insights.append(
            f"Best day: {best_row['Day']} (avg ${best_row['Avg_Sales']:,.0f}). "
            f"Worst: {worst_row['Day']} (avg ${worst_row['Avg_Sales']:,.0f})."
        )

    # 5. Month-over-month change
    if len(monthly) >= 2:
        last = monthly.iloc[-1]
        delta_pct = last.get("Sales_Delta_Pct", 0)
        if pd.notna(delta_pct):
            insights.append(f"Latest month-over-month sales change: {delta_pct:+.1f}%.")

    # 6. Marketing efficiency
    if marketing is not None and not marketing.empty and "ROAS" in marketing.columns:
        total_spend = marketing["Spend"].sum()
        total_mkt_sales = marketing["Sales"].sum()
        overall_roas = total_mkt_sales / total_spend if total_spend > 0 else 0
        insights.append(f"Marketing: ${total_spend:,.0f} spend, ${total_mkt_sales:,.0f} sales, ROAS {overall_roas:.2f}x.")

    # 7. New customer trend
    if not nc_trend.empty:
        total_nc = nc_trend["New_Customers"].sum()
        insights.append(f"New customers acquired in period: {total_nc:,}.")

    # 8. Anomaly detection
    if len(daily) >= 14:
        mean_sales = daily["Sales"].mean()
        std_sales = daily["Sales"].std()
        if std_sales > 0:
            anomalies = daily[
                (daily["Sales"] > mean_sales + 2 * std_sales)
                | (daily["Sales"] < mean_sales - 2 * std_sales)
            ]
            if len(anomalies) > 0:
                dates = anomalies["Date"].dt.strftime("%m/%d").tolist()
                insights.append(f"Anomaly days ({len(anomalies)}): {', '.join(dates[:5])}.")

    if not insights:
        insights.append("DeepDive analysis complete. Upload more data for richer insights.")

    return insights


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------


def _write_excel(tables: dict[str, pd.DataFrame], insights: list[str]) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in tables.items():
            if df is not None and not df.empty:
                df.to_excel(writer, sheet_name=sheet_name[:31], index=True)
        # Insights sheet
        insights_df = pd.DataFrame({"Insight": insights})
        insights_df.to_excel(writer, sheet_name="Insights", index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeepDiveInputs:
    date_range: str  # MM/DD/YYYY-MM/DD/YYYY (full 3-month span)
    operator_name: str = ""
    excluded_dates_text: str = ""


def generate_deepdive_bundle(
    inputs: DeepDiveInputs,
    *,
    data_root: Path,
) -> dict[str, Any]:
    """
    Run full DeepDive pivot analysis on 3-month financial + marketing data.

    Returns keys: excel_bytes, filename, summary_text, insights, tables.
    """
    global _STREAMLIT_DUMMY

    if _STREAMLIT_DUMMY is None:
        _STREAMLIT_DUMMY = _build_dummy_streamlit_module()
    dummy_st = _STREAMLIT_DUMMY
    dummy_st.session_state = _SessionState()
    sys.modules["streamlit"] = dummy_st  # type: ignore[assignment]

    app_dir = _cloud_app_dir()
    sys.path.insert(0, str(app_dir))

    try:
        utils = importlib.import_module("utils")
        marketing_analysis = importlib.import_module("marketing_analysis")

        start_date, end_date = _parse_date_range(inputs.date_range)
        excluded_dates = _parse_excluded_dates(inputs.excluded_dates_text)
        operator_name = inputs.operator_name.strip() or "operator"

        dd_path = data_root / "dd-data.csv"
        ue_path = data_root / "ue-data.csv"

        # Load raw filtered DataFrames
        frames: list[pd.DataFrame] = []

        if dd_path.is_file():
            dd_raw = utils.filter_master_file_by_date_range(
                dd_path, start_date, end_date, utils.DD_DATE_COLUMN_VARIATIONS, excluded_dates
            )
            dd_norm = _normalize_dd_raw(dd_raw, utils)
            if not dd_norm.empty:
                frames.append(dd_norm)

        if ue_path.is_file():
            ue_raw = utils.filter_master_file_by_date_range(
                ue_path, start_date, end_date, utils.UE_DATE_COLUMN_VARIATIONS, excluded_dates
            )
            ue_norm = _normalize_ue_raw(ue_raw, utils)
            if not ue_norm.empty:
                frames.append(ue_norm)

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["Date", "Store ID", "Sales", "Payouts", "Order_ID", "Platform"]
        )

        # Run pivots
        daily = _daily_trend(combined)
        weekly = _weekly_trend(combined)
        dow = _day_of_week_avg(daily)
        stores = _store_ranking(combined)
        monthly = _monthly_comparison(combined)
        marketing = _marketing_breakdown(data_root, start_date, end_date, excluded_dates, marketing_analysis)
        nc_trend = _new_customer_trend(data_root, start_date, end_date, excluded_dates, marketing_analysis)

        # Generate insights
        insights = _generate_insights(daily, stores, dow, monthly, marketing, nc_trend)

        # Excel export
        excel_tables = {
            "Daily Trend": daily,
            "Weekly Trend": weekly,
            "Day of Week": dow,
            "Store Ranking": stores,
            "Monthly Comparison": monthly,
        }
        if marketing is not None and not marketing.empty:
            excel_tables["Marketing Breakdown"] = marketing
        if not nc_trend.empty:
            excel_tables["New Customers"] = nc_trend

        excel_bytes = _write_excel(excel_tables, insights)
        filename = f"DeepDive_{operator_name}_{datetime.now():%Y%m%d}.xlsx"

        summary = insights[0] if insights else "DeepDive analysis complete."

        return {
            "excel_bytes": excel_bytes,
            "filename": filename,
            "summary_text": summary,
            "insights": insights,
            "tables": {
                "daily_trend": _df_to_records(daily),
                "weekly_trend": _df_to_records(weekly),
                "day_of_week": _df_to_records(dow),
                "store_ranking": _df_to_records(stores, max_rows=200),
                "monthly_comparison": _df_to_records(monthly),
                "marketing_breakdown": _df_to_records(marketing),
                "new_customer_trend": _df_to_records(nc_trend),
            },
        }
    finally:
        try:
            sys.path.remove(str(app_dir))
        except ValueError:
            pass
