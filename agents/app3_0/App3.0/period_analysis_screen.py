"""Period Analysis screen: MoM, YoY, QoQ, Last 3 Months, Pre vs Post."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import DD_DATA_MASTER, ROOT_DIR, UE_DATA_MASTER
from period_analysis_engine import (
    DOLLAR_METRICS,
    COUNT_METRICS,
    PCT_METRICS,
    build_monthly_dataset,
    compute_mom,
    compute_yoy,
    compute_qoq,
    compute_last_n_months,
    compute_pre_vs_post,
    compute_ly_pre_vs_post,
    build_growth_summary,
    aggregate_platform,
)
from app_design import render_page_header, render_section_header, style_signed_table
from dashboard_charts import (
    build_monthly_trend_df,
    build_strategic_diagnosis_from_tables,
    render_comparison_dashboard,
    render_growth_funnel_bubbles_from_tables,
    render_metric_definitions_expander,
    render_strategic_diagnosis,
    render_trend_lines,
)


def _resolve_paths():
    dd = st.session_state.get("uploaded_dd_data")
    if dd is None:
        if DD_DATA_MASTER.exists():
            dd = DD_DATA_MASTER
        else:
            cands = [p for p in ROOT_DIR.glob("*.csv") if any(k in p.name.upper() for k in ["FINANCIAL", "DD", "DOORDASH"])]
            dd = cands[0] if cands else None

    ue = st.session_state.get("uploaded_ue_data")
    if ue is None:
        if UE_DATA_MASTER.exists():
            ue = UE_DATA_MASTER
        else:
            cands = [p for p in ROOT_DIR.glob("*.csv") if any(k in p.name.upper() for k in ["UE", "UBEREATS", "ORDER"])]
            ue = cands[0] if cands else None

    mkt = st.session_state.get("uploaded_marketing_folder")
    if mkt:
        mkt = Path(mkt)
    return dd, ue, mkt


def _fmt_val(metric_name: str, v) -> str:
    if pd.isna(v):
        return "—"
    v = float(v)
    if metric_name in DOLLAR_METRICS:
        return f"${v:,.2f}"
    if metric_name in COUNT_METRICS:
        return f"{int(round(v)):,}"
    if metric_name in PCT_METRICS:
        return f"{v:.1f}%"
    return f"{v:,.2f}"


def _fmt_growth(v) -> str:
    if pd.isna(v):
        return "—"
    v = float(v)
    return f"{v:+.1f}%"


def _fmt_change(metric_name: str, v) -> str:
    if pd.isna(v):
        return "—"
    v = float(v)
    sign = "+" if v >= 0 else ""
    if metric_name in DOLLAR_METRICS:
        return f"{sign}${v:,.2f}"
    if metric_name in COUNT_METRICS:
        return f"{sign}{int(round(v)):,}"
    if metric_name in PCT_METRICS:
        return f"{sign}{v:.1f} pts"
    return f"{sign}{v:,.2f}"


def _format_comparison_table(tbl: pd.DataFrame) -> pd.DataFrame:
    if tbl.empty:
        return tbl
    out = tbl.copy()
    for col in out.columns:
        out[col] = out[col].astype(object)
    value_cols = [c for c in out.columns if c not in ("Metric", "Change", "Growth%")]
    for _, row in out.iterrows():
        m = row["Metric"]
        idx = row.name
        for vc in value_cols:
            out.at[idx, vc] = _fmt_val(m, row[vc])
        out.at[idx, "Change"] = _fmt_change(m, row["Change"])
        out.at[idx, "Growth%"] = _fmt_growth(row["Growth%"])
    return out


def _format_trend_table(tbl: pd.DataFrame) -> pd.DataFrame:
    if tbl.empty:
        return tbl
    out = tbl.copy()
    for col in out.columns:
        out[col] = out[col].astype(object)
    month_cols = [c for c in out.columns if c != "Metric"]
    for _, row in out.iterrows():
        m = row["Metric"]
        idx = row.name
        for mc in month_cols:
            out.at[idx, mc] = _fmt_val(m, row[mc])
    return out


PLATFORM_LABELS = {"DD": "DoorDash", "UE": "UberEats", "Combined": "Combined"}
KPI_METRICS = ["Sales", "Payouts", "Orders", "AOV", "Marketing Fees", "Profitability%"]
BAR_METRICS = ["Sales", "Payouts", "Orders", "AOV", "Marketing Fees", "New Customers", "Profitability%"]
TREND_METRICS = ["Sales", "Payouts", "Orders", "AOV"]


def _render_platform_comparison(comparisons, platform, raw_tables: bool = False):
    label = PLATFORM_LABELS.get(platform, platform)
    if not comparisons:
        st.info(f"No data available for {label}.")
        return
    latest = comparisons[-1]["table"]
    if not raw_tables:
        render_section_header(f"{label} — latest period", comparisons[-1]["label"])
        render_comparison_dashboard(
            latest,
            format_value=_fmt_val,
            format_delta=_fmt_change,
            kpi_metrics=KPI_METRICS,
            bar_metrics=BAR_METRICS,
        )
    for comp in comparisons:
        st.markdown(f"**{label} — {comp['label']}**")
        formatted = _format_comparison_table(comp["table"])
        st.dataframe(
            style_signed_table(formatted, signed_columns=["Change", "Growth%"]),
            width="stretch",
            hide_index=True,
        )


def _render_single_table(tbl, platform, title_suffix="", show_dashboard: bool = True):
    label = PLATFORM_LABELS.get(platform, platform)
    if tbl is None or (isinstance(tbl, pd.DataFrame) and tbl.empty):
        st.info(f"No data available for {label}.")
        return
    suffix = f" — {title_suffix}" if title_suffix else ""
    st.markdown(f"**{label}{suffix}**")
    if show_dashboard:
        render_comparison_dashboard(
            tbl,
            format_value=_fmt_val,
            format_delta=_fmt_change,
            kpi_metrics=KPI_METRICS,
            bar_metrics=BAR_METRICS,
        )
    formatted = _format_comparison_table(tbl)
    st.dataframe(
        style_signed_table(formatted, signed_columns=["Change", "Growth%"]),
        width="stretch",
        hide_index=True,
    )


def _render_monthly_trends(monthly: pd.DataFrame, platform: str) -> None:
    trend_df = build_monthly_trend_df(monthly, platform)
    if trend_df.empty:
        return
    render_section_header(
        f"{PLATFORM_LABELS.get(platform, platform)} — monthly trends",
        "Core metrics across available months.",
    )
    render_trend_lines(
        trend_df,
        "Period Label",
        TREND_METRICS,
        title="Sales, payouts, orders, and AOV over time",
    )


def _month_count_hint(monthly: pd.DataFrame, platform: str) -> str | None:
    agg = aggregate_platform(monthly, platform)
    n = len(agg)
    if n < 2:
        return f"Monthwise views need at least two months — {PLATFORM_LABELS.get(platform, platform)} has {n}."
    return None


@st.cache_data(show_spinner="Loading monthly data…")
def _cached_monthly(dd_str, ue_str, mkt_str, excluded_dates):
    dd = Path(dd_str) if dd_str else None
    ue = Path(ue_str) if ue_str else None
    mkt = Path(mkt_str) if mkt_str else None
    return build_monthly_dataset(dd, ue, mkt, list(excluded_dates) if excluded_dates else None)


def display_period_analysis_screen():
    for key in ["pre_start_date", "pre_end_date", "post_start_date", "post_end_date"]:
        if not st.session_state.get(key) and key in st.query_params:
            val = st.query_params.get(key)
            if val:
                st.session_state[key] = val

    pre_start = st.session_state.get("pre_start_date", "")
    pre_end = st.session_state.get("pre_end_date", "")
    post_start = st.session_state.get("post_start_date", "")
    post_end = st.session_state.get("post_end_date", "")
    excluded_dates = tuple(str(v) for v in st.session_state.get("excluded_dates", []))

    render_page_header(
        "Period Analysis",
        "Trend Comparisons",
        "Automatic MoM, YoY, QoQ, and trend analysis across platforms.",
        meta_items=[
            (f"Pre {pre_start or '—'} – {pre_end or '—'}", "info"),
            (f"Post {post_start or '—'} – {post_end or '—'}", "info"),
        ],
    )
    st.markdown(
        '<div style="margin:-0.35rem 0 1rem;">'
        '<a href="/" target="_self" style="display:inline-block;padding:0.5rem 0.9rem;'
        "border:1px solid #D0D5DD;border-radius:8px;background:#FFFFFF;color:#344054;"
        'text-decoration:none;font-weight:650;">Back to dashboard</a></div>',
        unsafe_allow_html=True,
    )

    dd_path, ue_path, mkt_path = _resolve_paths()
    if not dd_path and not ue_path:
        st.warning("Upload DD or UE data files on the Setup & Upload screen first.")
        return

    monthly = _cached_monthly(
        str(dd_path) if dd_path else "",
        str(ue_path) if ue_path else "",
        str(mkt_path) if mkt_path else "",
        excluded_dates,
    )
    if monthly.empty:
        st.warning("No monthly data could be derived from the uploaded files.")
        return

    available_platforms = sorted(monthly["platform"].unique().tolist())
    has_dd = "DD" in available_platforms
    has_ue = "UE" in available_platforms
    show_platforms = ["DD", "UE", "Combined"] if (has_dd and has_ue) else available_platforms

    with st.expander("Filters & definitions", expanded=True):
        platform_filter = st.selectbox(
            "Platform",
            show_platforms,
            format_func=lambda p: PLATFORM_LABELS.get(p, p),
            key="period_platform_filter",
        )
        render_metric_definitions_expander()

    filtered_platforms = [platform_filter]

    tabs = st.tabs(["MoM", "YoY", "QoQ", "Last 3 Months", "Pre vs Post", "LY Pre vs Post"])

    # --- MoM ---
    with tabs[0]:
        render_section_header("Month over Month", "Consecutive month comparisons for each platform.")
        hint = _month_count_hint(monthly, platform_filter)
        if hint:
            st.caption(hint)
        _render_monthly_trends(monthly, platform_filter)
        for plat in filtered_platforms:
            comps = compute_mom(monthly, plat)
            _render_platform_comparison(comps, plat)
            if comps:
                summary = build_growth_summary(comps)
                if not summary.empty:
                    st.markdown(f"**{PLATFORM_LABELS.get(plat, plat)} — Growth% Summary**")
                    growth_cols = [c for c in summary.columns if c != "Metric"]
                    st.dataframe(
                        style_signed_table(summary, signed_columns=growth_cols),
                        width="stretch",
                        hide_index=True,
                    )
            st.markdown("---")

    # --- YoY ---
    with tabs[1]:
        render_section_header("Year over Year", "Same-month comparisons across years.")
        hint = _month_count_hint(monthly, platform_filter)
        if hint:
            st.caption(hint)
        _render_monthly_trends(monthly, platform_filter)
        for plat in filtered_platforms:
            comps = compute_yoy(monthly, plat)
            _render_platform_comparison(comps, plat)
            if comps:
                summary = build_growth_summary(comps)
                if not summary.empty:
                    st.markdown(f"**{PLATFORM_LABELS.get(plat, plat)} — Growth% Summary**")
                    growth_cols = [c for c in summary.columns if c != "Metric"]
                    st.dataframe(
                        style_signed_table(summary, signed_columns=growth_cols),
                        width="stretch",
                        hide_index=True,
                    )
            st.markdown("---")

    # --- QoQ ---
    with tabs[2]:
        render_section_header("Quarter over Quarter", "Consecutive quarter comparisons.")
        for plat in filtered_platforms:
            comps = compute_qoq(monthly, plat)
            _render_platform_comparison(comps, plat)
            if comps:
                summary = build_growth_summary(comps)
                if not summary.empty:
                    st.markdown(f"**{PLATFORM_LABELS.get(plat, plat)} — Growth% Summary**")
                    growth_cols = [c for c in summary.columns if c != "Metric"]
                    st.dataframe(
                        style_signed_table(summary, signed_columns=growth_cols),
                        width="stretch",
                        hide_index=True,
                    )
            st.markdown("---")

    # --- Last 3 Months ---
    with tabs[3]:
        render_section_header("Last 3 Months", "Most recent three months of data side-by-side.")
        for plat in filtered_platforms:
            tbl = compute_last_n_months(monthly, plat, n=3)
            if tbl.empty:
                st.info(f"No data for {PLATFORM_LABELS.get(plat, plat)}.")
            else:
                trend_df = build_monthly_trend_df(monthly, plat).tail(3)
                if not trend_df.empty:
                    render_trend_lines(
                        trend_df,
                        "Period Label",
                        TREND_METRICS,
                        title=f"{PLATFORM_LABELS.get(plat, plat)} — last 3 months",
                    )
                formatted = _format_trend_table(tbl)
                st.markdown(f"**{PLATFORM_LABELS.get(plat, plat)}**")
                st.dataframe(formatted, width="stretch", hide_index=True)
            st.markdown("---")

    # --- Pre vs Post ---
    with tabs[4]:
        render_section_header("Pre vs Post", "Comparison using the sidebar date ranges.")
        if not all([pre_start, pre_end, post_start, post_end]):
            st.warning("Set Pre and Post date ranges on the Setup & Upload screen to use this view.")
        else:
            results = compute_pre_vs_post(
                dd_path, ue_path, mkt_path,
                pre_start, pre_end, post_start, post_end,
                list(excluded_dates) if excluded_dates else None,
            )
            scoped = {k: v for k, v in results.items() if k in filtered_platforms or k == "Combined"}
            if platform_filter != "Combined":
                scoped = {platform_filter: results.get(platform_filter)}
            render_growth_funnel_bubbles_from_tables(scoped, PLATFORM_LABELS)
            render_strategic_diagnosis(build_strategic_diagnosis_from_tables(scoped, PLATFORM_LABELS))
            for plat in filtered_platforms:
                tbl = results.get(plat)
                if tbl is not None and not tbl.empty:
                    _render_single_table(tbl, plat, f"{pre_start}–{pre_end} vs {post_start}–{post_end}")
                else:
                    st.info(f"No data for {PLATFORM_LABELS.get(plat, plat)}.")
                st.markdown("---")

    # --- Last Year Pre vs Post ---
    with tabs[5]:
        render_section_header(
            "Last Year Pre vs Post",
            "Same calendar windows as your Pre/Post ranges, shifted back one year.",
        )
        if not all([pre_start, pre_end, post_start, post_end]):
            st.warning("Set Pre and Post date ranges on the Setup & Upload screen to use this view.")
        else:
            ly_results = compute_ly_pre_vs_post(
                dd_path, ue_path, mkt_path,
                pre_start, pre_end, post_start, post_end,
                list(excluded_dates) if excluded_dates else None,
            )
            scoped = {k: v for k, v in ly_results.items() if k in filtered_platforms}
            if platform_filter == "Combined" and "Combined" in ly_results:
                scoped["Combined"] = ly_results["Combined"]
            render_growth_funnel_bubbles_from_tables(scoped, PLATFORM_LABELS)
            render_strategic_diagnosis(build_strategic_diagnosis_from_tables(scoped, PLATFORM_LABELS))
            for plat in filtered_platforms:
                tbl = ly_results.get(plat)
                if tbl is not None and not tbl.empty:
                    _render_single_table(tbl, plat, "last-year windows")
                else:
                    st.info(f"No data for {PLATFORM_LABELS.get(plat, plat)}.")
                st.markdown("---")
