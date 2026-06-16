/**
 * TODC Partnership Performance Report — document export.
 *
 * Fills the branded "Partnership Performance Report" template (cover, KPI strip,
 * Pre/Post + YoY tables, DoorDash / Uber Eats sections, store-level, day-part,
 * charts, footer) with live analysis data and produces:
 *   - a Word-openable .doc download (light theme, no canvas),
 *   - a print-to-PDF window (full dark/print-aware design with charts),
 *   - a native Google Doc pushed to the same Shared Drive as the Excel export.
 *
 * Mirrors exportWorkbook.js for the Google push endpoint / env config.
 */

import { format } from 'date-fns';
import { buildSlotAnalysis } from '../engine/slots';
import { combinedPayoutPerStore } from '../utils/summaryKpis';
import { captureOperatorMapScreenshot } from './mapExportCapture.js';

const GOOGLE_SHEETS_EXPORT_URL = import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL;
const GOOGLE_DOC_EXPORT_URL = import.meta.env.VITE_GOOGLE_DOC_EXPORT_URL;
const LOCAL_EXPORT_API_PORT = import.meta.env.VITE_LOCAL_EXPORT_API_PORT || '8765';

const METRIC_ORDER = ['sales', 'payouts', 'orders', 'profitability', 'aov'];
const METRIC_LABELS = {
  sales: 'Sales',
  payouts: 'Payouts',
  orders: 'Orders',
  profitability: 'Profitability',
  aov: 'Average Check',
};
const METRIC_KIND = {
  sales: 'usd',
  payouts: 'usd',
  orders: 'int',
  profitability: 'pct',
  aov: 'usd2',
};

/* ── Formatting helpers ──────────────────────────────────────────────────── */

