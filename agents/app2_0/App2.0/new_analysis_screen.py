"""Isolated deep-dive Streamlit screen for diagnosis-heavy analytics."""

from __future__ import annotations

from pathlib import Path
from io import BytesIO
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DD_DATA_MASTER, ROOT_DIR, SABRRO_DATA_DIR, UE_DATA_MASTER
from file_upload_screen import resolve_batch_folder
from new_analysis_engine import (
    CAMPAIGN_METRICS,
    PRIMARY_METRICS,
    aggregate_metrics,
    build_analysis_dataset,
    build_gc_bucket_table,
    build_metric_bridge,
    load_dd_campaign_performance,
    payout_change_decomposition,
    rank_entities_by_percentile,
    safe_divide,
    sales_change_decomposition,
    spend_change_decomposition,
    summarize_metric,
)
from app_design import render_page_header, render_section_header, style_signed_table


COUNT_METRICS = {"Orders"}
PERCENT_METRICS = {"Payout Margin %"}
RATE_METRICS = {"ROAS"}

# Display order for funnel bubble view (pre vs post growth %).
FUNNEL_METRIC_SPECS: list[tuple[str, str | None]] = [
    ("Sales", "Sales"),
    ("AOV", "AOV"),
    ("Orders", "Orders"),
    ("Payouts", "Payouts"),
    ("Spends", "Spends"),
    ("Commission", None),  # Sales − Payouts (platform take), growth on aggregate
    ("Error Δ (ROAS)", "ROAS"),  # Efficiency / spend-quality proxy when spend exists
]


def _growth_pct_pre_post(df: pd.DataFrame, engine_metric: str | None) -> float:
    """Post vs pre growth %; engine_metric None means Commission = Sales − Payouts."""
    if df is None or df.empty:
        return float("nan")
    if engine_metric is None:
        sales = summarize_metric(df, "Sales")
        pay = summarize_metric(df, "Payouts")
        pre_c = sales["Pre"] - pay["Pre"]
        post_c = sales["Post"] - pay["Post"]
        if abs(pre_c) < 1e-9:
            return 0.0 if abs(post_c) < 1e-9 else float("nan")
        return (post_c - pre_c) / abs(pre_c) * 100.0
    return float(summarize_metric(df, engine_metric)["Growth%"])


