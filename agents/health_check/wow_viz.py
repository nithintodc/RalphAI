"""
WoW Bucket Analysis visualization for the Health Check agent.

Generates a self-contained interactive HTML report comparing two weekly CSVs
(built by ``data_processor.build_weekly_csv``) across orders (GC buckets),
sales, profitability, and AOV — with store / day / daypart filters,
stacked distribution charts, a waterfall of net bucket change, and a detail table.

The weekly-CSV rows are embedded directly as JSON, so the output HTML opens
from disk (file://) with no HTTP server. Chart.js loads from CDN.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Columns the viz consumes from each weekly CSV (built by build_weekly_csv).
VIZ_COLUMNS = [
    "Merchant Store ID",
    "Week",
    "Day",
    "Day part",
    "Sales",
    "GC $0-15",
    "GC $15-20",
    "GC $20-25",
    "GC $25-30",
    "GC $30-$35",
    "GC $35-$40",
    "GC $40+",
    "Profitability_%",
    "AOV",
]


def _load_rows(csv_path: Path) -> list[dict]:
    """Read a weekly CSV and return only the columns the viz needs."""
    import pandas as pd

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    cols = [c for c in VIZ_COLUMNS if c in df.columns]
    missing = [c for c in VIZ_COLUMNS if c not in df.columns]
    if missing:
        logger.warning("WoW viz: %s missing columns %s", csv_path.name, missing)
    out = df[cols].copy()
    # NaN/inf are invalid JSON — the viz coerces blanks to 0 via Number(x || 0).
    out = out.where(out.notna(), None)
    records = out.to_dict(orient="records")
    for row in records:
        for key, value in row.items():
            if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                row[key] = None
    return records


def build_wow_viz_html(
    week1_csv: Path,
    week2_csv: Path,
    output_path: Path,
    *,
    week1_label: str | None = None,
    week2_label: str | None = None,
    title_suffix: str = "",
) -> Optional[Path]:
    """
    Build the self-contained WoW bucket viz HTML from two weekly CSVs.

    Args:
        week1_csv: Older completed week CSV.
        week2_csv: Newer completed week CSV.
        output_path: Where to write the HTML.
        week1_label / week2_label: Display labels; default to each CSV's ``Week`` value.
        title_suffix: Optional suffix for the page title (e.g. operator name).

    Returns the output path, or None on failure (never raises — viz is best-effort).
    """
    try:
        week1_rows = _load_rows(Path(week1_csv))
        week2_rows = _load_rows(Path(week2_csv))
    except Exception as e:
        logger.warning("WoW viz: failed to read weekly CSVs (%s / %s): %s", week1_csv, week2_csv, e)
        return None

    if not week1_rows or not week2_rows:
        logger.warning("WoW viz: empty weekly data — skipping (%s: %d rows, %s: %d rows)",
                       Path(week1_csv).name, len(week1_rows), Path(week2_csv).name, len(week2_rows))
        return None

    label1 = week1_label or str(week1_rows[0].get("Week") or "Week 1")
    label2 = week2_label or str(week2_rows[0].get("Week") or "Week 2")

    payload = json.dumps(
        {"week1": week1_rows, "week2": week2_rows, "labels": {"week1": label1, "week2": label2}},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    # Defend against </script> sequences inside data values.
    payload = payload.replace("</", "<\\/")

    html = (
        _TEMPLATE
        .replace("__TITLE_SUFFIX__", f" — {title_suffix}" if title_suffix else "")
        .replace("__EMBEDDED_DATA__", payload)
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("WoW viz written: %s (%d + %d rows)", output_path, len(week1_rows), len(week2_rows))
    return output_path


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WoW Bucket Analysis__TITLE_SUFFIX__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e1e4e8; padding: 24px; }
  h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; color: #fff; }
  .subtitle { color: #8b949e; font-size: 14px; margin-bottom: 28px; max-width: 980px; }
  .controls { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; align-items: end; }
  .controls > div { min-width: 160px; }
  .controls label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 6px; }
  select { width: 100%; background: #1c1f26; border: 1px solid #30363d; color: #e1e4e8; padding: 8px 12px; border-radius: 6px; font-size: 13px; cursor: pointer; }
  select:hover { border-color: #58a6ff; }
  .status { margin-bottom: 18px; font-size: 13px; color: #8b949e; }
  .status.error { color: #f85149; }
  .section { margin-bottom: 48px; }
  .section-title { font-size: 20px; font-weight: 600; margin-bottom: 6px; color: #fff; }
  .section-desc { font-size: 13px; color: #8b949e; margin-bottom: 20px; }
  .chart-container { background: #161b22; border: 1px solid #21262d; border-radius: 12px; padding: 24px; }
  .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  @media (max-width: 1200px) { .chart-row { grid-template-columns: 1fr; } }
  canvas { max-height: 420px; }
  .summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; text-align: center; }
  .card .value { font-size: 24px; font-weight: 700; color: #fff; }
  .card .label { font-size: 11px; color: #8b949e; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
  .card .delta { font-size: 13px; margin-top: 6px; }
  .card .delta.positive { color: #3fb950; }
  .card .delta.negative { color: #f85149; }
  .card .week-vals { font-size: 11px; color: #8b949e; margin-top: 4px; }
  .waterfall-table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
  .waterfall-table th, .waterfall-table td { padding: 10px 16px; border-bottom: 1px solid #21262d; }
  .waterfall-table th { text-align: left; color: #8b949e; font-weight: 600; }
  .waterfall-table td { color: #c9d1d9; }
  .waterfall-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .waterfall-table tr:last-child { border-top: 2px solid #30363d; font-weight: 700; }
  .bar-cell { width: 320px; }
  .bar-track { height: 22px; background: #21262d; border-radius: 4px; position: relative; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; position: absolute; top: 0; }
  .share-shift { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
  .share-shift.up { background: rgba(63,185,80,0.15); color: #3fb950; }
  .share-shift.down { background: rgba(248,81,73,0.15); color: #f85149; }
  .share-shift.flat { background: rgba(139,148,158,0.15); color: #8b949e; }
</style>
</head>
<body>

<h1>WoW Bucket Analysis__TITLE_SUFFIX__</h1>
<p id="subtitle" class="subtitle">Week-over-week bucket movement across orders, sales, profitability, and AOV. Filter by store, day, and daypart to isolate the exact slice you want.</p>

<div class="controls">
  <div>
    <label for="metricFilter">Metric</label>
    <select id="metricFilter"></select>
  </div>
  <div>
    <label for="storeFilter">Store</label>
    <select id="storeFilter"></select>
  </div>
  <div>
    <label for="dayFilter">Day</label>
    <select id="dayFilter"></select>
  </div>
  <div>
    <label for="daypartFilter">Daypart</label>
    <select id="daypartFilter"></select>
  </div>
</div>

<div id="status" class="status">Loading…</div>
<div id="summaryCards" class="summary-cards"></div>

<div class="section">
  <h2 class="section-title">1. Distribution Comparison</h2>
  <p id="distributionDesc" class="section-desc"></p>
  <div class="chart-row">
    <div class="chart-container">
      <canvas id="stackedAbsolute"></canvas>
    </div>
    <div class="chart-container">
      <canvas id="stackedPercent"></canvas>
    </div>
  </div>
</div>

<div class="section">
  <h2 class="section-title">2. Waterfall: Net Change per Bucket</h2>
  <p id="waterfallDesc" class="section-desc"></p>
  <div class="chart-container">
    <canvas id="waterfallChart"></canvas>
  </div>
</div>

<div class="section">
  <h2 class="section-title">3. Bucket Detail Table</h2>
  <p id="tableDesc" class="section-desc"></p>
  <div class="chart-container" id="detailTableContainer"></div>
</div>

<script id="wow-data" type="application/json">__EMBEDDED_DATA__</script>
<script>
const EMBEDDED = JSON.parse(document.getElementById('wow-data').textContent);

const METRICS = {
  orders: {
    label: 'Orders',
    kind: 'bucket-counts',
    unitLabel: 'orders',
    totalLabel: 'Total Orders',
    bucketLabel: 'GC Bucket',
    valueFormatter: value => Number(value).toLocaleString(),
    percentFormatter: value => `${Number(value).toFixed(1)}%`,
    shareFormatter: value => `${Number(value).toFixed(1)}%`,
    bucketColumns: [
      'GC $0-15',
      'GC $15-20',
      'GC $20-25',
      'GC $25-30',
      'GC $30-$35',
      'GC $35-$40',
      'GC $40+',
    ],
    descriptions: {
      distribution: 'Side-by-side view of order counts and % share per GC bucket. Use day and daypart filters to narrow the exact slot mix you want to compare.',
      waterfall: 'Each bar shows the net gain or loss in orders for that GC bucket. Green = more orders this week, red = fewer.',
      table: 'Exact order counts, deltas, % change, and share-of-total movement per GC bucket.',
    },
  },
  sales: {
    label: 'Sales',
    kind: 'value-buckets',
    unitLabel: 'slots',
    totalLabel: 'Total Sales',
    bucketLabel: 'Sales Bucket',
    valueFormatter: value => `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`,
    percentFormatter: value => `${Number(value).toFixed(1)}%`,
    shareFormatter: value => `${Number(value).toFixed(1)}%`,
    bins: [
      { label: '$0-100', min: 0, max: 100 },
      { label: '$100-200', min: 100, max: 200 },
      { label: '$200-300', min: 200, max: 300 },
      { label: '$300-400', min: 300, max: 400 },
      { label: '$400+', min: 400, max: Infinity },
    ],
    rowValue: row => Number(row.Sales || 0),
    aggregateTotal: rows => rows.reduce((sum, row) => sum + Number(row.Sales || 0), 0),
    descriptions: {
      distribution: 'Rows are grouped into sales buckets, then compared week over week by slot count and share. The total card shows raw sales for the filtered slice.',
      waterfall: 'Net slot change per sales bucket. This shows whether more day/daypart slots landed in higher or lower sales bands.',
      table: 'Bucket-level slot counts, share shift, and total sales for the selected slice.',
    },
  },
  profitability: {
    label: 'Profitability',
    kind: 'value-buckets',
    unitLabel: 'slots',
    totalLabel: 'Avg Profitability',
    bucketLabel: 'Profitability Bucket',
    valueFormatter: value => `${Number(value).toFixed(1)}%`,
    percentFormatter: value => `${Number(value).toFixed(1)}pp`,
    shareFormatter: value => `${Number(value).toFixed(1)}%`,
    bins: [
      { label: '<60%', min: -Infinity, max: 60 },
      { label: '60-70%', min: 60, max: 70 },
      { label: '70-80%', min: 70, max: 80 },
      { label: '80-90%', min: 80, max: 90 },
      { label: '90-100%', min: 90, max: 100 },
      { label: '100%+', min: 100, max: Infinity },
    ],
    rowValue: row => Number(row['Profitability_%'] || 0),
    aggregateTotal: rows => average(rows.map(row => Number(row['Profitability_%'] || 0))),
    descriptions: {
      distribution: 'Rows are grouped into profitability bands using the slot-level `Profitability_%` from the weekly CSVs. The total card shows the average profitability for the filtered slice.',
      waterfall: 'Net slot change per profitability band. Positive means more slots landed in that band this week.',
      table: 'Bucket-level slot counts, share shift, and the average profitability for the selected slice.',
    },
  },
  aov: {
    label: 'AOV',
    kind: 'value-buckets',
    unitLabel: 'slots',
    totalLabel: 'Avg AOV',
    bucketLabel: 'AOV Bucket',
    valueFormatter: value => `$${Number(value).toFixed(2)}`,
    percentFormatter: value => `${Number(value).toFixed(1)}%`,
    shareFormatter: value => `${Number(value).toFixed(1)}%`,
    bins: [
      { label: '<$12', min: -Infinity, max: 12 },
      { label: '$12-15', min: 12, max: 15 },
      { label: '$15-18', min: 15, max: 18 },
      { label: '$18-21', min: 18, max: 21 },
      { label: '$21+', min: 21, max: Infinity },
    ],
    rowValue: row => Number(row.AOV || 0),
    aggregateTotal: rows => average(rows.map(row => Number(row.AOV || 0))),
    descriptions: {
      distribution: 'Rows are grouped into AOV bands using slot-level `AOV`. The total card shows the average AOV for the filtered slice.',
      waterfall: 'Net slot change per AOV band. This shows where the selected day/daypart mix shifted across ticket-size ranges.',
      table: 'Bucket-level slot counts, share shift, and the average AOV for the selected slice.',
    },
  },
};

const COLORS = ['#636efa', '#00cc96', '#ef553b', '#ab63fa', '#ffa15a', '#19d3f3', '#ff6692', '#2ca02c'];
const DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const DAYPART_ORDER = ['Early morning', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late night'];

const state = {
  rows: { week1: [], week2: [] },
  labels: { week1: 'Week 1', week2: 'Week 2' },
};

const metricFilter = document.getElementById('metricFilter');
const storeFilter = document.getElementById('storeFilter');
const dayFilter = document.getElementById('dayFilter');
const daypartFilter = document.getElementById('daypartFilter');
const statusEl = document.getElementById('status');

let chartAbs = null;
let chartPct = null;
let chartWaterfall = null;

function average(values) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function sortByReference(values, reference) {
  const rank = new Map(reference.map((value, index) => [value, index]));
  return [...values].sort((a, b) => {
    const aRank = rank.has(a) ? rank.get(a) : Number.MAX_SAFE_INTEGER;
    const bRank = rank.has(b) ? rank.get(b) : Number.MAX_SAFE_INTEGER;
    return aRank === bRank ? String(a).localeCompare(String(b)) : aRank - bRank;
  });
}

function formatSignedNumber(value, digits = 0) {
  const number = Number(value);
  const sign = number > 0 ? '+' : '';
  return `${sign}${number.toFixed(digits)}`;
}

function formatPercentChange(delta, base) {
  if (!base) return '—';
  return `${((delta / base) * 100).toFixed(1)}%`;
}

function metricConfig() {
  return METRICS[metricFilter.value] || METRICS.orders;
}

function currentFilters() {
  return {
    store: storeFilter.value || 'all',
    day: dayFilter.value || 'all',
    daypart: daypartFilter.value || 'all',
  };
}

function applyFilters(rows) {
  const filters = currentFilters();
  return rows.filter(row => {
    if (filters.store !== 'all' && String(row['Merchant Store ID']) !== filters.store) return false;
    if (filters.day !== 'all' && row.Day !== filters.day) return false;
    if (filters.daypart !== 'all' && row['Day part'] !== filters.daypart) return false;
    return true;
  });
}

function getBucketData(rows, config) {
  if (config.kind === 'bucket-counts') {
    const counts = Object.fromEntries(config.bucketColumns.map(bucket => [bucket, 0]));
    rows.forEach(row => {
      config.bucketColumns.forEach(bucket => {
        counts[bucket] += Number(row[bucket] || 0);
      });
    });
    return {
      buckets: config.bucketColumns,
      counts,
      total: config.aggregateTotal ? config.aggregateTotal(rows) : config.bucketColumns.reduce((sum, bucket) => sum + counts[bucket], 0),
      slotCount: rows.length,
    };
  }

  const counts = Object.fromEntries(config.bins.map(bin => [bin.label, 0]));
  rows.forEach(row => {
    const value = config.rowValue(row);
    const bucket = config.bins.find(bin => value >= bin.min && value < bin.max);
    if (bucket) counts[bucket.label] += 1;
  });

  return {
    buckets: config.bins.map(bin => bin.label),
    counts,
    total: config.aggregateTotal(rows),
    slotCount: rows.length,
  };
}

function buildViewModel() {
  const config = metricConfig();
  const week1Rows = applyFilters(state.rows.week1);
  const week2Rows = applyFilters(state.rows.week2);
  const week1Data = getBucketData(week1Rows, config);
  const week2Data = getBucketData(week2Rows, config);

  return {
    config,
    week1Rows,
    week2Rows,
    week1Data,
    week2Data,
    labels: state.labels,
  };
}

function setDescriptions(config) {
  document.getElementById('distributionDesc').textContent = config.descriptions.distribution;
  document.getElementById('waterfallDesc').textContent = config.descriptions.waterfall;
  document.getElementById('tableDesc').textContent = config.descriptions.table;
  document.getElementById('subtitle').textContent = `Week-over-week bucket movement for ${config.label.toLowerCase()}. Filter by store, day, and daypart to isolate the exact slice you want.`;
}

function renderCards(model) {
  const { config, week1Data, week2Data, labels } = model;
  const container = document.getElementById('summaryCards');
  container.innerHTML = '';

  week1Data.buckets.forEach((bucket, index) => {
    const value1 = week1Data.counts[bucket] || 0;
    const value2 = week2Data.counts[bucket] || 0;
    const delta = value2 - value1;
    const cls = delta > 0 ? 'positive' : delta < 0 ? 'negative' : '';
    container.innerHTML += `<div class="card">
      <div class="value">${value2.toLocaleString()}</div>
      <div class="label">${bucket}</div>
      <div class="delta ${cls}">${formatSignedNumber(delta)} ${config.unitLabel}</div>
      <div class="week-vals">${labels.week1}: ${value1.toLocaleString()}</div>
    </div>`;
  });

  const totalDelta = week2Data.total - week1Data.total;
  const totalCls = totalDelta > 0 ? 'positive' : totalDelta < 0 ? 'negative' : '';
  const totalDigits = config.label === 'AOV' || config.label === 'Sales' || config.label === 'Profitability' ? 1 : 0;

  container.innerHTML += `<div class="card" style="border-color:#58a6ff">
    <div class="value">${config.valueFormatter(week2Data.total)}</div>
    <div class="label">${config.totalLabel}</div>
    <div class="delta ${totalCls}">${formatSignedNumber(totalDelta, totalDigits)}${config.label === 'Profitability' ? 'pp' : ''}</div>
    <div class="week-vals">${labels.week1}: ${config.valueFormatter(week1Data.total)}</div>
  </div>`;

  container.innerHTML += `<div class="card">
    <div class="value">${week2Data.slotCount.toLocaleString()}</div>
    <div class="label">Week 2 Slots</div>
    <div class="delta">${labels.week2}</div>
    <div class="week-vals">${labels.week1}: ${week1Data.slotCount.toLocaleString()}</div>
  </div>`;
}

function renderStackedBars(model) {
  const { config, week1Data, week2Data, labels } = model;
  const total1 = week1Data.buckets.reduce((sum, bucket) => sum + week1Data.counts[bucket], 0);
  const total2 = week2Data.buckets.reduce((sum, bucket) => sum + week2Data.counts[bucket], 0);

  const absoluteData = {
    labels: [labels.week1, labels.week2],
    datasets: week1Data.buckets.map((bucket, index) => ({
      label: bucket,
      data: [week1Data.counts[bucket], week2Data.counts[bucket]],
      backgroundColor: COLORS[index % COLORS.length],
      borderRadius: 2,
    })),
  };

  const percentData = {
    labels: [labels.week1, labels.week2],
    datasets: week1Data.buckets.map((bucket, index) => ({
      label: bucket,
      data: [
        total1 ? (week1Data.counts[bucket] / total1) * 100 : 0,
        total2 ? (week2Data.counts[bucket] / total2) * 100 : 0,
      ],
      backgroundColor: COLORS[index % COLORS.length],
      borderRadius: 2,
    })),
  };

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: { color: '#8b949e', boxWidth: 12, padding: 10, font: { size: 11 } },
      },
    },
    scales: {
      x: { stacked: true, ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
      y: { stacked: true, ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
    },
  };

  if (chartAbs) chartAbs.destroy();
  if (chartPct) chartPct.destroy();

  chartAbs = new Chart(document.getElementById('stackedAbsolute'), {
    type: 'bar',
    data: absoluteData,
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        title: { display: true, text: `Absolute ${config.unitLabel[0].toUpperCase() + config.unitLabel.slice(1)} by Bucket`, color: '#c9d1d9', font: { size: 14 } },
      },
      scales: {
        ...baseOptions.scales,
        y: {
          ...baseOptions.scales.y,
          title: { display: true, text: config.unitLabel[0].toUpperCase() + config.unitLabel.slice(1), color: '#8b949e' },
        },
      },
    },
  });

  chartPct = new Chart(document.getElementById('stackedPercent'), {
    type: 'bar',
    data: percentData,
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        title: { display: true, text: 'Percentage Distribution', color: '#c9d1d9', font: { size: 14 } },
        tooltip: {
          callbacks: {
            label: context => `${context.dataset.label}: ${Number(context.raw).toFixed(1)}%`,
          },
        },
      },
      scales: {
        ...baseOptions.scales,
        y: {
          ...baseOptions.scales.y,
          max: 100,
          title: { display: true, text: `% of ${config.unitLabel}`, color: '#8b949e' },
          ticks: { color: '#8b949e', callback: value => `${value}%` },
        },
      },
    },
  });
}

function renderWaterfall(model) {
  const { config, week1Data, week2Data, labels } = model;
  const deltas = week1Data.buckets.map(bucket => (week2Data.counts[bucket] || 0) - (week1Data.counts[bucket] || 0));
  const netDelta = deltas.reduce((sum, delta) => sum + delta, 0);
  const labelsWithTotal = [...week1Data.buckets, 'Net Total'];
  const barData = [];
  const bgColors = [];

  let cumulative = 0;
  deltas.forEach(delta => {
    const bottom = delta >= 0 ? cumulative : cumulative + delta;
    const top = delta >= 0 ? cumulative + delta : cumulative;
    barData.push([bottom, top]);
    bgColors.push(delta >= 0 ? '#3fb950' : '#f85149');
    cumulative += delta;
  });

  barData.push([0, netDelta]);
  bgColors.push(netDelta >= 0 ? 'rgba(63,185,80,0.5)' : 'rgba(248,81,73,0.5)');

  if (chartWaterfall) chartWaterfall.destroy();

  chartWaterfall = new Chart(document.getElementById('waterfallChart'), {
    type: 'bar',
    data: {
      labels: labelsWithTotal,
      datasets: [{
        data: barData,
        backgroundColor: bgColors,
        borderWidth: 1,
        borderRadius: 3,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: `Net ${config.unitLabel} Change per Bucket (${labels.week1} → ${labels.week2})`,
          color: '#c9d1d9',
          font: { size: 14 },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const index = context.dataIndex;
              if (index < week1Data.buckets.length) {
                const bucket = week1Data.buckets[index];
                const value1 = week1Data.counts[bucket] || 0;
                const value2 = week2Data.counts[bucket] || 0;
                return `${bucket}: ${formatSignedNumber(deltas[index])} ${config.unitLabel} (${value1} → ${value2})`;
              }
              return `Net: ${formatSignedNumber(netDelta)} ${config.unitLabel}`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { color: '#8b949e', font: { size: 11 } }, grid: { color: '#21262d' } },
        y: {
          grid: { color: '#21262d' },
          ticks: { color: '#8b949e', callback: value => formatSignedNumber(Number(value)) },
          title: { display: true, text: `${config.unitLabel[0].toUpperCase() + config.unitLabel.slice(1)} Change`, color: '#8b949e' },
        },
      },
    },
    plugins: [{
      id: 'waterfallLabels',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        const meta = chart.getDatasetMeta(0);
        ctx.save();
        ctx.font = '600 11px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        meta.data.forEach((bar, index) => {
          const value = index < deltas.length ? deltas[index] : netDelta;
          const y = value >= 0 ? bar.y - 8 : bar.y + bar.height + 14;
          ctx.fillStyle = value >= 0 ? '#3fb950' : '#f85149';
          ctx.fillText(formatSignedNumber(value), bar.x, y);
        });
        ctx.restore();
      },
    }],
  });
}

function renderDetailTable(model) {
  const { config, week1Data, week2Data, labels } = model;
  const total1 = week1Data.buckets.reduce((sum, bucket) => sum + week1Data.counts[bucket], 0);
  const total2 = week2Data.buckets.reduce((sum, bucket) => sum + week2Data.counts[bucket], 0);
  const container = document.getElementById('detailTableContainer');
  const maxDelta = Math.max(...week1Data.buckets.map(bucket => Math.abs((week2Data.counts[bucket] || 0) - (week1Data.counts[bucket] || 0))), 1);

  let html = `<table class="waterfall-table">
    <thead>
      <tr>
        <th>${config.bucketLabel}</th>
        <th style="text-align:right">${labels.week1}</th>
        <th style="text-align:right">${labels.week2}</th>
        <th style="text-align:right">Delta</th>
        <th style="text-align:right">% Change</th>
        <th style="text-align:right">Share ${labels.week1}</th>
        <th style="text-align:right">Share ${labels.week2}</th>
        <th style="text-align:right">Share Shift</th>
        <th class="bar-cell">Delta Bar</th>
      </tr>
    </thead>
    <tbody>`;

  week1Data.buckets.forEach((bucket, index) => {
    const value1 = week1Data.counts[bucket] || 0;
    const value2 = week2Data.counts[bucket] || 0;
    const delta = value2 - value1;
    const percentChange = formatPercentChange(delta, value1);
    const share1 = total1 ? (value1 / total1) * 100 : 0;
    const share2 = total2 ? (value2 / total2) * 100 : 0;
    const shareShift = share2 - share1;
    const shiftClass = shareShift > 0 ? 'up' : shareShift < 0 ? 'down' : 'flat';
    const shiftLabel = `${shareShift > 0 ? '+' : ''}${shareShift.toFixed(1)}pp`;
    const barPct = Math.abs(delta) / maxDelta * 100;
    const isPositive = delta >= 0;

    html += `<tr>
      <td style="color:${COLORS[index % COLORS.length]};font-weight:600">${bucket}</td>
      <td class="num">${value1.toLocaleString()}</td>
      <td class="num">${value2.toLocaleString()}</td>
      <td class="num" style="color:${delta > 0 ? '#3fb950' : delta < 0 ? '#f85149' : '#8b949e'};font-weight:600">${formatSignedNumber(delta)}</td>
      <td class="num" style="color:${delta > 0 ? '#3fb950' : delta < 0 ? '#f85149' : '#8b949e'}">${percentChange}</td>
      <td class="num">${config.shareFormatter(share1)}</td>
      <td class="num">${config.shareFormatter(share2)}</td>
      <td class="num"><span class="share-shift ${shiftClass}">${shiftLabel}</span></td>
      <td class="bar-cell">
        <div class="bar-track">
          <div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:#30363d"></div>
          <div class="bar-fill" style="background:${isPositive ? '#3fb950' : '#f85149'};left:${isPositive ? 50 : 50 - barPct / 2}%;width:${barPct / 2}%;opacity:0.8"></div>
        </div>
      </td>
    </tr>`;
  });

  html += `<tr>
    <td style="font-weight:700;color:#fff">Total</td>
    <td class="num" style="font-weight:700">${total1.toLocaleString()}</td>
    <td class="num" style="font-weight:700">${total2.toLocaleString()}</td>
    <td class="num" style="color:${total2 - total1 >= 0 ? '#3fb950' : '#f85149'};font-weight:700">${formatSignedNumber(total2 - total1)}</td>
    <td class="num" style="color:${total2 - total1 >= 0 ? '#3fb950' : '#f85149'};font-weight:700">${formatPercentChange(total2 - total1, total1)}</td>
    <td class="num">100.0%</td>
    <td class="num">100.0%</td>
    <td></td>
    <td></td>
  </tr>`;

  html += '</tbody></table>';
  container.innerHTML = html;
}

function renderAll() {
  const model = buildViewModel();
  setDescriptions(model.config);
  renderCards(model);
  renderStackedBars(model);
  renderWaterfall(model);
  renderDetailTable(model);
}

function populateSelect(select, options, defaultValue = 'all') {
  select.innerHTML = '';
  options.forEach(option => {
    const node = document.createElement('option');
    node.value = option.value;
    node.textContent = option.label;
    if (option.value === defaultValue) node.selected = true;
    select.appendChild(node);
  });
}

function init() {
  try {
    state.rows.week1 = EMBEDDED.week1 || [];
    state.rows.week2 = EMBEDDED.week2 || [];
    state.labels.week1 = (EMBEDDED.labels && EMBEDDED.labels.week1) || 'Week 1';
    state.labels.week2 = (EMBEDDED.labels && EMBEDDED.labels.week2) || 'Week 2';

    const allRows = [...state.rows.week1, ...state.rows.week2];
    const storeValues = sortByReference(new Set(allRows.map(row => String(row['Merchant Store ID']))), []);
    const dayValues = sortByReference(new Set(allRows.map(row => row.Day)), DAY_ORDER);
    const daypartValues = sortByReference(new Set(allRows.map(row => row['Day part'])), DAYPART_ORDER);

    populateSelect(metricFilter, Object.entries(METRICS).map(([value, config]) => ({ value, label: config.label })), 'orders');
    populateSelect(storeFilter, [{ value: 'all', label: 'All Stores (Aggregate)' }, ...storeValues.map(value => ({ value, label: `Store ${value}` }))], 'all');
    populateSelect(dayFilter, [{ value: 'all', label: 'All Days' }, ...dayValues.map(value => ({ value, label: value }))], 'all');
    populateSelect(daypartFilter, [{ value: 'all', label: 'All Dayparts' }, ...daypartValues.map(value => ({ value, label: value }))], 'all');

    [metricFilter, storeFilter, dayFilter, daypartFilter].forEach(select => {
      select.addEventListener('change', renderAll);
    });

    statusEl.textContent = `Loaded ${state.rows.week1.length} rows for ${state.labels.week1} and ${state.rows.week2.length} rows for ${state.labels.week2}.`;
    renderAll();
  } catch (error) {
    statusEl.textContent = `Failed to render: ${error.message}`;
    statusEl.classList.add('error');
  }
}

init();
</script>
</body>
</html>
"""
