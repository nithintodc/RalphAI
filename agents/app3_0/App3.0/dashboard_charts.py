"""Reusable Plotly / Streamlit dashboard visuals for TODC analytics screens."""

from __future__ import annotations

import math
import uuid
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app_design import render_section_header


def _chart_key(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

COLOR_POSITIVE = "#059669"
COLOR_NEGATIVE = "#DC2626"
COLOR_NEUTRAL = "#94A3B8"
COLOR_PRE = "#6366F1"
COLOR_POST = "#2563EB"
CHART_BG = "#FFFFFF"
PAPER_BG = "#F8FAFC"
GRID_COLOR = "#E2E8F0"

METRIC_DEFINITIONS: dict[str, str] = {
    "Sales": "Gross order subtotal (excl. tax where applicable).",
    "Payouts": "Net payout to merchant after platform fees and adjustments.",
    "Orders": "Distinct order count in the selected window.",
    "AOV": "Average order value = Sales ÷ Orders.",
    "Spends": "Total marketing spend (promotion + sponsored listing fees).",
    "Marketing Fees": "DoorDash marketing fees from promotion and sponsored-listing files.",
    "Commission": "Platform take proxy = Sales − Payouts (aggregate pre vs post).",
    "ROAS": "Return on ad spend = Sales ÷ Spends; efficiency signal when spend > 0.",
    "Profitability%": "Payout margin = Payouts ÷ Sales × 100.",
    "Payout Margin %": "Payouts as a share of sales after aggregation.",
    "New Customers": "Customers acquired via marketing promotions (DoorDash).",
    "Existing Customers": "Orders minus new customers (approximate repeat base).",
    "Customer Discount": "Merchant-funded discount from promotion files.",
    "Corp Spend": "Corporate / DoorDash-funded marketing credit + third-party contribution.",
    "TODC Spend": "Merchant-funded discount plus marketing fees.",
    "Error Δ (ROAS)": "ROAS movement pre vs post — flags spend-efficiency shifts.",
    "GC Bucket": "Orders grouped by average ticket size (guest-count proxy).",
}

DEFAULT_KPI_METRICS = ["Sales", "Payouts", "Orders", "AOV", "Spends", "ROAS"]
DEFAULT_BAR_METRICS = ["Sales", "Payouts", "Orders", "AOV", "Spends", "ROAS", "New Customers"]
FUNNEL_METRIC_ORDER = [
    "Sales", "AOV", "Orders", "Payouts", "Spends", "Commission", "Error Δ (ROAS)",
]


def render_metric_definitions_expander(extra: Iterable[str] | None = None) -> None:
    """Collapsible metric glossary."""
    keys = list(METRIC_DEFINITIONS.keys())
    if extra:
        keys = list(dict.fromkeys(list(extra) + keys))
    with st.expander("Metric definitions", expanded=False):
        for name in keys:
            if name in METRIC_DEFINITIONS:
                st.markdown(f"**{name}** — {METRIC_DEFINITIONS[name]}")


def _growth_color(value: float) -> str:
    if not math.isfinite(value) or value == 0:
        return COLOR_NEUTRAL
    return COLOR_POSITIVE if value > 0 else COLOR_NEGATIVE


def _parse_table_row(table: pd.DataFrame, metric: str) -> dict | None:
    if table is None or table.empty or "Metric" not in table.columns:
        return None
    hit = table[table["Metric"] == metric]
    if hit.empty:
        return None
    row = hit.iloc[0]
    value_cols = [c for c in table.columns if c not in ("Metric", "Change", "Growth%", "Entity")]
    if len(value_cols) < 2:
        return None
    prev_col, curr_col = value_cols[0], value_cols[1]
    pre = pd.to_numeric(row.get(prev_col), errors="coerce")
    post = pd.to_numeric(row.get(curr_col), errors="coerce")
    change = pd.to_numeric(row.get("Change"), errors="coerce")
    growth = pd.to_numeric(row.get("Growth%"), errors="coerce")
    if pd.isna(change) and pd.notna(pre) and pd.notna(post):
        change = post - pre
    if pd.isna(growth) and pd.notna(pre) and pre != 0 and pd.notna(change):
        growth = change / abs(pre) * 100.0
    return {
        "Pre": float(pre) if pd.notna(pre) else float("nan"),
        "Post": float(post) if pd.notna(post) else float("nan"),
        "Delta": float(change) if pd.notna(change) else float("nan"),
        "Growth%": float(growth) if pd.notna(growth) else float("nan"),
        "prev_label": prev_col,
        "curr_label": curr_col,
    }


def commission_growth_from_table(table: pd.DataFrame) -> float:
    """Growth % on aggregate (Sales − Payouts)."""
    sales = _parse_table_row(table, "Sales")
    payouts = _parse_table_row(table, "Payouts")
    if not sales or not payouts:
        return float("nan")
    pre_c = sales["Pre"] - payouts["Pre"]
    post_c = sales["Post"] - payouts["Post"]
    if abs(pre_c) < 1e-9:
        return 0.0 if abs(post_c) < 1e-9 else float("nan")
    return (post_c - pre_c) / abs(pre_c) * 100.0


def build_funnel_from_tables(
    platform_tables: dict[str, pd.DataFrame],
    platform_labels: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Long-form bubble data from per-platform comparison tables."""
    labels = platform_labels or {"Combined": "Combined", "DD": "DoorDash", "UE": "UberEats"}
    metric_map = {
        "Sales": "Sales",
        "AOV": "AOV",
        "Orders": "Orders",
        "Payouts": "Payouts",
        "Spends": "Marketing Fees",
        "Commission": None,
        "Error Δ (ROAS)": "ROAS",
    }
    rows = []
    for plat_key, scope in labels.items():
        tbl = platform_tables.get(plat_key)
        empty = tbl is None or tbl.empty
        for display, source in metric_map.items():
            if source is None:
                g = commission_growth_from_table(tbl) if not empty else float("nan")
            else:
                parsed = _parse_table_row(tbl, source) if not empty else None
                g = parsed["Growth%"] if parsed else float("nan")
            rows.append(
                {
                    "Scope": scope,
                    "Metric": display,
                    "Growth %": g,
                    "Has data": not empty,
                }
            )
    return pd.DataFrame(rows)


def render_growth_funnel_bubbles_from_tables(
    platform_tables: dict[str, pd.DataFrame],
    platform_labels: dict[str, str] | None = None,
) -> None:
    """Matrix bubble chart: platforms × metrics with green/red % change."""
    render_section_header(
        "Growth funnel (pre vs post)",
        "Bubble size scales with |growth %|; green = up, red = down.",
    )
    long_df = build_funnel_from_tables(platform_tables, platform_labels)
    if long_df.empty:
        st.info("No data for growth funnel.")
        return

    fg = long_df["Growth %"].replace([np.inf, -np.inf], np.nan).dropna()
    cap = float(fg.abs().max()) if not fg.empty else 1.0
    if cap < 1e-9:
        cap = 1.0

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

    scopes = long_df["Scope"].unique().tolist()
    scope_order = [s for s in ["Combined", "DoorDash", "UberEats"] if s in scopes] + [
        s for s in scopes if s not in {"Combined", "DoorDash", "UberEats"}
    ]

    fig = go.Figure()
    for scope in scope_order:
        sub = long_df[long_df["Scope"] == scope]
        colors = []
        for _, r in sub.iterrows():
            if not r["Has data"]:
                colors.append("rgba(156,163,175,0.55)")
            elif not isinstance(r["Growth %"], (int, float)) or not math.isfinite(float(r["Growth %"])):
                colors.append("rgba(107,114,128,0.7)")
            elif r["Growth %"] >= 0:
                colors.append(COLOR_POSITIVE)
            else:
                colors.append(COLOR_NEGATIVE)
        fig.add_trace(
            go.Scatter(
                x=sub["Metric"],
                y=[scope] * len(sub),
                mode="markers+text",
                showlegend=False,
                marker=dict(size=sub["bubble_size"], color=colors, line=dict(width=1.5, color="#1f2937"), sizemode="diameter"),
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
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        xaxis=dict(categoryorder="array", categoryarray=FUNNEL_METRIC_ORDER, tickangle=-28, gridcolor=GRID_COLOR),
        yaxis=dict(categoryorder="array", categoryarray=list(reversed(scope_order)), gridcolor=GRID_COLOR),
    )
    st.plotly_chart(fig, width="stretch", key=_chart_key("chart"))
    st.caption(
        "Commission = aggregate (Sales − Payouts). Spends = Marketing Fees where available. "
        "ROAS / Error Δ reflects sales per marketing dollar when spend data exists."
    )


def render_kpi_cards_from_table(
    table: pd.DataFrame,
    metrics: Sequence[str] | None = None,
    format_value: Callable[[str, float], str] | None = None,
    format_delta: Callable[[str, float], str] | None = None,
) -> None:
    """KPI row: pre, post, delta, % change via st.metric."""
    if table is None or table.empty:
        return
    metric_list = list(metrics or DEFAULT_KPI_METRICS)
    cols = st.columns(len(metric_list))
    for idx, metric in enumerate(metric_list):
        parsed = _parse_table_row(table, metric)
        with cols[idx]:
            if not parsed:
                st.metric(metric, "—", "—")
                continue
            post_val = parsed["Post"]
            growth = parsed["Growth%"]
            delta = parsed["Delta"]
            display_post = format_value(metric, post_val) if format_value else f"{post_val:,.2f}"
            delta_help = format_delta(metric, delta) if format_delta else f"{delta:+,.2f}"
            growth_label = f"{growth:+.1f}%" if math.isfinite(growth) else "—"
            st.metric(
                metric,
                display_post,
                growth_label,
                help=f"{parsed['prev_label']}: {parsed['Pre']:,.2f} → {parsed['curr_label']}: {post_val:,.2f}. Δ {delta_help}",
            )


def render_grouped_bar_chart(
    table: pd.DataFrame,
    metrics: Sequence[str] | None = None,
    title: str = "Pre vs Post by metric",
) -> None:
    """Side-by-side grouped bars for period comparison."""
    if table is None or table.empty:
        return
    metric_list = [m for m in (metrics or DEFAULT_BAR_METRICS) if m in table["Metric"].values]
    if not metric_list:
        return
    subset = table[table["Metric"].isin(metric_list)].copy()
    value_cols = [c for c in subset.columns if c not in ("Metric", "Change", "Growth%", "Entity")]
    if len(value_cols) < 2:
        return
    prev_col, curr_col = value_cols[0], value_cols[1]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name=prev_col,
            x=subset["Metric"],
            y=pd.to_numeric(subset[prev_col], errors="coerce"),
            marker_color=COLOR_PRE,
        )
    )
    fig.add_trace(
        go.Bar(
            name=curr_col,
            x=subset["Metric"],
            y=pd.to_numeric(subset[curr_col], errors="coerce"),
            marker_color=COLOR_POST,
        )
    )
    fig.update_layout(
        barmode="group",
        title=title,
        height=380,
        margin=dict(l=24, r=24, t=48, b=48),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis=dict(gridcolor=GRID_COLOR),
    )
    st.plotly_chart(fig, width="stretch", key=_chart_key("chart"))


def render_waterfall_chart(
    table: pd.DataFrame,
    anchor_metric: str = "Sales",
    title: str = "Sales bridge (pre → post)",
) -> None:
    """Waterfall from pre level through change to post."""
    parsed = _parse_table_row(table, anchor_metric)
    if not parsed or not math.isfinite(parsed["Pre"]) or not math.isfinite(parsed["Post"]):
        return
    pre, post, delta = parsed["Pre"], parsed["Post"], parsed["Delta"]
    fig = go.Figure(
        go.Waterfall(
            name=anchor_metric,
            orientation="v",
            measure=["absolute", "relative", "total"],
            x=[parsed["prev_label"], "Change", parsed["curr_label"]],
            y=[pre, delta, post],
            text=[f"{pre:,.0f}", f"{delta:+,.0f}", f"{post:,.0f}"],
            textposition="outside",
            connector={"line": {"color": GRID_COLOR}},
            increasing={"marker": {"color": COLOR_POSITIVE}},
            decreasing={"marker": {"color": COLOR_NEGATIVE}},
            totals={"marker": {"color": COLOR_POST}},
        )
    )
    fig.update_layout(
        title=title,
        height=360,
        margin=dict(l=24, r=24, t=48, b=48),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch", key=_chart_key("chart"))


def render_delta_bar_chart(
    table: pd.DataFrame,
    metrics: Sequence[str] | None = None,
    title: str = "Metric deltas",
) -> None:
    """Horizontal bar chart of Change column — useful for multi-metric delta view."""
    if table is None or table.empty or "Change" not in table.columns:
        return
    metric_list = [m for m in (metrics or DEFAULT_BAR_METRICS) if m in table["Metric"].values]
    subset = table[table["Metric"].isin(metric_list)].copy()
    changes = pd.to_numeric(subset["Change"], errors="coerce")
    colors = [COLOR_POSITIVE if (v >= 0 and pd.notna(v)) else COLOR_NEGATIVE for v in changes]
    fig = go.Figure(
        go.Bar(
            y=subset["Metric"],
            x=changes,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+,.0f}" if pd.notna(v) else "" for v in changes],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        height=max(280, 40 * len(subset)),
        margin=dict(l=24, r=24, t=48, b=48),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        xaxis=dict(gridcolor=GRID_COLOR, zeroline=True, zerolinecolor=GRID_COLOR),
    )
    st.plotly_chart(fig, width="stretch", key=_chart_key("chart"))


def render_trend_lines(
    ts_df: pd.DataFrame,
    x_col: str,
    metric_cols: Sequence[str],
    title: str = "Trend over time",
    color_col: str | None = None,
) -> None:
    """Multi-series line chart for time granularity views."""
    if ts_df is None or ts_df.empty or x_col not in ts_df.columns:
        st.info("Not enough time buckets for a trend chart.")
        return
    fig = go.Figure()
    if color_col and color_col in ts_df.columns:
        for group, chunk in ts_df.groupby(color_col):
            for metric in metric_cols:
                if metric not in chunk.columns:
                    continue
                fig.add_trace(
                    go.Scatter(
                        x=chunk[x_col],
                        y=pd.to_numeric(chunk[metric], errors="coerce"),
                        mode="lines+markers",
                        name=f"{group} · {metric}",
                    )
                )
    else:
        for metric in metric_cols:
            if metric not in ts_df.columns:
                continue
            fig.add_trace(
                go.Scatter(
                    x=ts_df[x_col],
                    y=pd.to_numeric(ts_df[metric], errors="coerce"),
                    mode="lines+markers",
                    name=metric,
                )
            )
    fig.update_layout(
        title=title,
        height=400,
        margin=dict(l=24, r=24, t=48, b=48),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR),
    )
    st.plotly_chart(fig, width="stretch", key=_chart_key("chart"))


def build_monthly_trend_df(monthly_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Prepare monthly aggregates for trend charts from period_analysis_engine output."""
    from period_analysis_engine import aggregate_platform, format_month

    agg = aggregate_platform(monthly_df, platform)
    if agg.empty:
        return pd.DataFrame()
    out = agg.copy()
    out["Period Label"] = out["year_month"].map(format_month)
    rename = {
        "sales": "Sales",
        "payouts": "Payouts",
        "orders": "Orders",
        "aov": "AOV",
        "marketing_fees": "Spends",
        "new_customers": "New Customers",
        "profitability_pct": "Profitability%",
    }
    for src, dst in rename.items():
        if src in out.columns:
            out[dst] = out[src]
    if "Spends" in out.columns:
        out["ROAS"] = np.where(out["Spends"] > 0, out["Sales"] / out["Spends"], np.nan)
    return out


def build_timeseries_from_orders(
    df: pd.DataFrame,
    time_col: str,
    metrics: Sequence[str],
) -> pd.DataFrame:
    """Aggregate order-level comparison dataset by time bucket."""
    from new_analysis_engine import aggregate_metrics

    if df.empty or time_col not in df.columns:
        return pd.DataFrame()
    grouped = aggregate_metrics(df, [time_col])
    if grouped.empty:
        return pd.DataFrame()
    return grouped.sort_values(time_col)


def _pick_platform_table(
    platform_tables: dict[str, pd.DataFrame],
    preferred_keys: Sequence[str],
) -> pd.DataFrame | None:
    """Return the first non-empty table for preferred keys (avoids ambiguous DataFrame truth tests)."""
    for key in preferred_keys:
        tbl = platform_tables.get(key)
        if tbl is not None and not tbl.empty:
            return tbl
    return None


def build_strategic_diagnosis_from_tables(
    platform_tables: dict[str, pd.DataFrame],
    platform_labels: dict[str, str] | None = None,
) -> list[str]:
    """Multi-metric, multi-platform plain-language bullets."""
    labels = platform_labels or {"Combined": "Combined", "DD": "DoorDash", "UE": "UberEats"}
    bullets: list[str] = []
    for key, name in labels.items():
        tbl = platform_tables.get(key)
        if tbl is None or tbl.empty:
            bullets.append(f"**{name}**: no data in this window.")
            continue
        parts = []
        for metric in ("Sales", "Orders", "AOV", "Payouts", "Spends", "ROAS", "Marketing Fees"):
            if metric not in tbl["Metric"].values:
                continue
            p = _parse_table_row(tbl, metric)
            if not p or not math.isfinite(p["Growth%"]):
                continue
            direction = "up" if p["Growth%"] >= 0 else "down"
            parts.append(f"{metric} {direction} {abs(p['Growth%']):.1f}%")
        if parts:
            bullets.append(f"**{name}** — " + "; ".join(parts) + ".")
        comm_g = commission_growth_from_table(tbl)
        if math.isfinite(comm_g):
            direction = "widened" if comm_g >= 0 else "narrowed"
            bullets.append(f"**{name}** platform take (Sales − Payouts) {direction} {abs(comm_g):.1f}%.")

    combined = _pick_platform_table(platform_tables, ("Combined", *labels.keys()))
    if combined is not None:
        sales = _parse_table_row(combined, "Sales")
        orders = _parse_table_row(combined, "Orders")
        aov = _parse_table_row(combined, "AOV")
        if sales and orders and aov and all(math.isfinite(x["Growth%"]) for x in (sales, orders, aov)):
            if orders["Growth%"] > 0 and aov["Growth%"] < 0:
                bullets.append(
                    "Volume-led growth: orders rose while AOV softened — check discounting or mix shift."
                )
            elif orders["Growth%"] < 0 and aov["Growth%"] > 0:
                bullets.append(
                    "Ticket-led growth: fewer orders but higher AOV — concentration in larger checks."
                )
            spend = _parse_table_row(combined, "Spends") or _parse_table_row(combined, "Marketing Fees")
            if spend and spend["Delta"] > 0 and sales and sales["Delta"] < 0:
                bullets.append(
                    "Spend up while sales fell — review campaign efficiency and store-level ROAS."
                )
    return bullets


def render_strategic_diagnosis(bullets: list[str]) -> None:
    """Render diagnosis section with bullets."""
    render_section_header("Strategic Diagnosis", "Plain-language read across metrics and platforms.")
    if not bullets:
        st.info("Not enough data to generate a diagnosis.")
        return
    for bullet in bullets:
        st.markdown(f"- {bullet}")


def build_platform_comparison_tables_from_df(
    df: pd.DataFrame,
    summarize_fn: Callable[[pd.DataFrame, str], dict[str, float]],
    metrics: Sequence[str],
    platform_col: str = "Platform",
) -> dict[str, pd.DataFrame]:
    """Build DD / UE / Combined comparison tables from a pre/post order-level frame."""
    tables: dict[str, pd.DataFrame] = {}
    if df is None or df.empty:
        return tables
    tables["Combined"] = build_comparison_table_from_summaries(summarize_fn, df, metrics)
    for plat, key in (("DoorDash", "DD"), ("UberEats", "UE")):
        sub = df[df[platform_col] == plat] if platform_col in df.columns else pd.DataFrame()
        if not sub.empty:
            tables[key] = build_comparison_table_from_summaries(summarize_fn, sub, metrics)
    return tables


def build_comparison_table_from_summaries(
    summarize_fn: Callable[[pd.DataFrame, str], dict[str, float]],
    df: pd.DataFrame,
    metrics: Sequence[str],
    prev_label: str = "Pre",
    curr_label: str = "Post",
) -> pd.DataFrame:
    """Build a standard comparison table from a summarize_metric-style callback."""
    rows = []
    for metric in metrics:
        s = summarize_fn(df, metric)
        rows.append(
            {
                "Metric": metric,
                prev_label: s.get("Pre", float("nan")),
                curr_label: s.get("Post", float("nan")),
                "Change": s.get("Delta", float("nan")),
                "Growth%": s.get("Growth%", float("nan")),
            }
        )
    return pd.DataFrame(rows)


def render_comparison_dashboard(
    table: pd.DataFrame,
    format_value: Callable[[str, float], str] | None = None,
    format_delta: Callable[[str, float], str] | None = None,
    show_waterfall: bool = True,
    kpi_metrics: Sequence[str] | None = None,
    bar_metrics: Sequence[str] | None = None,
) -> None:
    """Full visual stack for a single comparison table: KPIs, bars, waterfall, delta bars."""
    if table is None or table.empty:
        st.info("No comparison data to visualize.")
        return
    render_kpi_cards_from_table(table, kpi_metrics, format_value, format_delta)
    c1, c2 = st.columns(2)
    with c1:
        render_grouped_bar_chart(table, bar_metrics)
    with c2:
        render_delta_bar_chart(table, bar_metrics)
    if show_waterfall and "Sales" in table["Metric"].values:
        render_waterfall_chart(table)
