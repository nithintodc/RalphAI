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
    ue_analysis: dict | None = None,
    output_path: Path,
    title_suffix: str = "",
    ue_has_data: bool = False,
    campaigns_analysis: dict | None = None,
) -> Optional[Path]:
    """Self-contained HTML for DD (+ optional UE) register WoW."""
    payload = json.dumps(
        _json_safe({
            "dd": dd_analysis,
            "ue": ue_analysis,
            "ueHasData": bool(ue_has_data and ue_analysis),
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
<title>Register WoW__TITLE_SUFFIX__</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e1e4e8; padding: 24px; max-width: 1400px; margin: 0 auto; }
  h1 { font-size: 26px; font-weight: 700; margin-bottom: 8px; color: #fff; }
  .subtitle { color: #8b949e; font-size: 14px; margin-bottom: 28px; line-height: 1.5; }
  .metric-section { margin-bottom: 40px; }
  .metric-title { font-size: 20px; font-weight: 600; color: #fff; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #30363d; }
  .summary-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }
  .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; }
  .card .label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 22px; font-weight: 700; color: #fff; margin-top: 6px; }
  .card .delta { font-size: 13px; margin-top: 6px; }
  .pos { color: #3fb950; }
  .neg { color: #f85149; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
  h3 { font-size: 14px; color: #8b949e; margin-bottom: 10px; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { padding: 8px 10px; border-bottom: 1px solid #21262d; text-align: left; }
  th { color: #8b949e; font-weight: 600; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .status { margin-bottom: 16px; font-size: 13px; color: #8b949e; }
  .platform { margin-bottom: 48px; }
  .platform h2.platform-title { font-size: 22px; color: #58a6ff; margin-bottom: 16px; }
  .rollup-block { margin-bottom: 28px; }
  .rollup-block h3 { font-size: 15px; color: #c9d1d9; margin-bottom: 4px; }
  .rollup-hint { font-size: 12px; color: #6e7681; margin-bottom: 12px; }
</style>
</head>
<body>
<h1>Register Week-over-Week__TITLE_SUFFIX__</h1>
<p class="subtitle" id="subtitle"></p>
<div id="status" class="status"></div>
<div id="platforms"></div>
<div id="campaigns"></div>
<script id="wow-data" type="application/json">__EMBEDDED_DATA__</script>
<script>
const ROOT = JSON.parse(document.getElementById('wow-data').textContent);
const METRICS = ['Sales', 'Payouts', 'Orders', 'AOV'];
const CAMPAIGN_METRICS = ['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Promo AOV', 'Check After Promo'];
const ROLLUP_VIEWS = [
  { key: 'by_store', label: 'Stores', hint: 'All days & slots per store', col: 'Store' },
  { key: 'by_day', label: 'Days', hint: 'All stores & slots per weekday', col: 'Day' },
  { key: 'by_daypart', label: 'Slots', hint: 'All stores & days per daypart', col: 'Slot' },
  { key: 'by_day_daypart', label: 'Day · slot', hint: 'All stores per weekday × daypart', col: 'Day · slot' },
];

function fmtMoney(v) {
  return '$' + Number(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 });
}
function fmtNum(v) {
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
}
function fmtVal(metric, v) {
  if (metric === 'Sales' || metric === 'Payouts' || metric === 'AOV') return fmtMoney(v);
  return fmtNum(v);
}
function fmtDelta(metric, d) {
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
  const sign = pct > 0 ? '+' : '';
  return sign + Number(pct).toFixed(1) + '%';
}
function deltaClass(d) {
  return d > 0 ? 'pos' : d < 0 ? 'neg' : '';
}

function renderMoversTable(rows, metric, colLabel) {
  if (!rows.length) return '<p class="subtitle">No movers in this bucket.</p>';
  let html = `<table><thead><tr><th>${colLabel}</th><th>Week 1</th><th>Week 2</th><th>Δ</th><th>%</th></tr></thead><tbody>`;
  for (const row of rows) {
    const m = row.metrics[metric];
    html += `<tr>
      <td>${row.label}</td>
      <td class="num">${fmtVal(metric, m.week1)}</td>
      <td class="num">${fmtVal(metric, m.week2)}</td>
      <td class="num ${deltaClass(m.delta)}">${fmtDelta(metric, m.delta)}</td>
      <td class="num ${deltaClass(m.delta)}">${fmtPct(m.pct)}</td>
    </tr>`;
  }
  return html + '</tbody></table>';
}

function renderRollupViews(metric, DATA) {
  const rollups = (DATA.rollups && DATA.rollups[metric]) || {};
  const k = DATA.topK;
  return ROLLUP_VIEWS.map(view => {
    const bucket = rollups[view.key] || { top_up: [], top_down: [] };
    const up = bucket.top_up || [];
    const down = bucket.top_down || [];
    const upTitle = up.length ? `Increases (${up.length}${k ? ` of up to ${k}` : ''})` : 'No increases';
    const downTitle = down.length ? `Decreases (${down.length}${k ? ` of up to ${k}` : ''})` : 'No decreases';
    return `<div class="rollup-block">
      <h3>${view.label}</h3>
      <p class="rollup-hint">${view.hint}</p>
      <div class="grid-2">
        <div>
          <h3>${upTitle}</h3>
          ${renderMoversTable(up, metric, view.col)}
        </div>
        <div>
          <h3>${downTitle}</h3>
          ${renderMoversTable(down, metric, view.col)}
        </div>
      </div>
    </div>`;
  }).join('');
}

function renderPlatform(platformLabel, DATA) {
  if (!DATA || !DATA.slotCount) {
    return `<section class="platform"><h2 class="platform-title">${platformLabel}</h2><p class="subtitle">No register data for this platform.</p></section>`;
  }
  const w1 = DATA.labels.week1;
  const w2 = DATA.labels.week2;
  const k = DATA.topK;
  let html = `<section class="platform"><h2 class="platform-title">${platformLabel}</h2>
    <p class="subtitle">${DATA.slotCount} underlying slots · ${w1} → ${w2} · up to ${k} largest increases / decreases per rollup (actual row counts shown below)</p>`;
  html += METRICS.map(metric => renderMetric(metric, DATA)).join('');
  return html + '</section>';
}

function renderMetric(metric, DATA) {
  const t = DATA.totals[metric];
  const w1 = DATA.labels.week1;
  const w2 = DATA.labels.week2;

  return `<section class="metric-section">
    <h2 class="metric-title">${metric}</h2>
    <div class="summary-row">
      <div class="card">
        <div class="label">${w1}</div>
        <div class="value">${fmtVal(metric, t.week1)}</div>
      </div>
      <div class="card">
        <div class="label">${w2}</div>
        <div class="value">${fmtVal(metric, t.week2)}</div>
      </div>
      <div class="card">
        <div class="label">Change</div>
        <div class="value ${deltaClass(t.delta)}">${fmtVal(metric, t.delta)}</div>
        <div class="delta ${deltaClass(t.delta)}">${fmtPct(t.pct)} vs prior week</div>
      </div>
    </div>
    ${renderRollupViews(metric, DATA)}
  </section>`;
}

document.getElementById('subtitle').textContent =
  'WoW rollups: stores → days → slots (dayparts) → day·slot. Underlying grain is store × day × daypart from weekly health-check CSVs.';

document.getElementById('status').textContent =
  `Metrics: ${METRICS.join(', ')}. DoorDash from health-check weekly CSV; Uber Eats when UE files are supplied.`;

let platformsHtml = renderPlatform('DoorDash', ROOT.dd);
if (ROOT.ueHasData) {
  platformsHtml += renderPlatform('Uber Eats', ROOT.ue);
} else {
  platformsHtml += `<section class="platform"><h2 class="platform-title">Uber Eats</h2><p class="subtitle">No UE weekly data in this health-check run — register CSVs are zero-filled placeholders.</p></section>`;
}
document.getElementById('platforms').innerHTML = platformsHtml;

function renderCampaignTable(rows, title) {
  if (!rows || !rows.length) return `<section class="platform"><h2 class="platform-title">${title}</h2><p class="subtitle">No campaigns in this bucket.</p></section>`;
  let html = `<section class="platform"><h2 class="platform-title">${title}</h2><p class="subtitle">Top ${rows.length} campaigns by |sales WoW Δ|</p><table><thead><tr><th>Campaign</th><th>Store</th><th>Sales Δ</th><th>Orders Δ</th><th>Spend Δ</th><th>ROAS Δ</th><th>CPO Δ</th><th>Check Δ</th><th>Status</th></tr></thead><tbody>`;
  for (const r of rows) {
    html += `<tr>
      <td>${r.name}</td>
      <td>${r.storeId}</td>
      <td class="num ${deltaClass(r.salesDelta)}">${fmtMoney(r.salesDelta)}</td>
      <td class="num ${deltaClass(r.ordersDelta)}">${fmtNum(r.ordersDelta)}</td>
      <td class="num ${deltaClass(r.spendDelta)}">${fmtMoney(r.spendDelta)}</td>
      <td class="num ${deltaClass(r.roasDelta)}">${fmtNum(r.roasDelta)}</td>
      <td class="num ${deltaClass(r.cpoDelta)}">${fmtMoney(r.cpoDelta)}</td>
      <td class="num ${deltaClass(r.checkDelta)}">${fmtMoney(r.checkDelta)}</td>
      <td>${r.status || ''}</td>
    </tr>`;
  }
  return html + '</tbody></table></section>';
}

function renderSlotReview(SR) {
  if (!SR || (!SR.keep?.length && !SR.pause?.length && !SR.monitor?.length)) return '';
  const th = SR.thresholds || {};
  let html = `<section class="platform"><h2 class="platform-title">Step 5 — Slot-level review</h2>
    <p class="subtitle">${SR.weekLabels?.prior || '?'} → ${SR.weekLabels?.current || '?'} · `
    + `Keep when ROAS ≥ ${th.keep_roas_gte || 5}× · Pause/reduce when ROAS &lt; ${th.pause_roas_lt || 2}×</p>`;
  if (SR.transitionSummary) {
    html += `<p class="subtitle"><strong>Slot vs prior blanket:</strong> ${SR.transitionSummary}</p>`;
  }
  if (SR.actionCounts) {
    html += `<p class="subtitle">Actions: ${SR.actionCounts.keep_increase_budget || 0} keep/increase · `
      + `${SR.actionCounts.pause_or_reduce_bid || 0} pause/reduce · ${SR.actionCounts.monitor || 0} monitor</p>`;
  }
  function slotTable(rows, title) {
    if (!rows?.length) return '';
    let t = `<h3 style="margin:16px 0 8px;color:#c9d1d9">${title}</h3><table><thead><tr>`
      + `<th>Slot</th><th>Store</th><th>Campaign</th><th>ROAS</th><th>Action</th></tr></thead><tbody>`;
    for (const r of rows) {
      t += `<tr><td>${r.slot}</td><td>${r.storeId}</td><td>${r.name}</td>`
        + `<td class="num">${Number(r.roas).toFixed(1)}×</td><td>${r.action}</td></tr>`;
    }
    return t + '</tbody></table>';
  }
  html += slotTable(SR.keep, 'ROAS ≥ 5× — keep & increase budget');
  html += slotTable(SR.pause, 'ROAS &lt; 2× — pause or reduce bid');
  html += slotTable(SR.monitor, 'Monitor (2×–5×)');
  return html + '</section>';
}

const C = ROOT.campaigns;
let campaignsHtml = '';
if (C && (C.promo?.length || C.ads?.length)) {
  campaignsHtml +=
    '<h2 style="font-size:22px;color:#58a6ff;margin:32px 0 16px">Campaign WoW (Promo &amp; Ads)</h2>' +
    renderCampaignTable(C.promo, 'Promo campaigns') +
    renderCampaignTable(C.ads, 'Ads campaigns');
}
if (C?.slotReview) {
  campaignsHtml += renderSlotReview(C.slotReview);
}
document.getElementById('campaigns').innerHTML = campaignsHtml;
</script>
</body>
</html>
"""