def build_growth_funnel_dataframe(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Long-form rows for Combined / DoorDash / UberEats bubble chart."""
    scopes: list[tuple[str, pd.DataFrame]] = [
        ("Combined", filtered_df),
        ("DoorDash", filtered_df[filtered_df["Platform"] == "DoorDash"]),
        ("UberEats", filtered_df[filtered_df["Platform"] == "UberEats"]),
    ]
    rows = []
    for scope, sdf in scopes:
        empty = sdf is None or sdf.empty
        for label, eng in FUNNEL_METRIC_SPECS:
            g = _growth_pct_pre_post(sdf if not empty else pd.DataFrame(), eng)
            rows.append(
                {
                    "Scope": scope,
                    "Metric": label,
                    "Growth %": g,
                    "Abs growth %": abs(g) if not math.isnan(g) else 0.0,
                    "Has data": not empty,
                }
            )
    return pd.DataFrame(rows)


def render_growth_funnel_bubbles(filtered_df: pd.DataFrame) -> None:
    """Funnel-style bubble grid: one row per scope, bubble size = |growth %|."""
    render_section_header(
        "Growth funnel (pre vs post)",
        "Bubble size scales with the magnitude of growth %; color shows direction (green up, red down).",
    )
    long_df = build_growth_funnel_dataframe(filtered_df)
    if long_df.empty:
        st.info("No data for growth funnel.")
        return

    fg = long_df["Growth %"].replace([np.inf, -np.inf], np.nan).dropna()
    cap = float(fg.abs().max()) if not fg.empty else 1.0
    if cap < 1e-9:
        cap = 1.0

    # Size: map |growth| into ~18–72 px radius feel (plotly size is area-ish)
    sizes = []
    for _, r in long_df.iterrows():
        g = r["Growth %"]
        if not r["Has data"] or (isinstance(g, float) and not math.isfinite(g)):
            sizes.append(10)
        else:
            a = min(abs(g), cap * 1.2) / cap
            sizes.append(18 + a * 55)

    long_df = long_df.copy()
    long_df["bubble_size"] = sizes
    long_df["Label"] = long_df.apply(
        lambda r: "n/a"
        if (not r["Has data"])
        else ("n/a" if not math.isfinite(r["Growth %"]) else f'{r["Growth %"]:+.1f}%'),
        axis=1,
    )

    orders = [m[0] for m in FUNNEL_METRIC_SPECS]
    fig = go.Figure()
    for scope in ["Combined", "DoorDash", "UberEats"]:
        sub = long_df[long_df["Scope"] == scope]

        colors = []
        for _, r in sub.iterrows():
            if not r["Has data"]:
                colors.append("rgba(156,163,175,0.55)")
            elif not isinstance(r["Growth %"], (int, float)) or not math.isfinite(float(r["Growth %"])):
                colors.append("rgba(107,114,128,0.7)")
            elif r["Growth %"] >= 0:
                colors.append("#16a34a")
            else:
                colors.append("#dc2626")

        fig.add_trace(
            go.Scatter(
                x=sub["Metric"],
                y=[scope] * len(sub),
                mode="markers+text",
                name=scope,
                showlegend=False,
                marker=dict(
                    size=sub["bubble_size"],
                    color=colors,
                    line=dict(width=1.5, color="#1f2937"),
                    sizemode="diameter",
                ),
                text=sub["Label"],
                textposition="middle center",
                textfont=dict(size=10, color="#0f172a"),
                hovertemplate="%{y} · %{x}<br>Growth: %{customdata}<extra></extra>",
                customdata=[
                    f"{r['Growth %']:+.2f}%"
                    if isinstance(r["Growth %"], (int, float)) and math.isfinite(float(r["Growth %"]))
                    else "n/a"
                    for _, r in sub.iterrows()
                ],
            )
        )

    fig.update_layout(
        height=420,
        margin=dict(l=24, r=24, t=48, b=80),
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#FFFFFF",
        xaxis=dict(
            categoryorder="array",
            categoryarray=orders,
            tickangle=-28,
            title="",
            gridcolor="#E5E7EB",
        ),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=["UberEats", "DoorDash", "Combined"],
            autorange="reversed",
            gridcolor="#E5E7EB",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Commission = aggregate (Sales − Payouts), pre vs post. "
        "ROAS reflects sales per marketing dollar; when spend is zero it may read as n/a. "
        "Use ROAS as an efficiency / anomaly signal alongside your spend data."
    )


def resolve_source_paths() -> tuple[Path | None, Path | None, Path | None]:
    """Resolve uploaded or auto-detected source paths the same way the main dashboard does."""
    dd_data_path = st.session_state.get("uploaded_dd_data")
    ue_data_path = st.session_state.get("uploaded_ue_data")
    marketing_folder_path = st.session_state.get("uploaded_marketing_folder")

    if SABRRO_DATA_DIR.is_dir() and any(SABRRO_DATA_DIR.glob("*.csv")):
        batch = resolve_batch_folder(SABRRO_DATA_DIR)
        if dd_data_path is None and batch.get("dd_financial"):
            dd_data_path = batch["dd_financial"]
        if ue_data_path is None and batch.get("ue_financial"):
            ue_data_path = batch["ue_financial"]
        if marketing_folder_path is None and batch.get("marketing_folder"):
            marketing_folder_path = batch["marketing_folder"]

    if dd_data_path is None:
        if DD_DATA_MASTER.exists():
            dd_data_path = DD_DATA_MASTER
        else:
            root_csvs = list(ROOT_DIR.glob("*.csv"))
            dd_candidates = [path for path in root_csvs if any(keyword in path.name.upper() for keyword in ["FINANCIAL", "DD", "DOORDASH"])]
            dd_data_path = dd_candidates[0] if dd_candidates else None

    if ue_data_path is None:
        if UE_DATA_MASTER.exists():
            ue_data_path = UE_DATA_MASTER
        else:
            root_csvs = list(ROOT_DIR.glob("*.csv"))
            ue_candidates = [path for path in root_csvs if any(keyword in path.name.upper() for keyword in ["UE", "UBEREATS", "ORDER"])]
            ue_data_path = ue_candidates[0] if ue_candidates else None

    if marketing_folder_path:
        marketing_folder_path = Path(marketing_folder_path)
    return dd_data_path, ue_data_path, marketing_folder_path


def format_metric_value(metric: str, value: float) -> str:
    """Format metric values consistently across the view."""
    if metric in COUNT_METRICS:
        return f"{int(round(value)):,}"
    if metric in PERCENT_METRICS:
        return f"{value:.1f}%"
    if metric in RATE_METRICS:
        return f"{value:.2f}x"
    return f"${value:,.1f}"


def format_delta(metric: str, value: float) -> str:
    """Format deltas consistently across the view."""
    sign = "+" if value >= 0 else ""
    if metric in COUNT_METRICS:
        return f"{sign}{int(round(value)):,}"
    if metric in PERCENT_METRICS:
        return f"{sign}{value:.1f} pts"
    if metric in RATE_METRICS:
        return f"{sign}{value:.2f}x"
    return f"{sign}${value:,.1f}"


def render_summary_cards(filtered_df: pd.DataFrame) -> None:
    """Render the top-line strategic metrics."""
    metric_order = ["Sales", "Payouts", "Orders", "AOV", "Spends", "ROAS"]
    columns = st.columns(len(metric_order))
    for idx, metric in enumerate(metric_order):
        summary = summarize_metric(filtered_df, metric)
        with columns[idx]:
            st.metric(
                metric,
                format_metric_value(metric, summary["Post"]),
                f"{summary['Growth%']:.1f}%",
                help=f"Post vs Pre comparison. Delta: {format_delta(metric, summary['Delta'])}",
            )


def render_narrative(filtered_df: pd.DataFrame) -> None:
    """Render the strategist-style narrative diagnosis."""
    sales_summary = summarize_metric(filtered_df, "Sales")
    payouts_summary = summarize_metric(filtered_df, "Payouts")
    spend_summary = summarize_metric(filtered_df, "Spends")
    sales_bridge = build_metric_bridge(filtered_df, "Sales", ["Store Label"])

    sales_decomp = sales_change_decomposition(filtered_df)
    payout_decomp = payout_change_decomposition(filtered_df)
    spend_decomp = spend_change_decomposition(filtered_df)

    top_growth = sales_bridge.iloc[0] if not sales_bridge.empty else None
    top_decline = sales_bridge.iloc[-1] if not sales_bridge.empty else None

    bullets = [
        f"Sales moved from {format_metric_value('Sales', sales_summary['Pre'])} to {format_metric_value('Sales', sales_summary['Post'])}, a change of {format_delta('Sales', sales_summary['Delta'])}.",
        f"Order movement contributed {format_delta('Sales', sales_decomp['orders_effect'])} to sales change, while ticket size contributed {format_delta('Sales', sales_decomp['aov_effect'])}.",
        f"Payouts changed by {format_delta('Payouts', payouts_summary['Delta'])}; sales mix contributed {format_delta('Payouts', payout_decomp['sales_effect'])} and payout-margin shift contributed {format_delta('Payouts', payout_decomp['margin_effect'])}.",
        f"Marketing spend changed by {format_delta('Spends', spend_summary['Delta'])}; TODC-funded movement was {format_delta('Spends', spend_decomp['todc_effect'])} and corporate-funded movement was {format_delta('Spends', spend_decomp['corp_effect'])}.",
    ]
    if top_growth is not None:
        bullets.append(
            f"Biggest positive store contribution: {top_growth['Store Label']} at {format_delta('Sales', top_growth['Delta'])} ({top_growth['Contribution%']:.1f}% of net sales change)."
        )
    if top_decline is not None:
        bullets.append(
            f"Biggest negative store contribution: {top_decline['Store Label']} at {format_delta('Sales', top_decline['Delta'])} ({top_decline['Contribution%']:.1f}% of net sales change)."
        )

    render_section_header("Strategic Diagnosis", "Plain-language explanation of what moved and why.")
    for bullet in bullets:
        st.write(f"- {bullet}")


def render_driver_table(filtered_df: pd.DataFrame, metric: str, level: str, label_column: str) -> None:
    """Render a ranked contributor table and quick chart."""
    bridge = build_metric_bridge(filtered_df, metric, [level])
    if bridge.empty:
        st.info("No data available for this metric and hierarchy level.")
        return

    display = bridge.head(12).copy()
    display["Pre"] = display["Pre"].map(lambda value: format_metric_value(metric, value))
    display["Post"] = display["Post"].map(lambda value: format_metric_value(metric, value))
    display["Delta"] = bridge.head(12)["Delta"].map(lambda value: format_delta(metric, value))
    display["Growth%"] = bridge.head(12)["Growth%"].map(lambda value: f"{value:.1f}%")
    display["Contribution%"] = bridge.head(12)["Contribution%"].map(lambda value: f"{value:.1f}%")

    chart_source = bridge.head(12).set_index(level)[["Delta"]]
    st.bar_chart(chart_source)
    st.dataframe(style_signed_table(display.rename(columns={level: label_column})), use_container_width=True, hide_index=True)


def build_summary_snapshot(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Create a compact overview of where sales movement came from."""
    rows = []
    for level, column in [("Store", "Store Label"), ("Day", "Day"), ("Slot", "Slot")]:
        bridge = build_metric_bridge(filtered_df, "Sales", [column])
        if bridge.empty:
            continue
        top_gain = bridge.iloc[0]
        top_loss = bridge.iloc[-1]
        top5_share = bridge["Delta"].abs().head(5).sum()
        total_abs = bridge["Delta"].abs().sum()
        rows.append(
            {
                "Level": level,
                "Top Positive Contributor": f"{top_gain[column]} ({format_delta('Sales', top_gain['Delta'])})",
                "Top Negative Contributor": f"{top_loss[column]} ({format_delta('Sales', top_loss['Delta'])})",
                "Net Delta": format_delta("Sales", bridge["Delta"].sum()),
                "Top 5 Concentration": f"{safe_divide(top5_share, total_abs) * 100:.1f}%",
            }
        )
    return pd.DataFrame(rows)


def render_drilldown(filtered_df: pd.DataFrame, metric: str) -> None:
    """Render store -> day -> slot drilldown."""
    store_bridge = build_metric_bridge(filtered_df, metric, ["Store Label"])
    if store_bridge.empty:
        st.info("No drilldown available.")
        return

    store_options = store_bridge["Store Label"].tolist()
    focus_store = st.session_state.get("new_focus_store")
    store_index = store_options.index(focus_store) if focus_store in store_options else 0
    selected_store = st.selectbox("Store", store_options, index=store_index, key="drilldown_focus_store")
    store_filtered = filtered_df[filtered_df["Store Label"] == selected_store]

    day_bridge = build_metric_bridge(store_filtered, metric, ["Day"])
    if day_bridge.empty:
        st.info("No day-level movement is available for the selected store.")
        return
    selected_day = st.selectbox("Day", day_bridge["Day"].astype(str).tolist(), index=0)
    day_filtered = store_filtered[store_filtered["Day"].astype(str) == selected_day]

    slot_bridge = build_metric_bridge(day_filtered, metric, ["Slot"])

    left, right = st.columns(2)
    with left:
        st.write("**Store drivers**")
        st.dataframe(style_signed_table(store_bridge.head(10)), use_container_width=True, hide_index=True)
    with right:
        st.write(f"**{selected_store} -> day drivers**")
        st.dataframe(style_signed_table(day_bridge), use_container_width=True, hide_index=True)

    st.write(f"**{selected_store} -> {selected_day} -> slot drivers**")
    st.dataframe(style_signed_table(slot_bridge), use_container_width=True, hide_index=True)


def render_marketing_tab(filtered_df: pd.DataFrame, campaign_df: pd.DataFrame) -> None:
    """Render spend split and efficiency views."""
    spend_summary = aggregate_metrics(filtered_df, ["Period"])
    if spend_summary.empty or spend_summary[["Spends", "Corp Spend", "TODC Spend"]].sum().sum() == 0:
        st.info("Marketing diagnostics require DoorDash marketing files with spend fields.")
        return

    spend_display = spend_summary.copy()
    for col in ["Sales", "Spends", "Corp Spend", "TODC Spend"]:
        spend_display[col] = spend_display[col].map(lambda value: format_metric_value("Sales", value))
    spend_display["ROAS"] = spend_summary["ROAS"].map(lambda value: format_metric_value("ROAS", value))
    spend_display["Payout Margin %"] = spend_summary["Payout Margin %"].map(lambda value: format_metric_value("Payout Margin %", value))
    st.write("**Spend split and efficiency**")
    st.dataframe(style_signed_table(spend_display), use_container_width=True, hide_index=True)

    st.write("**Store-level spend contribution**")
    render_driver_table(filtered_df[filtered_df["Spends"] != 0], "Spends", "Store Label", "Store")

    if not campaign_df.empty:
        campaign_options = campaign_df["Campaign Label"].drop_duplicates().sort_values().tolist()
        focus_campaign = st.session_state.get("new_focus_campaign")
        default_index = campaign_options.index(focus_campaign) if focus_campaign in campaign_options else 0
        selected_campaign = st.selectbox("Focused campaign", campaign_options, index=default_index, key="marketing_focus_campaign")
        st.caption("Campaign focus is prefilled from the Top / Bottom tab when you click `Use as focus`.")
        campaign_view = campaign_df[campaign_df["Campaign Label"] == selected_campaign][["Campaign Label", "Period", "Sales", "Spend", "Orders", "ROAS", "Cost per Order"]].copy()
        st.write("**Focused campaign detail**")
        st.dataframe(style_signed_table(campaign_view), use_container_width=True, hide_index=True)


def render_focus_selector(
    ranked_df: pd.DataFrame,
    entity_col: str,
    metric: str,
    percentile_cutoff: int,
    focus_key: str,
    label: str,
    ascending: bool,
) -> None:
    """Push a percentile entity into another tab's default selection."""
    if ranked_df.empty:
        return

    percentile_col = f"{metric}_Percentile"
    post_col = f"{metric}_Post"
    if percentile_col not in ranked_df.columns:
        return

    if ascending:
        sliced = ranked_df[ranked_df[percentile_col] <= percentile_cutoff].sort_values(post_col, ascending=True)
    else:
        sliced = ranked_df[ranked_df[percentile_col] >= 100 - percentile_cutoff].sort_values(post_col, ascending=False)

    if sliced.empty:
        return

    options = sliced[entity_col].astype(str).tolist()
    selected = st.selectbox(label, options, key=f"{focus_key}_{label}_{'asc' if ascending else 'desc'}")
    if st.button("Use as focus", key=f"{focus_key}_button_{label}_{'asc' if ascending else 'desc'}"):
        st.session_state[focus_key] = selected


def render_percentile_table(
    ranked_df: pd.DataFrame,
    entity_col: str,
    metric: str,
    percentile_cutoff: int,
    title: str,
    ascending: bool,
) -> None:
    """Render top or bottom percentile slices."""
    if ranked_df.empty:
        st.info("No ranked data is available.")
        return

    percentile_col = f"{metric}_Percentile"
    post_col = f"{metric}_Post"
    delta_col = f"{metric}_Delta"
    growth_col = f"{metric}_Growth%"
    if percentile_col not in ranked_df.columns:
        st.info("The selected metric is not available for this ranking.")
        return

    if ascending:
        sliced = ranked_df[ranked_df[percentile_col] <= percentile_cutoff].sort_values(post_col, ascending=True)
    else:
        sliced = ranked_df[ranked_df[percentile_col] >= 100 - percentile_cutoff].sort_values(post_col, ascending=False)

    if sliced.empty:
        st.info("No entities matched the selected percentile cutoff.")
        return

    display = sliced[[entity_col, post_col, delta_col, growth_col, percentile_col]].copy()
    display = display.rename(
        columns={
            entity_col: "Entity",
            post_col: "Post",
            delta_col: "Delta",
            growth_col: "Growth%",
            percentile_col: "Percentile",
        }
    )
    display["Post"] = display["Post"].map(lambda value: format_metric_value(metric, value))
    display["Delta"] = display["Delta"].map(lambda value: format_delta(metric, value))
    display["Growth%"] = display["Growth%"].map(lambda value: f"{value:.1f}%")
    display["Percentile"] = display["Percentile"].map(lambda value: f"{value:.1f}")

    st.write(f"**{title}**")
    st.dataframe(style_signed_table(display), use_container_width=True, hide_index=True)


def build_gc_percentile_dataset(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Create a periodized GC-bucket dataset for ranking."""
    if filtered_df.empty:
        return pd.DataFrame()
    bucketed = filtered_df.copy()
    bucketed["GC Bucket"] = pd.cut(
        bucketed["Sales"],
        bins=[-float("inf"), 15, 25, 40, 60, float("inf")],
        labels=["Under $15", "$15-$25", "$25-$40", "$40-$60", "$60+"],
    )
    bucketed = bucketed.dropna(subset=["GC Bucket"])
    if bucketed.empty:
        return pd.DataFrame()
    return bucketed


@st.cache_data(show_spinner=False)
def cached_campaign_dataset(marketing_path_str, pre_start, pre_end, post_start, post_end, excluded_dates):
    """Cache a campaign-level DD marketing dataset across pre and post periods."""
    marketing_path = Path(marketing_path_str) if marketing_path_str else None
    if marketing_path is None:
        return pd.DataFrame()

    pre_campaigns = load_dd_campaign_performance(marketing_path, pre_start, pre_end, excluded_dates)
    post_campaigns = load_dd_campaign_performance(marketing_path, post_start, post_end, excluded_dates)
    frames = []
    if not pre_campaigns.empty:
        pre_campaigns = pre_campaigns.copy()
        pre_campaigns["Period"] = "Pre"
        frames.append(pre_campaigns)
    if not post_campaigns.empty:
        post_campaigns = post_campaigns.copy()
        post_campaigns["Period"] = "Post"
        frames.append(post_campaigns)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def render_percentile_views(filtered_df: pd.DataFrame, campaign_df: pd.DataFrame) -> None:
    """Render top/bottom percentile views for stores and campaigns."""
    percentile_cutoff = st.slider("Percentile slice", min_value=1, max_value=25, value=5, step=1, help="Top and bottom percentile bucket to display.")

    st.write("**Stores ranked by metric**")
    store_platform_options = ["All"] + sorted(filtered_df["Platform"].dropna().unique().tolist())
    selected_store_platform = st.selectbox("Store platform scope", store_platform_options, index=0, key="store_percentile_platform")
    scoped_store_df = filtered_df if selected_store_platform == "All" else filtered_df[filtered_df["Platform"] == selected_store_platform]
    store_metric = st.selectbox("Store metric", PRIMARY_METRICS, index=0, key="store_percentile_metric")
    ranked_stores = rank_entities_by_percentile(scoped_store_df, "Store Label", PRIMARY_METRICS)
    left, right = st.columns(2)
    with left:
        render_percentile_table(ranked_stores, "Store Label", store_metric, percentile_cutoff, f"Top {percentile_cutoff}% stores by {store_metric}", ascending=False)
        render_focus_selector(ranked_stores, "Store Label", store_metric, percentile_cutoff, "new_focus_store", "Focus from top stores", ascending=False)
    with right:
        render_percentile_table(ranked_stores, "Store Label", store_metric, percentile_cutoff, f"Bottom {percentile_cutoff}% stores by {store_metric}", ascending=True)
        render_focus_selector(ranked_stores, "Store Label", store_metric, percentile_cutoff, "new_focus_store", "Focus from bottom stores", ascending=True)

    st.write("**Days and slots ranked by metric**")
    hierarchy_metric = st.selectbox("Hierarchy metric", PRIMARY_METRICS, index=0, key="hierarchy_percentile_metric")
    ranked_days = rank_entities_by_percentile(filtered_df, "Day", PRIMARY_METRICS)
    ranked_slots = rank_entities_by_percentile(filtered_df, "Slot", PRIMARY_METRICS)
    day_left, day_right = st.columns(2)
    with day_left:
        render_percentile_table(ranked_days, "Day", hierarchy_metric, percentile_cutoff, f"Top {percentile_cutoff}% days by {hierarchy_metric}", ascending=False)
    with day_right:
        render_percentile_table(ranked_days, "Day", hierarchy_metric, percentile_cutoff, f"Bottom {percentile_cutoff}% days by {hierarchy_metric}", ascending=True)
    slot_left, slot_right = st.columns(2)
    with slot_left:
        render_percentile_table(ranked_slots, "Slot", hierarchy_metric, percentile_cutoff, f"Top {percentile_cutoff}% slots by {hierarchy_metric}", ascending=False)
    with slot_right:
        render_percentile_table(ranked_slots, "Slot", hierarchy_metric, percentile_cutoff, f"Bottom {percentile_cutoff}% slots by {hierarchy_metric}", ascending=True)

    st.write("**GC buckets ranked by metric**")
    gc_df = build_gc_percentile_dataset(filtered_df)
    gc_metric_options = ["Sales", "Orders", "AOV"]
    gc_metric = st.selectbox("GC metric", gc_metric_options, index=0, key="gc_percentile_metric")
    ranked_gc = rank_entities_by_percentile(gc_df, "GC Bucket", gc_metric_options)
    gc_left, gc_right = st.columns(2)
    with gc_left:
        render_percentile_table(ranked_gc, "GC Bucket", gc_metric, percentile_cutoff, f"Top {percentile_cutoff}% GC buckets by {gc_metric}", ascending=False)
    with gc_right:
        render_percentile_table(ranked_gc, "GC Bucket", gc_metric, percentile_cutoff, f"Bottom {percentile_cutoff}% GC buckets by {gc_metric}", ascending=True)

    st.write("**Campaigns ranked by metric**")
    if campaign_df.empty:
        st.info("Campaign percentile views require DoorDash marketing promotion or sponsored-listing files.")
        return

    campaign_source_options = ["All"] + sorted(campaign_df["Source"].dropna().unique().tolist())
    selected_campaign_source = st.selectbox("Campaign source scope", campaign_source_options, index=0, key="campaign_percentile_source")
    scoped_campaign_df = campaign_df if selected_campaign_source == "All" else campaign_df[campaign_df["Source"] == selected_campaign_source]
    campaign_metric = st.selectbox("Campaign metric", CAMPAIGN_METRICS, index=0, key="campaign_percentile_metric")
    ranked_campaigns = rank_entities_by_percentile(scoped_campaign_df, "Campaign Label", CAMPAIGN_METRICS)
    left, right = st.columns(2)
    with left:
        render_percentile_table(ranked_campaigns, "Campaign Label", campaign_metric, percentile_cutoff, f"Top {percentile_cutoff}% campaigns by {campaign_metric}", ascending=False)
        render_focus_selector(ranked_campaigns, "Campaign Label", campaign_metric, percentile_cutoff, "new_focus_campaign", "Focus from top campaigns", ascending=False)
    with right:
        render_percentile_table(ranked_campaigns, "Campaign Label", campaign_metric, percentile_cutoff, f"Bottom {percentile_cutoff}% campaigns by {campaign_metric}", ascending=True)
        render_focus_selector(ranked_campaigns, "Campaign Label", campaign_metric, percentile_cutoff, "new_focus_campaign", "Focus from bottom campaigns", ascending=True)


def build_exceptions_table(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Flag contradictory movement patterns that deserve investigation."""
    by_store_period = aggregate_metrics(filtered_df, ["Store Label", "Period"])
    if by_store_period.empty:
        return pd.DataFrame()

    pivot = by_store_period.pivot_table(
        index="Store Label",
        columns="Period",
        values=["Sales", "Payouts", "Orders", "Spends", "AOV", "ROAS"],
        fill_value=0,
    )
    pivot.columns = [f"{metric}_{period}" for metric, period in pivot.columns]
    pivot = pivot.reset_index()
    for metric in ["Sales", "Payouts", "Orders", "Spends", "AOV", "ROAS"]:
        pivot[f"{metric}_Delta"] = pivot.get(f"{metric}_Post", 0) - pivot.get(f"{metric}_Pre", 0)

    exceptions = []
    for _, row in pivot.iterrows():
        if row["Sales_Delta"] < 0 and row["Spends_Delta"] > 0:
            exceptions.append({"Store": row["Store Label"], "Signal": "Spend up while sales fell", "Impact": format_delta("Sales", row["Sales_Delta"])})
        if row["Sales_Delta"] > 0 and row["Payouts_Delta"] < 0:
            exceptions.append({"Store": row["Store Label"], "Signal": "Sales up while payouts fell", "Impact": format_delta("Payouts", row["Payouts_Delta"])})
        if row["Orders_Delta"] > 0 and row["AOV_Delta"] < 0:
            exceptions.append({"Store": row["Store Label"], "Signal": "Orders up while AOV fell", "Impact": format_delta("AOV", row["AOV_Delta"])})
        if row["ROAS_Delta"] < 0 and row["Spends_Delta"] > 0:
            exceptions.append({"Store": row["Store Label"], "Signal": "ROAS deteriorated despite higher spend", "Impact": format_delta("ROAS", row["ROAS_Delta"])})
    return pd.DataFrame(exceptions)


def render_gc_bucket_analysis(filtered_df: pd.DataFrame) -> None:
    """Render order-ticket bucket movement."""
    gc_table = build_gc_bucket_table(filtered_df)
    if gc_table.empty:
        st.info("No GC bucket analysis available.")
        return

    st.write("**Guest count / ticket bucket movement**")
    st.bar_chart(gc_table.set_index("GC Bucket")[["Delta Orders"]])
    st.dataframe(style_signed_table(gc_table), use_container_width=True, hide_index=True)


def build_download_workbook(filtered_df: pd.DataFrame) -> bytes:
    """Create an Excel export for the New view."""
    output = BytesIO()
    overview_df = pd.DataFrame(
        [
            {
                "Metric": metric,
                "Pre": summarize_metric(filtered_df, metric)["Pre"],
                "Post": summarize_metric(filtered_df, metric)["Post"],
                "Delta": summarize_metric(filtered_df, metric)["Delta"],
                "Growth%": summarize_metric(filtered_df, metric)["Growth%"],
            }
            for metric in ["Sales", "Payouts", "Orders", "AOV", "Spends", "ROAS", "Payout Margin %"]
        ]
    )
    snapshot_df = build_summary_snapshot(filtered_df)
    store_contrib_df = build_metric_bridge(filtered_df, "Sales", ["Store Label"])
    day_contrib_df = build_metric_bridge(filtered_df, "Sales", ["Day"])
    slot_contrib_df = build_metric_bridge(filtered_df, "Sales", ["Slot"])
    gc_df = build_gc_bucket_table(filtered_df)
    exceptions_df = build_exceptions_table(filtered_df)
    marketing_df = aggregate_metrics(filtered_df, ["Period"])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        overview_df.to_excel(writer, sheet_name="Topline", index=False)
        snapshot_df.to_excel(writer, sheet_name="Snapshot", index=False)
        store_contrib_df.to_excel(writer, sheet_name="Store Contribution", index=False)
        day_contrib_df.to_excel(writer, sheet_name="Day Contribution", index=False)
        slot_contrib_df.to_excel(writer, sheet_name="Slot Contribution", index=False)
        gc_df.to_excel(writer, sheet_name="GC Buckets", index=False)
        marketing_df.to_excel(writer, sheet_name="Marketing", index=False)
        exceptions_df.to_excel(writer, sheet_name="Exceptions", index=False)

    output.seek(0)
    return output.getvalue()


def render_data_notes() -> None:
    """Render explicit analytical assumptions."""
    st.write("**Analytical assumptions**")
    notes = [
        "The New view is isolated from the existing dashboard and reads the same uploaded files and date filters.",
        "Hierarchy is diagnosed as Store -> Day -> Slot, with Day derived from order date and Slot derived from local order timestamps.",
        "AOV, ROAS, and payout margin are derived after aggregation; additive metrics drive contributor math.",
        "DoorDash marketing spend uses uploaded promotion and sponsored-listing files. TODC Spend is modeled as merchant-funded discount plus marketing fees. Corp Spend is modeled as DoorDash marketing credit plus third-party contribution.",
        "If marketing files are missing, spend diagnostics remain available only for metrics present in transaction data.",
    ]
    for note in notes:
        st.write(f"- {note}")


@st.cache_data(show_spinner=False)
def cached_dataset(dd_path_str, ue_path_str, marketing_path_str, pre_start, pre_end, post_start, post_end, excluded_dates):
    """Cache the unified deep-analysis dataset."""
    dd_path = Path(dd_path_str) if dd_path_str else None
    ue_path = Path(ue_path_str) if ue_path_str else None
    marketing_path = Path(marketing_path_str) if marketing_path_str else None
    return build_analysis_dataset(dd_path, ue_path, marketing_path, pre_start, pre_end, post_start, post_end, excluded_dates)


def display_new_analysis_screen() -> None:
    """Entry point for the New deep-dive screen."""
    # Bootstrap key filters from query params if the page is opened directly or refreshed.
    for key in ["pre_start_date", "pre_end_date", "post_start_date", "post_end_date", "operator_name"]:
        if not st.session_state.get(key) and key in st.query_params:
            value = st.query_params.get(key)
            if value:
                st.session_state[key] = value

    if not st.session_state.get("pre_date_range") and st.session_state.get("pre_start_date") and st.session_state.get("pre_end_date"):
        st.session_state["pre_date_range"] = f"{st.session_state['pre_start_date']}-{st.session_state['pre_end_date']}"
    if not st.session_state.get("post_date_range") and st.session_state.get("post_start_date") and st.session_state.get("post_end_date"):
        st.session_state["post_date_range"] = f"{st.session_state['post_start_date']}-{st.session_state['post_end_date']}"

    pre_start = st.session_state.get("pre_start_date", "")
    pre_end = st.session_state.get("pre_end_date", "")
    post_start = st.session_state.get("post_start_date", "")
    post_end = st.session_state.get("post_end_date", "")
    excluded_dates = tuple(str(value) for value in st.session_state.get("excluded_dates", []))

    render_page_header(
        "Diagnostic Workspace",
        "Root-Cause Analysis",
        "Step-by-step diagnosis of growth, decline, and drivers across store, day, slot, and campaign.",
        meta_items=[
            (f"Pre {pre_start or 'not set'} - {pre_end or 'not set'}", "info"),
            (f"Post {post_start or 'not set'} - {post_end or 'not set'}", "info"),
        ],
    )
    st.markdown(
        """
        <div style="margin: -0.35rem 0 1rem;">
            <a href="/" target="_self" style="display:inline-block;padding:0.5rem 0.9rem;border:1px solid #D0D5DD;border-radius:8px;background:#FFFFFF;color:#344054;text-decoration:none;font-weight:650;">Back to dashboard</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not all([pre_start, pre_end, post_start, post_end]):
        st.warning("Set pre and post date ranges on the Setup & Upload screen before using the New view.")
        return

    dd_data_path, ue_data_path, marketing_folder_path = resolve_source_paths()
    dataset = cached_dataset(
        str(dd_data_path) if dd_data_path else "",
        str(ue_data_path) if ue_data_path else "",
        str(marketing_folder_path) if marketing_folder_path else "",
        pre_start,
        pre_end,
        post_start,
        post_end,
        excluded_dates,
    )
    if dataset.empty:
        st.warning("No analyzable rows were found for the selected files and date ranges.")
        return

    campaign_df = cached_campaign_dataset(
        str(marketing_folder_path) if marketing_folder_path else "",
        pre_start,
        pre_end,
        post_start,
        post_end,
        excluded_dates,
    )

    with st.expander("Filters", expanded=True):
        platform_options = sorted(dataset["Platform"].unique().tolist())
        selected_platforms = st.multiselect("Platforms", platform_options, default=platform_options)
        filtered_df = dataset[dataset["Platform"].isin(selected_platforms)].copy()

        store_options = filtered_df["Store Label"].drop_duplicates().sort_values().tolist()
        selected_stores = st.multiselect(
            "Stores",
            store_options,
            default=[],
            help="Leave empty to analyze every available store in the selected platforms.",
        )
        if selected_stores:
            filtered_df = filtered_df[filtered_df["Store Label"].isin(selected_stores)]

    if filtered_df.empty:
        st.info("No rows remain after filtering.")
        return

    render_section_header("Diagnostic Summary", "Top-line movement for the filtered workspace.")
    render_summary_cards(filtered_df)
    render_growth_funnel_bubbles(filtered_df)
    render_narrative(filtered_df)

    st.download_button(
        "Download New Analysis (.xlsx)",
        data=build_download_workbook(filtered_df),
        file_name="new_analysis_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )

    tabs = st.tabs(["Overview", "Contribution", "Hierarchy Drilldown", "Marketing", "Top / Bottom", "GC / AOV", "Exceptions", "Notes"])

    with tabs[0]:
        left, right = st.columns(2)
        with left:
            st.write("**Top positive sales contributors**")
            render_driver_table(filtered_df, "Sales", "Store Label", "Store")
        with right:
            st.write("**Top negative spend / payout pressure points**")
            render_driver_table(filtered_df, "Payouts", "Store Label", "Store")
        summary_snapshot = build_summary_snapshot(filtered_df)
        if not summary_snapshot.empty:
            st.write("**What changed / where it came from**")
            st.dataframe(style_signed_table(summary_snapshot), use_container_width=True, hide_index=True)

    with tabs[1]:
        metric = st.selectbox("Metric", PRIMARY_METRICS, index=0, key="new_view_metric")
        hierarchy_labels = {
            "Platform": "Platform",
            "Store": "Store Label",
            "Day": "Day",
            "Slot": "Slot",
        }
        hierarchy_choice = st.radio("Hierarchy", list(hierarchy_labels.keys()), horizontal=True)
        render_driver_table(filtered_df, metric, hierarchy_labels[hierarchy_choice], hierarchy_choice)

    with tabs[2]:
        drill_metric = st.selectbox("Drilldown Metric", PRIMARY_METRICS, index=0, key="new_view_drill_metric")
        render_drilldown(filtered_df, drill_metric)

    with tabs[3]:
        render_marketing_tab(filtered_df, campaign_df)

    with tabs[4]:
        render_percentile_views(filtered_df, campaign_df)

    with tabs[5]:
        render_gc_bucket_analysis(filtered_df)

    with tabs[6]:
        exceptions_table = build_exceptions_table(filtered_df)
        if exceptions_table.empty:
            st.info("No major contradictory signals were detected in the current filter set.")
        else:
            st.write("**Priority exceptions to investigate**")
            st.dataframe(style_signed_table(exceptions_table), use_container_width=True, hide_index=True)

    with tabs[7]:
        render_data_notes()
