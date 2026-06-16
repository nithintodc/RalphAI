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

from agents.health_check.health_summary import build_health_summary
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
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; padding: 28px 24px 48px; max-width: 920px; margin: 0 auto; line-height: 1.5; }
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
  table.data { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 24px; }
  table.data th, table.data td { padding: 8px 10px; border-bottom: 1px solid #21262d; text-align: left; }
  table.data th { color: #8b949e; }
  table.data td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .pos { color: #3fb950; }
  .neg { color: #f85149; }
</style>
</head>
<body>
<h1>Health Check__TITLE_SUFFIX__</h1>
<p class="subtitle" id="subtitle"></p>
<div class="legend" id="legend"></div>
<div id="all-clear"></div>
<table class="summary-table" id="summary-table">
  <thead><tr><th>Metric</th><th>Week 1</th><th>Week 2</th><th>WoW change</th><th>Status</th></tr></thead>
  <tbody id="summary-body"></tbody>
</table>
<div id="drilldowns"></div>
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
function nodeLine(metric, node) {
  const pct = node.pct;
  const delta = node.delta;
  const cls = pct != null && pct < 0 ? 'neg' : '';
  return `<span class="node-label">${node.label}</span> ${statusBadge(node.status)}`
    + `<span class="node-stats"><span class="${cls}">${fmtPct(pct)}</span> (${fmtDelta(metric, delta)})</span>`;
}

function renderUnhealthyTree(metric, items, level) {
  if (!items || !items.length) return '';
  const unhealthy = items.filter(n => n.status === 'unhealthy');
  if (!unhealthy.length) return '';
  let html = '<ul class="tree">';
  for (const node of unhealthy) {
    html += '<li>' + nodeLine(metric, node);
    if (level === 'stores' && node.mix) {
      html += `<div class="mix-line">${fmtMix(node.mix)}</div>`;
      html += renderUnhealthyTree(metric, node.days || [], 'days');
    } else if (level === 'days' && node.mix) {
      html += `<div class="mix-line">${fmtMix(node.mix)}</div>`;
      const badSlots = (node.slots || []).filter(s => s.status === 'unhealthy');
      if (badSlots.length) {
        html += '<ul class="tree">';
        for (const slot of badSlots) {
          html += '<li>' + nodeLine(metric, slot) + '</li>';
        }
        html += '</ul>';
      }
    }
    if (node.note) html += `<div class="node-stats" style="margin-top:4px">${node.note}</div>`;
    html += '</li>';
  }
  return html + '</ul>';
}

function renderDrilldowns() {
  const unhealthy = (S.metrics || []).filter(m => m.status === 'unhealthy' && !m.skipped);
  if (!unhealthy.length) {
    document.getElementById('drilldowns').innerHTML = '';
    return;
  }
  let html = '<h2 class="section-title">Where declines came from</h2>'
    + '<p class="subtitle" style="margin-top:-8px;margin-bottom:20px">Degrowth metrics only. Each level shows healthy / neutral / unhealthy counts, then drills into unhealthy branches.</p>';
  for (const m of unhealthy) {
    html += `<div class="drill-metric"><h3>${m.name} — ${fmtPct(m.pct)} ${statusBadge('unhealthy')}</h3>`
      + `<p class="drill-headline">Overall ${fmtDelta(m.name, m.delta)} (${fmtVal(m.name, m.week1)} → ${fmtVal(m.name, m.week2)})</p>`;
    const dd = m.drilldown;
    if (dd && dd.items && dd.items.length) {
      if (dd.mix) html += `<div class="mix-line">${fmtMix(dd.mix)}</div>`;
      html += renderUnhealthyTree(m.name, dd.items, 'stores');
    } else {
      html += '<p class="empty-drill">Decline is spread evenly — no single store/day/slot dominates.</p>';
    }
    html += '</div>';
  }
  document.getElementById('drilldowns').innerHTML = html;
}

function renderSummary() {
  const w1 = LABELS.week1 || 'Week 1';
  const w2 = LABELS.week2 || 'Week 2';
  document.getElementById('subtitle').textContent = `${w1} → ${w2} · DoorDash only`;
  document.getElementById('legend').innerHTML =
    `<span><span class="badge badge-healthy">Healthy</span> ≥ ${THRESH}% growth</span>`
    + `<span><span class="badge badge-neutral">Neutral</span> 0% to &lt; ${THRESH}%</span>`
    + `<span><span class="badge badge-unhealthy">Unhealthy</span> &lt; 0% (degrowth)</span>`;

  const tbody = document.getElementById('summary-body');
  let rows = '';
  for (const m of (S.metrics || [])) {
    if (m.skipped) {
      rows += `<tr><td class="metric-name">${m.name}</td><td colspan="3" style="color:#8b949e">${m.note || 'No data'}</td><td>—</td></tr>`;
      continue;
    }
    rows += `<tr>
      <td class="metric-name">${m.name}</td>
      <td class="num">${fmtVal(m.name, m.week1)}</td>
      <td class="num">${fmtVal(m.name, m.week2)}</td>
      <td class="num ${pctClass(m.pct)}">${fmtPct(m.pct)} (${fmtDelta(m.name, m.delta)})</td>
      <td>${statusBadge(m.status)}</td>
    </tr>`;
  }
  tbody.innerHTML = rows;

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

function deltaClass(d) { return d > 0 ? 'pos' : d < 0 ? 'neg' : ''; }

function renderCampaignTable(rows, title) {
  if (!rows || !rows.length) return `<h3 style="margin:20px 0 10px;color:#c9d1d9">${title}</h3><p class="subtitle">No campaigns in this bucket.</p>`;
  let html = `<h3 style="margin:20px 0 10px;color:#c9d1d9">${title}</h3><table class="data"><thead><tr><th>Campaign</th><th>Store</th><th>Sales Δ</th><th>Orders Δ</th><th>Spend Δ</th><th>Status</th></tr></thead><tbody>`;
  for (const r of rows) {
    html += `<tr><td>${r.name}</td><td>${r.storeId}</td>`
      + `<td class="num ${deltaClass(r.salesDelta)}">${fmtMoney(r.salesDelta)}</td>`
      + `<td class="num ${deltaClass(r.ordersDelta)}">${fmtNum(r.ordersDelta)}</td>`
      + `<td class="num ${deltaClass(r.spendDelta)}">${fmtMoney(r.spendDelta)}</td>`
      + `<td>${r.status || ''}</td></tr>`;
  }
  return html + '</tbody></table>';
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
  campaignsHtml = '<h2>Campaigns (reference)</h2>';
  if (C.promo?.length) campaignsHtml += renderCampaignTable(C.promo, 'Promo');
  if (C.ads?.length) campaignsHtml += renderCampaignTable(C.ads, 'Ads');
  if (C.slotReview) campaignsHtml += renderSlotReview(C.slotReview);
}
document.getElementById('campaigns').innerHTML = campaignsHtml;
</script>
</body>
</html>
"""
