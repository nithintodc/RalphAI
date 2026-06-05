/**
 * TODC Partnership Performance Report — document export.
 *
 * Fills the branded "Partnership Performance Report" template (cover, KPI strip,
 * Pre/Post + YoY tables, DoorDash / Uber Eats sections, store-level, day-part,
 * charts, footer) with live analysis data and produces:
 *   - a Word-openable .doc download (light theme, no canvas),
 *   - a print-to-PDF window (Super App light theme with charts),
 *   - a native Google Doc pushed to the same Shared Drive as the Excel export.
 *
 * Mirrors exportWorkbook.js for the Google push endpoint / env config.
 */

import { format } from 'date-fns';
import { buildSlotAnalysis, SLOT_DEFINITIONS, getSlotTimeRange } from '../engine/slots';
import { loadBrandLogosAsDataUri } from '../brand/brandLogos';
import { pivotDowntimeByStore } from '../utils/opsProductPivot';
import { buildNewCustomersSummary } from '../engine/newCustomers';

import { resolveDocExportUrl } from './exportApi.js';
import { buildExportFilename } from './exportFilename.js';
import {
  buildAlignedExportStoreTables,
  combinedExportStoreId,
  combinedExportStoreName,
  EXPORT_NA,
  exportStoreName,
  legacyStoreIdCell,
} from './storeExportLayout.js';

const GOOGLE_SHEETS_EXPORT_URL = import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL;
const GOOGLE_DOC_EXPORT_URL = import.meta.env.VITE_GOOGLE_DOC_EXPORT_URL;

function defaultExportDocUrl() {
  if (typeof window === 'undefined') return null;
  return `${window.location.origin}/api/export-doc`;
}

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

/** Google Docs HTML import respects width/height attributes better than CSS-only sizing. */
function imgTagDoc(src, alt, width, height, style = '') {
  if (!src) return '';
  return `<img src="${src}" alt="${escapeHtml(alt)}" width="${width}" height="${height}" style="${style}" />`;
}

function platformLogoKey(label) {
  if (/doordash/i.test(label)) return 'dd';
  if (/uber/i.test(label)) return 'ue';
  return null;
}

function platformInlineLabel(label, logos) {
  const key = platformLogoKey(label);
  const img = key && logos?.[key] ? imgTag(logos[key], label, 'platform-inline-logo') : '';
  return `${img}${escapeHtml(label)}`;
}

function coverRightHtml(logos) {
  if (logos?.todc) {
    return `<div class="cover-right">${imgTag(logos.todc, 'TODC', 'cover-logo-todc')}<div class="todc-sub">The On Demand Company</div></div>`;
  }
  return `<div class="cover-right"><div class="todc-logo">TODC</div><div class="todc-sub">The On Demand Company</div></div>`;
}

