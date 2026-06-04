"""
DeepDive HTML report generator — produces a beautiful single-file report
with tables, charts (matplotlib/base64), pivots, and narrative insights.
"""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from shared.config.settings import data_root


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(analysis: dict[str, Any], output_dir: Path | None = None) -> Path:
    """Generate a full HTML report from analysis results. Returns path to HTML file."""
    operator_id = analysis.get("operator_id", "unknown")
    sections = analysis.get("sections", {})

    if output_dir is None:
        output_dir = data_root() / "operators" / operator_id / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    html = _build_html(sections, operator_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"deepdive_{operator_id}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    return path


def as_json_dict(analysis: dict[str, Any]) -> dict:
    """Return JSON-serializable dict (strips non-serializable values)."""
    return json.loads(json.dumps(analysis, default=str))


# Legacy compat
def write_report(report) -> Path:
    from shared.models.report import DeepDiveReport
    path = data_root() / "operators" / report.operator_id / "reports" / "deepdive.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_report(operator_id: str):
    from shared.models.report import DeepDiveReport
    path = data_root() / "operators" / operator_id / "reports" / "deepdive.json"
    if not path.is_file():
        return None
    return DeepDiveReport.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# HTML Builder
# ---------------------------------------------------------------------------

def _build_html(sections: dict[str, Any], operator_id: str) -> str:
    summary = sections.get("executive_summary", {})
    fin = sections.get("financial", {})
    sales = sections.get("sales", {})
    mkt = sections.get("marketing", {})
    ops = sections.get("operations", {})
    sup = sections.get("support", {})
    mh = sections.get("metric_hierarchy") or {}

    parts: list[str] = []
    parts.append(_html_head(operator_id))
    parts.append('<body><div class="container">')

    # Header
    parts.append(f"""
    <div class="header">
        <h1>DeepDive Analytics Report</h1>
        <p class="subtitle">Operator: <strong>{operator_id}</strong> | Generated: {datetime.now().strftime("%B %d, %Y %I:%M %p")}</p>
    </div>
    """)

    # Executive Summary
    parts.append(_section_executive_summary(summary))

    # KPI Cards
    parts.append(_section_kpi_cards(summary))

    # Hierarchical metrics (FINANCIAL_DETAILED delivered orders)
    parts.append(_section_metric_hierarchy(mh))

    # Tab controls
    parts.append("""
    <div class="tabs">
        <button class="tab-btn active" data-tab="financials">Financials</button>
        <button class="tab-btn" data-tab="sales">Sales</button>
        <button class="tab-btn" data-tab="marketing">Marketing</button>
        <button class="tab-btn" data-tab="operations">Operations</button>
    </div>
    """)

    # Tab panels
    parts.append('<div id="financials" class="tab-panel active">')
    parts.append(_section_financial(fin))
    parts.append('</div>')

    parts.append('<div id="sales" class="tab-panel">')
    parts.append(_section_sales(sales))
    parts.append('</div>')

    parts.append('<div id="marketing" class="tab-panel">')
    parts.append(_section_marketing(mkt))
    parts.append('</div>')

    # Keep support grouped with operations for a cleaner top-level view.
    parts.append('<div id="operations" class="tab-panel">')
    parts.append(_section_operations(ops))
    parts.append(_section_support(sup))
    parts.append('</div>')

    parts.append('</div></body></html>')
    return "\n".join(parts)


def _html_head(title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DeepDive — {title}</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Outfit', system-ui, sans-serif; background: #ffffff; color: #252525; line-height: 1.6; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
.header {{
    background: linear-gradient(135deg, #04493a 0%, #046e54 40%, #049772 100%);
    color: white; padding: 44px 40px; border-radius: 16px; margin-bottom: 28px;
    box-shadow: 0 24px 60px -32px rgb(4 73 58 / 0.35);
    position: relative; overflow: hidden;
}}
.header::before {{
    content: ''; position: absolute; top: -50%; right: -20%; width: 60%; height: 200%;
    background: radial-gradient(circle, rgb(5 215 159 / 0.2), transparent 60%);
    pointer-events: none;
}}
.header h1 {{ font-size: 2.2em; font-weight: 700; margin-bottom: 8px; letter-spacing: -0.5px; position: relative; }}
.subtitle {{ opacity: 0.85; font-size: 1.05em; font-weight: 300; position: relative; }}
.section {{
    background: linear-gradient(135deg, rgb(255 255 255 / 0.92), rgb(241 252 248 / 0.88));
    border-radius: 14px; padding: 28px; margin-bottom: 20px;
    box-shadow: 0 0 0 1px rgb(37 37 37 / 0.06), 0 24px 60px -32px rgb(37 37 37 / 0.10);
    backdrop-filter: blur(18px);
}}
.section h2 {{ font-size: 1.5em; color: #252525; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 3px solid #05d79f; display: inline-block; font-weight: 600; }}
.section h3 {{ font-size: 1.15em; color: #3f3f3f; margin: 20px 0 12px; font-weight: 500; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.kpi-card {{
    background: linear-gradient(135deg, rgb(255 255 255 / 0.95), rgb(241 252 248 / 0.90));
    border-radius: 14px; padding: 22px 20px;
    box-shadow: 0 0 0 1px rgb(37 37 37 / 0.06), 0 20px 50px -32px rgb(37 37 37 / 0.14);
    text-align: center; border-top: 4px solid #05d79f;
    backdrop-filter: blur(18px); transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
.kpi-card:hover {{ transform: translateY(-2px); box-shadow: 0 0 0 1px rgb(37 37 37 / 0.08), 0 28px 60px -28px rgb(37 37 37 / 0.18); }}
.kpi-card.green {{ border-top-color: #049772; }}
.kpi-card.blue {{ border-top-color: #41e2b8; }}
.kpi-card.orange {{ border-top-color: #7deccf; }}
.kpi-card.purple {{ border-top-color: #b0f4e2; }}
.kpi-value {{ font-size: 2em; font-weight: 700; color: #252525; }}
.kpi-label {{ font-size: 0.82em; color: #6a6a6a; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 500; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.9em; }}
th {{ background: #252525; color: white; padding: 11px 14px; text-align: left; font-weight: 500; white-space: nowrap; letter-spacing: 0.3px; }}
th:first-child {{ border-radius: 8px 0 0 0; }}
th:last-child {{ border-radius: 0 8px 0 0; }}
td {{ padding: 9px 14px; border-bottom: 1px solid #e7e7e7; }}
tr:nth-child(even) {{ background: rgb(241 252 248 / 0.5); }}
tr:hover {{ background: rgb(5 215 159 / 0.08); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.chart-container {{ text-align: center; margin: 16px 0; }}
.chart-container img {{ max-width: 100%; border-radius: 10px; box-shadow: 0 4px 16px rgb(37 37 37 / 0.06); }}
.insights-list {{ list-style: none; padding: 0; }}
.insights-list li {{ padding: 12px 18px; margin: 8px 0; background: rgb(241 252 248 / 0.9); border-left: 4px solid #05d79f; border-radius: 6px; font-size: 0.95em; font-weight: 400; }}
.insights-list li.warning {{ background: rgb(125 236 207 / 0.15); border-left-color: #049772; }}
.insights-list li.danger {{ background: rgb(4 73 58 / 0.06); border-left-color: #04493a; color: #04493a; font-weight: 500; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
.pill {{ display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }}
.pill-green {{ background: #d5fbf1; color: #04493a; }}
.pill-red {{ background: #f8d7da; color: #721c24; }}
.pill-blue {{ background: #b0f4e2; color: #046e54; }}
.tabs {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin: 8px 0 16px;
}}
.tab-btn {{
    border: 1px solid #d7ece5;
    background: white;
    color: #04493a;
    border-radius: 999px;
    padding: 8px 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
}}
.tab-btn:hover {{ background: #f1fcf8; }}
.tab-btn.active {{
    background: #05d79f;
    border-color: #05d79f;
    color: #252525;
}}
.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; }}
.table-scroll {{ max-height: 460px; overflow: auto; border: 1px solid #e7e7e7; border-radius: 10px; margin: 12px 0; }}
.table-scroll table {{ margin: 0; }}
</style>
<script>
document.addEventListener("DOMContentLoaded", function () {{
  const buttons = Array.from(document.querySelectorAll(".tab-btn"));
  const panels = Array.from(document.querySelectorAll(".tab-panel"));
  buttons.forEach((btn) => {{
    btn.addEventListener("click", () => {{
      const tab = btn.getAttribute("data-tab");
      buttons.forEach((b) => b.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = document.getElementById(tab);
      if (panel) panel.classList.add("active");
    }});
  }});
}});
</script>
</head>"""


# ---------------------------------------------------------------------------
# Section Builders
# ---------------------------------------------------------------------------

def _section_executive_summary(s: dict) -> str:
    if not s:
        return ""
    insights = s.get("insights", [])
    items = ""
    for ins in insights:
        css = ""
        if "elevated" in ins.lower() or "investigate" in ins.lower():
            css = ' class="danger"'
        elif "room to grow" in ins.lower() or "consider" in ins.lower():
            css = ' class="warning"'
        items += f"<li{css}>{ins}</li>\n"

    return f"""
    <div class="section">
        <h2>Executive Summary</h2>
        <ul class="insights-list">{items}</ul>
    </div>
    """


def _section_metric_hierarchy(mh: dict) -> str:
    """Hierarchical rollups: overall → store → store×slot → … → slot (all days, all stores)."""
    if not mh or mh.get("source") == "none":
        msg = mh.get("message", "No hierarchy data.") if isinstance(mh, dict) else "No data."
        return f"""
    <div class="section">
        <h2>Performance hierarchy</h2>
        <p style="color:#555;">{msg} Place export zips under <strong>data/TriArch</strong> (CLI default) or upload zips that include <strong>FINANCIAL_DETAILED_TRANSACTIONS</strong> with order timestamps.</p>
    </div>
    """

    desc = mh.get("description", "")
    money = ["sales", "payouts", "aov", "mode_order_value", "commission", "marketing_fees", "net_per_order"]
    metric_map = {
        "orders": "Orders",
        "sales": "Sales ($)",
        "payouts": "Payouts ($)",
        "profitability_pct": "Profitability %",
        "aov": "AOV ($)",
        "mode_order_value": "Mode order ($)",
        "commission": "Commission ($)",
        "marketing_fees": "Mkt fees ($)",
        "net_per_order": "Net / order ($)",
    }

    def _wrap(t: str) -> str:
        return f'<div class="table-scroll">{t}</div>'

    parts: list[str] = [
        '<div class="section">',
        "<h2>Performance hierarchy</h2>",
        f'<p style="color:#555;font-size:0.95em;margin-bottom:14px;">{desc}</p>',
    ]

    ov = mh.get("overall")
    if ov:
        parts.append("<h3>1. Overall</h3>")
        parts.append(
            _wrap(
                _table(
                    [ov],
                    {"label": "Scope", **metric_map},
                    money_cols=money,
                    number_cols=["orders", "profitability_pct"],
                )
            )
        )

    keys = [
        ("by_store", "2. Store level", {"store_id": "Store ID", "store_name": "Store"}),
        ("by_store_slot", "3. Store × slot (all weekdays)", {"store_id": "Store ID", "store_name": "Store", "slot": "Slot"}),
        ("by_store_weekday", "4. Store × weekday", {"store_id": "Store ID", "store_name": "Store", "weekday": "Weekday"}),
        (
            "by_store_weekday_slot",
            "5. Store × weekday × slot",
            {"store_id": "Store ID", "store_name": "Store", "weekday": "Weekday", "slot": "Slot"},
        ),
        ("by_weekday_all_stores", "6. Weekday (all stores)", {"weekday": "Weekday"}),
        ("by_weekday_slot_all_stores", "7. Weekday × slot (all stores)", {"weekday": "Weekday", "slot": "Slot"}),
        ("by_slot_all_stores", "8. Slot (all stores, all weekdays)", {"slot": "Slot"}),
    ]

    for key, title, dim_map in keys:
        rows = mh.get(key) or []
        if not rows:
            continue
        parts.append(f"<h3>{title}</h3>")
        parts.append(_wrap(_table(rows, {**dim_map, **metric_map}, money_cols=money, number_cols=["orders", "profitability_pct"])))

    parts.append("</div>")
    return "\n".join(parts)


def _section_kpi_cards(s: dict) -> str:
    if not s:
        return ""
    cards = [
        ("Total Revenue", f"${s.get('total_revenue', 0):,.0f}", ""),
        ("Net Payout", f"${s.get('total_net_payout', 0):,.0f}", "green"),
        ("Total Orders", f"{s.get('total_orders', 0):,}", "blue"),
        ("Avg Order Value", f"${s.get('avg_order_value', 0):,.2f}", "purple"),
        ("DashPass Rate", f"{s.get('dashpass_rate_pct', 0):.1f}%", "blue"),
        ("Marketing ROAS", f"{s.get('marketing_roas', 0):.1f}x", "green"),
        ("New Customers", f"{s.get('new_customers_acquired', 0):,}", "orange"),
        ("Cancel Rate", f"{s.get('cancellation_rate_pct', 0):.1f}%", ""),
        ("Support Cases", f"{s.get('total_support_cases', 0):,}", "orange"),
        ("Avg Wait Time", f"{s.get('avg_avoidable_wait_min', 0):.1f} min", "purple"),
    ]
    html = '<div class="kpi-grid">\n'
    for label, value, color in cards:
        cls = f" {color}" if color else ""
        html += f'<div class="kpi-card{cls}"><div class="kpi-value">{value}</div><div class="kpi-label">{label}</div></div>\n'
    html += '</div>\n'
    return html


def _section_financial(fin: dict) -> str:
    if not fin:
        return ""
    parts = ['<div class="section"><h2>Financial Analysis</h2>']

    # Summary table
    summary_rows = [
        ("Total Subtotal (Gross Sales)", f"${fin.get('total_subtotal', 0):,.2f}"),
        ("Total Net Revenue (Payouts)", f"${fin.get('total_net_revenue', 0):,.2f}"),
        ("Total Commission", f"${fin.get('total_commission', 0):,.2f}"),
        ("Total Marketing Fees", f"${fin.get('total_marketing_fees', 0):,.2f}"),
        ("Merchant-Funded Discounts", f"${fin.get('total_customer_discounts_funded_by_you', 0):,.2f}"),
        ("Avg Order Value", f"${fin.get('avg_order_value', 0):,.2f}"),
        ("Avg Net per Order", f"${fin.get('avg_net_per_order', 0):,.2f}"),
        ("Payout Ratio", f"{fin.get('payout_ratio', 0):.1f}%"),
        ("Error Charges", f"${fin.get('total_error_charges', 0):,.2f}"),
        ("Adjustments", f"${fin.get('total_adjustments', 0):,.2f}"),
    ]
    parts.append(_kv_table(summary_rows))

    # Daily revenue chart
    daily = fin.get("daily_trend", [])
    if daily:
        parts.append('<h3>Daily Revenue Trend</h3>')
        parts.append(_chart_line(
            [r["date"] for r in daily],
            [r["subtotal"] for r in daily],
            "Gross Sales ($)", color=_BRAND_500,
            secondary_data=[r["net_total"] for r in daily],
            secondary_label="Net Payout ($)", secondary_color=_BRAND_900
        ))

    # Monthly breakdown
    monthly = fin.get("monthly_breakdown", [])
    if monthly:
        parts.append('<h3>Monthly Breakdown</h3>')
        parts.append(_table(monthly, {
            "month": "Month", "orders": "Orders", "subtotal": "Gross Sales", "net_total": "Net Payout"
        }, money_cols=["subtotal", "net_total"], number_cols=["orders"]))

    # By store
    by_store = fin.get("by_store", [])
    if by_store:
        parts.append('<h3>Revenue by Store</h3>')
        parts.append(_table(by_store[:10], {
            "Store name": "Store", "orders": "Orders", "subtotal": "Gross Sales",
            "net_total": "Net Payout", "commission": "Commission", "aov": "AOV"
        }, money_cols=["subtotal", "net_total", "commission", "aov"], number_cols=["orders"]))

        # Bar chart
        top5 = by_store[:5]
        parts.append(_chart_bar(
            [_short_name(r["Store name"]) for r in top5],
            [r["subtotal"] for r in top5],
            "Top 5 Stores — Gross Sales ($)", color=_BRAND_800
        ))

    parts.append('</div>')
    return "\n".join(parts)


def _section_sales(sales: dict) -> str:
    if not sales:
        return ""
    parts = ['<div class="section"><h2>Sales Analysis</h2>']

    # Order-level summary
    summary_rows = [
        ("Total Orders", f"{sales.get('total_orders', 0):,}"),
        ("Total Subtotal", f"${sales.get('total_subtotal', 0):,.2f}"),
        ("Avg Order Value", f"${sales.get('avg_order_value', 0):,.2f}"),
        ("DashPass Orders", f"{sales.get('dashpass_orders', 0):,} ({sales.get('dashpass_rate', 0):.1f}%)"),
        ("Cancelled Orders", f"{sales.get('cancelled_orders', 0):,} ({sales.get('cancellation_rate', 0):.1f}%)"),
        ("Missing/Incorrect", f"{sales.get('missing_or_incorrect_count', 0):,} ({sales.get('error_rate', 0):.1f}%)"),
    ]
    if sales.get("avg_rating"):
        summary_rows.append(("Avg Rating", f"{sales['avg_rating']} ({sales.get('rated_orders_pct', 0):.0f}% rated)"))
    parts.append(_kv_table(summary_rows))

    # Daily order volume chart
    daily = sales.get("daily_orders", [])
    if daily:
        parts.append('<h3>Daily Order Volume</h3>')
        parts.append(_chart_line(
            [r["date"] for r in daily],
            [r["orders"] for r in daily],
            "Orders", color=_BRAND_600
        ))

    # Day of week
    dow = sales.get("day_of_week", [])
    if dow:
        parts.append('<h3>Orders by Day of Week</h3>')
        parts.append(_chart_bar(
            [r["dow"] for r in dow],
            [r["orders"] for r in dow],
            "Orders by Day of Week", color=_BRAND_700
        ))

    # Store performance
    sp = sales.get("store_performance", [])
    if sp:
        parts.append('<h3>Store Performance (Product View)</h3>')
        display_cols = {}
        for c in ["Store Name", "Merchant Supplied ID", "Gross Sales", "Total Delivered or Picked Up Orders", "AOV", "Total Commission", "Dashpass Sales", "Dashpass Orders"]:
            if any(c in r for r in sp):
                display_cols[c] = c.replace("Total Delivered or Picked Up Orders", "Delivered Orders")
        parts.append(_table(sp, display_cols, money_cols=["Gross Sales", "AOV", "Total Commission", "Dashpass Sales"]))

    # Store customer view
    sc = sales.get("store_customers", [])
    if sc:
        parts.append('<h3>Store Performance (Customer View)</h3>')
        display_cols = {}
        for c in ["Store Name", "Gross Sales", "Total Delivered or Picked Up Orders", "New Customer Count", "Existing Customer Count", "Dashpass Customer Count"]:
            if any(c in r for r in sc):
                display_cols[c] = c.replace("Total Delivered or Picked Up Orders", "Delivered Orders")
        parts.append(_table(sc, display_cols, money_cols=["Gross Sales"]))

    # Time series customers
    tsc = sales.get("time_series_customers", [])
    if tsc and len(tsc) > 5:
        parts.append('<h3>New vs Existing Customers Over Time</h3>')
        dates = [r.get("Start Date", "") for r in tsc]
        new_c = [r.get("New Customer Count", 0) for r in tsc]
        exist_c = [r.get("Existing Customer Count", 0) for r in tsc]
        parts.append(_chart_line(dates, new_c, "New Customers", _BRAND_500,
                                  secondary_data=exist_c, secondary_label="Existing Customers", secondary_color=_BRAND_800))

    parts.append('</div>')
    return "\n".join(parts)


def _section_marketing(mkt: dict) -> str:
    if not mkt:
        return ""
    parts = ['<div class="section"><h2>Marketing Analysis</h2>']

    # Combined summary
    parts.append('<div class="two-col"><div>')
    parts.append('<h3>Promotions</h3>')
    promo_rows = [
        ("Total Orders", f"{mkt.get('promo_total_orders', 0):,.0f}"),
        ("Total Sales", f"${mkt.get('promo_total_sales', 0):,.2f}"),
        ("Total Spend", f"${mkt.get('promo_total_spend', 0):,.2f}"),
        ("ROAS", f"{mkt.get('promo_roas', 0):.2f}x"),
        ("Cost per Order", f"${mkt.get('promo_cost_per_order', 0):,.2f}"),
        ("New Customers", f"{mkt.get('promo_new_customers', 0):,.0f}"),
        ("Cost per New Customer", f"${mkt.get('promo_cost_per_new_customer', 0):,.2f}"),
    ]
    parts.append(_kv_table(promo_rows))
    parts.append('</div><div>')

    parts.append('<h3>Sponsored Listings</h3>')
    sp_rows = [
        ("Total Impressions", f"{mkt.get('sponsored_impressions', 0):,.0f}"),
        ("Total Clicks", f"{mkt.get('sponsored_clicks', 0):,.0f}"),
        ("CTR", f"{mkt.get('sponsored_ctr', 0):.2f}%"),
        ("Total Orders", f"{mkt.get('sponsored_total_orders', 0):,.0f}"),
        ("Total Sales", f"${mkt.get('sponsored_total_sales', 0):,.2f}"),
        ("Total Spend", f"${mkt.get('sponsored_total_spend', 0):,.2f}"),
        ("ROAS", f"{mkt.get('sponsored_roas', 0):.2f}x"),
        ("Conversion Rate", f"{mkt.get('sponsored_conversion_rate', 0):.1f}%"),
    ]
    parts.append(_kv_table(sp_rows))
    parts.append('</div></div>')

    # Corporate vs TODC
    corp_promo = mkt.get("corporate_vs_todc_promos", [])
    if corp_promo:
        parts.append('<h3>Corporate vs TODC — Promotions</h3>')
        parts.append(_table(corp_promo, {
            "segment": "Segment", "orders": "Orders", "sales": "Sales",
            "spend": "Spend", "roas": "ROAS", "new_customers": "New Customers", "cost_per_order": "CPO"
        }, money_cols=["sales", "spend", "cost_per_order"]))

        # Pie chart
        labels = [r["segment"] for r in corp_promo]
        values = [r["sales"] for r in corp_promo]
        parts.append(_chart_pie(labels, values, "Promo Sales: Corporate vs TODC"))

    corp_sp = mkt.get("corporate_vs_todc_sponsored", [])
    if corp_sp:
        parts.append('<h3>Corporate vs TODC — Sponsored Listings</h3>')
        parts.append(_table(corp_sp, {
            "segment": "Segment", "orders": "Orders", "sales": "Sales",
            "spend": "Spend", "roas": "ROAS", "impressions": "Impressions", "clicks": "Clicks", "ctr": "CTR%"
        }, money_cols=["sales", "spend"]))

    # Top campaigns
    top_camp = mkt.get("top_promo_campaigns", [])
    if top_camp:
        parts.append('<h3>Top Promotion Campaigns</h3>')
        parts.append(_table(top_camp[:10], {
            "Campaign name": "Campaign", "orders": "Orders", "sales": "Sales",
            "spend": "Spend", "roas": "ROAS", "new_customers": "New Cust."
        }, money_cols=["sales", "spend"]))

    # Monthly promo trend
    promo_trend = mkt.get("promo_monthly_trend", [])
    if promo_trend:
        parts.append('<h3>Monthly Promotion Trend</h3>')
        parts.append(_chart_bar(
            [r["month"] for r in promo_trend],
            [r["sales"] for r in promo_trend],
            "Promo Sales ($)", color=_BRAND_600
        ))
        parts.append(_table(promo_trend, {
            "month": "Month", "orders": "Orders", "sales": "Sales",
            "spend": "Spend", "roas": "ROAS", "new_customers": "New Cust."
        }, money_cols=["sales", "spend"]))

    parts.append('</div>')
    return "\n".join(parts)


def _section_operations(ops: dict) -> str:
    if not ops:
        return ""
    parts = ['<div class="section"><h2>Operations & Quality</h2>']

    # Avoidable Wait
    if ops.get("total_orders_with_wait_data"):
        parts.append('<h3>Avoidable Wait Time</h3>')
        wait_rows = [
            ("Orders Analyzed", f"{ops['total_orders_with_wait_data']:,}"),
            ("Avg Avoidable Wait", f"{ops.get('avg_avoidable_wait_min', 0):.2f} min"),
            ("Avg Total Delivery Time", f"{ops.get('avg_delivery_time_min', 0):.2f} min"),
        ]
        parts.append(_kv_table(wait_rows))

        # Wait distribution chart
        wait_dist = ops.get("wait_distribution", {})
        if wait_dist:
            parts.append(_chart_bar(
                list(wait_dist.keys()),
                list(wait_dist.values()),
                "Avoidable Wait Distribution", color=_BRAND_800
            ))

        # By store
        wait_store = ops.get("wait_by_store", [])
        if wait_store:
            parts.append(_table(wait_store[:10], {
                "Store Name": "Store", "orders": "Orders",
                "avg_wait": "Avg Wait (min)", "avg_delivery": "Avg Delivery (min)", "p90_wait": "P90 Wait (min)"
            }))

    # Cancellations
    if ops.get("total_cancellations"):
        parts.append('<h3>Cancellations</h3>')
        parts.append(f'<p>Total: <strong>{ops["total_cancellations"]}</strong> | Paid: {ops.get("cancellations_paid", 0)} | Unpaid: {ops.get("cancellations_unpaid", 0)}</p>')

        reasons = ops.get("cancellation_reasons", {})
        if reasons:
            parts.append(_chart_pie(list(reasons.keys()), list(reasons.values()), "Cancellation Reasons"))

        cancel_store = ops.get("cancellations_by_store", [])
        if cancel_store:
            parts.append(_table(cancel_store[:10], {
                "Store Name": "Store", "cancellations": "Cancellations"
            }))

    # Missing / Incorrect
    if ops.get("total_error_items"):
        parts.append('<h3>Missing & Incorrect Items</h3>')
        err_rows = [
            ("Total Error Items", f"{ops['total_error_items']:,}"),
            ("Total Error Charges", f"${ops.get('total_error_charges', 0):,.2f}"),
        ]
        parts.append(_kv_table(err_rows))

        cats = ops.get("error_categories", {})
        if cats:
            parts.append(_chart_pie(list(cats.keys()), list(cats.values()), "Error Categories"))

        top_items = ops.get("top_error_items", [])
        if top_items:
            parts.append('<h3>Top Items with Errors</h3>')
            parts.append(_table(top_items[:10], {
                "Item Name": "Item", "count": "Count", "total_charge": "Total Charge ($)"
            }, money_cols=["total_charge"]))

        menu_cats = ops.get("errors_by_menu_category", [])
        if menu_cats:
            parts.append('<h3>Errors by Menu Category</h3>')
            parts.append(_table(menu_cats[:10], {
                "Menu Category": "Category", "count": "Count", "total_charge": "Total Charge ($)"
            }, money_cols=["total_charge"]))

    parts.append('</div>')
    return "\n".join(parts)


def _section_support(sup: dict) -> str:
    if not sup:
        return ""
    parts = ['<div class="section"><h2>Support & Refunds</h2>']

    summary_rows = [
        ("Total Support Cases", f"{sup.get('total_support_cases', 0):,}"),
        ("Total Original Order Value", f"${sup.get('total_original_order_value', 0):,.2f}"),
        ("Total Refund to Customer", f"${sup.get('total_refund_to_customer', 0):,.2f}"),
        ("Total Refund to Store", f"${sup.get('total_refund_to_store', 0):,.2f}"),
        ("Full Refund %", f"{sup.get('full_refund_pct', 0):.1f}%"),
    ]
    parts.append(_kv_table(summary_rows))

    # Primary reasons
    primary = sup.get("primary_reasons", {})
    if primary:
        parts.append('<h3>Primary Reasons</h3>')
        parts.append(_chart_pie(list(primary.keys()), list(primary.values()), "Support — Primary Reasons"))

    # Responsible party
    party = sup.get("responsible_party", {})
    if party:
        parts.append('<h3>Responsible Party</h3>')
        parts.append(_chart_pie(list(party.keys()), list(party.values()), "Refund Responsibility"))

    # By store
    by_store = sup.get("support_by_store", [])
    if by_store:
        parts.append('<h3>Support Cases by Store</h3>')
        parts.append(_table(by_store[:10], {
            "Store name": "Store", "cases": "Cases"
        }))

    # Monthly trend
    monthly = sup.get("monthly_support_trend", [])
    if monthly:
        parts.append('<h3>Monthly Support Trend</h3>')
        parts.append(_chart_bar(
            [r["month"] for r in monthly],
            [r["cases"] for r in monthly],
            "Support Cases by Month", color=_BRAND_900
        ))

    parts.append('</div>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Chart helpers (matplotlib -> base64 PNG)
# ---------------------------------------------------------------------------

# Brand-aligned chart colors (teal/green palette matching dashboard)
_BRAND_500 = "#05d79f"
_BRAND_600 = "#05c391"
_BRAND_700 = "#049772"
_BRAND_800 = "#046e54"
_BRAND_900 = "#04493a"
_BRAND_300 = "#7deccf"
_BRAND_200 = "#b0f4e2"
_INK_900 = "#252525"
_INK_700 = "#3f3f3f"
_INK_400 = "#8a8a8a"
_CHART_PALETTE = [_BRAND_500, _BRAND_900, _BRAND_700, _BRAND_300, _INK_700, _BRAND_200, "#41e2b8", _BRAND_800]


def _style_ax(ax):
    """Apply consistent brand styling to axes."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#e7e7e7")
    ax.spines["bottom"].set_color("#e7e7e7")
    ax.tick_params(colors=_INK_700, labelsize=9)
    ax.grid(axis="y", alpha=0.15, color=_INK_400)


def _chart_line(x, y, label, color=_BRAND_500, secondary_data=None, secondary_label=None, secondary_color=_BRAND_900) -> str:
    fig, ax = plt.subplots(figsize=(12, 4), dpi=120)
    fig.patch.set_facecolor("white")
    n = len(x)
    step = max(1, n // 15)
    ax.plot(range(n), y, color=color, linewidth=2.2, label=label)
    ax.fill_between(range(n), y, alpha=0.08, color=color)
    if secondary_data:
        ax.plot(range(n), secondary_data, color=secondary_color, linewidth=2, label=secondary_label, linestyle="--")
        ax.legend(fontsize=9, frameon=False)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([x[i] for i in range(0, n, step)], rotation=45, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}" if max(y) > 100 else f"{v:,.0f}"))
    _style_ax(ax)
    ax.set_title(label, fontsize=12, fontweight="bold", pad=12, color=_INK_900, fontfamily="sans-serif")
    fig.tight_layout()
    return _fig_to_html(fig)


def _chart_bar(labels, values, title, color=_BRAND_700) -> str:
    fig, ax = plt.subplots(figsize=(10, 4), dpi=120)
    fig.patch.set_facecolor("white")
    bars = ax.bar(range(len(labels)), values, color=color, alpha=0.88, width=0.6,
                  edgecolor="white", linewidth=0.5)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{val:,.0f}",
                ha="center", va="bottom", fontsize=8, color=_INK_700)
    _style_ax(ax)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12, color=_INK_900, fontfamily="sans-serif")
    fig.tight_layout()
    return _fig_to_html(fig)


def _chart_pie(labels, values, title) -> str:
    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=120)
    fig.patch.set_facecolor("white")
    wedges, texts, autotexts = ax.pie(
        values, labels=None, autopct="%1.1f%%", startangle=90,
        colors=_CHART_PALETTE[:len(labels)], pctdistance=0.8,
        wedgeprops={"edgecolor": "white", "linewidth": 2}
    )
    for t in autotexts:
        t.set_fontsize(8)
        t.set_fontweight("bold")
        t.set_color(_INK_900)
    ax.legend(
        wedges,
        labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=9,
        labelcolor=_INK_700,
        title="Categories",
        title_fontsize=10,
    )
    ax.set_title(title, fontsize=12, fontweight="bold", pad=15, color=_INK_900, fontfamily="sans-serif")
    fig.tight_layout(rect=(0, 0, 0.82, 1))
    return _fig_to_html(fig)


def _fig_to_html(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    return f'<div class="chart-container"><img src="data:image/png;base64,{b64}" alt="chart"></div>'


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _table(rows: list[dict], col_map: dict[str, str], money_cols: list[str] | None = None, number_cols: list[str] | None = None) -> str:
    if not rows:
        return "<p><em>No data</em></p>"
    money_cols = money_cols or []
    number_cols = number_cols or []
    headers = "".join(f"<th>{label}</th>" for label in col_map.values())
    body = ""
    for r in rows:
        cells = ""
        for key in col_map:
            val = r.get(key, "")
            if key in money_cols and isinstance(val, (int, float)):
                cells += f'<td class="num">${val:,.2f}</td>'
            elif key in number_cols and isinstance(val, (int, float)):
                cells += f'<td class="num">{val:,}</td>'
            elif isinstance(val, float):
                cells += f'<td class="num">{val:,.2f}</td>'
            elif isinstance(val, int):
                cells += f'<td class="num">{val:,}</td>'
            else:
                cells += f"<td>{val}</td>"
        body += f"<tr>{cells}</tr>\n"
    return f"<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"


def _kv_table(rows: list[tuple[str, str]]) -> str:
    body = ""
    for label, val in rows:
        body += f"<tr><td><strong>{label}</strong></td><td class='num'>{val}</td></tr>\n"
    return f'<table style="max-width:500px"><tbody>{body}</tbody></table>'


def _short_name(name: str, max_len: int = 25) -> str:
    return name[:max_len] + "..." if len(name) > max_len else name
