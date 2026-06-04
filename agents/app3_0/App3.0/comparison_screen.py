"""Comparison Hub: unified filters and period comparison tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DD_DATA_MASTER, ROOT_DIR, UE_DATA_MASTER
from comparison_engine import (
    COMPARISON_TYPES,
    COUNT_METRICS,
    DOLLAR_METRICS,
    PCT_METRICS,
    RATE_METRICS,
    available_granularities,
    build_gc_bucket_comparison,
    compute_period_comparison,
    compute_sequential_comparisons,
    filter_platform,
    granularity_hint,
    load_comparison_dataset,
    monthly_platform_comparisons,
)
from app_design import render_page_header, render_section_header, style_signed_table
from period_analysis_screen import _render_platform_comparison
from dashboard_charts import (
    build_strategic_diagnosis_from_tables,
    build_timeseries_from_orders,
    render_comparison_dashboard,
    render_growth_funnel_bubbles_from_tables,
    render_metric_definitions_expander,
    render_strategic_diagnosis,
    render_trend_lines,
    COLOR_POSITIVE,
    COLOR_NEGATIVE,
    CHART_BG,
    PAPER_BG,
    GRID_COLOR,
)


def _resolve_paths():
    dd = st.session_state.get("uploaded_dd_data")
    if dd is None:
        dd = DD_DATA_MASTER if DD_DATA_MASTER.exists() else None
        if dd is None:
            cands = [p for p in ROOT_DIR.glob("*.csv") if any(k in p.name.upper() for k in ["FINANCIAL", "DD", "DOORDASH"])]
            dd = cands[0] if cands else None

    ue = st.session_state.get("uploaded_ue_data")
    if ue is None:
        ue = UE_DATA_MASTER if UE_DATA_MASTER.exists() else None
        if ue is None:
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
    if metric_name in RATE_METRICS:
        return f"{v:.2f}x"
    return f"{v:,.2f}"


def _fmt_growth(v) -> str:
    if pd.isna(v):
        return "—"
    return f"{float(v):+.1f}%"


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
    if metric_name in RATE_METRICS:
        return f"{sign}{v:.2f}x"
    return f"{sign}{v:,.2f}"


def _format_metric_table(tbl: pd.DataFrame) -> pd.DataFrame:
    if tbl.empty:
        return tbl
    out = tbl.copy()
    for col in out.columns:
        out[col] = out[col].astype(object)
    value_cols = [c for c in out.columns if c not in ("Metric", "Entity", "Change", "Growth%")]
    for _, row in out.iterrows():
        m = row["Metric"]
        idx = row.name
        for vc in value_cols:
            out.at[idx, vc] = _fmt_val(m, row[vc])
        if "Change" in out.columns:
            out.at[idx, "Change"] = _fmt_change(m, row["Change"])
        if "Growth%" in out.columns:
            out.at[idx, "Growth%"] = _fmt_growth(row["Growth%"])
    return out


def _format_gc_table(tbl: pd.DataFrame) -> pd.DataFrame:
    if tbl.empty:
        return tbl
    out = tbl.copy()
    for col in out.columns:
        out[col] = out[col].astype(object)
    for _, row in out.iterrows():
        idx = row.name
        for col in out.columns:
            if col in ("GC Bucket",):
                continue
            if col == "Growth%":
                out.at[idx, col] = _fmt_growth(row[col])
            elif col == "Change":
                out.at[idx, col] = _fmt_change("Orders", row[col])
            else:
                out.at[idx, col] = _fmt_val("Orders", row[col])
    return out


def _render_filter_bar(dataset: pd.DataFrame) -> dict:
    """Shared filter controls; returns selections dict."""
    gran_choices = available_granularities(dataset)
    hint = granularity_hint(dataset)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        platform = st.selectbox("Platform", ["Combined", "DD", "UE"], key="cmp_platform")
    with c2:
        comparison = st.selectbox(
            "Comparison",
            list(COMPARISON_TYPES.keys()),
            format_func=lambda k: COMPARISON_TYPES[k][2],
            key="cmp_comparison",
        )
    with c3:
        dimension = st.selectbox(
            "Drill-down",
            list(["Overall", "Store", "Slot", "Day + Slot", "Corp vs TODC"]),
            key="cmp_dimension",
        )
    with c4:
        granularity = st.selectbox(
            "Time granularity",
            gran_choices,
            key="cmp_granularity",
            help=hint or "Overall rolls up the full selected windows.",
        )

    store_filter = []
    scoped = filter_platform(dataset, platform)
    if dimension == "Store" and not scoped.empty:
        store_opts = sorted(scoped["Store Label"].dropna().unique().tolist())
        store_filter = st.multiselect(
            "Stores (optional)",
            store_opts,
            default=[],
            help="Leave empty for all stores; table shows top movers.",
            key="cmp_stores",
        )

    if hint and granularity in ("Weekwise", "Monthwise", "Datewise") and granularity not in gran_choices:
        st.warning(hint)
    elif hint and granularity != "Overall":
        st.caption(hint)

    return {
        "platform": platform,
        "comparison": comparison,
        "dimension": dimension,
        "granularity": granularity,
        "store_filter": store_filter or None,
        "scoped_df": scoped,
    }


def _platform_tables_from_summary(summary: pd.DataFrame, platform: str) -> dict[str, pd.DataFrame]:
    """Wrap a single summary table for funnel/diagnosis when only one platform is selected."""
    key = platform if platform in ("DD", "UE", "Combined") else "Combined"
    return {key: summary}


def _render_period_comparison_block(filters: dict) -> None:
    summary, details = compute_period_comparison(
        filters["scoped_df"],
        filters["comparison"],
        dimension=filters["dimension"],
        granularity=filters["granularity"],
        entity_filters=filters["store_filter"],
    )
    label = COMPARISON_TYPES[filters["comparison"]][2]
    render_section_header(label, "Delta and growth % for core metrics in the filtered slice.")

    if summary.empty:
        st.info("No data for this filter combination.")
        return

    render_metric_definitions_expander()
    render_comparison_dashboard(
        summary,
        format_value=_fmt_val,
        format_delta=_fmt_change,
        kpi_metrics=["Sales", "Payouts", "Orders", "AOV", "Spends", "ROAS"],
        bar_metrics=["Sales", "Payouts", "Orders", "AOV", "Spends", "ROAS", "New Customers"],
    )

    if filters["comparison"] == "pre_vs_post" and filters["dimension"] == "Overall":
        plat = filters["platform"]
        funnel_tables = _platform_tables_from_summary(summary, plat)
        if plat == "Combined":
            dd_sum, _ = compute_period_comparison(
                filter_platform(filters["scoped_df"], "DD"),
                filters["comparison"],
                dimension="Overall",
                granularity="Overall",
            )
            ue_sum, _ = compute_period_comparison(
                filter_platform(filters["scoped_df"], "UE"),
                filters["comparison"],
                dimension="Overall",
                granularity="Overall",
            )
            funnel_tables = {"Combined": summary}
            if not dd_sum.empty:
                funnel_tables["DD"] = dd_sum
            if not ue_sum.empty:
                funnel_tables["UE"] = ue_sum
        render_growth_funnel_bubbles_from_tables(
            funnel_tables,
            {"Combined": "Combined", "DD": "DoorDash", "UE": "UberEats"},
        )
        render_strategic_diagnosis(build_strategic_diagnosis_from_tables(funnel_tables))

    gran = filters["granularity"]
    time_col = {"Monthwise": "Month", "Weekwise": "Week", "Datewise": "Date"}.get(gran)
    if time_col:
        ts = build_timeseries_from_orders(filters["scoped_df"], time_col, ["Sales", "Payouts", "Orders", "AOV"])
        if not ts.empty and ts[time_col].nunique() >= 2:
            render_trend_lines(
                ts,
                time_col,
                ["Sales", "Payouts", "Orders", "AOV"],
                title=f"Trend by {gran.replace('wise', '')}",
            )

    st.markdown("**Summary table**")
    st.dataframe(
        style_signed_table(_format_metric_table(summary), signed_columns=["Change", "Growth%"]),
        width="stretch",
        hide_index=True,
    )

    if details:
        st.markdown("**Breakdown**")
        for detail in details:
            st.dataframe(
                style_signed_table(_format_metric_table(detail), signed_columns=["Change", "Growth%"]),
                width="stretch",
                hide_index=True,
            )


@st.cache_data(show_spinner="Loading comparison data…")
def _cached_dataset(dd_str, ue_str, mkt_str, pre_start, pre_end, post_start, post_end, excluded_dates):
    dd = Path(dd_str) if dd_str else None
    ue = Path(ue_str) if ue_str else None
    mkt = Path(mkt_str) if mkt_str else None
    return load_comparison_dataset(
        dd, ue, mkt, pre_start, pre_end, post_start, post_end,
        list(excluded_dates) if excluded_dates else None,
    )


def display_comparison_screen() -> None:
    """Entry point for the Comparison Hub page."""
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
        "Comparison Hub",
        "Period Comparisons",
        "Pre vs Post, YoY, last-year windows, MoM, and drill-downs by platform, store, slot, and spend type.",
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

    if not all([pre_start, pre_end, post_start, post_end]):
        st.warning("Set Pre and Post date ranges on Setup & Upload before using comparisons.")
        return

    dd_path, ue_path, mkt_path = _resolve_paths()
    if not dd_path and not ue_path:
        st.warning("Upload DD or UE data on Setup & Upload first.")
        return

    dataset = _cached_dataset(
        str(dd_path) if dd_path else "",
        str(ue_path) if ue_path else "",
        str(mkt_path) if mkt_path else "",
        pre_start, pre_end, post_start, post_end,
        excluded_dates,
    )
    if dataset.empty:
        st.warning("No rows found for the configured date windows.")
        return

    tabs = st.tabs([
        "Pre / Post / YoY",
        "MoM & WoW",
        "GC Buckets",
        "Monthly (platform)",
    ])

    with tabs[0]:
        filters = _render_filter_bar(dataset)
        _render_period_comparison_block(filters)

    with tabs[1]:
        filters = _render_filter_bar(dataset)
        scoped = filters["scoped_df"]
        gran = filters["granularity"]
        st.caption("Sequential comparisons use the selected time granularity on loaded order data.")

        time_col_map = {"Monthwise": "Month", "Weekwise": "Week", "Datewise": "Date"}
        if gran in time_col_map:
            tc = time_col_map[gran]
            ts = build_timeseries_from_orders(scoped, tc, ["Sales", "Payouts", "Orders"])
            if not ts.empty and ts[tc].nunique() >= 2:
                render_trend_lines(ts, tc, ["Sales", "Payouts", "Orders"], title=f"{gran} trend")

        if gran == "Monthwise":
            seq = compute_sequential_comparisons(scoped, "Month", "MoM", filters["dimension"], filters["platform"])
            if not seq:
                st.info("Need at least two months in the data for MoM.")
            else:
                for item in seq[-6:]:
                    st.markdown(f"**{item['label']}**")
                    st.dataframe(
                        style_signed_table(_format_metric_table(item["table"]), signed_columns=["Change", "Growth%"]),
                        width="stretch",
                        hide_index=True,
                    )
        elif gran == "Weekwise":
            seq = compute_sequential_comparisons(scoped, "Week", "WoW", filters["dimension"], filters["platform"])
            if not seq:
                st.info("Need at least two ISO weeks for week-over-week.")
            else:
                for item in seq[-8:]:
                    st.markdown(f"**{item['label']}**")
                    st.dataframe(
                        style_signed_table(_format_metric_table(item["table"]), signed_columns=["Change", "Growth%"]),
                        width="stretch",
                        hide_index=True,
                    )
        elif gran == "Datewise":
            seq = compute_sequential_comparisons(scoped, "Date", "DoD", filters["dimension"], filters["platform"])
            if not seq:
                st.info("Need at least two dates for day-over-day.")
            else:
                for item in seq[-14:]:
                    st.markdown(f"**{item['label']}**")
                    st.dataframe(
                        style_signed_table(_format_metric_table(item["table"]), signed_columns=["Change", "Growth%"]),
                        width="stretch",
                        hide_index=True,
                    )
        else:
            st.info("Select Weekwise or Monthwise granularity for sequential MoM/WoW tables, or use the Monthly tab.")

    with tabs[2]:
        filters = _render_filter_bar(dataset)
        gc_tbl = build_gc_bucket_comparison(filters["scoped_df"], filters["comparison"])
        render_section_header("GC bucket order counts", "Orders by average ticket (guest-count proxy) bucket.")
        if gc_tbl.empty:
            st.info("No GC bucket data for this selection.")
        else:
            changes = pd.to_numeric(gc_tbl["Change"], errors="coerce")
            colors = [COLOR_POSITIVE if (v >= 0 and pd.notna(v)) else COLOR_NEGATIVE for v in changes]
            fig = go.Figure(
                go.Bar(
                    x=gc_tbl["GC Bucket"],
                    y=changes,
                    marker_color=colors,
                    text=[f"{v:+,.0f}" if pd.notna(v) else "" for v in changes],
                    textposition="outside",
                )
            )
            fig.update_layout(
                title="Order delta by GC bucket",
                height=360,
                paper_bgcolor=PAPER_BG,
                plot_bgcolor=CHART_BG,
                yaxis=dict(gridcolor=GRID_COLOR),
            )
            st.plotly_chart(fig, width="stretch")
            st.dataframe(
                style_signed_table(_format_gc_table(gc_tbl), signed_columns=["Change", "Growth%"]),
                width="stretch",
                hide_index=True,
            )

    with tabs[3]:
        render_section_header("Platform monthly MoM / YoY", "Uses full file history (not only sidebar windows).")
        sub = st.radio("View", ["MoM", "YoY"], horizontal=True, key="cmp_monthly_view")
        plat_map = {"DD": "DD", "UE": "UE", "Combined": "Combined"}
        comparisons = monthly_platform_comparisons(
            dd_path, ue_path, mkt_path,
            list(excluded_dates) if excluded_dates else None,
            "mom" if sub == "MoM" else "yoy",
        )
        for plat in ["DD", "UE", "Combined"]:
            comps = comparisons.get(plat, [])
            if comps:
                _render_platform_comparison(comps, plat)