function platformBadgeHtml(badgeClass, label, logoText, logos, sectionNum = '') {
  const key = badgeClass === 'dd' ? 'dd' : badgeClass === 'ue' ? 'ue' : null;
  const logoImg = key && logos?.[key] ? imgTag(logos[key], label, 'platform-badge-img') : '';
  const num = sectionNum
    ? `<div class="platform-badge-num">${escapeHtml(sectionNum)}</div>`
    : '';
  return `<div class="platform-badge ${badgeClass}">
    <div class="platform-badge-left">${logoImg}<div class="platform-badge-name">${escapeHtml(label)}</div></div>
    <div class="platform-badge-right">${num}<div class="platform-badge-logo">${escapeHtml(logoText)}</div></div>
  </div>`;
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
      ${pctDeltaCell(r.lyGrowthPct)}
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

function baselineRows(summaryTables, logos) {
  const rows = [
    { label: 'DoorDash', row: summaryRow(summaryTables?.dd, 'sales') },
    { label: 'Uber Eats', row: summaryRow(summaryTables?.ue, 'sales') },
    { label: 'Total', row: summaryRow(summaryTables?.combined, 'sales'), total: true },
  ];
  return rows
    .filter(({ row }) => row)
    .map(({ label, row, total }) => `<tr${total ? ' class="totals-row"' : ''}>
      <td>${platformInlineLabel(label, logos)}</td>
      ${td(row.postLY, 'usd')}${td(row.post, 'usd')}
      ${deltaCell(row.yoy, 'usd')}
      ${pctDeltaCell(row.yoyPct)}
    </tr>`).join('');
}

function storePrePostRows(stores, metric = 'sales', platform = 'combined', dominantPlatform = 'dd') {
  return (stores || []).map((s) => {
    const storeId = platform === 'combined'
      ? combinedExportStoreId(s, dominantPlatform)
      : legacyStoreIdCell(s, platform);
    const storeName = platform === 'combined'
      ? combinedExportStoreName(s, dominantPlatform)
      : exportStoreName(s);
    const na = s._isNa;
    return `<tr>
    <td>${escapeHtml(storeId)}</td>
    <td>${escapeHtml(storeName)}</td>
    ${na ? `<td>${EXPORT_NA}</td><td>${EXPORT_NA}</td><td>${EXPORT_NA}</td><td>${EXPORT_NA}</td><td>${EXPORT_NA}</td><td>${EXPORT_NA}</td>` : `${td(s[`pre_${metric}`], 'usd')}${td(s[`post_${metric}`], 'usd')}
    ${deltaCell(s[`${metric}_prevspost`], 'usd')}
    ${deltaCell(s[`${metric}_ly_prevspost`], 'usd')}
    ${pctDeltaCell(s[`${metric}_growth_pct`])}
    ${pctDeltaCell(s[`${metric}_ly_growth_pct`])}`}
  </tr>`;
  }).join('') || emptyRow(8);
}

function storeYoyRows(stores, metric = 'sales', platform = 'combined', dominantPlatform = 'dd') {
  return (stores || []).map((s) => {
    const storeId = platform === 'combined'
      ? combinedExportStoreId(s, dominantPlatform)
      : legacyStoreIdCell(s, platform);
    const storeName = platform === 'combined'
      ? combinedExportStoreName(s, dominantPlatform)
      : exportStoreName(s);
    const na = s._isNa;
    return `<tr>
    <td>${escapeHtml(storeId)}</td>
    <td>${escapeHtml(storeName)}</td>
    ${na ? `<td>${EXPORT_NA}</td><td>${EXPORT_NA}</td><td>${EXPORT_NA}</td><td>${EXPORT_NA}</td>` : `${td(s[`postLY_${metric}`], 'usd')}${td(s[`post_${metric}`], 'usd')}
    ${deltaCell(s[`${metric}_yoy`], 'usd')}
    ${pctDeltaCell(s[`${metric}_yoy_pct`])}`}
  </tr>`;
  }).join('') || emptyRow(6);
}

function slotPrePostRows(rows) {
  return (rows || []).map(r => `<tr>
    <td>${escapeHtml(r.slot)}</td>
    <td>${escapeHtml(getSlotTimeRange(r.slot))}</td>
    ${td(r.pre, 'usd')}${td(r.post, 'usd')}
    ${deltaCell(r.prevspost, 'usd')}
    ${pctDeltaCell(r.growthPct)}
  </tr>`).join('') || emptyRow(6);
}

function slotYoyRows(rows) {
  return (rows || []).map(r => `<tr>
    <td>${escapeHtml(r.slot)}</td>
    <td>${escapeHtml(getSlotTimeRange(r.slot))}</td>
    ${td(r.postLY, 'usd')}${td(r.post, 'usd')}
    ${deltaCell(r.yoy, 'usd')}
    ${pctDeltaCell(r.yoyPct)}
  </tr>`).join('') || emptyRow(6);
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

function markupTableRows(storeTables) {
  const stores = storeTables?.combined || storeTables?.dd || storeTables?.ue || [];
  if (!stores.length) {
    return Array.from({ length: 3 }, () =>
      '<tr><td>[Store Name]</td><td>[XX%]</td></tr>').join('');
  }
  return stores.map((s) =>
    `<tr><td>${escapeHtml(s.storeId)}</td><td>—</td></tr>`).join('');
}

function markupTable(storeTables) {
  return `<div class="table-wrap"><table>
    <thead><tr><th>Store Name</th><th>Markup</th></tr></thead>
    <tbody>${markupTableRows(storeTables)}</tbody>
  </table></div>`;
}

function emptyRow(cols) {
  return `<tr><td colspan="${cols}" style="text-align:center;color:var(--text-muted)">No data for this period</td></tr>`;
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

/* ── Super App theme tokens (mirrors index.css) ─────────────────────────── */

const APP_THEME = {
  bg: '#FAFAF9',
  surface: '#FFFFFF',
  surface2: '#F5F5F4',
  border: '#E7E5E4',
  borderStrong: '#D6D3D1',
  text: '#0C0A09',
  textMuted: '#57534E',
  textSubtle: '#A8A29E',
  accent: '#059669',
  accentSoft: '#ECFDF5',
  accentBorder: '#A7F3D0',
  accentText: '#065F46',
  positive: '#059669',
  negative: '#DC2626',
  ddColor: '#EF4444',
  ueColor: '#111827',
  posBg: 'rgba(5,150,105,0.08)',
  negBg: 'rgba(220,38,38,0.08)',
  rowAlt: 'rgba(0,0,0,0.02)',
  font: "'Inter', system-ui, -apple-system, sans-serif",
};

/* ── CSS (Super App light theme — screen + print) ─────────────────────────── */

function reportCss() {
  const t = APP_THEME;
  return `
  :root{
    --bg:${t.bg};--surface:${t.surface};--surface2:${t.surface2};
    --border:${t.border};--border-light:${t.borderStrong};
    --text:${t.text};--text-muted:${t.textMuted};--text-dim:${t.textMuted};--text-subtle:${t.textSubtle};
    --accent:${t.accent};--accent-soft:${t.accentSoft};--accent-border:${t.accentBorder};--accent-text:${t.accentText};
    --dd-red:${t.ddColor};--ue-green:${t.ueColor};--red-mc:${t.negative};
    --pos:${t.positive};--neg:${t.negative};--pos-bg:${t.posBg};--neg-bg:${t.negBg};
    --row-alt:${t.rowAlt};
    --mono:${t.font};--display:${t.font};--body:${t.font};
    --radius:12px;--shadow:0 1px 2px rgba(0,0,0,0.05);
  }
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
  html{font-size:14px;}
  body{background:var(--bg);color:var(--text);font-family:var(--body);font-weight:400;line-height:1.5;-webkit-font-smoothing:antialiased;}
  @media print{body{background:#fff;}.page-break{page-break-before:always;}.no-print{display:none;}}
  .report{max-width:1100px;margin:0 auto;padding:72px 24px 60px;}
  @media print{.report{padding-top:24px;}}
  .cover{display:flex;align-items:flex-end;justify-content:space-between;padding:32px 28px;margin-bottom:32px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);}
  .cover-tag{font-size:10px;font-weight:600;letter-spacing:.12em;color:var(--accent-text);text-transform:uppercase;margin-bottom:10px;}
  .cover-title{font-size:36px;font-weight:700;line-height:1.15;letter-spacing:-.02em;color:var(--text);}
  .cover-title span{color:var(--accent);}
  .cover-sub{font-size:16px;font-weight:500;color:var(--text-muted);margin-top:8px;}
  .cover-platforms{display:flex;align-items:center;flex-wrap:wrap;gap:6px;}
  .cover-platform-logo{height:18px;width:auto;object-fit:contain;}
  .cover-right{text-align:right;display:flex;flex-direction:column;align-items:flex-end;justify-content:flex-end;gap:8px;min-width:140px;}
  .cover-logo-todc{height:52px;width:auto;max-width:180px;object-fit:contain;}
  .todc-logo{font-size:28px;font-weight:700;letter-spacing:.04em;color:var(--text);line-height:1;}
  .todc-sub{font-size:9px;font-weight:500;letter-spacing:.14em;color:var(--accent-text);text-transform:uppercase;}
  .meta-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--border);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;margin-bottom:32px;box-shadow:var(--shadow);}
  .meta-cell{background:var(--surface);padding:14px 18px;}
  .meta-label{font-size:10px;font-weight:600;letter-spacing:.08em;color:var(--text-subtle);text-transform:uppercase;margin-bottom:4px;}
  .meta-value{font-size:13px;color:var(--text);font-weight:500;font-variant-numeric:tabular-nums;}
  .meta-value.placeholder{color:var(--text-subtle);font-style:italic;}
  .section{margin-bottom:40px;}
  .section-header{display:flex;align-items:center;gap:12px;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid var(--border);position:relative;}
  .section-header::before{content:'';display:block;width:4px;height:24px;border-radius:2px;flex-shrink:0;}
  .section-header.gold::before,.section-header.accent::before{background:var(--accent);}
  .section-header.red::before{background:var(--dd-red);}
  .section-header.green::before{background:var(--ue-green);}
  .section-header.mc::before{background:var(--red-mc);}
  .section-title{font-size:18px;font-weight:600;color:var(--text);}
  .section-num{font-size:10px;color:var(--text-subtle);letter-spacing:.08em;margin-left:auto;font-weight:500;}
  .subsection-title{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);margin:20px 0 10px;display:flex;align-items:center;gap:8px;}
  .subsection-title::after{content:'';flex:1;height:1px;background:var(--border);}
  .platform-badge{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-radius:8px;margin-bottom:14px;}
  .platform-badge-right{display:flex;align-items:center;gap:12px;}
  .platform-badge-num{font-family:var(--mono);font-size:10px;color:rgba(255,255,255,.75);letter-spacing:.06em;}
  .platform-badge-left{display:flex;align-items:center;gap:10px;min-width:0;}
  .platform-badge-img{height:28px;width:auto;max-width:72px;object-fit:contain;background:#fff;border-radius:6px;padding:3px 6px;}
  .platform-inline-logo{height:16px;width:auto;max-width:48px;object-fit:contain;vertical-align:middle;margin-right:6px;}
  .meta-label .platform-inline-logo{height:14px;max-width:40px;margin-right:4px;}
  .platform-badge.dd{background:var(--dd-red);}
  .platform-badge.ue{background:var(--ue-green);}
  .platform-badge-name{font-size:16px;font-weight:600;color:#fff;text-transform:uppercase;letter-spacing:.03em;}
  .platform-badge-logo{font-size:10px;font-weight:500;color:rgba(255,255,255,.85);letter-spacing:.08em;text-transform:uppercase;border:1px solid rgba(255,255,255,.35);padding:3px 10px;border-radius:6px;}
  .kpi-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px;}
  .kpi-card{background:var(--surface);padding:16px 14px;text-align:center;border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);position:relative;overflow:hidden;}
  .kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent);}
  .kpi-label{font-size:10px;font-weight:500;letter-spacing:.06em;color:var(--text-muted);text-transform:uppercase;margin-bottom:8px;}
  .kpi-value{font-size:28px;font-weight:700;color:var(--text);line-height:1;margin-bottom:6px;font-variant-numeric:tabular-nums;}
  .kpi-value.placeholder{color:var(--text-subtle);}
  .kpi-delta{font-size:11px;font-weight:500;font-variant-numeric:tabular-nums;}
  .kpi-delta.up{color:var(--pos);}.kpi-delta.down{color:var(--neg);}
  .table-wrap{border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;margin-bottom:16px;background:var(--surface);box-shadow:var(--shadow);}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  thead tr{background:var(--surface2);}
  thead th{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);padding:10px 14px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap;}
  thead th:first-child{text-align:left;}
  tbody tr{border-bottom:1px solid var(--border);}
  tbody tr:last-child{border-bottom:none;}
  tbody tr:nth-child(even){background:var(--row-alt);}
  tbody td{font-size:12px;padding:9px 14px;text-align:right;color:var(--text-muted);white-space:nowrap;font-variant-numeric:tabular-nums;}
  tbody td:first-child{text-align:left;font-weight:500;font-size:13px;color:var(--text);}
  td.pos{color:var(--pos);background:var(--pos-bg);font-weight:500;}
  td.neg{color:var(--neg);background:var(--neg-bg);font-weight:500;}
  .thead-dd thead tr{background:#FEF2F2;}.thead-dd thead th{color:#B91C1C;border-color:#FECACA;}
  .thead-ue thead tr{background:#F5F5F4;}.thead-ue thead th{color:#111827;border-color:#E7E5E4;}
  .chart-container{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px;box-shadow:var(--shadow);}
  .chart-title{font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);margin-bottom:16px;}
  .chart-canvas-wrap{position:relative;height:280px;}
  canvas{display:block;}
  .chart-caption{font-size:10px;color:var(--text-subtle);text-align:center;margin-top:12px;font-style:italic;}
  .report-footer{border-top:1px solid var(--border);padding:20px 0 0;display:flex;justify-content:space-between;align-items:center;}
  .footer-left,.footer-right{font-size:10px;color:var(--text-subtle);}
  .totals-row td{font-weight:600!important;color:var(--text)!important;border-top:2px solid var(--border-light)!important;}
  .print-bar{position:fixed;top:0;left:0;right:0;background:var(--surface);border-bottom:1px solid var(--border);padding:10px 24px;display:flex;gap:10px;align-items:center;z-index:100;box-shadow:var(--shadow);}
  .btn{font-size:12px;font-weight:600;padding:8px 16px;border-radius:8px;border:none;cursor:pointer;}
  .btn-gold,.btn-accent{background:var(--accent);color:#fff;}
  .btn-gold:hover,.btn-accent:hover{background:#047857;}
  .print-label{font-size:11px;color:var(--text-muted);margin-left:auto;}
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

const DOWNTIME_REPORT_HEADERS = ['Store', 'Days', 'Hours', 'Minutes', 'Total (min)', 'Rows'];

function getDowntimeStoreRows(data) {
  const raw = data?.ddOps?.byStore?.downtime?.data;
  if (!Array.isArray(raw) || !raw.length) return [];
  const columns = raw[0] ? Object.keys(raw[0]) : [];
  const pivot = pivotDowntimeByStore(raw, columns);
  return pivot?.rows?.length ? pivot.rows : [];
}

function buildSlotDefinitionsScreenSection() {
  const body = SLOT_DEFINITIONS.map(({ name, range }) =>
    `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(range)}</td></tr>`).join('');
  return `
    <div class="section">
      <div class="section-header gold"><div class="section-title">Day Part Definitions</div></div>
      <p class="text-xs" style="color:var(--text-subtle);margin:0 0 12px;font-size:11px;line-height:1.5">
        DoorDash financial dayparts use <strong>Order received local time</strong>; SALES_BY_ORDER uses <strong>Order placed time</strong>. Uber Eats uses <strong>Order Accept Time</strong>.
      </p>
      <div class="table-wrap"><table>
        <thead><tr><th>Day part</th><th>Time window</th></tr></thead>
        <tbody>${body}</tbody>
      </table></div>
    </div>`;
}

function buildSlotDefinitionsWordSection() {
  const body = SLOT_DEFINITIONS.map(({ name, range }) =>
    `<tr>${wLabelTd(name)}${wLabelTd(range)}</tr>`).join('');
  return `${wSectionHeader('Day Part Definitions', '09', W.accentBar)}
    ${wSub('Time windows (DoorDash financial: Order received local time · SALES_BY_ORDER: Order placed time · Uber Eats: Order Accept Time)')}
    ${wDataTable(['Day part', 'Time window'], body)}`;
}

function buildAppendixScreenSection(data) {
  const rows = getDowntimeStoreRows(data);
  if (!rows.length) return '';

  const body = rows.map((r) => `<tr>
    <td>${escapeHtml(r.store)}</td>
    <td>${num(r.days ?? 0)}</td>
    <td>${num(r.hours ?? 0)}</td>
    <td>${num(r.minutes ?? 0)}</td>
    <td>${num(r.totalMinutes ?? 0)}</td>
    <td>${num(r.lineCount ?? 0)}</td>
  </tr>`).join('');

  const head = DOWNTIME_REPORT_HEADERS.map((h, i) =>
    `<th${i === 0 ? '' : ''}>${h}</th>`).join('');

  return `
    <div class="section">
      <div class="section-header mc"><div class="section-title">Appendix</div><div class="section-num">08</div></div>
      <div class="subsection-title">DoorDash Downtime — by store</div>
      <div class="table-wrap"><table>
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table></div>
    </div>`;
}

function kpiCard(label, value, deltaPct, hasData, deltaSuffix = 'YoY') {
  if (!hasData) {
    return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value placeholder">—</div><div class="kpi-delta" style="color:var(--text-muted)">no data</div></div>`;
  }
  const dir = Number(deltaPct || 0) < 0 ? 'down' : 'up';
  const arrow = dir === 'down' ? '▼' : '▲';
  const deltaText = deltaPct == null
    ? '—'
    : `${arrow} ${num(Math.abs(Number(deltaPct)), 1)}% ${deltaSuffix}`;
  return `<div class="kpi-card"><div class="kpi-label">${label}</div><div class="kpi-value">${value}</div><div class="kpi-delta ${dir}">${deltaText}</div></div>`;
}

function buildReportBody(data, config, variant, logos = null) {
  const summaryTables = data.summaryTables || {};
  const storeTables = data.storeTables || {};
  const alignedStores = buildAlignedExportStoreTables(storeTables, config?.ddToUeStoreMap || {});
  const exportStoreTables = {
    combined: alignedStores.combined,
    dd: alignedStores.dd,
    ue: alignedStores.ue,
  };
  const dominantPlatform = alignedStores.dominantPlatform;
  const marketingTables = data.marketingTables || {};
  const ddSlot = platformSlotAnalysis(data, config, 'dd');
  const ueSlot = platformSlotAnalysis(data, config, 'ue');
  const includeCharts = variant !== 'word';

  const cSales = summaryRow(summaryTables.combined, 'sales');
  const cOrders = summaryRow(summaryTables.combined, 'orders');
  const cPay = summaryRow(summaryTables.combined, 'payouts');
  const ddStores = activeStoreCount(storeTables, 'dd');
  const ueStores = activeStoreCount(storeTables, 'ue');
  const payoutLiftPerStore = cPay && (ddStores + ueStores) > 0
    ? cPay.prevspost / (ddStores + ueStores)
    : null;

  const prePeriod = periodText(config.ddPreStart, config.ddPreEnd);
  const postPeriod = periodText(config.ddPostStart, config.ddPostEnd);
  const today = format(new Date(), 'MM/dd/yyyy');
  const operatorName = (config.operatorName || '').trim();
  const operatorDisplay = operatorName || '[Operator Name]';
  const accountManager = (config.accountManager || '').trim();

  const chart = chartData(summaryTables, ddSlot);

  const chartBlock = (title, id) => includeCharts
    ? `<div class="chart-container"><div class="chart-title">${title}</div><div class="chart-canvas-wrap"><canvas id="${id}" height="280"></canvas></div></div>`
    : '';

  const ncSummary = buildNewCustomersSummary(data, config);
  const cNewCust = ncSummary?.combined;

  const platformSection = (key, label, badgeClass, badgeLogo, sectionNum, includeMarketing) => {
    const summary = summaryTables[key];
    return `
  <div class="section">
    ${platformBadgeHtml(badgeClass, label, badgeLogo, logos, sectionNum)}
    <div class="subsection-title">Pre vs Post</div>
    <div class="table-wrap thead-${badgeClass}"><table>
      <thead><tr><th>Metric</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>LY Δ ($)</th><th>Growth %</th><th>LY Growth %</th></tr></thead>
      <tbody>${metricPrePostRows(summary) || emptyRow(6)}</tbody>
    </table></div>
    <div class="subsection-title">YoY</div>
    <div class="table-wrap thead-${badgeClass}"><table>
      <thead><tr><th>Metric</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${metricYoyRows(summary) || emptyRow(5)}</tbody>
    </table></div>
    ${includeMarketing ? `
    <div class="subsection-title">Corporate vs TODC — Promos &amp; Ads</div>
    <div class="table-wrap thead-${badgeClass}"><table>
      <thead><tr><th>Campaign</th><th>Orders</th><th>Sales</th><th>Spend</th><th>ROAS</th><th>Cost / Order</th></tr></thead>
      <tbody>${marketingSourceRows(marketingTables)}</tbody>
    </table></div>
    ${chartBlock('DoorDash vs Uber Eats — Sales Pre vs Post', 'chart-platform')}` : ''}
  </div>`;
  };

  const storeLevelBlock = (key, label, badgeClass) => `
    ${badgeClass ? platformBadgeHtml(badgeClass, label, badgeClass.toUpperCase(), logos) : ''}
    <div class="subsection-title">${label} — Pre vs Post</div>
    <div class="table-wrap ${badgeClass ? `thead-${badgeClass}` : ''}"><table>
      <thead><tr><th>Store ID</th><th>Store Name</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>LY Δ ($)</th><th>Growth %</th><th>LY Growth %</th></tr></thead>
      <tbody>${storePrePostRows(exportStoreTables[key], 'sales', key, dominantPlatform)}</tbody>
    </table></div>
    <div class="subsection-title">${label} — YoY</div>
    <div class="table-wrap ${badgeClass ? `thead-${badgeClass}` : ''}"><table>
      <thead><tr><th>Store ID</th><th>Store Name</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${storeYoyRows(exportStoreTables[key], 'sales', key, dominantPlatform)}</tbody>
    </table></div>`;

  const daypartBlock = (slot, label, badgeClass, logo) => slot ? `
    ${platformBadgeHtml(badgeClass, label, logo, logos)}
    <div class="subsection-title">Sales — Pre vs Post</div>
    <div class="table-wrap thead-${badgeClass}"><table><thead><tr><th>Daypart</th><th>Slot time</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>Growth %</th></tr></thead>
      <tbody>${slotPrePostRows(slot.salesPrePost)}</tbody></table></div>
    <div class="subsection-title">Sales — YoY</div>
    <div class="table-wrap thead-${badgeClass}"><table><thead><tr><th>Daypart</th><th>Slot time</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${slotYoyRows(slot.salesYoY)}</tbody></table></div>
    <div class="subsection-title">Payouts — Pre vs Post</div>
    <div class="table-wrap thead-${badgeClass}"><table><thead><tr><th>Daypart</th><th>Slot time</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>Growth %</th></tr></thead>
      <tbody>${slotPrePostRows(slot.payoutsPrePost)}</tbody></table></div>
    <div class="subsection-title">Payouts — YoY</div>
    <div class="table-wrap thead-${badgeClass}"><table><thead><tr><th>Daypart</th><th>Slot time</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
      <tbody>${slotYoyRows(slot.payoutsYoY)}</tbody></table></div>` : '';

  const printBar = variant === 'screen'
    ? `<div class="print-bar no-print"><button class="btn btn-accent" onclick="window.print()">Print / Save as PDF</button><span class="print-label">TODC Partnership Performance Report</span></div>`
    : '';

  return `${printBar}
  <div class="report">
    <div class="cover">
      <div class="cover-left">
        <div class="cover-tag">Partnership Performance Report</div>
        <div class="cover-title">${escapeHtml(operatorDisplay)} <span>&lt;&gt;</span> TODC</div>
        <div class="cover-sub cover-platforms">${logos?.dd ? imgTag(logos.dd, 'DoorDash', 'cover-platform-logo') : ''}<span>DoorDash &amp; Uber Eats</span>${logos?.ue ? imgTag(logos.ue, 'Uber Eats', 'cover-platform-logo') : ''}<span>— Combined Analysis</span></div>
      </div>
      ${coverRightHtml(logos)}
    </div>

    <div class="meta-grid">
      <div class="meta-cell"><div class="meta-label">Report Type</div>${metaValue('Custom Period')}</div>
      <div class="meta-cell"><div class="meta-label">Pre Period</div>${prePeriod ? metaValue(prePeriod) : metaValue('[MM/DD/YYYY] – [MM/DD/YYYY]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Post Period</div>${postPeriod ? metaValue(postPeriod) : metaValue('[MM/DD/YYYY] – [MM/DD/YYYY]', true)}</div>
      <div class="meta-cell"><div class="meta-label">${platformInlineLabel('Active Stores — DoorDash', logos)}</div>${metaValue(`${ddStores} stores`)}</div>
      <div class="meta-cell"><div class="meta-label">${platformInlineLabel('Active Stores — Uber Eats', logos)}</div>${metaValue(`${ueStores} stores`)}</div>
      <div class="meta-cell"><div class="meta-label">Average Markup</div>${metaValue('[XX.XX%]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Account Manager</div>${accountManager ? metaValue(accountManager) : metaValue('[Name]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Operator</div>${operatorName ? metaValue(operatorName) : metaValue('[Operator Name]', true)}</div>
      <div class="meta-cell"><div class="meta-label">Date Prepared</div>${metaValue(today)}</div>
    </div>

    <div class="section">
      <div class="section-header gold"><div class="section-title">Overview</div><div class="section-num">01</div></div>
      <div class="kpi-strip">
        ${kpiCard('Sales Growth', cSales ? `${num(cSales.growthPct, 1)}%` : '—', cSales?.yoyPct, !!cSales)}
        ${kpiCard('Order Growth', cOrders ? `${num(cOrders.growthPct, 1)}%` : '—', cOrders?.yoyPct, !!cOrders)}
        ${kpiCard('New Customers', cNewCust ? num(cNewCust.post) : '—', cNewCust?.growthPct, !!cNewCust, 'Pre vs Post')}
        ${kpiCard('Payout Lift / Store', payoutLiftPerStore != null ? `$${num(payoutLiftPerStore)}` : '—', cPay?.yoyPct, payoutLiftPerStore != null)}
        ${kpiCard('Avg Markup', '—', null, false)}
      </div>
      <div class="subsection-title">Pre-TODC YoY Baseline (Sales)</div>
      <div class="table-wrap"><table>
        <thead><tr><th>Platform</th><th>Prior Year</th><th>Current Year</th><th>Δ ($)</th><th>Δ (%)</th></tr></thead>
        <tbody>${baselineRows(summaryTables, logos) || emptyRow(5)}</tbody>
      </table></div>
    </div>

    <div class="section">
      <div class="section-header gold"><div class="section-title">Store Level Markups</div><div class="section-num">02</div></div>
      ${markupTable(storeTables)}
    </div>

    <div class="section">
      <div class="section-header gold"><div class="section-title">Combined Performance</div><div class="section-num">03</div></div>
      <div class="subsection-title">Pre vs Post</div>
      <div class="table-wrap"><table>
        <thead><tr><th>Metric</th><th>Pre</th><th>Post</th><th>Δ ($)</th><th>LY Δ ($)</th><th>Growth %</th><th>LY Growth %</th></tr></thead>
        <tbody>${metricPrePostRows(summaryTables.combined) || emptyRow(6)}</tbody>
      </table></div>
      ${chartBlock('Sales &amp; Payout — Pre vs Post (Combined)', 'chart-combined-pvp')}
      <div class="subsection-title">YoY: Post (Last Year) vs Post (Current)</div>
      <div class="table-wrap"><table>
        <thead><tr><th>Metric</th><th>LY Post</th><th>Post</th><th>YoY ($)</th><th>YoY %</th></tr></thead>
        <tbody>${metricYoyRows(summaryTables.combined) || emptyRow(5)}</tbody>
      </table></div>
      ${chartBlock('YoY Sales — DoorDash / Uber Eats / Combined', 'chart-yoy')}
    </div>

    ${platformSection('dd', 'DoorDash', 'dd', 'DD · Platform Analytics', '04', true)}
    ${platformSection('ue', 'Uber Eats', 'ue', 'UE · Platform Analytics', '05', false)}

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

    ${buildAppendixScreenSection(data)}

    ${buildSlotDefinitionsScreenSection()}

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
  var FONT = { family: "'Inter', system-ui, sans-serif", size: 11 };
  var GRID = 'rgba(0,0,0,0.06)';
  var PRE_BAR = 'rgba(214,211,209,0.9)';
  var POST_BAR = 'rgba(5,150,105,0.85)';

  function fmtMoney(v) {
    var n = Number(v) || 0;
    var abs = Math.abs(n);
    if (abs >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return '$' + (n / 1e3).toFixed(abs >= 1e4 ? 0 : 1) + 'k';
    return '$' + Math.round(n).toLocaleString();
  }

  function fmtDelta(pre, post) {
    var p = Number(pre) || 0;
    var q = Number(post) || 0;
    if (!p && !q) return '';
    if (!p) return q ? '▲ —' : '';
    var pct = ((q - p) / p) * 100;
    var arrow = pct >= 0 ? '▲' : '▼';
    return arrow + ' ' + Math.abs(pct).toFixed(1) + '%';
  }

  function deltaColor(pre, post) {
    var p = Number(pre) || 0;
    if (!p) return '#57534E';
    var pct = ((Number(post) || 0) - p) / p;
    return pct >= 0 ? '#059669' : '#DC2626';
  }

  function barValueDeltaPlugin(money, showDelta) {
    return {
      id: 'barValueDelta',
      afterDatasetsDraw: function (chart) {
        var ctx = chart.ctx;
        var preData = chart.data.datasets[0] ? chart.data.datasets[0].data : [];
        chart.data.datasets.forEach(function (dataset, di) {
          var meta = chart.getDatasetMeta(di);
          if (meta.hidden) return;
          meta.data.forEach(function (bar, i) {
            var val = dataset.data[i];
            if (val == null || Number.isNaN(Number(val))) return;
            var valueText = money ? fmtMoney(val) : Number(val).toLocaleString();
            var x = bar.x;
            var baseY = bar.y - 6;
            ctx.save();
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.font = "600 10px Inter, system-ui, sans-serif";
            ctx.fillStyle = '#44403C';
            if (showDelta && di === 1) {
              var deltaText = fmtDelta(preData[i], val);
              if (deltaText) {
                ctx.font = "600 9px Inter, system-ui, sans-serif";
                ctx.fillStyle = deltaColor(preData[i], val);
                ctx.fillText(deltaText, x, baseY - 12);
              }
            }
            ctx.font = "600 10px Inter, system-ui, sans-serif";
            ctx.fillStyle = '#44403C';
            ctx.fillText(valueText, x, baseY);
            ctx.restore();
          });
        });
      },
    };
  }

  function bar(id, labels, pre, post, money) {
    var ctx = document.getElementById(id);
    if (!ctx || !window.Chart) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Pre', data: pre, backgroundColor: PRE_BAR, borderColor: '#D6D3D1', borderWidth: 1, borderRadius: 6 },
          { label: 'Post', data: post, backgroundColor: POST_BAR, borderColor: '#059669', borderWidth: 1, borderRadius: 6 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 40 } },
        plugins: {
          legend: { position: 'top', labels: { font: FONT, boxWidth: 12, padding: 16, color: '#57534E' } },
        },
        scales: {
          x: { grid: { color: GRID }, ticks: { font: FONT, color: '#57534E' } },
          y: {
            grid: { color: GRID },
            ticks: {
              font: FONT,
              color: '#57534E',
              callback: function (v) {
                return money ? '$' + (v / 1000).toFixed(0) + 'k' : v.toLocaleString();
              },
            },
          },
        },
      },
      plugins: [barValueDeltaPlugin(money, true)],
    });
  }

  bar('chart-combined-pvp', DATA.combinedPvp.labels, DATA.combinedPvp.pre, DATA.combinedPvp.post, true);
  bar('chart-yoy', DATA.yoy.labels, DATA.yoy.pre, DATA.yoy.post, true);
  bar('chart-platform', DATA.platform.labels, DATA.platform.pre, DATA.platform.post, true);
  bar('chart-daypart-dd', DATA.daypart.labels, DATA.daypart.pre, DATA.daypart.post, true);
</script>`;
}

/* ── Word / Google Docs builder ──────────────────────────────────────────────
   Word and Google Docs' HTML import ignore CSS variables, flexbox, grid and
   pseudo-elements, so the styled variant must use table-based layout with fully
   inline styles and concrete colours. This light, branded build matches the
   printed PDF (accent section bars, KPI cards, platform badges, ± colour cells).
*/

const W = {
  text: APP_THEME.text,
  muted: APP_THEME.textMuted,
  dim: APP_THEME.textMuted,
  border: APP_THEME.border,
  accentBar: APP_THEME.accent,
  accentText: APP_THEME.accentText,
  ddRed: APP_THEME.ddColor,
  ueGreen: APP_THEME.ueColor,
  mcRed: APP_THEME.negative,
  posText: APP_THEME.positive,
  posBg: APP_THEME.posBg,
  negText: APP_THEME.negative,
  negBg: APP_THEME.negBg,
  theadBg: APP_THEME.surface2,
  theadText: APP_THEME.textMuted,
  body: APP_THEME.font,
  display: APP_THEME.font,
  mono: APP_THEME.font,
};

function wValTd(value, kind) {
  return `<td style="border:1px solid ${W.border};padding:7px 10px;font-family:${W.mono};font-size:11px;color:${W.dim};text-align:right">${fmtValue(value, kind)}</td>`;
}
function wLabelTd(text) {
  return `<td style="border:1px solid ${W.border};padding:7px 10px;font-family:${W.body};font-size:12px;font-weight:bold;color:${W.text};text-align:left">${escapeHtml(text)}</td>`;
}
function wPlatformLabelTd(label, logos) {
  const key = platformLogoKey(label);
  const img = key && logos?.[key]
    ? `<img src="${logos[key]}" alt="" style="height:14px;width:auto;vertical-align:middle;margin-right:6px;" />`
    : '';
  return `<td style="border:1px solid ${W.border};padding:7px 10px;font-family:${W.body};font-size:12px;font-weight:bold;color:${W.text};text-align:left">${img}${escapeHtml(label)}</td>`;
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
function wBadge(name, logo, bg, logos, platformKey, sectionNum = '') {
  const imgHtml = platformKey && logos?.[platformKey]
    ? `<img src="${logos[platformKey]}" alt="" style="height:20px;width:auto;vertical-align:middle;margin-right:8px;background:#fff;border-radius:4px;padding:2px 5px;" />`
    : '';
  const numCell = sectionNum
    ? `<td style="background:${bg};padding:9px 12px;text-align:right;font-family:${W.mono};font-size:10px;color:rgba(255,255,255,.8);width:36px">${escapeHtml(sectionNum)}</td>`
    : '';
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin:0 0 10px"><tr>
    <td style="background:${bg};padding:9px 16px;font-family:${W.display};font-size:16px;font-weight:bold;letter-spacing:.05em;text-transform:uppercase;color:#ffffff">${imgHtml}${escapeHtml(name)}</td>
    <td style="background:${bg};padding:9px 16px;text-align:right;font-family:${W.mono};font-size:10px;color:#ffffff">${escapeHtml(logo)}</td>
    ${numCell}
  </tr></table>`;
}

const DD_ACCENT = { bg: W.negBg, text: W.negText };
const UE_ACCENT = { bg: W.posBg, text: '#04864a' };

const PVP_METRIC_HEADERS = ['Metric', 'Pre', 'Post', 'Δ ($)', 'LY Δ ($)', 'Growth %', 'LY Growth %'];
const YOY_METRIC_HEADERS = ['Metric', 'LY Post', 'Post', 'YoY ($)', 'YoY %'];
const STORE_PVP_HEADERS = ['Store ID', 'Store Name', 'Pre', 'Post', 'Δ ($)', 'LY Δ ($)', 'Growth %', 'LY Growth %'];
const STORE_YOY_HEADERS = ['Store ID', 'Store Name', 'LY Post', 'Post', 'YoY ($)', 'YoY %'];
const SLOT_PVP_HEADERS = ['Daypart', 'Slot time', 'Pre', 'Post', 'Δ ($)', 'Growth %'];
const SLOT_YOY_HEADERS = ['Daypart', 'Slot time', 'LY Post', 'Post', 'YoY ($)', 'YoY %'];

function buildAppendixWordSection(data) {
  const rows = getDowntimeStoreRows(data);
  if (!rows.length) return '';

  const body = rows.map((r) => `<tr>
    ${wLabelTd(r.store)}
    ${wValTd(r.days, 'int')}
    ${wValTd(r.hours, 'int')}
    ${wValTd(r.minutes, 'int')}
    ${wValTd(r.totalMinutes, 'int')}
    ${wValTd(r.lineCount, 'int')}
  </tr>`).join('');

  return `${wSectionHeader('Appendix', '08', W.mcRed)}
    ${wSub('DoorDash Downtime — by store')}
    ${wDataTable(DOWNTIME_REPORT_HEADERS, body)}`;
}

function wMetricPvp(summary) {
  return METRIC_ORDER.map((m) => {
    const r = summaryRow(summary, m);
    if (!r) return '';
    const k = METRIC_KIND[m];
    return `<tr>${wLabelTd(METRIC_LABELS[m])}${wValTd(r.pre, k)}${wValTd(r.post, k)}${wDeltaTd(r.prevspost, k)}${wDeltaTd(r.lyPrevspost, k)}${wDeltaTd(r.growthPct, 'pct')}${wDeltaTd(r.lyGrowthPct, 'pct')}</tr>`;
  }).join('') || wEmpty(7);
}
function wMetricYoy(summary) {
  return METRIC_ORDER.map((m) => {
    const r = summaryRow(summary, m);
    if (!r) return '';
    const k = METRIC_KIND[m];
    return `<tr>${wLabelTd(METRIC_LABELS[m])}${wValTd(r.postLY, k)}${wValTd(r.post, k)}${wDeltaTd(r.yoy, k)}${wDeltaTd(r.yoyPct, 'pct')}</tr>`;
  }).join('') || wEmpty(5);
}
function wStorePvp(stores, platform = 'combined', dominantPlatform = 'dd') {
  return (stores || []).map((s) => {
    const storeId = platform === 'combined'
      ? combinedExportStoreId(s, dominantPlatform)
      : legacyStoreIdCell(s, platform);
    const storeName = platform === 'combined'
      ? combinedExportStoreName(s, dominantPlatform)
      : exportStoreName(s);
    if (s._isNa) {
      return `<tr>${wLabelTd(storeId)}${wLabelTd(storeName)}${wValTd(EXPORT_NA, 'text')}${wValTd(EXPORT_NA, 'text')}${wDeltaTd(EXPORT_NA, 'usd')}${wDeltaTd(EXPORT_NA, 'usd')}${wDeltaTd(EXPORT_NA, 'pct')}${wDeltaTd(EXPORT_NA, 'pct')}</tr>`;
    }
    return `<tr>${wLabelTd(storeId)}${wLabelTd(storeName)}${wValTd(s.pre_sales, 'usd')}${wValTd(s.post_sales, 'usd')}${wDeltaTd(s.sales_prevspost, 'usd')}${wDeltaTd(s.sales_ly_prevspost, 'usd')}${wDeltaTd(s.sales_growth_pct, 'pct')}${wDeltaTd(s.sales_ly_growth_pct, 'pct')}</tr>`;
  }).join('') || wEmpty(8);
}
function wStoreYoy(stores, platform = 'combined', dominantPlatform = 'dd') {
  return (stores || []).map((s) => {
    const storeId = platform === 'combined'
      ? combinedExportStoreId(s, dominantPlatform)
      : legacyStoreIdCell(s, platform);
    const storeName = platform === 'combined'
      ? combinedExportStoreName(s, dominantPlatform)
      : exportStoreName(s);
    if (s._isNa) {
      return `<tr>${wLabelTd(storeId)}${wLabelTd(storeName)}${wValTd(EXPORT_NA, 'text')}${wValTd(EXPORT_NA, 'text')}${wDeltaTd(EXPORT_NA, 'usd')}${wDeltaTd(EXPORT_NA, 'pct')}</tr>`;
    }
    return `<tr>${wLabelTd(storeId)}${wLabelTd(storeName)}${wValTd(s.postLY_sales, 'usd')}${wValTd(s.post_sales, 'usd')}${wDeltaTd(s.sales_yoy, 'usd')}${wDeltaTd(s.sales_yoy_pct, 'pct')}</tr>`;
  }).join('') || wEmpty(6);
}
function wSlotPvp(rows) {
  return (rows || []).map(r =>
    `<tr>${wLabelTd(r.slot)}${wLabelTd(getSlotTimeRange(r.slot))}${wValTd(r.pre, 'usd')}${wValTd(r.post, 'usd')}${wDeltaTd(r.prevspost, 'usd')}${wDeltaTd(r.growthPct, 'pct')}</tr>`).join('') || wEmpty(6);
}
function wSlotYoy(rows) {
  return (rows || []).map(r =>
    `<tr>${wLabelTd(r.slot)}${wLabelTd(getSlotTimeRange(r.slot))}${wValTd(r.postLY, 'usd')}${wValTd(r.post, 'usd')}${wDeltaTd(r.yoy, 'usd')}${wDeltaTd(r.yoyPct, 'pct')}</tr>`).join('') || wEmpty(6);
}
function wBaseline(summaryTables, logos) {
  const rows = [
    { label: 'DoorDash', row: summaryRow(summaryTables?.dd, 'sales') },
    { label: 'Uber Eats', row: summaryRow(summaryTables?.ue, 'sales') },
    { label: 'Total', row: summaryRow(summaryTables?.combined, 'sales') },
  ].filter(({ row }) => row);
  return rows.map(({ label, row }) =>
    `<tr>${wPlatformLabelTd(label, logos)}${wValTd(row.postLY, 'usd')}${wValTd(row.post, 'usd')}${wDeltaTd(row.yoy, 'usd')}${wDeltaTd(row.yoyPct, 'pct')}</tr>`).join('') || wEmpty(5);
}
function wMetaLabel(text, logos) {
  const key = platformLogoKey(text);
  const img = key && logos?.[key]
    ? `<img src="${logos[key]}" alt="" style="height:12px;width:auto;vertical-align:middle;margin-right:4px;" />`
    : '';
  return `${img}${escapeHtml(text)}`;
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
  const tds = cards.map(c => `<td style="border:1px solid ${W.border};border-top:3px solid ${W.accentBar};padding:14px 8px;text-align:center;width:${width};vertical-align:top">
    <div style="font-family:${W.mono};font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:${W.muted};margin-bottom:6px">${c.label}</div>
    <div style="font-family:${W.display};font-size:24px;font-weight:bold;color:${c.value === '—' ? W.accentText : W.text};margin-bottom:4px">${c.value}</div>
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
      ? `<td style="border:1px solid ${W.border};padding:12px 16px;width:33.3%;vertical-align:top"><div style="font-family:${W.mono};font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:${W.muted};margin-bottom:4px">${c.labelHtml ?? escapeHtml(c.label)}</div><div style="font-family:${W.mono};font-size:12px;color:${c.placeholder ? W.accentText : W.dim};font-style:${c.placeholder ? 'italic' : 'normal'}">${escapeHtml(c.value)}</div></td>`
      : `<td style="border:1px solid ${W.border}"></td>`).join('') + '</tr>';
  }
  return `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:32px">${rows}</table>`;
}
function wMarkupRows(stores) {
  if (!stores.length) {
    return Array.from({ length: 3 }, () =>
      `<tr>${wLabelTd('[Store Name]')}${wValTd('[XX%]', 'text')}</tr>`).join('');
  }
  return stores.map((s) =>
    `<tr>${wLabelTd(s.storeId)}${wValTd('—', 'text')}</tr>`).join('');
}