function num(value, decimals = 0) {
  const n = Number(value || 0);
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtValue(value, kind) {
  switch (kind) {
    case 'usd': return `$${num(value)}`;
    case 'usd2': return `$${num(value, 2)}`;
    case 'int': return num(value);
    case 'pct': return `${num(value, 1)}%`;
    case 'roas': return num(value, 2);
    default: return String(value ?? '');
  }
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function imgTag(src, alt, className) {
  if (!src) return '';
  return `<img src="${src}" alt="${escapeHtml(alt)}" class="${className}" />`;
}

/** A signed delta cell with arrow + pos/neg colour class. */
function deltaCell(value, kind) {
  const n = Number(value || 0);
  const cls = n < 0 ? 'neg' : 'pos';
  const arrow = n < 0 ? '▼' : '▲';
  const sign = n < 0 ? '-' : '+';
  let body;
  switch (kind) {
    case 'usd': body = `$${num(Math.abs(n))}`; break;
    case 'usd2': body = `$${num(Math.abs(n), 2)}`; break;
    case 'int': body = num(Math.abs(n)); break;
    case 'pct': body = `${num(Math.abs(n), 1)}%`; break;
    default: body = num(Math.abs(n));
  }
  return `<td class="${cls}">${arrow} ${sign}${body}</td>`;
}

function pctDeltaCell(value) {
  return deltaCell(value, 'pct');
}

function td(value, kind) {
  return `<td>${fmtValue(value, kind)}</td>`;
}

/* ── Data lookups ────────────────────────────────────────────────────────── */

function summaryRow(summary, metric) {
  return (summary || []).find(r => r.metric === metric) || null;
}

function activeStoreCount(storeTables, key) {
  return Array.isArray(storeTables?.[key]) ? storeTables[key].length : 0;
}

/** Re-create exportWorkbook's per-platform day-part slot analysis. */
function platformSlotAnalysis(data, config, platform) {
  const rawData = platform === 'ue' ? data.ueFinancial : data.ddFinancial;
  const prefix = platform === 'ue' ? 'ue' : 'dd';
  if (!rawData) return null;
  const preStart = config[`${prefix}PreStart`];
  const preEnd = config[`${prefix}PreEnd`];
  const postStart = config[`${prefix}PostStart`];
  const postEnd = config[`${prefix}PostEnd`];
  if (!preStart || !preEnd || !postStart || !postEnd) return null;
  return buildSlotAnalysis(rawData, {
    preStart,
    preEnd,
    postStart,
    postEnd,
    excludedDates: config[`${prefix}ExcludedDates`] || [],
    platform,
  });
}

/* ── Table builders ──────────────────────────────────────────────────────── */

function metricPrePostRows(summary) {
  return METRIC_ORDER.map((metric) => {
    const r = summaryRow(summary, metric);
    if (!r) return '';
    const kind = METRIC_KIND[metric];
    return `<tr>
      <td>${METRIC_LABELS[metric]}</td>
      ${td(r.pre, kind)}${td(r.post, kind)}
      ${deltaCell(r.prevspost, kind)}
      ${deltaCell(r.lyPrevspost, kind)}
      ${pctDeltaCell(r.growthPct)}
    </tr>`;
  }).join('');
}

function metricYoyRows(summary) {
  return METRIC_ORDER.map((metric) => {
    const r = summaryRow(summary, metric);
    if (!r) return '';
    const kind = METRIC_KIND[metric];
    return `<tr>
      <td>${METRIC_LABELS[metric]}</td>
      ${td(r.postLY, kind)}${td(r.post, kind)}
      ${deltaCell(r.yoy, kind)}
      ${pctDeltaCell(r.yoyPct)}
    </tr>`;
  }).join('');
}

function baselineRows(summaryTables) {
  const rows = [
    { label: 'DoorDash', row: summaryRow(summaryTables?.dd, 'sales') },
    { label: 'Uber Eats', row: summaryRow(summaryTables?.ue, 'sales') },
    { label: 'Total', row: summaryRow(summaryTables?.combined, 'sales'), total: true },
  ];
  return rows
    .filter(({ row }) => row)
    .map(({ label, row, total }) => `<tr${total ? ' class="totals-row"' : ''}>
      <td>${label}</td>
      ${td(row.postLY, 'usd')}${td(row.post, 'usd')}
      ${deltaCell(row.yoy, 'usd')}
      ${pctDeltaCell(row.yoyPct)}
    </tr>`).join('');
}

function storePrePostRows(stores, metric = 'sales') {
  return (stores || []).map(s => `<tr>
    <td>${escapeHtml(s.storeId)}</td>
    ${td(s[`pre_${metric}`], 'usd')}${td(s[`post_${metric}`], 'usd')}
    ${deltaCell(s[`${metric}_prevspost`], 'usd')}
    ${deltaCell(s[`${metric}_ly_prevspost`], 'usd')}
    ${pctDeltaCell(s[`${metric}_growth_pct`])}
  </tr>`).join('') || emptyRow(6);
}

function storeYoyRows(stores, metric = 'sales') {
  return (stores || []).map(s => `<tr>
    <td>${escapeHtml(s.storeId)}</td>
    ${td(s[`postLY_${metric}`], 'usd')}${td(s[`post_${metric}`], 'usd')}
    ${deltaCell(s[`${metric}_yoy`], 'usd')}
    ${pctDeltaCell(s[`${metric}_yoy_pct`])}
  </tr>`).join('') || emptyRow(5);
}

function slotPrePostRows(rows) {
  return (rows || []).map(r => `<tr>
    <td>${escapeHtml(r.slot)}</td>
    ${td(r.pre, 'usd')}${td(r.post, 'usd')}
    ${deltaCell(r.prevspost, 'usd')}
    ${pctDeltaCell(r.growthPct)}
  </tr>`).join('') || emptyRow(5);
}

function slotYoyRows(rows) {
  return (rows || []).map(r => `<tr>
    <td>${escapeHtml(r.slot)}</td>
    ${td(r.postLY, 'usd')}${td(r.post, 'usd')}
    ${deltaCell(r.yoy, 'usd')}
    ${pctDeltaCell(r.yoyPct)}
  </tr>`).join('') || emptyRow(5);
}

function marketingSourceRows(marketingTables) {
  const source = marketingTables?.bySource?.combined;
  const make = (entry) => {
    if (!entry) return '';
    return `<tr>
      <td>${escapeHtml(entry.label)}</td>
      ${td(entry.ordersPost, 'int')}
      ${td(entry.salesPost, 'usd')}
      ${td(entry.spendPost, 'usd')}
      ${td(entry.roasPost, 'roas')}
      ${td(entry.cpoPost, 'usd2')}
    </tr>`;
  };
  const out = `${make(source?.corp)}${make(source?.todc)}`;
  return out || emptyRow(6);
}

function markupCells(storeTables) {
  const stores = storeTables?.combined || storeTables?.dd || storeTables?.ue || [];
  if (!stores.length) {
    return Array.from({ length: 8 }, () =>
      `<div class="markup-cell"><span class="markup-store">[Store #]</span><span class="markup-pct">[XX%]</span></div>`).join('');
  }
  return stores.map(s =>
    `<div class="markup-cell"><span class="markup-store">${escapeHtml(s.storeId)}</span><span class="markup-pct">—</span></div>`).join('');
}

function emptyRow(cols) {
  return `<tr><td colspan="${cols}" style="text-align:center;color:var(--text-muted)">No data for this period</td></tr>`;
}

/** Subsection title + table/chart block that should not split across printed pages. */
function keepTogether(titleHtml, bodyHtml) {
  if (!bodyHtml) return '';
  const title = titleHtml ? `<div class="subsection-title">${titleHtml}</div>` : '';
  return `<div class="keep-together">${title}${bodyHtml}</div>`;
}

function tableBlock(title, tableInnerHtml, theadClass = '') {
  return keepTogether(title, `<div class="table-wrap ${theadClass}">${tableInnerHtml}</div>`);
}

function mapSectionHtml(mapImageDataUri, operatorName) {
  if (!mapImageDataUri) return '';
  return `
    <div class="section">
      <div class="section-header gold"><div class="section-title">Store Locations</div><div class="section-num">Map</div></div>
      ${keepTogether('', `<div class="map-export-wrap">${imgTag(mapImageDataUri, `${operatorName || 'Operator'} store map`, 'map-export-img')}</div>`)}
      <p class="chart-caption">Operator store locations — Post-period KPIs shown on map pins when analysis data is loaded.</p>
    </div>`;
}

/* ── Chart data ──────────────────────────────────────────────────────────── */

function chartData(summaryTables, ddSlot) {
  const cSales = summaryRow(summaryTables?.combined, 'sales') || {};
  const cPay = summaryRow(summaryTables?.combined, 'payouts') || {};
  const ddSales = summaryRow(summaryTables?.dd, 'sales') || {};
  const ueSales = summaryRow(summaryTables?.ue, 'sales') || {};
  const dpLabels = (ddSlot?.salesPrePost || []).map(r => r.slot);
  return {
    combinedPvp: {
      labels: ['Sales', 'Payouts'],
      pre: [cSales.pre || 0, cPay.pre || 0],
      post: [cSales.post || 0, cPay.post || 0],
    },
    yoy: {
      labels: ['DoorDash', 'Uber Eats', 'Total'],
      pre: [ddSales.postLY || 0, ueSales.postLY || 0, cSales.postLY || 0],
      post: [ddSales.post || 0, ueSales.post || 0, cSales.post || 0],
    },
    platform: {
      labels: ['DoorDash', 'Uber Eats'],
      pre: [ddSales.pre || 0, ueSales.pre || 0],
      post: [ddSales.post || 0, ueSales.post || 0],
    },
    daypart: {
      labels: dpLabels,
      pre: (ddSlot?.salesPrePost || []).map(r => r.pre || 0),
      post: (ddSlot?.salesPrePost || []).map(r => r.post || 0),
    },
  };
}

/* ── CSS (mirrors the report template design system) ─────────────────────── */

function reportCss(variant) {
  const lightVars = variant === 'word'
    ? `--bg:#fff;--surface:#fff;--surface2:#f1f3f5;--border:#d0d5e0;--border-light:#b8bfce;--text:#111827;--text-muted:#6b7280;--text-dim:#374151;--row-alt:rgba(0,0,0,.025);`
    : `--bg:#0a0d14;--surface:#111520;--surface2:#161c2d;--border:#1e2740;--border-light:#252f47;--text:#e2e8f0;--text-muted:#64748b;--text-dim:#94a3b8;--row-alt:rgba(255,255,255,.02);`;
  const titleColor = variant === 'word' ? '#111827' : '#fff';
  return `
  :root{${lightVars}--gold:#f5c842;--gold-dim:#c9a227;--red-mc:#da291c;--dd-red:#ff3008;--ue-green:#06c167;--pos:#22c55e;--neg:#ef4444;--pos-bg:rgba(34,197,94,.08);--neg-bg:rgba(239,68,68,.08);--mono:'DM Mono',ui-monospace,monospace;--display:'Barlow Condensed','Arial Narrow',sans-serif;--body:'Barlow',Arial,sans-serif;}
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
  html{font-size:14px;}
  body{background:var(--bg);color:var(--text);font-family:var(--body);font-weight:400;line-height:1.5;-webkit-font-smoothing:antialiased;}
  @media print{
    body{background:#fff;color:#000;}
    .page-break{page-break-before:always;break-before:page;}
    .no-print{display:none;}
    :root{--bg:#fff;--surface:#f8f9fa;--surface2:#f1f3f5;--text:#111;--text-muted:#555;--border:#ddd;}
    .keep-together,.table-wrap,.chart-container,.kpi-strip,.meta-grid,.cover,.map-export-wrap{
      break-inside:avoid;
      page-break-inside:avoid;
    }
    .table-wrap{overflow:visible;}
    thead{display:table-header-group;}
    .chart-canvas-wrap canvas{display:none!important;}
    .chart-print-img{display:block!important;width:100%;height:auto;}
  }
  .report{max-width:1100px;margin:0 auto;padding:0 24px 60px;}
  .cover{display:flex;align-items:flex-end;justify-content:space-between;padding:48px 0 32px;border-bottom:2px solid var(--gold);margin-bottom:40px;}
  .cover-tag{font-family:var(--mono);font-size:10px;letter-spacing:.18em;color:var(--gold);text-transform:uppercase;margin-bottom:10px;}
  .cover-title{font-family:var(--display);font-size:52px;font-weight:800;line-height:1;letter-spacing:-.01em;color:${titleColor};}
  .cover-title span{color:var(--gold);}
  .cover-sub{font-family:var(--display);font-size:22px;font-weight:600;color:var(--text-dim);letter-spacing:.02em;margin-top:6px;}
  .cover-right{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:10px;}
  .todc-logo{font-family:var(--display);font-size:36px;font-weight:800;letter-spacing:.06em;color:${titleColor};line-height:1;}
  .todc-sub{font-family:var(--mono);font-size:9px;letter-spacing:.2em;color:var(--gold);text-transform:uppercase;}
  .meta-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--border);border:1px solid var(--border);border-radius:4px;overflow:hidden;margin-bottom:40px;}
  .meta-cell{background:var(--surface);padding:14px 18px;}
  .meta-label{font-family:var(--mono);font-size:9px;letter-spacing:.15em;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px;}
  .meta-value{font-family:var(--mono);font-size:13px;color:var(--text-dim);font-weight:500;}
  .meta-value.placeholder{color:var(--gold-dim);font-style:italic;}
  .section{margin-bottom:48px;}
  .section-header{display:flex;align-items:center;gap:12px;margin-bottom:20px;padding-bottom:10px;border-bottom:2px solid var(--border);position:relative;}
  .section-header::before{content:'';display:block;width:4px;height:28px;border-radius:2px;flex-shrink:0;}
  .section-header.gold::before{background:var(--gold);}.section-header.red::before{background:var(--dd-red);}.section-header.green::before{background:var(--ue-green);}.section-header.mc::before{background:var(--red-mc);}
  .section-title{font-family:var(--display);font-size:22px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:${titleColor};}
  .section-num{font-family:var(--mono);font-size:10px;color:var(--text-muted);letter-spacing:.1em;margin-left:auto;}
  .subsection-title{font-family:var(--display);font-size:15px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--text-dim);margin:24px 0 10px;display:flex;align-items:center;gap:8px;}
  .subsection-title::after{content:'';flex:1;height:1px;background:var(--border);}
  .platform-badge{display:flex;align-items:center;justify-content:space-between;padding:12px 20px;border-radius:4px;margin-bottom:14px;}
  .platform-badge.dd{background:var(--dd-red);}.platform-badge.ue{background:var(--ue-green);}
  .platform-badge-name{font-family:var(--display);font-size:20px;font-weight:800;letter-spacing:.05em;color:#fff;text-transform:uppercase;}
  .platform-badge-logo{font-family:var(--mono);font-size:11px;font-weight:500;color:rgba(255,255,255,.7);letter-spacing:.1em;text-transform:uppercase;border:1px solid rgba(255,255,255,.3);padding:3px 10px;border-radius:3px;}
  .kpi-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--border);border:1px solid var(--border);border-radius:4px;overflow:hidden;margin-bottom:28px;}
  .kpi-card{background:var(--surface);padding:20px 16px;text-align:center;position:relative;overflow:hidden;}
  .kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--gold);}
  .kpi-label{font-family:var(--mono);font-size:9px;letter-spacing:.15em;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;}
  .kpi-value{font-family:var(--display);font-size:32px;font-weight:800;color:${titleColor};line-height:1;margin-bottom:6px;}
  .kpi-value.placeholder{color:var(--gold-dim);}
  .kpi-delta{font-family:var(--mono);font-size:11px;font-weight:500;}.kpi-delta.up{color:var(--pos);}.kpi-delta.down{color:var(--neg);}
  .table-wrap{border:1px solid var(--border);border-radius:4px;overflow:hidden;margin-bottom:16px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  thead tr{background:var(--surface2);}
  thead th{font-family:var(--mono);font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--text-muted);padding:10px 14px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap;font-weight:500;}
  thead th:first-child{text-align:left;}
  tbody tr{border-bottom:1px solid var(--border);}
  tbody tr:last-child{border-bottom:none;}
  tbody tr:nth-child(even){background:var(--row-alt);}
  tbody td{font-family:var(--mono);font-size:12px;padding:9px 14px;text-align:right;color:var(--text-dim);white-space:nowrap;}
  tbody td:first-child{text-align:left;font-family:var(--body);font-weight:500;font-size:13px;color:var(--text);}
  td.pos{color:var(--pos);background:var(--pos-bg);}td.neg{color:var(--neg);background:var(--neg-bg);}
  .thead-dd thead tr{background:${variant === 'word' ? '#fdecea' : '#1a0800'};}.thead-dd thead th{color:${variant === 'word' ? '#c0341d' : '#ff6b4a'};border-color:${variant === 'word' ? '#f3cabf' : '#2d1008'};}
  .thead-ue thead tr{background:${variant === 'word' ? '#e8f8ef' : '#001a0d'};}.thead-ue thead th{color:${variant === 'word' ? '#04864a' : '#06e07a'};border-color:${variant === 'word' ? '#c3ead4' : '#002b14'};}
  .chart-container{background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:24px;margin-bottom:16px;break-inside:avoid;page-break-inside:avoid;}
  .chart-title{font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-muted);margin-bottom:20px;}
  .chart-canvas-wrap{position:relative;height:240px;}
  canvas{display:block;}
  .chart-print-img{display:none;width:100%;height:auto;}
  .chart-caption{font-family:var(--mono);font-size:9px;color:var(--text-muted);letter-spacing:.1em;text-align:center;margin-top:12px;font-style:italic;}
  .map-export-wrap{background:var(--surface);border:1px solid var(--border);border-radius:4px;overflow:hidden;margin-bottom:16px;}
  .map-export-img{display:block;width:100%;height:auto;max-height:420px;object-fit:contain;background:var(--surface2);}
  .markup-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--border);border:1px solid var(--border);border-radius:4px;overflow:hidden;}
  .markup-cell{background:var(--surface);padding:10px 14px;display:flex;justify-content:space-between;align-items:center;}
  .markup-store{font-family:var(--mono);font-size:11px;color:var(--text-muted);}
  .markup-pct{font-family:var(--mono);font-size:13px;font-weight:500;color:var(--gold);}
  .appendix-box{border:1px dashed var(--border-light);border-radius:4px;padding:32px;text-align:center;min-height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;background:var(--surface);}
  .appendix-box-icon{font-size:28px;opacity:.3;}
  .appendix-box-label{font-family:var(--mono);font-size:10px;letter-spacing:.15em;color:var(--text-muted);text-transform:uppercase;}
  .report-footer{border-top:1px solid var(--border);padding:20px 0 0;display:flex;justify-content:space-between;align-items:center;}
  .footer-left,.footer-right{font-family:var(--mono);font-size:10px;color:var(--text-muted);letter-spacing:.1em;}
  .totals-row td{font-weight:600!important;color:var(--text)!important;border-top:2px solid var(--border-light)!important;}
  .print-bar{position:fixed;top:0;left:0;right:0;background:var(--surface2);border-bottom:1px solid var(--border);padding:10px 24px;display:flex;gap:10px;align-items:center;z-index:100;}
  .btn{font-family:var(--mono);font-size:11px;letter-spacing:.08em;font-weight:500;padding:7px 16px;border-radius:3px;border:none;cursor:pointer;text-transform:uppercase;}
  .btn-gold{background:var(--gold);color:#000;}
  .print-label{font-family:var(--mono);font-size:10px;color:var(--text-muted);letter-spacing:.12em;margin-left:auto;}
  @media print{.print-bar{display:none;}}`;
}

/* ── HTML assembly ───────────────────────────────────────────────────────── */

function metaValue(text, placeholder = false) {
  const cls = placeholder ? 'meta-value placeholder' : 'meta-value';
  return `<div class="${cls}">${escapeHtml(text)}</div>`;
}

function periodText(start, end) {
  if (!start || !end) return null;
  return `${format(start, 'MM/dd/yyyy')} – ${format(end, 'MM/dd/yyyy')}`;
}

function kpiCard(label, value, deltaPct, hasData) {
  if (!hasData) {
    return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value placeholder">—</div><div class="kpi-delta" style="color:var(--text-muted)">no data</div></div>`;
  }
  const dir = Number(deltaPct || 0) < 0 ? 'down' : 'up';
  const arrow = dir === 'down' ? '▼' : '▲';
  const deltaText = deltaPct == null
    ? '— combined'
    : `${arrow} ${num(Math.abs(Number(deltaPct)), 1)}% YoY`;
  return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-delta ${dir}">${deltaText}</div></div>`;
}

function buildReportBody(data, config, variant, mapImageDataUri = null) {
  const summaryTables = data.summaryTables || {};
  const storeTables = data.storeTables || {};
  const marketingTables = data.marketingTables || {};
  const ddSlot = platformSlotAnalysis(data, config, 'dd');
  const ueSlot = platformSlotAnalysis(data, config, 'ue');
  const includeCharts = variant !== 'word';

  const cSales = summaryRow(summaryTables.combined, 'sales');
  const cOrders = summaryRow(summaryTables.combined, 'orders');
  const cPay = summaryRow(summaryTables.combined, 'payouts');
  const ddStores = activeStoreCount(storeTables, 'dd');
  const ueStores = activeStoreCount(storeTables, 'ue');
  const payoutPerStore = combinedPayoutPerStore(summaryTables, storeTables, 'post');

  const prePeriod = periodText(config.ddPreStart, config.ddPreEnd);
  const postPeriod = periodText(config.ddPostStart, config.ddPostEnd);
  const today = format(new Date(), 'MM/dd/yyyy');
  const operatorName = (config.operatorName || '').trim();
  const operatorDisplay = operatorName || '[Operator Name]';

  const chart = chartData(summaryTables, ddSlot);

  const chartBlock = (title, id) => includeCharts
    ? `<div class="keep-together"><div class="chart-container"><div class="chart-title">${title}</div><div class="chart-canvas-wrap"><canvas id="${id}" height="240"></canvas></div></div></div>`
    : '';

  const platformSection = (key, label, colorClass, badgeClass, badgeLogo, includeMarketing) => {
    const summary = summaryTables[key];
    const marketingBlock = includeMarketing ? `
    ${tableBlock('Corporate vs TODC — Promos &amp; Ads', `<table>
      <thead><tr><th>Campaign</th><th>Orders</th><th>Sales</th><th>Spend</th><th>ROAS</th><th>Cost / Order</th></tr></thead>
      <tbody>${marketingSourceRows(marketingTables)}</tbody>
    </table>`, `thead-${badgeClass}`)}
    ${chartBlock('DoorDash vs Uber Eats — Sales Pre vs Post', 'chart-platform')}` : '';
    return `
  <div class="section">
    <div class="section-header ${colorClass}">
      <div class="section-title">${label}</div>
      <div class="section-num">${key === 'dd' ? '04' : '05'}</div>
    </div>
    <div class="platform-badge ${badgeClass}">
      <div class="platform-badge-name">${label}</div>
      <div class="platform-badge-logo">${badgeLogo}</div>
    </div>
    ${tableBlock('Pre vs Post', `<table>
      <thead><tr><th>Metric</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>LY Δ ($)</th><th>Growth %</th></tr></thead>
      <tbody>${metricPrePostRows(summary) || emptyRow(6)}</tbody>
    </table>`, `thead-${badgeClass}`)}
    ${tableBlock('YoY', `<table>
      <thead><tr><th>Metric</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${metricYoyRows(summary) || emptyRow(5)}</tbody>
    </table>`, `thead-${badgeClass}`)}
    ${marketingBlock}
  </div>`;
  };

  const storeLevelBlock = (key, label, badgeClass) => {
    const badge = badgeClass ? `<div class="platform-badge ${badgeClass}" style="margin-top:24px;"><div class="platform-badge-name">${label}</div><div class="platform-badge-logo">${badgeClass.toUpperCase()}</div></div>` : '';
    return `${badge}
    ${tableBlock(`${label} — Pre vs Post`, `<table>
      <thead><tr><th>Store ID</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>LY Δ ($)</th><th>Growth %</th></tr></thead>
      <tbody>${storePrePostRows(storeTables[key])}</tbody>
    </table>`, badgeClass ? `thead-${badgeClass}` : '')}
    ${tableBlock(`${label} — YoY`, `<table>
      <thead><tr><th>Store ID</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${storeYoyRows(storeTables[key])}</tbody>
    </table>`, badgeClass ? `thead-${badgeClass}` : '')}`;
  };

  const daypartBlock = (slot, label, badgeClass, logo) => slot ? `
    <div class="platform-badge ${badgeClass}"><div class="platform-badge-name">${label}</div><div class="platform-badge-logo">${logo}</div></div>
    ${tableBlock('Sales — Pre vs Post', `<table><thead><tr><th>Daypart</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>Growth %</th></tr></thead>
      <tbody>${slotPrePostRows(slot.salesPrePost)}</tbody></table>`, `thead-${badgeClass}`)}
    ${tableBlock('Sales — YoY', `<table><thead><tr><th>Daypart</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${slotYoyRows(slot.salesYoY)}</tbody></table>`, `thead-${badgeClass}`)}
    ${tableBlock('Payouts — Pre vs Post', `<table><thead><tr><th>Daypart</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>Growth %</th></tr></thead>
      <tbody>${slotPrePostRows(slot.payoutsPrePost)}</tbody></table>`, `thead-${badgeClass}`)}
    ${tableBlock('Payouts — YoY', `<table><thead><tr><th>Daypart</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${slotYoyRows(slot.payoutsYoY)}</tbody></table>`, `thead-${badgeClass}`)}` : '';

  const printBar = variant === 'screen'
    ? `<div class="print-bar no-print"><button class="btn btn-gold" id="printBtn" disabled>Preparing charts…</button><span class="print-label" id="printStatus">Rendering charts for PDF export…</span></div>`
    : '';

  return `${printBar}
  <div class="report">
    <div class="cover">
      <div class="cover-left">
        <div class="cover-tag">Partnership Performance Report</div>
        <div class="cover-title">${escapeHtml(operatorDisplay)} <span>&lt;&gt;</span> TODC</div>
        <div class="cover-sub">DoorDash &amp; Uber Eats — Combined Analysis</div>
      </div>
      <div class="cover-right">
        <div class="todc-logo">TODC</div>
        <div class="todc-sub">The On Demand Company</div>
      </div>
    </div>

    <div class="meta-grid">
      <div class="meta-cell"><div class="meta-label">Report Type</div>${metaValue('Custom Period')}</div>
      <div class="meta-cell"><div class="meta-label">Pre Period</div>${prePeriod ? metaValue(prePeriod) : metaValue('[MM/DD/YYYY] – [MM/DD/YYYY]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Post Period</div>${postPeriod ? metaValue(postPeriod) : metaValue('[MM/DD/YYYY] – [MM/DD/YYYY]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Active Stores — DoorDash</div>${metaValue(`${ddStores} stores`)}</div>
      <div class="meta-cell"><div class="meta-label">Active Stores — Uber Eats</div>${metaValue(`${ueStores} stores`)}</div>
      <div class="meta-cell"><div class="meta-label">Average Markup</div>${metaValue('[XX.XX%]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Account Manager</div>${metaValue('[Name]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Operator</div>${operatorName ? metaValue(operatorName) : metaValue('[Operator Name]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Date Prepared</div>${metaValue(today)}</div>
    </div>

    <div class="section">
      <div class="section-header gold"><div class="section-title">Overview</div><div class="section-num">01</div></div>
      <div class="kpi-strip">
        ${kpiCard('Sales Growth', cSales ? `${num(cSales.growthPct, 1)}%` : '—', cSales?.yoyPct, !!cSales)}
        ${kpiCard('Order Growth', cOrders ? `${num(cOrders.growthPct, 1)}%` : '—', cOrders?.yoyPct, !!cOrders)}
        ${kpiCard('New Customers', '—', null, false)}
        ${kpiCard('Payout / Store', payoutPerStore != null ? `$${num(payoutPerStore)}` : '—', cPay?.yoyPct, payoutPerStore != null)}
        ${kpiCard('Avg Markup', '—', null, false)}
      </div>
      ${tableBlock('Pre-TODC YoY Baseline (Sales)', `<table>
        <thead><tr><th>Platform</th><th>Prior Year</th><th>Current Year</th><th>Δ ($)</th><th>Δ (%)</th></tr></thead>
        <tbody>${baselineRows(summaryTables) || emptyRow(5)}</tbody>
      </table>`)}
    </div>

    ${mapSectionHtml(mapImageDataUri, operatorDisplay)}

    <div class="section">
      <div class="section-header gold"><div class="section-title">Store Level Markups</div><div class="section-num">02</div></div>
      ${keepTogether('', `<div class="markup-grid">${markupCells(storeTables)}</div>`)}
    </div>

    <div class="section">
      <div class="section-header gold"><div class="section-title">Combined Performance</div><div class="section-num">03</div></div>
      ${tableBlock('Pre vs Post', `<table>
        <thead><tr><th>Metric</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>LY Δ ($)</th><th>Growth %</th></tr></thead>
        <tbody>${metricPrePostRows(summaryTables.combined) || emptyRow(6)}</tbody>
      </table>`)}
      ${chartBlock('Sales &amp; Payout — Pre vs Post (Combined)', 'chart-combined-pvp')}
      ${tableBlock('YoY: Post (Last Year) vs Post (Current)', `<table>
        <thead><tr><th>Metric</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
        <tbody>${metricYoyRows(summaryTables.combined) || emptyRow(5)}</tbody>
      </table>`)}
      ${chartBlock('YoY Sales — DoorDash / Uber Eats / Combined', 'chart-yoy')}
    </div>

    ${platformSection('dd', 'DoorDash', 'red', 'dd', 'DD · Platform Analytics', true)}
    ${platformSection('ue', 'Uber Eats', 'green', 'ue', 'UE · Platform Analytics', false)}

    <div class="section">
      <div class="section-header gold"><div class="section-title">Store Level Analysis</div><div class="section-num">06</div></div>
      ${storeLevelBlock('combined', 'Combined', '')}
      ${storeLevelBlock('dd', 'DoorDash — Store Level', 'dd')}
      ${storeLevelBlock('ue', 'Uber Eats — Store Level', 'ue')}
    </div>

    <div class="section">
      <div class="section-header gold"><div class="section-title">Day Part Analysis</div><div class="section-num">07</div></div>
      ${daypartBlock(ddSlot, 'DoorDash', 'dd', 'DD · Day Part')}
      ${chartBlock('DoorDash — Sales by Daypart (Pre vs Post)', 'chart-daypart-dd')}
      ${daypartBlock(ueSlot, 'Uber Eats', 'ue', 'UE · Day Part')}
    </div>

    <div class="section">
      <div class="section-header mc"><div class="section-title">Appendix</div><div class="section-num">08</div></div>
      <div class="subsection-title">DoorDash Downtime</div>
      <div class="appendix-box"><div class="appendix-box-icon">📎</div><div class="appendix-box-label">Insert DoorDash downtime screenshots or data exports here</div></div>
    </div>

    <div class="report-footer">
      <div class="footer-left">CONFIDENTIAL — The On Demand Company (TODC) · All rights reserved</div>
      <div class="footer-right">todc.com · ${escapeHtml(operatorDisplay)} Partnership Report</div>
    </div>
  </div>
  ${includeCharts ? chartScript(chart) : ''}`;
}

function chartScript(chart) {
  return `
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
  var DATA = ${JSON.stringify(chart)};
  var FONT = { family: "'DM Mono', monospace", size: 10 };
  var GRID = 'rgba(120,120,120,.18)';
  function bar(id, labels, pre, post, money){
    var ctx = document.getElementById(id); if(!ctx || !window.Chart) return;
    new Chart(ctx, { type:'bar', data:{ labels:labels, datasets:[
      { label:'Pre', data:pre, backgroundColor:'rgba(70,130,180,.85)', borderColor:'rgba(70,130,180,1)', borderWidth:1, borderRadius:3 },
      { label:'Post', data:post, backgroundColor:'rgba(30,200,120,.85)', borderColor:'rgba(30,200,120,1)', borderWidth:1, borderRadius:3 }
    ]}, options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ position:'top', labels:{ font:FONT, boxWidth:12, padding:16 } } },
      scales:{ x:{ grid:{ color:GRID }, ticks:{ font:FONT } },
        y:{ grid:{ color:GRID }, ticks:{ font:FONT, callback:function(v){ return money ? '$'+(v/1000).toFixed(0)+'k' : v.toLocaleString(); } } } } } });
  }
  bar('chart-combined-pvp', DATA.combinedPvp.labels, DATA.combinedPvp.pre, DATA.combinedPvp.post, true);
  bar('chart-yoy', DATA.yoy.labels, DATA.yoy.pre, DATA.yoy.post, true);
  bar('chart-platform', DATA.platform.labels, DATA.platform.pre, DATA.platform.post, true);
  bar('chart-daypart-dd', DATA.daypart.labels, DATA.daypart.pre, DATA.daypart.post, true);

  function finalizeChartsForPrint() {
    document.querySelectorAll('.chart-canvas-wrap canvas').forEach(function (canvas) {
      try {
        var img = document.createElement('img');
        img.src = canvas.toDataURL('image/png');
        img.className = 'chart-print-img';
        img.alt = canvas.closest('.chart-container')?.querySelector('.chart-title')?.textContent || 'Chart';
        canvas.parentNode.insertBefore(img, canvas);
      } catch (err) {
        console.warn('Chart print image failed', err);
      }
    });
  }

  function markPrintReady() {
    finalizeChartsForPrint();
    var btn = document.getElementById('printBtn');
    var status = document.getElementById('printStatus');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Print / Save as PDF';
      btn.onclick = function () { window.print(); };
    }
    if (status) status.textContent = 'Charts ready — use Print / Save as PDF';
  }

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () { setTimeout(markPrintReady, 350); });
  } else {
    window.addEventListener('load', function () { setTimeout(markPrintReady, 500); });
  }
</script>`;
}

/* ── Word / Google Docs builder ──────────────────────────────────────────────
   Word and Google Docs' HTML import ignore CSS variables, flexbox, grid and
   pseudo-elements, so the styled variant must use table-based layout with fully
   inline styles and concrete colours. This light, branded build matches the
   printed PDF (accent section bars, KPI cards, platform badges, ± colour cells).
*/

const W = {
  text: '#111827', muted: '#6b7280', dim: '#374151', border: '#d9dee8',
  goldBar: '#f5c842', goldText: '#9a7611',
  ddRed: '#ff3008', ueGreen: '#06c167', mcRed: '#da291c',
  posText: '#15803d', posBg: '#e9f9ef', negText: '#c0341d', negBg: '#fdecea',
  theadBg: '#f1f3f5', theadText: '#6b7280',
  display: "'Arial Narrow',Arial,sans-serif", body: 'Arial,Helvetica,sans-serif', mono: "'Courier New',monospace",
};

function wValTd(value, kind) {
  return `<td style="border:1px solid ${W.border};padding:7px 10px;font-family:${W.mono};font-size:11px;color:${W.dim};text-align:right">${fmtValue(value, kind)}</td>`;
}
function wLabelTd(text) {
  return `<td style="border:1px solid ${W.border};padding:7px 10px;font-family:${W.body};font-size:12px;font-weight:bold;color:${W.text};text-align:left">${escapeHtml(text)}</td>`;
}
function wDeltaTd(value, kind) {
  const n = Number(value || 0);
  const neg = n < 0;
  const color = neg ? W.negText : W.posText;
  const bg = neg ? W.negBg : W.posBg;
  const arrow = neg ? '▼' : '▲';
  const sign = neg ? '-' : '+';
  let body;
  switch (kind) {
    case 'usd': body = `$${num(Math.abs(n))}`; break;
    case 'usd2': body = `$${num(Math.abs(n), 2)}`; break;
    case 'int': body = num(Math.abs(n)); break;
    case 'pct': body = `${num(Math.abs(n), 1)}%`; break;
    default: body = num(Math.abs(n));
  }
  return `<td style="border:1px solid ${W.border};padding:7px 10px;font-family:${W.mono};font-size:11px;text-align:right;color:${color};background:${bg}">${arrow} ${sign}${body}</td>`;
}

function wThead(headers, accent) {
  const bg = accent?.bg || W.theadBg;
  const tc = accent?.text || W.theadText;
  const ths = headers.map((h, i) =>
    `<th style="background:${bg};border:1px solid ${W.border};padding:8px 10px;font-family:${W.mono};font-size:9px;letter-spacing:.04em;text-transform:uppercase;color:${tc};text-align:${i === 0 ? 'left' : 'right'};font-weight:bold">${h}</th>`).join('');
  return `<thead><tr>${ths}</tr></thead>`;
}
function wDataTable(headers, bodyRows, accent) {
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:14px">${wThead(headers, accent)}<tbody>${bodyRows}</tbody></table>`;
}
function wEmpty(cols) {
  return `<tr><td colspan="${cols}" style="border:1px solid ${W.border};padding:10px;text-align:center;font-family:${W.mono};font-size:11px;color:${W.muted}">No data for this period</td></tr>`;
}

function wSectionHeader(title, numStr, accentColor) {
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin:0 0 16px"><tr>
    <td style="width:5px;background:${accentColor};border-bottom:2px solid ${W.border}"></td>
    <td style="padding:0 0 8px 12px;border-bottom:2px solid ${W.border}"><span style="font-family:${W.display};font-size:20px;font-weight:bold;letter-spacing:.04em;text-transform:uppercase;color:${W.text}">${title}</span></td>
    <td style="padding:0 0 8px;border-bottom:2px solid ${W.border};text-align:right;font-family:${W.mono};font-size:10px;color:${W.muted};width:42px">${numStr}</td>
  </tr></table>`;
}
function wSub(title) {
  return `<p style="font-family:${W.display};font-size:13px;font-weight:bold;letter-spacing:.05em;text-transform:uppercase;color:${W.dim};margin:18px 0 8px">${title}</p>`;
}
function wBadge(name, logo, bg) {
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin:0 0 10px"><tr>
    <td style="background:${bg};padding:9px 16px;font-family:${W.display};font-size:16px;font-weight:bold;letter-spacing:.05em;text-transform:uppercase;color:#ffffff">${name}</td>
    <td style="background:${bg};padding:9px 16px;text-align:right;font-family:${W.mono};font-size:10px;color:#ffffff">${logo}</td>
  </tr></table>`;
}

const DD_ACCENT = { bg: W.negBg, text: W.negText };
const UE_ACCENT = { bg: W.posBg, text: '#04864a' };

const PVP_METRIC_HEADERS = ['Metric', 'Pre', 'Post', 'Δ ($)', 'LY Δ ($)', 'Growth %'];
const YOY_METRIC_HEADERS = ['Metric', 'LY Post', 'Post', 'YoY ($)', 'YoY %'];
const STORE_PVP_HEADERS = ['Store ID', 'Pre', 'Post', 'Δ ($)', 'LY Δ ($)', 'Growth %'];
const STORE_YOY_HEADERS = ['Store ID', 'LY Post', 'Post', 'YoY ($)', 'YoY %'];
const SLOT_PVP_HEADERS = ['Daypart', 'Pre', 'Post', 'Δ ($)', 'Growth %'];
const SLOT_YOY_HEADERS = ['Daypart', 'LY Post', 'Post', 'YoY ($)', 'YoY %'];

function wMetricPvp(summary) {
  return METRIC_ORDER.map((m) => {
    const r = summaryRow(summary, m);
    if (!r) return '';
    const k = METRIC_KIND[m];
    return `<tr>${wLabelTd(METRIC_LABELS[m])}${wValTd(r.pre, k)}${wValTd(r.post, k)}${wDeltaTd(r.prevspost, k)}${wDeltaTd(r.lyPrevspost, k)}${wDeltaTd(r.growthPct, 'pct')}</tr>`;
  }).join('') || wEmpty(6);
}
function wMetricYoy(summary) {
  return METRIC_ORDER.map((m) => {
    const r = summaryRow(summary, m);
    if (!r) return '';
    const k = METRIC_KIND[m];
    return `<tr>${wLabelTd(METRIC_LABELS[m])}${wValTd(r.postLY, k)}${wValTd(r.post, k)}${wDeltaTd(r.yoy, k)}${wDeltaTd(r.yoyPct, 'pct')}</tr>`;
  }).join('') || wEmpty(5);
}
function wStorePvp(stores) {
  return (stores || []).map(s =>
    `<tr>${wLabelTd(s.storeId)}${wValTd(s.pre_sales, 'usd')}${wValTd(s.post_sales, 'usd')}${wDeltaTd(s.sales_prevspost, 'usd')}${wDeltaTd(s.sales_ly_prevspost, 'usd')}${wDeltaTd(s.sales_growth_pct, 'pct')}</tr>`).join('') || wEmpty(6);
}
function wStoreYoy(stores) {
  return (stores || []).map(s =>
    `<tr>${wLabelTd(s.storeId)}${wValTd(s.postLY_sales, 'usd')}${wValTd(s.post_sales, 'usd')}${wDeltaTd(s.sales_yoy, 'usd')}${wDeltaTd(s.sales_yoy_pct, 'pct')}</tr>`).join('') || wEmpty(5);
}
function wSlotPvp(rows) {
  return (rows || []).map(r =>
    `<tr>${wLabelTd(r.slot)}${wValTd(r.pre, 'usd')}${wValTd(r.post, 'usd')}${wDeltaTd(r.prevspost, 'usd')}${wDeltaTd(r.growthPct, 'pct')}</tr>`).join('') || wEmpty(5);
}
function wSlotYoy(rows) {
  return (rows || []).map(r =>
    `<tr>${wLabelTd(r.slot)}${wValTd(r.postLY, 'usd')}${wValTd(r.post, 'usd')}${wDeltaTd(r.yoy, 'usd')}${wDeltaTd(r.yoyPct, 'pct')}</tr>`).join('') || wEmpty(5);
}
function wBaseline(summaryTables) {
  const rows = [
    { label: 'DoorDash', row: summaryRow(summaryTables?.dd, 'sales') },
    { label: 'Uber Eats', row: summaryRow(summaryTables?.ue, 'sales') },
    { label: 'Total', row: summaryRow(summaryTables?.combined, 'sales') },
  ].filter(({ row }) => row);
  return rows.map(({ label, row }) =>
    `<tr>${wLabelTd(label)}${wValTd(row.postLY, 'usd')}${wValTd(row.post, 'usd')}${wDeltaTd(row.yoy, 'usd')}${wDeltaTd(row.yoyPct, 'pct')}</tr>`).join('') || wEmpty(5);
}
function wMarketing(marketingTables) {
  const src = marketingTables?.bySource?.combined;
  const make = (e) => e
    ? `<tr>${wLabelTd(e.label)}${wValTd(e.ordersPost, 'int')}${wValTd(e.salesPost, 'usd')}${wValTd(e.spendPost, 'usd')}${wValTd(e.roasPost, 'roas')}${wValTd(e.cpoPost, 'usd2')}</tr>`
    : '';
  return `${make(src?.corp)}${make(src?.todc)}` || wEmpty(6);
}

function wKpiStrip(cards) {
  const width = `${Math.floor(100 / cards.length)}%`;
  const tds = cards.map(c => `<td style="border:1px solid ${W.border};border-top:3px solid ${W.goldBar};padding:14px 8px;text-align:center;width:${width};vertical-align:top">
    <div style="font-family:${W.mono};font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:${W.muted};margin-bottom:6px">${c.label}</div>
    <div style="font-family:${W.display};font-size:24px;font-weight:bold;color:${c.value === '—' ? W.goldText : W.text};margin-bottom:4px">${c.value}</div>
    <div style="font-family:${W.mono};font-size:9px;color:${c.deltaColor || W.muted}">${c.delta}</div>
  </td>`).join('');
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:24px"><tr>${tds}</tr></table>`;
}
function wMetaGrid(cells) {
  let rows = '';
  for (let i = 0; i < cells.length; i += 3) {
    const group = cells.slice(i, i + 3);
    while (group.length < 3) group.push(null);
    rows += '<tr>' + group.map(c => c
      ? `<td style="border:1px solid ${W.border};padding:12px 16px;width:33.3%;vertical-align:top"><div style="font-family:${W.mono};font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:${W.muted};margin-bottom:4px">${c.label}</div><div style="font-family:${W.mono};font-size:12px;color:${c.placeholder ? W.goldText : W.dim};font-style:${c.placeholder ? 'italic' : 'normal'}">${escapeHtml(c.value)}</div></td>`
      : `<td style="border:1px solid ${W.border}"></td>`).join('') + '</tr>';
  }
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:32px">${rows}</table>`;
}
function wMarkupGrid(stores) {
  const cells = stores.length
    ? stores.map(s => ({ id: s.storeId, pct: '—' }))
    : Array.from({ length: 8 }, () => ({ id: '[Store #]', pct: '[XX%]' }));
  let rows = '';
  for (let i = 0; i < cells.length; i += 4) {
    const group = cells.slice(i, i + 4);
    while (group.length < 4) group.push(null);
    rows += '<tr>' + group.map(c => c
      ? `<td style="border:1px solid ${W.border};padding:9px 14px;width:25%"><table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse"><tr><td style="font-family:${W.mono};font-size:11px;color:${W.muted};text-align:left;border:none;padding:0">${escapeHtml(c.id)}</td><td style="font-family:${W.mono};font-size:12px;font-weight:bold;color:${W.goldText};text-align:right;border:none;padding:0">${escapeHtml(c.pct)}</td></tr></table></td>`
      : `<td style="border:1px solid ${W.border}"></td>`).join('') + '</tr>';
  }
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:14px">${rows}</table>`;
}

function buildWordReportHtml(data, config) {
  const summaryTables = data.summaryTables || {};
  const storeTables = data.storeTables || {};
  const marketingTables = data.marketingTables || {};
  const ddSlot = platformSlotAnalysis(data, config, 'dd');
  const ueSlot = platformSlotAnalysis(data, config, 'ue');

  const cSales = summaryRow(summaryTables.combined, 'sales');
  const cOrders = summaryRow(summaryTables.combined, 'orders');
  const cPay = summaryRow(summaryTables.combined, 'payouts');
  const ddStores = activeStoreCount(storeTables, 'dd');
  const ueStores = activeStoreCount(storeTables, 'ue');
  const payoutPerStore = combinedPayoutPerStore(summaryTables, storeTables, 'post');

  const prePeriod = periodText(config.ddPreStart, config.ddPreEnd);
  const postPeriod = periodText(config.ddPostStart, config.ddPostEnd);
  const today = format(new Date(), 'MM/dd/yyyy');
  const operatorName = (config.operatorName || '').trim();
  const operatorDisplay = operatorName || '[Operator Name]';

  const kpiDelta = (r) => r && r.yoyPct != null
    ? { delta: `${Number(r.yoyPct) < 0 ? '▼' : '▲'} ${num(Math.abs(Number(r.yoyPct)), 1)}% YoY`, color: Number(r.yoyPct) < 0 ? W.negText : W.posText }
    : { delta: 'no data', color: W.muted };

  const salesKpi = kpiDelta(cSales);
  const ordersKpi = kpiDelta(cOrders);
  const payKpi = kpiDelta(cPay);

  const cover = `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:28px;border-bottom:3px solid ${W.goldBar}"><tr>
    <td style="padding:0 0 24px;vertical-align:bottom">
      <div style="font-family:${W.mono};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:${W.goldText};margin-bottom:8px">Partnership Performance Report</div>
      <div style="font-family:${W.display};font-size:40px;font-weight:bold;color:${W.text};line-height:1.05">${escapeHtml(operatorDisplay)} &lt;&gt; TODC</div>
      <div style="font-family:${W.display};font-size:18px;font-weight:bold;color:${W.dim};margin-top:6px">DoorDash &amp; Uber Eats — Combined Analysis</div>
    </td>
    <td style="padding:0 0 24px;text-align:right;vertical-align:bottom">
      <div style="font-family:${W.display};font-size:30px;font-weight:bold;letter-spacing:.06em;color:${W.text}">TODC</div>
      <div style="font-family:${W.mono};font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:${W.goldText}">The On Demand Company</div>
    </td>
  </tr></table>`;

  const meta = wMetaGrid([
    { label: 'Report Type', value: 'Custom Period' },
    { label: 'Pre Period', value: prePeriod || '[MM/DD/YYYY] – [MM/DD/YYYY]', placeholder: !prePeriod },
    { label: 'Post Period', value: postPeriod || '[MM/DD/YYYY] – [MM/DD/YYYY]', placeholder: !postPeriod },
    { label: 'Active Stores — DoorDash', value: `${ddStores} stores` },
    { label: 'Active Stores — Uber Eats', value: `${ueStores} stores` },
    { label: 'Average Markup', value: '[XX.XX%]', placeholder: true },
    { label: 'Account Manager', value: '[Name]', placeholder: true },
    { label: 'Operator', value: operatorName || '[Operator Name]', placeholder: !operatorName },
    { label: 'Date Prepared', value: today },
  ]);

  const overview = `${wSectionHeader('Overview', '01', W.goldBar)}
    ${wKpiStrip([
      { label: 'Sales Growth', value: cSales ? `${num(cSales.growthPct, 1)}%` : '—', ...salesKpi },
      { label: 'Order Growth', value: cOrders ? `${num(cOrders.growthPct, 1)}%` : '—', ...ordersKpi },
      { label: 'New Customers', value: '—', delta: 'no data', deltaColor: W.muted },
      { label: 'Payout / Store', value: payoutPerStore != null ? `$${num(payoutPerStore)}` : '—', ...payKpi },
      { label: 'Avg Markup', value: '—', delta: 'combined', deltaColor: W.muted },
    ].map(c => ({ label: c.label, value: c.value, delta: c.delta, deltaColor: c.deltaColor || c.color })))}
    ${wSub('Pre-TODC YoY Baseline (Sales)')}
    ${wDataTable(['Platform', 'Prior Year', 'Current Year', 'Δ ($)', 'Δ (%)'], wBaseline(summaryTables))}`;

  const markups = `${wSectionHeader('Store Level Markups', '02', W.goldBar)}${wMarkupGrid(storeTables.combined || storeTables.dd || storeTables.ue || [])}`;

  const combined = `${wSectionHeader('Combined Performance', '03', W.goldBar)}
    ${wSub('Pre vs Post')}${wDataTable(PVP_METRIC_HEADERS, wMetricPvp(summaryTables.combined))}
    ${wSub('YoY: Post (Last Year) vs Post (Current)')}${wDataTable(YOY_METRIC_HEADERS, wMetricYoy(summaryTables.combined))}`;

  const platform = (key, label, accent, badge, logo, accentColor, num2, withMarketing) => `${wSectionHeader(label, num2, accentColor)}
    ${wBadge(label, logo, badge)}
    ${wSub('Pre vs Post')}${wDataTable(PVP_METRIC_HEADERS, wMetricPvp(summaryTables[key]), accent)}
    ${wSub('YoY')}${wDataTable(YOY_METRIC_HEADERS, wMetricYoy(summaryTables[key]), accent)}
    ${withMarketing ? `${wSub('Corporate vs TODC — Promos & Ads')}${wDataTable(['Campaign', 'Orders', 'Sales', 'Spend', 'ROAS', 'Cost / Order'], wMarketing(marketingTables), accent)}` : ''}`;

  const storeBlock = (key, label, accent, badge, logo, badgeColor) => `
    ${badge ? wBadge(label, logo, badgeColor) : wSub(label)}
    ${wSub(`${label} — Pre vs Post`)}${wDataTable(STORE_PVP_HEADERS, wStorePvp(storeTables[key]), accent)}
    ${wSub(`${label} — YoY`)}${wDataTable(STORE_YOY_HEADERS, wStoreYoy(storeTables[key]), accent)}`;

  const stores = `${wSectionHeader('Store Level Analysis', '06', W.goldBar)}
    ${storeBlock('combined', 'Combined', null, false)}
    ${storeBlock('dd', 'DoorDash — Store Level', DD_ACCENT, true, 'DD', W.ddRed)}
    ${storeBlock('ue', 'Uber Eats — Store Level', UE_ACCENT, true, 'UE', W.ueGreen)}`;

  const daypart = (slot, label, accent, logo, badgeColor) => slot ? `
    ${wBadge(label, logo, badgeColor)}
    ${wSub('Sales — Pre vs Post')}${wDataTable(SLOT_PVP_HEADERS, wSlotPvp(slot.salesPrePost), accent)}
    ${wSub('Sales — YoY')}${wDataTable(SLOT_YOY_HEADERS, wSlotYoy(slot.salesYoY), accent)}
    ${wSub('Payouts — Pre vs Post')}${wDataTable(SLOT_PVP_HEADERS, wSlotPvp(slot.payoutsPrePost), accent)}
    ${wSub('Payouts — YoY')}${wDataTable(SLOT_YOY_HEADERS, wSlotYoy(slot.payoutsYoY), accent)}` : '';

  const dayparts = `${wSectionHeader('Day Part Analysis', '07', W.goldBar)}
    ${daypart(ddSlot, 'DoorDash', DD_ACCENT, 'DD · Day Part', W.ddRed)}
    ${daypart(ueSlot, 'Uber Eats', UE_ACCENT, 'UE · Day Part', W.ueGreen)}`;

  const appendix = `${wSectionHeader('Appendix', '08', W.mcRed)}
    ${wSub('DoorDash Downtime')}
    <table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:14px"><tr><td style="border:1px dashed ${W.border};padding:28px;text-align:center;font-family:${W.mono};font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:${W.muted}">Insert DoorDash downtime screenshots or data exports here</td></tr></table>`;

  const footer = `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;border-top:1px solid ${W.border};margin-top:24px"><tr>
    <td style="padding:14px 0 0;font-family:${W.mono};font-size:9px;color:${W.muted}">CONFIDENTIAL — The On Demand Company (TODC) · All rights reserved</td>
    <td style="padding:14px 0 0;text-align:right;font-family:${W.mono};font-size:9px;color:${W.muted}">todc.com · ${escapeHtml(operatorDisplay)} Partnership Report</td>
  </tr></table>`;

  const sections = [
    cover, meta, overview, markups, combined,
    platform('dd', 'DoorDash', DD_ACCENT, W.ddRed, 'DD · Platform Analytics', '04', W.ddRed, true),
    platform('ue', 'Uber Eats', UE_ACCENT, W.ueGreen, 'UE · Platform Analytics', '05', W.ueGreen, false),
    stores, dayparts, appendix, footer,
  ].join('\n');

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>TODC Partnership Performance Report</title></head>
<body style="margin:0;background:#ffffff;color:${W.text};font-family:${W.body}">
<div style="max-width:1000px;margin:0 auto;padding:24px">
${sections}
</div>
</body></html>`;
}

/**
 * Build a complete, self-contained Partnership Report HTML document.
 * @param {object} data   useDataStore state (summaryTables, storeTables, marketingTables, ddFinancial, ueFinancial)
 * @param {object} config useConfigStore state (period dates, exclusions, operatorName)
 * @param {object} [opts] { variant: 'screen' | 'word' }
 *   - 'screen': dark, print-aware design with Chart.js charts (used for Print → PDF).
 *   - 'word': light, table-based, inline-styled build for Word / Google Docs fidelity.
 */
export function buildReportHtml(data, config, { variant = 'screen', mapImageDataUri = null } = {}) {
  if (variant === 'word') return buildWordReportHtml(data, config);
  const fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700;800&family=Barlow+Condensed:wght@600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">';
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TODC Partnership Performance Report</title>
${fonts}
<style>${reportCss('screen')}</style>
</head><body>
${buildReportBody(data, config, 'screen', mapImageDataUri)}
</body></html>`;
}

/* ── Output sinks ────────────────────────────────────────────────────────── */

function timestamp() {
  return format(new Date(), 'yyyyMMdd_HHmmss');
}

function downloadBlob(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Save the report as a Word-openable .doc (light theme, tables, no canvas). */
export function downloadReportDoc(data, config, baseName) {
  const html = buildReportHtml(data, config, { variant: 'word' });
  // Prepend a UTF-8 BOM so Word opens the HTML with correct encoding.
  downloadBlob('\uFEFF' + html, `${baseName}.doc`, 'application/msword');
}

/** Open the report (dark/print-aware, with charts) in a new tab for Print → Save as PDF. */
export async function openReportForPdf(data, config) {
  let mapImageDataUri = null;
  try {
    mapImageDataUri = await captureOperatorMapScreenshot(config, data?.storeTables);
  } catch (err) {
    console.warn('Map capture skipped:', err);
  }
  const html = buildReportHtml(data, config, { variant: 'screen', mapImageDataUri });
  const win = window.open('', '_blank');
  if (!win) return false;
  win.document.open();
  win.document.write(html);
  win.document.close();
  return true;
}

async function pushReportToGoogleDoc(filename, html) {
  const runtimeHost = typeof window !== 'undefined' && window.location?.hostname
    ? window.location.hostname
    : 'localhost';
  const fallbackLocalUrl = `http://${runtimeHost}:${LOCAL_EXPORT_API_PORT}/export-doc`;
  const targetUrl = GOOGLE_DOC_EXPORT_URL
    || (GOOGLE_SHEETS_EXPORT_URL ? GOOGLE_SHEETS_EXPORT_URL.replace(/\/export\/?$/, '/export-doc') : null)
    || fallbackLocalUrl;

  const response = await fetch(targetUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, createdAt: new Date().toISOString(), html }),
  });
  if (!response.ok) {
    throw new Error(`Google Docs push failed (${response.status}) via ${targetUrl}`);
  }
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: true, message: text };
  }
}

function extractDocUrl(gd) {
  if (!gd || gd.error || gd.skipped) return null;
  const candidates = [gd.docUrl, gd.webViewLink, gd.url, gd.link];
  for (const u of candidates) {
    if (typeof u === 'string' && /^https?:\/\//i.test(u.trim())) return u.trim();
  }
  return null;
}

/**
 * Full report export: download .doc, push to Google Doc.
 * Returns { docFilename, googleDoc, docUrl } for the result modal.
 * The PDF path is offered interactively from the modal (openReportForPdf).
 */
export async function exportPartnershipReport(data, config) {
  const baseName = `TODC_Partnership_Report_${timestamp()}`;
  downloadReportDoc(data, config, baseName);

  const wordHtml = buildReportHtml(data, config, { variant: 'word' });
  let googleDoc;
  try {
    googleDoc = await pushReportToGoogleDoc(baseName, wordHtml);
  } catch (err) {
    googleDoc = { error: err.message || String(err) };
  }
  return {
    docFilename: `${baseName}.doc`,
    googleDoc,
    docUrl: extractDocUrl(googleDoc),
  };
}
