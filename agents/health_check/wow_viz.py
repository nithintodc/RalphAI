"""
Register-style WoW visualization for Health Check (no GC bucketing, no filters).

Compares two weekly CSVs at store × day × daypart — same grain as Super App Register.
"""

from __future__ import annotations

import json
import logging
import math
import numbers
from pathlib import Path
from typing import Optional

from agents.health_check.health_summary import build_health_summary, build_wow_table_payload
from shared.register_wow import build_slack_summary, compare_register_slots

logger = logging.getLogger(__name__)

VIZ_COLUMNS = [
    "Merchant Store ID",
    "Week",
    "Day",
    "Day part",
    "Sales",
    "Payouts",
    "Orders",
    "AOV",
]


def _json_safe(value):
    """Return a structure that can be emitted as strict browser JSON."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def load_weekly_rows(csv_path: Path) -> list[dict]:
    import pandas as pd

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    cols = [c for c in VIZ_COLUMNS if c in df.columns]
    missing = [c for c in VIZ_COLUMNS if c not in df.columns]
    if missing:
        logger.warning("WoW viz: %s missing columns %s", csv_path.name, missing)
    out = df[cols].copy()
    out = out.where(out.notna(), None)
    records = out.to_dict(orient="records")
    for row in records:
        for key, value in row.items():
            if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                row[key] = None
    return records


def build_register_wow_report_html(
    dd_analysis: dict,
    *,
    output_path: Path,
    title_suffix: str = "",
    campaigns_analysis: dict | None = None,
    growth_report: dict | None = None,
) -> Optional[Path]:
    """Self-contained HTML health-check report (DoorDash WoW + drill-down)."""
    summary = build_health_summary(dd_analysis, growth_report=growth_report)
    payload = json.dumps(
        _json_safe({
            "summary": summary,
            "campaigns": campaigns_analysis,
            "tables": build_wow_table_payload(dd_analysis),
        }),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    payload = payload.replace("</", "<\\/")
    html = (
        _REPORT_TEMPLATE.replace("__TITLE_SUFFIX__", f" — {title_suffix}" if title_suffix else "")
        .replace("__EMBEDDED_DATA__", payload)
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def build_wow_viz_html(
    week1_csv: Path,
    week2_csv: Path,
    output_path: Path,
    *,
    week1_label: str | None = None,
    week2_label: str | None = None,
    title_suffix: str = "",
) -> Optional[Path]:
    try:
        week1_rows = load_weekly_rows(Path(week1_csv))
        week2_rows = load_weekly_rows(Path(week2_csv))
    except Exception as e:
        logger.warning("WoW viz: failed to read weekly CSVs (%s / %s): %s", week1_csv, week2_csv, e)
        return None

    if not week1_rows or not week2_rows:
        logger.warning(
            "WoW viz: empty weekly data — skipping (%s: %d rows, %s: %d rows)",
            Path(week1_csv).name,
            len(week1_rows),
            Path(week2_csv).name,
            len(week2_rows),
        )
        return None

    label1 = week1_label or str(week1_rows[0].get("Week") or "Week 1")
    label2 = week2_label or str(week2_rows[0].get("Week") or "Week 2")

    analysis = compare_register_slots(
        week1_rows,
        week2_rows,
        labels={"week1": label1, "week2": label2},
    )

    path = build_register_wow_report_html(
        analysis,
        output_path=output_path,
        title_suffix=title_suffix,
    )
    if path:
        logger.info("WoW register viz written: %s (%d + %d rows)", path, len(week1_rows), len(week2_rows))
    return path


def build_wow_slack_message(
    week1_csv: Path,
    week2_csv: Path,
    *,
    week1_label: str | None = None,
    week2_label: str | None = None,
    title: str,
) -> str | None:
    """Build Slack summary text from two weekly CSVs (best-effort)."""
    try:
        week1_rows = load_weekly_rows(Path(week1_csv))
        week2_rows = load_weekly_rows(Path(week2_csv))
        if not week1_rows or not week2_rows:
            return None
        label1 = week1_label or str(week1_rows[0].get("Week") or "Week 1")
        label2 = week2_label or str(week2_rows[0].get("Week") or "Week 2")
        analysis = compare_register_slots(
            week1_rows,
            week2_rows,
            labels={"week1": label1, "week2": label2},
        )
        return build_slack_summary(analysis, title=title)
    except Exception as e:
        logger.warning("WoW Slack summary failed: %s", e)
        return None


_REPORT_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Health Check__TITLE_SUFFIX__</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; padding: 28px 24px 48px; max-width: 1440px; margin: 0 auto; line-height: 1.5; }
  h1 { font-size: 28px; font-weight: 700; color: #fff; margin-bottom: 6px; }
  .subtitle { color: #8b949e; font-size: 15px; margin-bottom: 28px; }
  .legend { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; font-size: 13px; color: #8b949e; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; letter-spacing: 0.02em; }
  .badge-healthy { background: rgba(63,185,80,0.18); color: #3fb950; border: 1px solid rgba(63,185,80,0.35); }
  .badge-neutral { background: rgba(210,153,34,0.18); color: #d29922; border: 1px solid rgba(210,153,34,0.35); }
  .badge-unhealthy { background: rgba(248,81,73,0.18); color: #f85149; border: 1px solid rgba(248,81,73,0.35); }
  .summary-table { width: 100%; border-collapse: collapse; margin-bottom: 36px; background: #161b22; border: 1px solid #30363d; border-radius: 10px; overflow: hidden; }
  .summary-table th, .summary-table td { padding: 14px 16px; text-align: left; border-bottom: 1px solid #21262d; }
  .summary-table th { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: #8b949e; font-weight: 600; background: #0d1117; }
  .summary-table tr:last-child td { border-bottom: none; }
  .summary-table td.metric-name { font-weight: 600; color: #fff; font-size: 15px; }
  .summary-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .pct-up { color: #3fb950; font-weight: 600; }
  .pct-down { color: #f85149; font-weight: 600; }
  .pct-flat { color: #8b949e; font-weight: 600; }
  .section-title { font-size: 18px; font-weight: 700; color: #58a6ff; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid #30363d; }
  .drill-metric { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px 20px; margin-bottom: 20px; }
  .drill-metric h3 { font-size: 16px; color: #fff; margin-bottom: 4px; }
  .drill-metric .drill-headline { font-size: 14px; color: #8b949e; margin-bottom: 14px; }
  .tree { list-style: none; padding-left: 0; }
  .tree ul { list-style: none; padding-left: 20px; margin-top: 6px; border-left: 2px solid #30363d; }
  .tree li { margin: 8px 0; font-size: 14px; }
  .tree .node-label { font-weight: 600; color: #c9d1d9; }
  .tree .node-stats { color: #8b949e; font-size: 13px; margin-left: 6px; }
  .tree .node-stats .neg { color: #f85149; }
  .mix-line { font-size: 13px; color: #8b949e; margin: 6px 0 8px; }
  .mix-line .c-healthy { color: #3fb950; font-weight: 600; }
  .mix-line .c-neutral { color: #d29922; font-weight: 600; }
  .mix-line .c-unhealthy { color: #f85149; font-weight: 600; }
  .empty-drill { color: #8b949e; font-size: 14px; font-style: italic; }
  .all-clear { background: rgba(63,185,80,0.1); border: 1px solid rgba(63,185,80,0.3); border-radius: 10px; padding: 16px 18px; color: #3fb950; font-size: 14px; margin-bottom: 24px; }
  .campaigns-section { margin-top: 40px; padding-top: 8px; border-top: 1px solid #30363d; }
  .campaigns-section h2 { font-size: 20px; color: #58a6ff; margin-bottom: 16px; }
  .table-wrap { overflow-x: auto; margin-bottom: 20px; }
  .store-block { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px 18px; margin-bottom: 16px; }
  .store-block h4 { font-size: 15px; color: #fff; margin-bottom: 10px; }
  .sub-table-title { font-size: 13px; font-weight: 600; color: #8b949e; margin: 14px 0 8px; text-transform: uppercase; letter-spacing: 0.04em; }
  table.data { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 8px; background: #0d1117; }
  table.data th, table.data td { padding: 8px 10px; border-bottom: 1px solid #21262d; text-align: left; white-space: nowrap; }
  table.data th { color: #8b949e; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; position: sticky; top: 0; background: #161b22; }
  table.data td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .pos { color: #3fb950; }
  .neg { color: #f85149; }
  .slot-grid-wrap { overflow-x: auto; margin-bottom: 16px; }
  .slot-grid { display: grid; gap: 6px; min-width: 860px; }
  .day-row-grid { min-width: 640px; }
  .slot-grid-corner { font-size: 11px; color: #8b949e; align-self: end; padding: 6px 4px; }
  .slot-grid-day-hdr { font-size: 11px; font-weight: 600; color: #c9d1d9; text-align: center; padding: 6px 4px; text-transform: uppercase; letter-spacing: 0.03em; }
  .slot-grid-row-hdr { font-size: 11px; font-weight: 600; color: #8b949e; padding: 8px 6px; display: flex; align-items: center; }
  .slot-grid-slot-hdr { font-size: 11px; font-weight: 600; color: #8b949e; padding: 8px 6px; display: flex; align-items: center; min-height: 112px; }
  .metric-cell { border-radius: 10px; padding: 10px 11px; font-size: 12px; line-height: 1.45; min-height: 112px; display: flex; flex-direction: column; justify-content: space-between; gap: 3px; }
  .slot-cell-healthy, .metric-cell-healthy { background: rgba(63,185,80,0.22); border: 1px solid rgba(63,185,80,0.5); }
  .slot-cell-neutral, .metric-cell-neutral { background: rgba(210,153,34,0.2); border: 1px solid rgba(210,153,34,0.45); }
  .slot-cell-unhealthy, .metric-cell-unhealthy { background: rgba(248,81,73,0.22); border: 1px solid rgba(248,81,73,0.5); }
  .slot-cell-empty, .metric-cell-empty { background: #161b22; border: 1px dashed #30363d; color: #6e7681; min-height: 112px; }
  .metric-cell .row { display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }
  .metric-cell .lbl { font-size: 10px; color: rgba(230,237,243,0.7); text-transform: uppercase; letter-spacing: 0.05em; flex-shrink: 0; }
  .metric-cell .val { font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; word-break: break-word; }
  .metric-cell .delta-line { margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.1); font-weight: 700; font-size: 12px; text-align: center; }
  .order-mix-cell { border-radius: 10px; padding: 9px 10px; font-size: 11px; line-height: 1.4; min-height: 132px; display: flex; flex-direction: column; gap: 4px; }
  .order-mix-cell .order-line { display: grid; grid-template-columns: 42px 1fr auto; gap: 4px; align-items: baseline; }
  .order-mix-cell .order-line .lbl { font-size: 9px; color: rgba(230,237,243,0.75); text-transform: uppercase; }
  .order-mix-cell .order-line .mini { font-size: 10px; color: #8b949e; text-align: right; }
  .order-mix-cell .order-line .chg { font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
  .campaign-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 20px; }
  .campaign-box { border-radius: 10px; padding: 12px 13px; min-height: 150px; display: flex; flex-direction: column; gap: 5px; }
  .campaign-box h5 { font-size: 12px; font-weight: 600; color: #fff; margin: 0 0 4px; line-height: 1.35; word-break: break-word; }
  .campaign-box .store-tag { font-size: 10px; color: #8b949e; margin-bottom: 4px; }
  .campaign-box .status-tag { font-size: 10px; font-weight: 600; margin-top: auto; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.08); }
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; margin-bottom: 32px; }
  .summary-box { border-radius: 10px; padding: 12px 14px; min-height: 130px; }
  .summary-box .metric-title, .metric-cell .metric-title { font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 6px; }
  .order-mix-cell.metric-cell-healthy { background: rgba(63,185,80,0.22); border: 1px solid rgba(63,185,80,0.5); }
  .order-mix-cell.metric-cell-neutral { background: rgba(210,153,34,0.2); border: 1px solid rgba(210,153,34,0.45); }
  .order-mix-cell.metric-cell-unhealthy { background: rgba(248,81,73,0.22); border: 1px solid rgba(248,81,73,0.5); }
  .order-mix-cell.metric-cell-empty { background: #161b22; border: 1px dashed #30363d; color: #6e7681; }
  .summary-box .metric-title { font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 8px; }
  .store-row-grid { min-width: 480px; }
  .slot-cell { border-radius: 10px; padding: 10px 11px; font-size: 12px; line-height: 1.45; min-height: 112px; display: flex; flex-direction: column; justify-content: space-between; gap: 3px; }
  .slot-cell .row { display: flex; justify-content: space-between; align-items: baseline; gap: 6px; }
  .slot-cell .lbl { font-size: 10px; color: rgba(230,237,243,0.7); text-transform: uppercase; letter-spacing: 0.05em; flex-shrink: 0; }
  .slot-cell .val { font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; word-break: break-word; }
  .slot-cell .delta-line { margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.1); font-weight: 700; font-size: 12px; text-align: center; }
  @media print {
    body { max-width: none; width: 100%; padding: 12px 16px 24px; }
    .slot-grid-wrap { overflow: visible; }
    .slot-grid, .day-row-grid, .store-row-grid { min-width: 0; width: 100%; page-break-inside: avoid; }
    .store-block, .drill-metric { page-break-inside: avoid; break-inside: avoid-page; }
    .metric-cell, .slot-cell, .order-mix-cell { break-inside: avoid; }
  }
</style>
</head>
<body>
<h1>Health Check__TITLE_SUFFIX__</h1>
<p class="subtitle" id="subtitle"></p>
<div class="legend" id="legend"></div>
<div id="all-clear"></div>
<div id="summary-grid" class="summary-grid"></div>
<div id="drilldowns"></div>
<div id="order-breakdown"></div>
<div class="campaigns-section" id="campaigns"></div>
<script id="wow-data" type="application/json">__EMBEDDED_DATA__</script>
<script>
const ROOT = JSON.parse(document.getElementById('wow-data').textContent);
const S = ROOT.summary || {};
const LABELS = S.labels || {};
const THRESH = S.threshold_pct || 2;

function fmtMoney(v) {
  if (v == null) return '—';
  return '$' + Number(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 });
}
function fmtNum(v) {
  if (v == null) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
}
function fmtVal(metric, v) {
  if (v == null) return '—';
  if (metric === 'Sales' || metric === 'Payouts' || metric === 'AOV') return fmtMoney(v);
  return fmtNum(v);
}
function fmtDelta(metric, d) {
  if (d == null) return '—';
  const n = Number(d);
  if (metric === 'Sales' || metric === 'Payouts' || metric === 'AOV') {
    const sign = n > 0 ? '+' : n < 0 ? '' : '';
    return sign + fmtMoney(n);
  }
  const sign = n > 0 ? '+' : '';
  return sign + fmtNum(n);
}
function fmtPct(pct) {
  if (pct == null) return '—';
  const n = Number(pct);
  const sign = n > 0 ? '+' : '';
  return sign + n.toFixed(1) + '%';
}
function pctClass(pct) {
  if (pct == null) return 'pct-flat';
  if (pct > 0) return 'pct-up';
  if (pct < 0) return 'pct-down';
  return 'pct-flat';
}
function statusBadge(status) {
  const label = status === 'healthy' ? 'Healthy' : status === 'neutral' ? 'Neutral' : 'Unhealthy';
  return `<span class="badge badge-${status}">${label}</span>`;
}
function fmtMix(mix) {
  if (!mix || !mix.total) return '';
  const unit = mix.unit || 'items';
  const cap = unit.charAt(0).toUpperCase() + unit.slice(1);
  return `${cap}: <span class="c-healthy">${mix.healthy}/${mix.total} healthy</span> · `
    + `<span class="c-neutral">${mix.neutral}/${mix.total} neutral</span> · `
    + `<span class="c-unhealthy">${mix.unhealthy}/${mix.total} unhealthy</span>`;
}
const TABLES = ROOT.tables || {};
const W1 = LABELS.week1 || 'Week 1';
const W2 = LABELS.week2 || 'Week 2';

function deltaClass(d) { return d > 0 ? 'pos' : d < 0 ? 'neg' : ''; }

function classifyFromPct(pct) {
  if (pct == null) return 'neutral';
  if (pct < 0) return 'unhealthy';
  if (pct >= THRESH) return 'healthy';
  return 'neutral';
}

function cellStatusClass(status, empty) {
  if (empty) return 'metric-cell-empty';
  return `metric-cell-${status || 'neutral'}`;
}

function renderSummaryMetricBox(m) {
  if (m.skipped) {
    return `<div class="metric-cell metric-cell-empty summary-box"><div class="metric-title">${m.name}</div><span class="lbl">${m.note || 'No data'}</span></div>`;
  }
  const status = m.status || classifyFromPct(m.pct);
  return `<div class="metric-cell ${cellStatusClass(status, false)} summary-box">`
    + `<div class="metric-title">${m.name}</div>`
    + `<div class="row"><span class="lbl">${W1}</span><span class="val">${fmtVal(m.name, m.week1)}</span></div>`
    + `<div class="row"><span class="lbl">${W2}</span><span class="val">${fmtVal(m.name, m.week2)}</span></div>`
    + `<div class="row"><span class="lbl">Δ</span><span class="val ${deltaClass(m.delta)}">${fmtDelta(m.name, m.delta)}</span></div>`
    + `<div class="delta-line ${pctClass(m.pct)}">${fmtPct(m.pct)}</div>`
    + `<div style="margin-top:6px">${statusBadge(status)}</div>`
    + '</div>';
}

function renderStoreRowGrid(stores, metric) {
  if (!stores?.length) return '';
  const colMin = 140;
  let html = `<div class="slot-grid-wrap"><div class="slot-grid store-row-grid" style="grid-template-columns: 80px repeat(${stores.length}, minmax(${colMin}px, 1fr))">`;
  html += '<div class="slot-grid-corner">Store →</div>';
  for (const row of stores) {
    html += `<div class="slot-grid-day-hdr">Store ${row.storeId}</div>`;
  }
  html += `<div class="slot-grid-row-hdr">${metric}</div>`;
  for (const row of stores) {
    html += renderMetricCellBox(row, metric, `Store ${row.storeId}`);
  }
  html += '</div></div>';
  return html;
}

function renderMetricCellBox(cell, metric, title) {
  if (!cell) {
    return `<div class="metric-cell metric-cell-empty" title="${title}"><span class="lbl">—</span></div>`;
  }
  const status = cell.status || classifyFromPct(cell.pct);
  const empty = (cell.week1 == null || cell.week1 === 0) && (cell.week2 == null || cell.week2 === 0);
  const cls = cellStatusClass(status, empty);
  const pct = cell.pct;
  const delta = cell.delta;
  return `<div class="metric-cell ${cls}" title="${title}">`
    + `<div class="row"><span class="lbl">${W1}</span><span class="val">${fmtVal(metric, cell.week1)}</span></div>`
    + `<div class="row"><span class="lbl">${W2}</span><span class="val">${fmtVal(metric, cell.week2)}</span></div>`
    + `<div class="row"><span class="lbl">Δ</span><span class="val ${deltaClass(delta)}">${fmtDelta(metric, delta)}</span></div>`
    + `<div class="delta-line ${pctClass(pct)}">${fmtPct(pct)}</div>`
    + '</div>';
}

function renderDayRowGrid(days, metric) {
  const dayOrder = TABLES.dayOrder || ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const lookup = {};
  for (const d of (days || [])) lookup[d.day] = d;
  const colMin = 118;
  let html = `<div class="slot-grid-wrap"><div class="slot-grid day-row-grid" style="grid-template-columns: 80px repeat(${dayOrder.length}, minmax(${colMin}px, 1fr))">`;
  html += '<div class="slot-grid-corner">Day →</div>';
  for (const day of dayOrder) {
    html += `<div class="slot-grid-day-hdr">${day}</div>`;
  }
  html += `<div class="slot-grid-row-hdr">${metric}</div>`;
  for (const day of dayOrder) {
    html += renderMetricCellBox(lookup[day], metric, day);
  }
  html += '</div></div>';
  return html;
}

function renderSlotGrid(slots, metric) {
  const dayOrder = TABLES.dayOrder || ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const slotOrder = TABLES.slotOrder || ['Overnight','Breakfast','Lunch','Afternoon','Dinner','Late night'];
  const lookup = {};
  for (const s of (slots || [])) {
    lookup[`${s.day}|${s.daypart}`] = s;
  }
  const colMin = 118;
  let html = `<div class="slot-grid-wrap"><div class="slot-grid" style="grid-template-columns: 100px repeat(${dayOrder.length}, minmax(${colMin}px, 1fr))">`;
  html += '<div class="slot-grid-corner">Slot ↓<br>Day →</div>';
  for (const day of dayOrder) {
    html += `<div class="slot-grid-day-hdr">${day}</div>`;
  }
  for (const slot of slotOrder) {
    html += `<div class="slot-grid-slot-hdr">${slot}</div>`;
    for (const day of dayOrder) {
      const cell = lookup[`${day}|${slot}`];
      const box = renderMetricCellBox(cell, metric, `${day} · ${slot}`);
      html += box.replace(/metric-cell/g, 'slot-cell');
    }
  }
  html += '</div></div>';
  return html;
}

function renderOrderAttributionLine(lbl, block) {
  const w1 = block?.week1 ?? 0;
  const w2 = block?.week2 ?? 0;
  const d = block?.delta ?? 0;
  return `<div class="order-line"><span class="lbl">${lbl}</span>`
    + `<span class="mini">${fmtNum(w1)}→${fmtNum(w2)}</span>`
    + `<span class="chg ${deltaClass(d)}">${fmtDelta('Orders', d)}</span></div>`;
}

function renderOrderMixCellBox(row, title) {
  if (!row) {
    return `<div class="order-mix-cell metric-cell-empty" title="${title}"><span class="lbl">—</span></div>`;
  }
  const o = row.organic || {};
  const p = row.promo || {};
  const a = row.ads || {};
  const b = row.both || {};
  const totalDelta = (o.delta || 0) + (p.delta || 0) + (a.delta || 0) + (b.delta || 0);
  const w1Total = (o.week1 || 0) + (p.week1 || 0) + (a.week1 || 0) + (b.week1 || 0);
  const w2Total = (o.week2 || 0) + (p.week2 || 0) + (a.week2 || 0) + (b.week2 || 0);
  const empty = w1Total === 0 && w2Total === 0;
  let status = 'neutral';
  if (totalDelta < 0) status = 'unhealthy';
  else if (totalDelta > 0) status = 'healthy';
  const cls = cellStatusClass(status, empty);
  return `<div class="order-mix-cell metric-cell ${cls}" title="${title}">`
    + renderOrderAttributionLine('Org', o)
    + renderOrderAttributionLine('Promo', p)
    + renderOrderAttributionLine('Ads', a)
    + renderOrderAttributionLine('P+A', b)
    + '</div>';
}

function renderOrderMixSlotGrid(rows, storeId) {
  const dayOrder = TABLES.dayOrder || ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const slotOrder = TABLES.slotOrder || ['Overnight','Breakfast','Lunch','Afternoon','Dinner','Late night'];
  const lookup = {};
  for (const r of (rows || [])) lookup[`${r.day}|${r.daypart}`] = r;
  const colMin = 118;
  let html = `<div class="slot-grid-wrap"><div class="slot-grid" style="grid-template-columns: 100px repeat(${dayOrder.length}, minmax(${colMin}px, 1fr))">`;
  html += '<div class="slot-grid-corner">Slot ↓<br>Day →</div>';
  for (const day of dayOrder) {
    html += `<div class="slot-grid-day-hdr">${day}</div>`;
  }
  for (const slot of slotOrder) {
    html += `<div class="slot-grid-slot-hdr">${slot}</div>`;
    for (const day of dayOrder) {
      html += renderOrderMixCellBox(lookup[`${day}|${slot}`], `Store ${storeId} · ${day} · ${slot}`);
    }
  }
  html += '</div></div>';
  return html;
}

function renderMetricGrids(metric, view) {
  if (!view || !view.stores?.length) return '';
  let html = `<p class="sub-table-title">All stores (row grid)</p>`;
  html += renderStoreRowGrid(view.stores, metric);
  for (const row of view.stores) {
    const sid = row.storeId;
    const days = (view.daysByStore || {})[sid] || [];
    const slots = (view.slotsByStore || {})[sid] || [];
    html += `<div class="store-block"><h4>Store ${sid}</h4>`;
    if (days.length) {
      html += `<p class="sub-table-title">By weekday (row grid)</p>`;
      html += renderDayRowGrid(days, metric);
    }
    if (slots.length) {
      html += `<p class="sub-table-title">Day × slot grid</p>`;
      html += renderSlotGrid(slots, metric);
    }
    html += '</div>';
  }
  return html;
}

function renderDrilldowns() {
  const unhealthy = (S.metrics || []).filter(m => m.status === 'unhealthy' && !m.skipped);
  const byMetric = TABLES.byMetric || {};
  let html = '<h2 class="section-title">Performance breakdown</h2>'
    + '<p class="subtitle" style="margin-top:-8px;margin-bottom:20px">Box grids per store. Green ≥2%, yellow 0–2%, red &lt;0%.</p>';

  const metricsToShow = unhealthy.length
    ? unhealthy.map(m => m.name)
    : Object.keys(byMetric);

  for (const name of metricsToShow) {
    const view = byMetric[name];
    if (!view) continue;
    const summary = (S.metrics || []).find(m => m.name === name);
    const headline = summary && !summary.skipped
      ? `<p class="drill-headline">Overall ${fmtDelta(name, summary.delta)} (${fmtVal(name, summary.week1)} → ${fmtVal(name, summary.week2)}, ${fmtPct(summary.pct)})</p>`
      : '';
    html += `<div class="drill-metric"><h3>${name}</h3>${headline}`;
    html += renderMetricGrids(name, view);
    html += '</div>';
  }

  if (!html.includes('drill-metric')) {
    html += '<p class="empty-drill">No breakdown data available.</p>';
  }
  document.getElementById('drilldowns').innerHTML = html;
}

function renderOrderBreakdown() {
  const byStore = TABLES.orderBreakdownByStore || {};
  const storeIds = Object.keys(byStore).sort();
  const el = document.getElementById('order-breakdown');
  if (!storeIds.length) {
    el.innerHTML = '';
    return;
  }
  let html = '<h2 class="section-title">Order mix by store × day × slot</h2>'
    + '<p class="subtitle" style="margin-top:-8px;margin-bottom:16px">Each box: organic, promo-only, ads-only, promo+ads (W1→W2 and Δ). Box color = net order change.</p>';
  for (const sid of storeIds) {
    html += `<div class="store-block"><h4>Store ${sid}</h4>`;
    html += renderOrderMixSlotGrid(byStore[sid], sid);
    html += '</div>';
  }
  el.innerHTML = html;
}

function renderSummary() {
  const w1 = LABELS.week1 || 'Week 1';
  const w2 = LABELS.week2 || 'Week 2';
  document.getElementById('subtitle').textContent = `${w1} → ${w2} · DoorDash only`;
  document.getElementById('legend').innerHTML =
    `<span><span class="badge badge-healthy">Healthy</span> ≥ ${THRESH}% growth</span>`
    + `<span><span class="badge badge-neutral">Neutral</span> 0% to &lt; ${THRESH}%</span>`
    + `<span><span class="badge badge-unhealthy">Unhealthy</span> &lt; 0% (degrowth)</span>`;

  document.getElementById('summary-grid').innerHTML = (S.metrics || []).map(renderSummaryMetricBox).join('');

  const un = S.unhealthy_metrics || [];
  const allClear = document.getElementById('all-clear');
  const topMix = S.counts || {};
  const topTotal = (topMix.healthy || 0) + (topMix.neutral || 0) + (topMix.unhealthy || 0);
  if (!un.length) {
    allClear.innerHTML = `<div class="all-clear">✓ No metrics in degrowth. Metrics: `
      + `<span class="c-healthy">${topMix.healthy || 0}/${topTotal} healthy</span> · `
      + `<span class="c-neutral">${topMix.neutral || 0}/${topTotal} neutral</span> · `
      + `<span class="c-unhealthy">${topMix.unhealthy || 0}/${topTotal} unhealthy</span>.</div>`;
  } else {
    allClear.innerHTML = `<div class="mix-line" style="margin-bottom:20px">Metrics: `
      + `<span class="c-healthy">${topMix.healthy || 0}/${topTotal} healthy</span> · `
      + `<span class="c-neutral">${topMix.neutral || 0}/${topTotal} neutral</span> · `
      + `<span class="c-unhealthy">${topMix.unhealthy || 0}/${topTotal} unhealthy</span></div>`;
  }
}

renderSummary();
renderDrilldowns();
renderOrderBreakdown();

function campaignBoxStatus(r) {
  const s = (r.status || '').toLowerCase();
  if (s === 'improving') return 'healthy';
  if (s === 'declining') return 'unhealthy';
  return 'neutral';
}

function renderCampaignBox(r) {
  const aovD = r.promoAovDelta != null ? r.promoAovDelta : null;
  const status = campaignBoxStatus(r);
  return `<div class="campaign-box metric-cell ${cellStatusClass(status, false)}">`
    + `<h5>${r.name}</h5>`
    + `<div class="store-tag">Store ${r.storeId}</div>`
    + `<div class="row"><span class="lbl">Sales Δ</span><span class="val ${deltaClass(r.salesDelta)}">${fmtMoney(r.salesDelta)}</span></div>`
    + `<div class="row"><span class="lbl">Orders Δ</span><span class="val ${deltaClass(r.ordersDelta)}">${fmtNum(r.ordersDelta)}</span></div>`
    + `<div class="row"><span class="lbl">Spend Δ</span><span class="val ${deltaClass(r.spendDelta)}">${fmtMoney(r.spendDelta)}</span></div>`
    + `<div class="row"><span class="lbl">AOV Δ</span><span class="val ${deltaClass(aovD)}">${aovD != null ? fmtMoney(aovD) : '—'}</span></div>`
    + `<div class="status-tag">${r.status || ''}</div>`
    + '</div>';
}

function campaignSortRank(r) {
  const s = (r.status || '').toLowerCase();
  if (s === 'declining') return 0;
  if (s === 'mixed') return 1;
  if (s === 'flat') return 2;
  if (s === 'improving') return 3;
  return 1.5;
}

function sortCampaignsWorstFirst(rows) {
  return [...rows].sort((a, b) => {
    const ra = campaignSortRank(a);
    const rb = campaignSortRank(b);
    if (ra !== rb) return ra - rb;
    return (a.salesDelta || 0) - (b.salesDelta || 0);
  });
}

function renderCampaignGrid(rows, title) {
  if (!rows?.length) return `<h3 style="margin:20px 0 10px;color:#c9d1d9">${title}</h3><p class="subtitle">No campaigns in this bucket.</p>`;
  const sorted = sortCampaignsWorstFirst(rows);
  let html = `<h3 style="margin:20px 0 10px;color:#c9d1d9">${title} (${sorted.length})</h3><div class="campaign-grid">`;
  for (const r of sorted) html += renderCampaignBox(r);
  return html + '</div>';
}

function renderSlotReview(SR) {
  if (!SR || (!SR.keep?.length && !SR.pause?.length && !SR.monitor?.length)) return '';
  let html = `<h3 style="margin:24px 0 10px;color:#c9d1d9">Slot-level campaign review</h3>`;
  if (SR.transitionSummary) html += `<p class="subtitle">${SR.transitionSummary}</p>`;
  return html;
}

const C = ROOT.campaigns;
let campaignsHtml = '';
if (C && (C.promo?.length || C.ads?.length || C.slotReview)) {
  campaignsHtml = '<h2>Campaign performance (week over week)</h2>'
    + '<p class="subtitle" style="margin-bottom:16px">Promo and Ads campaigns from marketing exports — each box is one campaign × store, compared to the prior week. Sorted worst → best (declining red on top, improving green on bottom).</p>';
  if (C.promo?.length) campaignsHtml += renderCampaignGrid(C.promo, 'Promo');
  if (C.ads?.length) campaignsHtml += renderCampaignGrid(C.ads, 'Ads');
  if (C.slotReview) campaignsHtml += renderSlotReview(C.slotReview);
}
document.getElementById('campaigns').innerHTML = campaignsHtml;
</script>
</body>
</html>
"""