function buildWordReportHtml(data, config, logos = null) {
  const summaryTables = data.summaryTables || {};
  const storeTables = data.storeTables || {};
  const alignedStores = buildAlignedExportStoreTables(storeTables, config?.ddToUeStoreMap || {});
  const exportStoreTables = {
    combined: alignedStores.combined,
    dd: alignedStores.dd,
    ue: alignedStores.ue,
  };
  const dominantPlatform = alignedStores.dominantPlatform;
  const marketingTables = data.marketingTables || {};
  const ddSlot = platformSlotAnalysis(data, config, 'dd');
  const ueSlot = platformSlotAnalysis(data, config, 'ue');

  const cSales = summaryRow(summaryTables.combined, 'sales');
  const cOrders = summaryRow(summaryTables.combined, 'orders');
  const cPay = summaryRow(summaryTables.combined, 'payouts');
  const ncSummary = buildNewCustomersSummary(data, config);
  const cNewCust = ncSummary?.combined;
  const ddStores = activeStoreCount(storeTables, 'dd');
  const ueStores = activeStoreCount(storeTables, 'ue');
  const payoutLiftPerStore = cPay && (ddStores + ueStores) > 0 ? cPay.prevspost / (ddStores + ueStores) : null;

  const prePeriod = periodText(config.ddPreStart, config.ddPreEnd);
  const postPeriod = periodText(config.ddPostStart, config.ddPostEnd);
  const today = format(new Date(), 'MM/dd/yyyy');
  const operatorName = (config.operatorName || '').trim();
  const operatorDisplay = operatorName || '[Operator Name]';
  const accountManager = (config.accountManager || '').trim();

  const kpiDelta = (r) => r && r.yoyPct != null
    ? { delta: `${Number(r.yoyPct) < 0 ? '▼' : '▲'} ${num(Math.abs(Number(r.yoyPct)), 1)}% YoY`, color: Number(r.yoyPct) < 0 ? W.negText : W.posText }
    : { delta: 'no data', color: W.muted };

  const salesKpi = kpiDelta(cSales);
  const ordersKpi = kpiDelta(cOrders);
  const payKpi = kpiDelta(cPay);

  const todcCoverRight = logos?.todc
    ? `${imgTagDoc(logos.todc, 'TODC', 170, 28, 'display:block;margin-left:auto;margin-bottom:6px;max-width:170px;height:auto;object-fit:contain;')}<div style="font-family:${W.mono};font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:${W.accentText};text-align:right;">The On Demand Company</div>`
    : `<div style="font-family:${W.display};font-size:30px;font-weight:bold;letter-spacing:.06em;color:${W.text};text-align:right;">TODC</div><div style="font-family:${W.mono};font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:${W.accentText};text-align:right;">The On Demand Company</div>`;

  const coverPlatformLogos = (logos?.dd || logos?.ue)
    ? `<span style="display:inline-flex;align-items:center;gap:8px;margin-top:8px;">${logos?.dd ? `<img src="${logos.dd}" alt="DoorDash" style="height:20px;width:auto;vertical-align:middle;" />` : ''}<span style="font-family:${W.display};font-size:14px;color:${W.dim};">DoorDash &amp; Uber Eats</span>${logos?.ue ? `<img src="${logos.ue}" alt="Uber Eats" style="height:20px;width:auto;vertical-align:middle;" />` : ''}<span style="font-family:${W.display};font-size:14px;color:${W.dim};">— Combined Analysis</span></span>`
    : `<div style="font-family:${W.display};font-size:18px;font-weight:bold;color:${W.dim};margin-top:6px">DoorDash &amp; Uber Eats — Combined Analysis</div>`;

  const cover = `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;margin-bottom:28px;border-bottom:3px solid ${W.accentBar}"><tr>
    <td style="padding:0 0 24px;vertical-align:bottom">
      <div style="font-family:${W.mono};font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:${W.accentText};margin-bottom:8px">Partnership Performance Report</div>
      <div style="font-family:${W.display};font-size:40px;font-weight:bold;color:${W.text};line-height:1.05">${escapeHtml(operatorDisplay)} &lt;&gt; TODC</div>
      ${coverPlatformLogos}
    </td>
    <td style="padding:0 0 24px 16px;text-align:right;vertical-align:bottom;width:200px;">${todcCoverRight}</td>
  </tr></table>`;

  const meta = wMetaGrid([
    { label: 'Report Type', value: 'Custom Period' },
    { label: 'Pre Period', value: prePeriod || '[MM/DD/YYYY] – [MM/DD/YYYY]', placeholder: !prePeriod },
    { label: 'Post Period', value: postPeriod || '[MM/DD/YYYY] – [MM/DD/YYYY]', placeholder: !postPeriod },
    { label: 'Active Stores — DoorDash', labelHtml: wMetaLabel('Active Stores — DoorDash', logos), value: `${ddStores} stores` },
    { label: 'Active Stores — Uber Eats', labelHtml: wMetaLabel('Active Stores — Uber Eats', logos), value: `${ueStores} stores` },
    { label: 'Average Markup', value: '[XX.XX%]', placeholder: true },
    { label: 'Account Manager', value: accountManager || '[Name]', placeholder: !accountManager },
    { label: 'Operator', value: operatorName || '[Operator Name]', placeholder: !operatorName },
    { label: 'Date Prepared', value: today },
  ]);

  const overview = `${wSectionHeader('Overview', '01', W.accentBar)}
    ${wKpiStrip([
      { label: 'Sales Growth', value: cSales ? `${num(cSales.growthPct, 1)}%` : '—', ...salesKpi },
      { label: 'Order Growth', value: cOrders ? `${num(cOrders.growthPct, 1)}%` : '—', ...ordersKpi },
      {
        label: 'New Customers',
        value: cNewCust ? num(cNewCust.post) : '—',
        delta: cNewCust && cNewCust.growthPct != null
          ? `${Number(cNewCust.growthPct) < 0 ? '▼' : '▲'} ${num(Math.abs(Number(cNewCust.growthPct)), 1)}% Pre vs Post`
          : 'no data',
        deltaColor: cNewCust ? (Number(cNewCust.growthPct) < 0 ? W.negText : W.posText) : W.muted,
      },
      { label: 'Payout Lift / Store', value: payoutLiftPerStore != null ? `$${num(payoutLiftPerStore)}` : '—', ...payKpi },
      { label: 'Avg Markup', value: '—', delta: 'combined', deltaColor: W.muted },
    ].map(c => ({ label: c.label, value: c.value, delta: c.delta, deltaColor: c.deltaColor || c.color })))}
    ${wSub('Pre-TODC YoY Baseline (Sales)')}
    ${wDataTable(['Platform', 'Prior Year', 'Current Year', 'Δ ($)', 'Δ (%)'], wBaseline(summaryTables, logos))}`;

  const markups = `${wSectionHeader('Store Level Markups', '02', W.accentBar)}${wDataTable(['Store Name', 'Markup'], wMarkupRows(storeTables.combined || storeTables.dd || storeTables.ue || []))}`;

  const combined = `${wSectionHeader('Combined Performance', '03', W.accentBar)}
    ${wSub('Pre vs Post')}${wDataTable(PVP_METRIC_HEADERS, wMetricPvp(summaryTables.combined))}
    ${wSub('YoY: Post (Last Year) vs Post (Current)')}${wDataTable(YOY_METRIC_HEADERS, wMetricYoy(summaryTables.combined))}`;

  const platform = (key, label, accent, badge, logo, num2, withMarketing) => `${wBadge(label, logo, badge, logos, key, num2)}
    ${wSub('Pre vs Post')}${wDataTable(PVP_METRIC_HEADERS, wMetricPvp(summaryTables[key]), accent)}
    ${wSub('YoY')}${wDataTable(YOY_METRIC_HEADERS, wMetricYoy(summaryTables[key]), accent)}
    ${withMarketing ? `${wSub('Corporate vs TODC — Promos & Ads')}${wDataTable(['Campaign', 'Orders', 'Sales', 'Spend', 'ROAS', 'Cost / Order'], wMarketing(marketingTables), accent)}` : ''}`;

  const storeBlock = (key, label, accent, badge, logo, badgeColor, platformKey) => `
    ${badge ? wBadge(label, logo, badgeColor, logos, platformKey) : wSub(label)}
    ${wSub(`${label} — Pre vs Post`)}${wDataTable(STORE_PVP_HEADERS, wStorePvp(exportStoreTables[key], key, dominantPlatform), accent)}
    ${wSub(`${label} — YoY`)}${wDataTable(STORE_YOY_HEADERS, wStoreYoy(exportStoreTables[key], key, dominantPlatform), accent)}`;

  const stores = `${wSectionHeader('Store Level Analysis', '06', W.accentBar)}
    ${storeBlock('combined', 'Combined', null, false)}
    ${storeBlock('dd', 'DoorDash — Store Level', DD_ACCENT, true, 'DD', W.ddRed, 'dd')}
    ${storeBlock('ue', 'Uber Eats — Store Level', UE_ACCENT, true, 'UE', W.ueGreen, 'ue')}`;

  const daypart = (slot, label, accent, logo, badgeColor, platformKey) => slot ? `
    ${wBadge(label, logo, badgeColor, logos, platformKey)}
    ${wSub('Sales — Pre vs Post')}${wDataTable(SLOT_PVP_HEADERS, wSlotPvp(slot.salesPrePost), accent)}
    ${wSub('Sales — YoY')}${wDataTable(SLOT_YOY_HEADERS, wSlotYoy(slot.salesYoY), accent)}
    ${wSub('Payouts — Pre vs Post')}${wDataTable(SLOT_PVP_HEADERS, wSlotPvp(slot.payoutsPrePost), accent)}
    ${wSub('Payouts — YoY')}${wDataTable(SLOT_YOY_HEADERS, wSlotYoy(slot.payoutsYoY), accent)}` : '';

  const dayparts = `${wSectionHeader('Day Part Analysis', '07', W.accentBar)}
    ${daypart(ddSlot, 'DoorDash', DD_ACCENT, 'DD · Day Part', W.ddRed, 'dd')}
    ${daypart(ueSlot, 'Uber Eats', UE_ACCENT, 'UE · Day Part', W.ueGreen, 'ue')}`;

  const appendix = buildAppendixWordSection(data);
  const slotDefinitions = buildSlotDefinitionsWordSection();

  const footer = `<table cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;border-top:1px solid ${W.border};margin-top:24px"><tr>
    <td style="padding:14px 0 0;font-family:${W.mono};font-size:9px;color:${W.muted}">CONFIDENTIAL — The On Demand Company (TODC) · All rights reserved</td>
    <td style="padding:14px 0 0;text-align:right;font-family:${W.mono};font-size:9px;color:${W.muted}">todc.com · ${escapeHtml(operatorDisplay)} Partnership Report</td>
  </tr></table>`;

  const sections = [
    cover, meta, overview, markups, combined,
    platform('dd', 'DoorDash', DD_ACCENT, W.ddRed, 'DD · Platform Analytics', '04', true),
    platform('ue', 'Uber Eats', UE_ACCENT, W.ueGreen, 'UE · Platform Analytics', '05', false),
    stores, dayparts,
    ...(appendix ? [appendix] : []),
    slotDefinitions,
    footer,
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
 * @param {object} config useConfigStore state (period dates, exclusions, operatorName, accountManager)
 * @param {object} [opts] { variant: 'screen' | 'word' }
 *   - 'screen': light Super App theme with Chart.js charts (used for Print → PDF).
 *   - 'word': light, table-based, inline-styled build for Word / Google Docs fidelity.
 */
export function buildReportHtml(data, config, { variant = 'screen', logos = null } = {}) {
  if (variant === 'word') return buildWordReportHtml(data, config, logos);
  const fonts = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">';
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TODC Partnership Performance Report</title>
${fonts}
<style>${reportCss()}</style>
</head><body>
${buildReportBody(data, config, 'screen', logos)}
</body></html>`;
}

/* ── Output sinks ────────────────────────────────────────────────────────── */

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
export async function downloadReportDoc(data, config, baseName, logos = null) {
  const resolved = logos || await loadBrandLogosAsDataUri();
  const html = buildReportHtml(data, config, { variant: 'word', logos: resolved });
  downloadBlob('\uFEFF' + html, `${baseName}.doc`, 'application/msword');
}

/** Open the report in a new tab for Print → Save as PDF. */
export async function openReportForPdf(data, config) {
  const logos = await loadBrandLogosAsDataUri();
  const html = buildReportHtml(data, config, { variant: 'screen', logos });
  const pdfName = buildExportFilename(config, 'pdf', { ext: 'pdf' });
  const win = window.open('', '_blank');
  if (!win) return false;
  win.document.open();
  win.document.write(html);
  win.document.close();
  win.document.title = pdfName;
  return true;
}

async function pushReportToGoogleDoc(filename, html) {
  const targetUrl = resolveDocExportUrl(
    GOOGLE_DOC_EXPORT_URL,
    GOOGLE_SHEETS_EXPORT_URL,
    defaultExportDocUrl,
  );

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
  const docFilename = buildExportFilename(config, 'doc', { ext: 'doc' });
  const baseName = docFilename.replace(/\.doc$/i, '');
  const logos = await loadBrandLogosAsDataUri();
  await downloadReportDoc(data, config, baseName, logos);

  const wordHtml = buildReportHtml(data, config, { variant: 'word', logos });
  let googleDoc;
  try {
    googleDoc = await pushReportToGoogleDoc(baseName, wordHtml);
  } catch (err) {
    googleDoc = { error: err.message || String(err) };
  }
  return {
    docFilename,
    pdfFilename: buildExportFilename(config, 'pdf', { ext: 'pdf' }),
    googleDoc,
    docUrl: extractDocUrl(googleDoc),
  };
}
