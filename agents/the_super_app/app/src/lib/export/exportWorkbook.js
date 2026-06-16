import * as XLSX from 'xlsx';
import { format, subYears } from 'date-fns';
import { buildSlotAnalysis, SLOT_METRIC_TABLES, getSlotTimeRange, SLOT_EXPORT_HEADERS_PVP, SLOT_EXPORT_HEADERS_YOY } from '../engine/slots';
import { buildSlotSalesOrderAnalysis, slotSalesOrderExportHeaders, slotSalesOrderExportRow, dashPassExportHeaders, dashPassExportRow, orderVolumeExportHeaders, orderVolumeExportRow } from '../engine/slotSalesOrder';
import { buildDdRegister, buildUeRegister, registerRowToExport, DD_REGISTER_COLUMNS, UE_REGISTER_COLUMNS } from '../engine/register';
import { normalizeDdSalesByOrder } from '../parsers/ddSalesByOrder';
import { normalizeUeOrdersForSlotView } from '../parsers/ueOrderSlots';
import { buildBucketAnalysis, buildOrderOriginMix } from '../engine/buckets';
import { buildOrderOriginAov, buildPayoutBridgePrePost, buildRevenueGrowthDrivers } from '../engine/diagnostics';
import { STORE_METRIC_SPECS, storeSpecsForPlatform } from '../engine/storeTableSpecs';
import { DATA_PLATFORM_SECTIONS, PLATFORM_SECTIONS } from '../platforms';
import { getStarAndDecliningStores, getAllStoresDailyExtremes } from '../engine/diagnostics';
import { growthPct, round, safeDivide } from '../utils/safeMath';
import { xf, exportByKind, exportSummaryMetric, exportStoreSpecValue } from '../utils/formatters';
import { parseDate, getLastYearDates, isInRange, formatCompactDateRange } from '../utils/dateUtils';
import {
  pivotOneWaySum,
  pickProductColumn,
  pickMetricColumn,
  pickProductMixQtyColumn,
  pickErrorChargeColumn,
} from '../utils/opsProductPivot';
const DATE_NAME_RE = /(^|[^a-z])date([^a-z]|$)|order\s*date|business\s*date|^day$/i;

const METRIC_LABELS = {
  sales: 'Sales',
  payouts: 'Payouts',
  orders: 'Orders',
  profitability: 'Profitability',
  aov: 'Average Check',
};

import { resolveSheetsExportUrl } from './exportApi.js';
import { buildExportFilename } from './exportFilename.js';
import { buildLegacyExportSheets } from './legacyExportSheets.js';
import {
  buildAlignedExportStoreTables,
  combinedExportStoreName,
  EXPORT_NA,
  EXPORT_STORE_ID_HEADERS,
  exportStoreIdCells,
  exportStoreIdHeaders,
  exportStoreIdRowCells,
  exportStoreName,
} from './storeExportLayout.js';
import { buildDdStoreIdToMerchantMap } from '../utils/storeCatalog';
import { ddMerchantStoreId } from '../utils/storeDisplay';
import { withSheetSummary } from './exportSheetSummaries.js';
import {
  resolveMarketingTables,
  marketingImpactExportRows,
  campaignImpactExportRows,
  marketingCampaignSlices,
  buildCampaignHighlights,
  MARKETING_IMPACT_HEADERS,
  CAMPAIGN_IMPACT_HEADERS,
} from './marketingExport.js';
import { appendOperationsExportSections } from './operationsExport.js';

const GOOGLE_SHEETS_EXPORT_URL = import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL;

/** Same-origin export API (RalphAI FastAPI; /api is proxied in dev). */
function defaultExportUrl() {
  if (typeof window === 'undefined') return null;
  return `${window.location.origin}/api/export`;
}

function cleanSheetName(name) {
  return name.replace(/[\][:\\/?*]/g, '').slice(0, 31);
}

function isPresent(rows) {
  return Array.isArray(rows) && rows.length > 0;
}

function addSection(rows, title, headers, dataRows) {
  if (!isPresent(dataRows)) return;
  if (rows.length) rows.push([]);
  rows.push([title]);
  rows.push(headers);
  rows.push(...dataRows);
}

function addBlock(rows, title, dataRows) {
  if (!isPresent(dataRows)) return;
  if (rows.length) rows.push([]);
  rows.push([title]);
  rows.push(...dataRows);
}

function appendSheet(wb, sheetDefs, name, rows) {
  if (!rows.length) return;
  const sheetName = cleanSheetName(name);
  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws['!cols'] = estimateColumnWidths(rows);
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  sheetDefs.push({ name: sheetName, rows });
}

function appendReportSheet(wb, sheetDefs, name, rows, data, config) {
  const body = rows.length ? rows : [[`No ${name.toLowerCase()} report data available for this export.`]];
  const withSummary = data && config ? withSheetSummary(name, body, data, config) : body;
  appendSheet(wb, sheetDefs, name, withSummary);
}

function estimateColumnWidths(rows) {
  const widths = [];
  for (const row of rows) {
    row.forEach((value, index) => {
      const len = String(value ?? '').length;
      widths[index] = Math.min(Math.max(widths[index] || 10, len + 2), 42);
    });
  }
  return widths.map(wch => ({ wch }));
}

function summaryPrePostRows(summary) {
  return (summary || []).map((row) => {
    const m = row.metric;
    const val = (v) => exportSummaryMetric(v, m);
    return [
      METRIC_LABELS[m] || m,
      val(row.pre),
      val(row.post),
      val(row.prevspost),
      val(row.lyPrevspost),
      xf.deltaPct(row.growthPct),
      xf.deltaPct(row.lyGrowthPct),
    ];
  });
}

function summaryYoyRows(summary) {
  return (summary || []).map((row) => {
    const m = row.metric;
    const val = (v) => exportSummaryMetric(v, m);
    return [
      METRIC_LABELS[m] || m,
      val(row.postLY),
      val(row.post),
      val(row.yoy),
      xf.deltaPct(row.yoyPct),
    ];
  });
}

function summaryRowByMetric(summary, metric) {
  return (summary || []).find((r) => r.metric === metric) || {};
}

function platformHasSummary(summary) {
  const sales = summaryRowByMetric(summary, 'sales');
  return (sales.pre || 0) !== 0 || (sales.post || 0) !== 0 || (sales.postLY || 0) !== 0;
}

function periodRangeLabel(start, end) {
  return formatCompactDateRange(start, end) || '—';
}

function growthHeadlineRow(label, summary) {
  const g = (m) => summaryRowByMetric(summary, m);
  return [
    label,
    xf.deltaPct(g('sales').growthPct),
    xf.deltaPct(g('payouts').growthPct),
    xf.deltaPct(g('orders').growthPct),
    xf.deltaPct(g('profitability').growthPct),
    xf.deltaPct(g('aov').growthPct),
    xf.deltaPct(g('sales').yoyPct),
    xf.deltaPct(g('payouts').yoyPct),
    xf.deltaPct(g('orders').yoyPct),
    xf.deltaPct(g('profitability').yoyPct),
    xf.deltaPct(g('aov').yoyPct),
  ];
}

const GROWTH_HEADLINE_HEADERS = [
  'Platform',
  'Sales PvP%',
  'Payouts PvP%',
  'Orders PvP%',
  'Profitability PvP%',
  'AOV PvP%',
  'Sales YoY%',
  'Payouts YoY%',
  'Orders YoY%',
  'Profitability YoY%',
  'AOV YoY%',
];

function buildSummaryDetailSections(summaryTables) {
  const summaryRows = [];
  for (const { key, label } of PLATFORM_SECTIONS) {
    const summary = summaryTables?.[key] || [];
    if (!platformHasSummary(summary)) continue;
    addSection(
      summaryRows,
      `${label} — Pre vs Post`,
      ['Metric', 'Pre', 'Post', 'Pre vs Post', 'LY Pre vs Post', 'Growth%', 'LY Growth%'],
      summaryPrePostRows(summary),
    );
    addSection(
      summaryRows,
      `${label} — Year over Year`,
      ['Metric', 'LY Post', 'Post', 'YoY', 'YoY%'],
      summaryYoyRows(summary),
    );
  }
  return summaryRows;
}

function buildSummarySheetRows(data, config) {
  const rows = [];
  const operator = (config.operatorName || '').trim();
  if (operator) {
    addBlock(rows, 'Report', [['Operator', operator]]);
  }

  addSection(
    rows,
    'Analysis periods',
    ['Platform', 'Pre period', 'Post period'],
    [
      [
        'Combined',
        periodRangeLabel(config.ddPreStart || config.uePreStart, config.ddPreEnd || config.uePreEnd),
        periodRangeLabel(config.ddPostStart || config.uePostStart, config.ddPostEnd || config.uePostEnd),
      ],
      ['DoorDash', periodRangeLabel(config.ddPreStart, config.ddPreEnd), periodRangeLabel(config.ddPostStart, config.ddPostEnd)],
      ['Uber Eats', periodRangeLabel(config.uePreStart, config.uePreEnd), periodRangeLabel(config.uePostStart, config.uePostEnd)],
    ],
  );

  const headlineData = [];
  for (const { key, label } of PLATFORM_SECTIONS) {
    const summary = data.summaryTables?.[key] || [];
    if (!platformHasSummary(summary)) continue;
    headlineData.push(growthHeadlineRow(label, summary));
  }
  if (headlineData.length) {
    addSection(rows, 'Growth summary (Pre vs Post & YoY %)', GROWTH_HEADLINE_HEADERS, headlineData);
  }

  const detail = buildSummaryDetailSections(data.summaryTables);
  if (detail.length) {
    if (rows.length) rows.push([]);
    rows.push(['Detailed summary tables']);
    rows.push(...detail);
  }
  return rows;
}

function storeIdNameCells(row, platform, dominantPlatform, ddToUeStoreMap = {}, ddStoreIdToMerchant = null) {
  return [
    ...exportStoreIdRowCells(row, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant),
    platform === 'combined'
      ? combinedExportStoreName(row, dominantPlatform)
      : exportStoreName(row),
  ];
}

function storeRows(stores, platform, dominantPlatform, ddToUeStoreMap = {}, ddStoreIdToMerchant = null) {
  return (stores || []).map((row) => [
    ...storeIdNameCells(row, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant),
    row._isNa ? EXPORT_NA : xf.usd(row.pre_sales),
    row._isNa ? EXPORT_NA : xf.usd(row.post_sales),
    row._isNa ? EXPORT_NA : xf.usd(row.sales_prevspost),
    row._isNa ? EXPORT_NA : xf.deltaPct(row.sales_growth_pct),
    row._isNa ? EXPORT_NA : xf.usd(row.postLY_sales),
    row._isNa ? EXPORT_NA : xf.usd(row.sales_yoy),
    row._isNa ? EXPORT_NA : xf.deltaPct(row.sales_yoy_pct),
    row._isNa ? EXPORT_NA : xf.usd(row.pre_payouts),
    row._isNa ? EXPORT_NA : xf.usd(row.post_payouts),
    row._isNa ? EXPORT_NA : xf.deltaPct(row.payouts_growth_pct),
    row._isNa ? EXPORT_NA : xf.int(row.pre_orders),
    row._isNa ? EXPORT_NA : xf.int(row.post_orders),
    row._isNa ? EXPORT_NA : xf.deltaPct(row.orders_growth_pct),
    row._isNa ? EXPORT_NA : xf.usd2(row.post_aov),
    row._isNa ? EXPORT_NA : xf.pct(row.post_profitability),
  ]);
}

function storeMetricPvpRows(stores, spec, platform, dominantPlatform, ddToUeStoreMap = {}, ddStoreIdToMerchant = null) {
  return (stores || []).map((row) => [
    ...storeIdNameCells(row, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.preKey]),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.postKey]),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.deltaKey]),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.lyDeltaKey]),
    row._isNa ? EXPORT_NA : xf.deltaPct(row[spec.deltaPctKey]),
    row._isNa ? EXPORT_NA : xf.deltaPct(row[spec.lyDeltaPctKey]),
  ]);
}

function storeMetricYoyRows(stores, spec, platform, dominantPlatform, ddToUeStoreMap = {}, ddStoreIdToMerchant = null) {
  return (stores || []).map((row) => [
    ...storeIdNameCells(row, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.postLyKey]),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.postKey]),
    row._isNa ? EXPORT_NA : exportStoreSpecValue(spec, row[spec.yoyDeltaKey]),
    row._isNa ? EXPORT_NA : xf.deltaPct(row[spec.yoyPctKey]),
  ]);
}

function buildStoresExportRows(data, config) {
  const rows = [];
  const ddToUe = config?.ddToUeStoreMap || {};
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const aligned = buildAlignedExportStoreTables(data.storeTables, ddToUe);
  const tableMap = { combined: aligned.combined, dd: aligned.dd, ue: aligned.ue };
  const metricHeadersPvp = ['Pre', 'Post', 'Pre vs Post Δ', 'LY Pre vs Post Δ', 'Pre vs Post %', 'LY Growth%'];
  const metricHeadersYoy = ['LY Post', 'Post', 'YoY Δ', 'YoY %'];

  for (const { key, label } of PLATFORM_SECTIONS) {
    const stores = tableMap[key] || [];
    if (!stores.length) continue;
    const pvpHeaders = [...exportStoreIdHeaders(key), 'Store Name', ...metricHeadersPvp];
    const yoyHeaders = [...exportStoreIdHeaders(key), 'Store Name', ...metricHeadersYoy];
    for (const spec of storeSpecsForPlatform(key)) {
      addSection(
        rows,
        `${label} — ${spec.label} (Pre vs Post)`,
        pvpHeaders,
        storeMetricPvpRows(stores, spec, key, aligned.dominantPlatform, ddToUe, ddStoreIdToMerchant),
      );
      addSection(
        rows,
        `${label} — ${spec.label} (YoY)`,
        yoyHeaders,
        storeMetricYoyRows(stores, spec, key, aligned.dominantPlatform, ddToUe, ddStoreIdToMerchant),
      );
    }
  }
  return rows;
}

function buildOverviewExportRows(data, config) {
  const rows = [];
  const stores = data.storeTables?.combined || [];
  const ddToUe = config?.ddToUeStoreMap || {};
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const aligned = buildAlignedExportStoreTables(data.storeTables, ddToUe);
  const spotlight = getStarAndDecliningStores(stores);
  const spotlightRow = (s) => {
    const [ddMerchantStoreId, ueStoreId] = exportStoreIdCells(
      s, 'combined', aligned.dominantPlatform, ddToUe, ddStoreIdToMerchant,
    );
    return [ddMerchantStoreId, ueStoreId, xf.deltaPct(s.sales_growth_pct)];
  };
  addSection(
    rows,
    'Store Spotlight — Star stores',
    [...EXPORT_STORE_ID_HEADERS, 'Sales Growth%'],
    (spotlight.stars || []).map(spotlightRow),
  );
  addSection(
    rows,
    'Store Spotlight — Declining stores',
    [...EXPORT_STORE_ID_HEADERS, 'Sales Growth%'],
    (spotlight.declining || []).map(spotlightRow),
  );

  const preExtremes = getAllStoresDailyExtremes(
    data.ddFinancial,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddExcludedDates || [],
  );
  const postExtremes = getAllStoresDailyExtremes(
    data.ddFinancial,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates || [],
  );
  const dayRow = (d) => [d.date ? format(d.date, 'yyyy-MM-dd') : d.dateKey, d.sales ?? 0];
  addSection(rows, 'Date Spotlight — Pre top days', ['Date', 'Sales'], (preExtremes.top || []).map(dayRow));
  addSection(rows, 'Date Spotlight — Pre low days', ['Date', 'Sales'], (preExtremes.low || []).map(dayRow));
  addSection(rows, 'Date Spotlight — Post top days', ['Date', 'Sales'], (postExtremes.top || []).map(dayRow));
  addSection(rows, 'Date Spotlight — Post low days', ['Date', 'Sales'], (postExtremes.low || []).map(dayRow));
  return rows;
}

function metricDecimals(metricKey) {
  if (metricKey === 'orders') return 0;
  if (['promoAov', 'cpo', 'checkAfterPromo', 'roas'].includes(metricKey)) return 2;
  return 0;
}

function slotRows(rows, valueKind) {
  const val = (v) => exportByKind(valueKind, v);
  return (rows || []).map((row) => [
    row.slot,
    getSlotTimeRange(row.slot),
    val(row.pre),
    val(row.post),
    val(row.prevspost),
    xf.deltaPct(row.growthPct),
    val(row.lyPrevspost),
    xf.deltaPct(row.lyGrowthPct),
  ]);
}

function appendSlotOrderAnalysisBlock(targetRows, blockTitle, salesOrderAnalysis) {
  if (!salesOrderAnalysis) return;
  const rich = salesOrderAnalysis.hasCustomerType || salesOrderAnalysis.hasItemCount;
  const soHeaders = rich ? slotSalesOrderExportHeaders() : orderVolumeExportHeaders();
  const soRow = rich ? slotSalesOrderExportRow : orderVolumeExportRow;
  const soRows = [];
  const addBreakdown = (prefix, preKey, postKey, labelFn) => {
    addSection(
      soRows,
      `${prefix} — Pre`,
      soHeaders,
      (salesOrderAnalysis.pre?.[preKey] || []).map((r) => soRow(labelFn(r), r)),
    );
    addSection(
      soRows,
      `${prefix} — Post`,
      soHeaders,
      (salesOrderAnalysis.post?.[postKey] || []).map((r) => soRow(labelFn(r), r)),
    );
  };
  addBreakdown('By slot', 'slot', 'slot', (r) => r.slot);
  addBreakdown('By day', 'day', 'day', (r) => r.day);
  addBreakdown('By day × slot', 'daySlot', 'daySlot', (r) => r.label);
  addBlock(targetRows, blockTitle, soRows);

  if (salesOrderAnalysis.hasDashPass) {
    const dpHeaders = dashPassExportHeaders();
    const dpRows = [];
    const addDashPassSections = (prefix, preKey, postKey, labelFn) => {
      addSection(
        dpRows,
        `${prefix} — Pre`,
        dpHeaders,
        (salesOrderAnalysis.pre?.[preKey] || []).map((r) => dashPassExportRow(labelFn(r), r)),
      );
      addSection(
        dpRows,
        `${prefix} — Post`,
        dpHeaders,
        (salesOrderAnalysis.post?.[postKey] || []).map((r) => dashPassExportRow(labelFn(r), r)),
      );
    };
    addDashPassSections('By slot', 'slot', 'slot', (r) => r.slot);
    addDashPassSections('By day', 'day', 'day', (r) => r.day);
    addDashPassSections('By day × slot', 'daySlot', 'daySlot', (r) => r.label);
    addBlock(targetRows, `${blockTitle} — DashPass mix`, dpRows);
  }
}

function buildPlatformSlotAnalysis(data, config, platform) {
  const rawData = platform === 'ue' ? data.ueFinancial : data.ddFinancial;
  const prefix = platform === 'ue' ? 'ue' : 'dd';
  if (!rawData?.length) return null;

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
    excludedStores: config[`${prefix}ExcludedStores`] || [],
    platform,
  });
}

function buildBucketSections(data, config) {
  const out = {};
  if (data.ddFinancial && config.ddPreStart && config.ddPostStart) {
    out.dd = {
      buckets: buildBucketAnalysis(data.ddFinancial, {
        preStart: config.ddPreStart,
        preEnd: config.ddPreEnd,
        postStart: config.ddPostStart,
        postEnd: config.ddPostEnd,
        excludedDates: config.ddExcludedDates || [],
        platform: 'dd',
      }),
      mix: buildOrderOriginMix(data.ddFinancial, config.ddPostStart, config.ddPostEnd, config.ddExcludedDates || [], 'dd'),
      mixPre: config.ddPreStart && config.ddPreEnd
        ? buildOrderOriginMix(data.ddFinancial, config.ddPreStart, config.ddPreEnd, config.ddExcludedDates || [], 'dd')
        : null,
    };
  }
  if (data.ueFinancial && config.uePreStart && config.uePostStart) {
    out.ue = {
      buckets: buildBucketAnalysis(data.ueFinancial, {
        preStart: config.uePreStart,
        preEnd: config.uePreEnd,
        postStart: config.uePostStart,
        postEnd: config.uePostEnd,
        excludedDates: config.ueExcludedDates || [],
        platform: 'ue',
      }),
      mix: buildOrderOriginMix(data.ueFinancial, config.uePostStart, config.uePostEnd, config.ueExcludedDates || [], 'ue'),
      mixPre: config.uePreStart && config.uePreEnd
        ? buildOrderOriginMix(data.ueFinancial, config.uePreStart, config.uePreEnd, config.ueExcludedDates || [], 'ue')
        : null,
    };
  }
  return Object.keys(out).length ? out : null;
}

function buildMixChangeRows(mixPre, mixPost) {
  return (mixPost || []).map((pm) => {
    const prem = (mixPre || []).find((x) => x.id === pm.id) || { value: 0 };
    const delta = Math.round(((pm.value || 0) - (prem.value || 0)) * 10) / 10;
    return [
      pm.label,
      xf.pct(prem.value),
      xf.pct(pm.value),
      xf.pp(delta),
    ];
  });
}

function objectColumns(rows) {
  return rows?.[0] ? Object.keys(rows[0]) : [];
}

function buildOperationsExportRows(data) {
  const rows = [];
  appendOperationsExportSections(
    (title, headers, dataRows) => addSection(rows, title, headers, dataRows),
    (title, dataRows) => addBlock(rows, title, dataRows),
    data,
  );
  return rows;
}

function toNum(v) {
  if (v == null) return 0;
  const n = Number(String(v).replace(/[$,]/g, ''));
  return Number.isFinite(n) ? n : 0;
}

function topCount(n, pct = 0.05) {
  if (!n) return 0;
  return Math.max(1, Math.ceil(n * pct));
}

function detectDateColumn(columns, rows) {
  const sample = (rows || []).slice(0, 25);
  const named = columns.find((c) => DATE_NAME_RE.test(String(c)));
  if (named && sample.some((r) => parseDate(r[named]))) return named;
  for (const c of columns) {
    let hits = 0;
    let n = 0;
    for (const r of sample) {
      const v = r[c];
      if (v == null || v === '') continue;
      n += 1;
      if (parseDate(v)) hits += 1;
    }
    if (n >= 5 && hits / n > 0.85) return c;
  }
  return null;
}

function buildProductPeriodData(ddProductMix, columns, config) {
  const productCol = pickProductColumn(columns);
  const valueCol = pickMetricColumn(ddProductMix, columns, [productCol].filter(Boolean))
    || columns.find((c) => /sales|revenue|amount|payout/i.test(String(c)))
    || null;
  const dateCol = detectDateColumn(columns, ddProductMix);
  if (!dateCol || !productCol || !valueCol) return [];
  const { ddPreStart, ddPreEnd, ddPostStart, ddPostEnd } = config;
  if (!ddPostStart || !ddPostEnd) return [];
  const ly = getLastYearDates(ddPostStart, ddPostEnd);
  const lyPre = ddPreStart && ddPreEnd ? getLastYearDates(ddPreStart, ddPreEnd) : null;

  const map = new Map();
  for (const r of ddProductMix || []) {
    const d = parseDate(r[dateCol]);
    if (!d) continue;
    const name = String(r[productCol] ?? '').trim();
    if (!name) continue;
    const sales = toNum(r[valueCol]);
    const cur = map.get(name) || { product: name, pre: 0, post: 0, preLY: 0, postLY: 0 };
    if (ddPreStart && ddPreEnd && isInRange(d, ddPreStart, ddPreEnd)) cur.pre += sales;
    if (isInRange(d, ddPostStart, ddPostEnd)) cur.post += sales;
    if (lyPre && isInRange(d, lyPre.start, lyPre.end)) cur.preLY += sales;
    if (isInRange(d, ly.start, ly.end)) cur.postLY += sales;
    map.set(name, cur);
  }
  return [...map.values()]
    .map((p) => ({
      ...p,
      pre: round(p.pre),
      post: round(p.post),
      postLY: round(p.postLY),
      growthPct: round(growthPct(p.pre, p.post), 1),
    }))
    .sort((a, b) => b.post - a.post);
}

function buildProductHighlightRows(ddProductMix, columns) {
  const productCol = pickProductColumn(columns);
  const salesCol = columns.find((c) => /sales|revenue|amount|payout/i.test(String(c))) || null;
  const qtyCol = pickProductMixQtyColumn(columns);
  const errorCol = pickErrorChargeColumn(columns);
  if (!productCol || !salesCol) return { topSelling: [], topAov: [], topErrorCharge: [], hasAov: false, hasErrorCharge: false };

  const map = new Map();
  for (const r of ddProductMix || []) {
    const name = String(r[productCol] ?? '').trim();
    if (!name) continue;
    const cur = map.get(name) || { product: name, sales: 0, qty: 0, errorCharges: 0 };
    cur.sales += toNum(r[salesCol]);
    if (qtyCol) cur.qty += toNum(r[qtyCol]);
    if (errorCol) cur.errorCharges += toNum(r[errorCol]);
    map.set(name, cur);
  }
  const agg = [...map.values()].map((p) => ({
    ...p,
    aov: p.qty > 0 ? p.sales / p.qty : null,
    errorChargePct: p.sales > 0 ? round(safeDivide(p.errorCharges, p.sales) * 100, 2) : null,
  }));

  const topSelling = [...agg].sort((a, b) => b.sales - a.sales).slice(0, topCount(agg.length));
  const withAov = agg.filter((p) => p.aov != null);
  const topAov = [...withAov].sort((a, b) => b.aov - a.aov).slice(0, topCount(withAov.length));
  const withError = agg.filter((p) => p.sales > 0 && p.errorChargePct != null && p.errorCharges > 0);
  const topErrorCharge = [...withError].sort((a, b) => b.errorChargePct - a.errorChargePct).slice(0, topCount(withError.length));

  return {
    topSelling: topSelling.map((p) => [p.product, round(p.sales), p.aov != null ? round(p.aov, 2) : '']),
    topAov: topAov.map((p) => [p.product, round(p.aov, 2), round(p.sales)]),
    topErrorCharge: topErrorCharge.map((p) => [
      p.product,
      round(p.errorChargePct, 2),
      round(p.errorCharges),
      round(p.sales),
    ]),
    hasAov: withAov.length > 0,
    hasErrorCharge: withError.length > 0,
  };
}

function sliceProductPct(n, pct = 0.10) {
  if (!n) return 0;
  return Math.max(1, Math.ceil(n * pct));
}

function splitProductGrowthRows(periodRows) {
  const eligible = periodRows.filter((p) => p.pre > 0);
  const n = sliceProductPct(eligible.length);
  const top = [...eligible].sort((a, b) => b.growthPct - a.growthPct).slice(0, n);
  const declining = [...eligible].sort((a, b) => a.growthPct - b.growthPct).slice(0, n);
  const toRow = (p) => [p.product, xf.usd(p.pre), xf.usd(p.post), xf.deltaPct(p.growthPct)];
  return {
    top: top.map(toRow),
    declining: declining.map(toRow),
  };
}

function buildProductMixExportRows(data, config) {
  const rows = [];
  const ddProductMix = data.ddProductMix || [];
  const columns = objectColumns(ddProductMix);
  const productCol = pickProductColumn(columns);
  const valueCol = pickMetricColumn(ddProductMix, columns, [productCol].filter(Boolean))
    || columns.find((c) => /sales|revenue|amount|payout/i.test(String(c)))
    || null;

  const highlights = buildProductHighlightRows(ddProductMix, columns);
  if (highlights.topSelling.length) {
    const headers = highlights.hasAov
      ? ['Product', 'Gross sales', 'AOV']
      : ['Product', 'Gross sales'];
    addSection(rows, 'Top 5% — highest selling', headers, highlights.topSelling);
  }
  if (highlights.topAov.length) {
    addSection(rows, 'Top 5% — highest AOV', ['Product', 'AOV', 'Gross sales'], highlights.topAov);
  }
  if (highlights.topErrorCharge.length) {
    addSection(
      rows,
      'Top 5% — highest error charge %',
      ['Product', 'Error charge %', 'Error charges', 'Gross sales'],
      highlights.topErrorCharge,
    );
  }

  const periodData = buildProductPeriodData(ddProductMix, columns, config);
  if (periodData.length) {
    const movers = splitProductGrowthRows(periodData);
    if (movers.top.length) {
      addSection(rows, 'Top 10% — highest growth', ['Product', 'Pre', 'Post', 'Growth %'], movers.top);
    }
    if (movers.declining.length) {
      addSection(rows, 'Declining 10% — largest drops', ['Product', 'Pre', 'Post', 'Growth %'], movers.declining);
    }
  } else if (valueCol && productCol) {
    const byProduct = pivotOneWaySum(ddProductMix, productCol, valueCol);
    addSection(rows, `By product (total ${valueCol})`, ['Product', 'Total'], byProduct.keys.map((k, i) => [k, byProduct.values[i]]));
  }
  return rows;
}

function dateValue(date) {
  if (!date) return '';
  if (date instanceof Date) return format(date, 'yyyy-MM-dd');
  return String(date).slice(0, 10);
}

function withinDate(date, start, end) {
  if (!date || !start || !end) return false;
  const d = new Date(`${dateValue(date)}T00:00:00`);
  return d >= start && d <= end;
}

function filterWindow(records, start, end, excludedDates = []) {
  if (!isPresent(records)) return [];
  const excluded = new Set(excludedDates.map(dateValue));
  return records.filter(row => {
    const date = dateValue(row.date);
    return withinDate(date, start, end) && !excluded.has(date);
  });
}

function buildDailyRows(records, platform, config, ddStoreIdToMerchant = null) {
  if (!isPresent(records)) return [];
  const prefix = platform === 'ue' ? 'ue' : 'dd';
  const start = config[`${prefix}PreStart`];
  const end = config[`${prefix}PostEnd`];
  const ddToUe = config?.ddToUeStoreMap || {};
  const grouped = new Map();

  for (const row of filterWindow(records, start, end, config[`${prefix}ExcludedDates`] || [])) {
    const date = dateValue(row.date);
    const rawStoreId = String(row.storeId ?? '');
    const merchantStoreId = platform === 'dd'
      ? (ddMerchantStoreId(row, ddStoreIdToMerchant) || rawStoreId)
      : rawStoreId;
    const key = `${date}|${merchantStoreId}`;
    const current = grouped.get(key) || {
      platform: platform === 'ue' ? 'UberEats' : 'DoorDash',
      date,
      storeId: merchantStoreId,
      merchantStoreId: platform === 'dd' ? merchantStoreId : '',
      sales: 0,
      payouts: 0,
      orders: new Set(),
    };

    current.sales += platform === 'ue' ? Number(row.sales || 0) : Number(row.subtotal || 0);
    current.payouts += platform === 'ue' ? Number(row.totalPayout || 0) : Number(row.netTotal || 0);
    if (row.orderId) current.orders.add(row.orderId);
    grouped.set(key, current);
  }

  return [...grouped.values()]
    .sort((a, b) => a.date.localeCompare(b.date) || a.storeId.localeCompare(b.storeId))
    .map((row) => {
      const pseudoRow = platform === 'dd'
        ? { storeId: row.merchantStoreId || row.storeId, merchantStoreId: row.merchantStoreId, _isNa: false }
        : { storeId: row.storeId, _isNa: false };
      const idCells = exportStoreIdRowCells(
        pseudoRow,
        platform,
        platform === 'ue' ? 'ue' : 'dd',
        ddToUe,
        ddStoreIdToMerchant,
      );
      return [row.platform, row.date, ...idCells, row.sales, row.payouts, row.orders.size];
    });
}

function metricValue(row, platform, metric) {
  if (metric === 'Sales') return platform === 'ue' ? Number(row.sales || 0) : Number(row.subtotal || 0);
  if (metric === 'Payouts') return platform === 'ue' ? Number(row.totalPayout || 0) : Number(row.netTotal || 0);
  return row.orderId;
}

function buildPeriodPivot(records, platform, metric, start, end, excludedDates = [], ddStoreIdToMerchant = null) {
  const rows = filterWindow(records, start, end, excludedDates);
  const dates = new Set();
  const stores = new Set();
  const grouped = new Map();

  const pivotStoreKey = (row) => {
    if (platform === 'ue') return String(row.storeId ?? '');
    return ddMerchantStoreId(row, ddStoreIdToMerchant) || String(row.storeId ?? '');
  };

  for (const row of rows) {
    const date = dateValue(row.date);
    const storeId = pivotStoreKey(row);
    if (!date || !storeId) continue;
    dates.add(date);
    stores.add(storeId);
    const key = `${date}|${storeId}`;
    if (metric === 'Orders') {
      if (!grouped.has(key)) grouped.set(key, new Set());
      const orderId = metricValue(row, platform, metric);
      if (orderId) grouped.get(key).add(orderId);
    } else {
      grouped.set(key, (grouped.get(key) || 0) + metricValue(row, platform, metric));
    }
  }

  const sortedDates = [...dates].sort();
  const sortedStores = [...stores].sort();
  if (!sortedDates.length || !sortedStores.length) return [];

  const pivot = [['Date', ...sortedStores]];
  for (const date of sortedDates) {
    pivot.push([
      date,
      ...sortedStores.map(storeId => {
        const value = grouped.get(`${date}|${storeId}`);
        return metric === 'Orders' ? (value?.size || 0) : (value || 0);
      }),
    ]);
  }
  return pivot;
}

function addTotalsToPivot(pivot) {
  if (!isPresent(pivot) || pivot.length < 2) return pivot || [];
  const headers = [...pivot[0], 'Total', 'Avg-Value'];
  const dataRows = pivot.slice(1);
  const withTotals = dataRows.map(row => {
    const total = row.slice(1).reduce((sum, value) => sum + Number(value || 0), 0);
    return [...row, total, 0];
  });
  const dailyAvg = withTotals.length
    ? withTotals.reduce((sum, row) => sum + Number(row[row.length - 2] || 0), 0) / withTotals.length
    : 0;
  const adjustedRows = withTotals.map(row => {
    const next = [...row];
    next[next.length - 1] = Number((dailyAvg - Number(next[next.length - 2] || 0)).toFixed(1));
    return next;
  });
  const totalRow = ['Total'];
  for (let col = 1; col < headers.length - 2; col += 1) {
    totalRow[col] = adjustedRows.reduce((sum, row) => sum + Number(row[col] || 0), 0);
  }
  totalRow[headers.length - 2] = adjustedRows.reduce((sum, row) => sum + Number(row[headers.length - 2] || 0), 0);
  totalRow[headers.length - 1] = '';
  return [headers, ...adjustedRows, totalRow];
}

function stitchBlocks(blocks, gapCols = 1) {
  const prepared = blocks
    .filter(block => isPresent(block.rows))
    .map(block => {
      const rows = addTotalsToPivot(block.rows);
      return {
        width: rows[0]?.length || 1,
        rows: [[block.title], ...rows],
      };
    });
  if (!prepared.length) return [];

  const height = Math.max(...prepared.map(block => block.rows.length));
  const output = Array.from({ length: height }, () => []);

  for (const block of prepared) {
    for (let rowIndex = 0; rowIndex < height; rowIndex += 1) {
      const source = block.rows[rowIndex] || [];
      const padded = Array.from({ length: block.width }, (_, index) => source[index] ?? '');
      output[rowIndex].push(...padded, ...Array(gapCols).fill(''));
    }
  }

  return output.map(row => {
    let end = row.length;
    while (end > 0 && row[end - 1] === '') end -= 1;
    return row.slice(0, end);
  });
}

function addApp2DatePivotSections(rows, data, config) {
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const definitions = [
    { platform: 'dd', label: 'DoorDash', records: data.ddFinancial, excludedDates: config.ddExcludedDates || [], ddStoreIdToMerchant },
    { platform: 'ue', label: 'UberEats', records: data.ueFinancial, excludedDates: config.ueExcludedDates || [], ddStoreIdToMerchant: null },
  ];

  for (const def of definitions) {
    if (!isPresent(def.records)) continue;
    const prefix = def.platform === 'ue' ? 'ue' : 'dd';
    const preStart = config[`${prefix}PreStart`];
    const preEnd = config[`${prefix}PreEnd`];
    const postStart = config[`${prefix}PostStart`];
    const postEnd = config[`${prefix}PostEnd`];
    if (!preStart || !preEnd || !postStart || !postEnd) continue;

    const currentYear = format(postStart, 'yy');
    const lastYear = format(subYears(postStart, 1), 'yy');
    const lyPreStart = subYears(preStart, 1);
    const lyPreEnd = subYears(preEnd, 1);
    const lyPostStart = subYears(postStart, 1);
    const lyPostEnd = subYears(postEnd, 1);

    for (const metric of ['Sales', 'Payouts', 'Orders']) {
      const pivotRows = stitchBlocks([
        { title: `Pre ${currentYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, preStart, preEnd, def.excludedDates, def.ddStoreIdToMerchant) },
        { title: `Post ${currentYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, postStart, postEnd, def.excludedDates, def.ddStoreIdToMerchant) },
        { title: `Pre ${lastYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, lyPreStart, lyPreEnd, def.excludedDates, def.ddStoreIdToMerchant) },
        { title: `Post ${lastYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, lyPostStart, lyPostEnd, def.excludedDates, def.ddStoreIdToMerchant) },
      ]);
      addBlock(rows, `${def.label} ${metric} Date Pivot`, pivotRows);
    }
  }
}

/** Best-effort URL from Apps Script / backend JSON (field names vary). */
function extractSpreadsheetUrl(gs) {
  if (!gs || gs.error || gs.skipped) return null;
  const candidates = [gs.spreadsheetUrl, gs.url, gs.webViewLink, gs.sheetUrl, gs.link];
  for (const u of candidates) {
    if (typeof u === 'string' && /^https?:\/\//i.test(u.trim())) return u.trim();
  }
  return null;
}

async function pushToGoogleSheets(filename, sheets) {
  const targetUrl = resolveSheetsExportUrl(GOOGLE_SHEETS_EXPORT_URL, defaultExportUrl);

  if (!targetUrl) {
    return {
      skipped: true,
      reason: 'Set VITE_GOOGLE_SHEETS_EXPORT_URL to an Apps Script or backend endpoint to enable Google Sheets push.',
    };
  }

  const response = await fetch(targetUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename,
      createdAt: new Date().toISOString(),
      sheets,
    }),
  });

  if (!response.ok) {
    throw new Error(`Google Sheets push failed (${response.status}) via ${targetUrl}`);
  }

  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: true, message: text };
  }
}

export async function exportAllReports(data, config) {
  const wb = XLSX.utils.book_new();
  const sheets = [];

  // Legacy App2.0 / reference workbook sheets (required baseline)
  for (const legacy of buildLegacyExportSheets(data, config)) {
    appendReportSheet(wb, sheets, legacy.name, legacy.rows, data, config);
  }

  const summarySheetRows = buildSummarySheetRows(data, config);
  appendReportSheet(wb, sheets, 'Extended Summary', summarySheetRows, data, config);

  const summaryRows = buildSummaryDetailSections(data.summaryTables);

  const storeLevelRows = [];
  const ddToUe = config?.ddToUeStoreMap || {};
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const alignedStores = buildAlignedExportStoreTables(data.storeTables, ddToUe);
  const storeMetricHeaders = [
    'Store Name',
    'Pre Sales',
    'Post Sales',
    'Sales Pre vs Post',
    'Sales Growth%',
    'LY Post Sales',
    'Sales YoY',
    'Sales YoY%',
    'Pre Payouts',
    'Post Payouts',
    'Payouts Growth%',
    'Pre Orders',
    'Post Orders',
    'Orders Growth%',
    'Post AOV',
    'Post Profitability%',
  ];
  for (const { key, label } of PLATFORM_SECTIONS) {
    addSection(
      storeLevelRows,
      `${label}: Store-Level Performance (summary)`,
      [...exportStoreIdHeaders(key), ...storeMetricHeaders],
      storeRows(
        { combined: alignedStores.combined, dd: alignedStores.dd, ue: alignedStores.ue }[key] || [],
        key,
        alignedStores.dominantPlatform,
        ddToUe,
        ddStoreIdToMerchant,
      ),
    );
  }

  const overviewRows = buildOverviewExportRows(data, config);

  const diagnosticsRows = [];
  addSection(
    diagnosticsRows,
    'Revenue Growth Contribution',
    ['Driver', 'Formula', 'Sales Impact', 'Contribution%'],
    buildRevenueGrowthDrivers(data.summaryTables?.combined || []).map((row) => [
      row.driver,
      row.formula,
      xf.usd(row.value),
      xf.deltaPct(row.contributionPct),
    ]),
  );
  addSection(
    diagnosticsRows,
    'Order Origin and AOV Mix (DoorDash Post Period)',
    ['Segment', 'Orders', 'Order Share%', 'Sales', 'Sales Share%', 'AOV'],
    buildOrderOriginAov(data.ddFinancial, config).map((row) => [
      row.segment,
      xf.int(row.orders),
      xf.pct(row.orderSharePct),
      xf.usd(row.sales),
      xf.pct(row.salesSharePct),
      xf.usd2(row.aov),
    ]),
  );
  const payoutFunnelExportRows = buildPayoutBridgePrePost(data.ddFinancial, config).rows.map((row) => [
    row.step,
    row.effectLabel,
    row.ownership,
    row.type,
    row.valuePre != null ? xf.usd(row.valuePre) : '',
    xf.usd(row.value),
    row.valueDelta != null ? xf.usd(row.valueDelta) : '',
    xf.deltaPct(row.valueDeltaPct),
    row.runningPre != null ? xf.usd(row.runningPre) : '',
    xf.usd(row.running),
  ]);
  addSection(
    diagnosticsRows,
    'Sales to Payout Funnel (DoorDash Pre vs Post)',
    [
      'Funnel Step',
      'Add or subtract',
      'Owner',
      'Type',
      'Pre $',
      'Post $',
      'Delta $',
      'Delta %',
      'Running Pre',
      'Running Post',
    ],
    payoutFunnelExportRows,
  );

  const fullRows = [];
  addBlock(fullRows, 'Summary Tables', summaryRows);
  addBlock(fullRows, 'Overview Spotlight', overviewRows);
  addBlock(fullRows, 'Store-Level Summary', storeLevelRows);
  addBlock(fullRows, 'Growth and Payout Drivers', diagnosticsRows);
  appendReportSheet(wb, sheets, 'Full', fullRows, data, config);

  const dateRows = [];
  addApp2DatePivotSections(dateRows, data, config);
  addSection(
    dateRows,
    'DoorDash Daily Store Export',
    ['Platform', 'Date', ...exportStoreIdHeaders('dd'), 'Sales', 'Payouts', 'Orders'],
    buildDailyRows(data.ddFinancial, 'dd', config, ddStoreIdToMerchant),
  );
  addSection(
    dateRows,
    'UberEats Daily Store Export',
    ['Platform', 'Date', ...exportStoreIdHeaders('ue'), 'Sales', 'Payouts', 'Orders'],
    buildDailyRows(data.ueFinancial, 'ue', config),
  );
  appendReportSheet(wb, sheets, 'Date', dateRows, data, config);

  const marketingTables = resolveMarketingTables(data, config);
  const marketingRows = [];
  const combined = marketingTables?.bySource?.combined;
  if (combined?.corp) {
    addSection(marketingRows, 'Corp vs TODC — Post period', MARKETING_IMPACT_HEADERS, marketingImpactExportRows(combined, 'post'));
    addSection(marketingRows, 'Corp vs TODC — Pre period', MARKETING_IMPACT_HEADERS, marketingImpactExportRows(combined, 'pre'));
  }
  const { promoCampaigns, adsCampaigns } = marketingCampaignSlices(marketingTables);
  if (promoCampaigns.length) {
    addSection(marketingRows, 'Promo campaigns', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(promoCampaigns));
    addSection(marketingRows, 'Promo — Top 10% by ROAS', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(buildCampaignHighlights(promoCampaigns, 'topRoas')));
    addSection(marketingRows, 'Promo — Top 10% by spend', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(buildCampaignHighlights(promoCampaigns, 'topSpend')));
    addSection(marketingRows, 'Promo — Bottom 10% by ROAS', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(buildCampaignHighlights(promoCampaigns, 'poorRoas')));
  }
  if (adsCampaigns.length) {
    addSection(marketingRows, 'Ads campaigns', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(adsCampaigns));
    addSection(marketingRows, 'Ads — Top 10% by ROAS', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(buildCampaignHighlights(adsCampaigns, 'topRoas')));
    addSection(marketingRows, 'Ads — Top 10% by spend', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(buildCampaignHighlights(adsCampaigns, 'topSpend')));
    addSection(marketingRows, 'Ads — Bottom 10% by ROAS', CAMPAIGN_IMPACT_HEADERS, campaignImpactExportRows(buildCampaignHighlights(adsCampaigns, 'poorRoas')));
  }
  appendReportSheet(wb, sheets, 'Marketing', marketingRows, data, config);

  const slotSheetRows = [];
  for (const { key, label } of DATA_PLATFORM_SECTIONS) {
    const analysis = buildPlatformSlotAnalysis(data, config, key);
    const rows = [];
    for (const { key, title, valueKind } of SLOT_METRIC_TABLES) {
      addSection(
        rows,
        `${title} - Pre vs Post`,
        SLOT_EXPORT_HEADERS_PVP,
        slotRows(analysis?.[`${key}PrePost`], valueKind),
      );
      addSection(
        rows,
        `${title} - Year over Year`,
        SLOT_EXPORT_HEADERS_YOY,
        slotRows(analysis?.[`${key}YoY`], valueKind),
      );
    }
    addBlock(slotSheetRows, `${label} Slot Analysis`, rows);
  }

  const salesByOrderNorm = normalizeDdSalesByOrder(data.ddSales?.byOrder);
  if (salesByOrderNorm.length && config.ddPreStart && config.ddPreEnd && config.ddPostStart && config.ddPostEnd) {
    const salesOrderAnalysis = buildSlotSalesOrderAnalysis(salesByOrderNorm, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart: config.ddPostStart,
      postEnd: config.ddPostEnd,
      excludedDates: config.ddExcludedDates || [],
    });
    appendSlotOrderAnalysisBlock(slotSheetRows, 'DoorDash Sales by Order — customer mix & items', salesOrderAnalysis);
  }

  const ueOrdersNorm = normalizeUeOrdersForSlotView(data.ueFinancial);
  if (ueOrdersNorm.length && config.uePreStart && config.uePreEnd && config.uePostStart && config.uePostEnd) {
    const ueSlotOrderAnalysis = buildSlotSalesOrderAnalysis(ueOrdersNorm, {
      preStart: config.uePreStart,
      preEnd: config.uePreEnd,
      postStart: config.uePostStart,
      postEnd: config.uePostEnd,
      excludedDates: config.ueExcludedDates || [],
    });
    appendSlotOrderAnalysisBlock(slotSheetRows, 'Uber Eats — order volume by slot / day', ueSlotOrderAnalysis);
  }

  appendReportSheet(wb, sheets, 'Slot', slotSheetRows, data, config);

  const bucketData = buildBucketSections(data, config);
  const bucketRows = [];
  for (const { key, label } of DATA_PLATFORM_SECTIONS) {
    const entry = bucketData?.[key];
    addSection(
      bucketRows,
      `${label} Order Bucketing`,
      ['Bucket', 'Pre Orders', 'Post Orders', 'Orders Change', 'Orders Growth%', 'Pre Sales', 'Post Sales', 'Sales Growth%'],
      (entry?.buckets || []).map((row) => [
        row.range,
        xf.int(row.pre_orders),
        xf.int(row.post_orders),
        xf.int(row.orders_change),
        xf.deltaPct(row.orders_growth_pct),
        xf.usd(row.pre_sales),
        xf.usd(row.post_sales),
        xf.deltaPct(row.sales_growth_pct),
      ]),
    );
    addSection(
      bucketRows,
      `${label} Order Origin Mix (Post)`,
      ['Origin', 'Share%', 'Count'],
      (entry?.mix || []).map((row) => [row.label, xf.pct(row.value), xf.int(row.count)]),
    );
    addSection(
      bucketRows,
      `${label} Order Origin Mix — Pre vs Post`,
      ['Segment', 'Pre share', 'Post share', 'Δ (pp)'],
      buildMixChangeRows(entry?.mixPre, entry?.mix),
    );
  }
  appendReportSheet(wb, sheets, 'Bucket', bucketRows, data, config);

  const storesRows = buildStoresExportRows(data, config);
  appendReportSheet(wb, sheets, 'Stores', storesRows, data, config);

  const opsRows = buildOperationsExportRows(data);
  appendReportSheet(wb, sheets, 'Operations', opsRows, data, config);

  const productMixRows = buildProductMixExportRows(data, config);
  appendReportSheet(wb, sheets, 'Product Mix', productMixRows, data, config);

  const ddRegister = buildDdRegister(data, config);
  if (ddRegister.length) {
    appendReportSheet(wb, sheets, 'DD Register', [
      DD_REGISTER_COLUMNS.map((c) => c.label),
      ...ddRegister.map((r) => registerRowToExport(r, DD_REGISTER_COLUMNS)),
    ], data, config);
  }

  const ueRegister = buildUeRegister(data, config);
  if (ueRegister.length) {
    appendReportSheet(wb, sheets, 'UE Register', [
      UE_REGISTER_COLUMNS.map((c) => c.label),
      ...ueRegister.map((r) => registerRowToExport(r, UE_REGISTER_COLUMNS)),
    ], data, config);
  }

  const filename = buildExportFilename(config, 'excel', { ext: 'xlsx' });
  XLSX.writeFile(wb, filename);

  let googleSheets;
  try {
    googleSheets = await pushToGoogleSheets(filename, sheets);
  } catch (err) {
    googleSheets = { error: err.message || String(err) };
  }
  return { filename, googleSheets, spreadsheetUrl: extractSpreadsheetUrl(googleSheets) };
}

function exportRegisterSheet(platform, data, config) {
  const isDd = platform === 'dd';
  const rows = isDd ? buildDdRegister(data, config) : buildUeRegister(data, config);
  if (!rows.length) {
    throw new Error(`No ${isDd ? 'DoorDash' : 'Uber Eats'} register data to export`);
  }
  const columns = isDd ? DD_REGISTER_COLUMNS : UE_REGISTER_COLUMNS;
  const wb = XLSX.utils.book_new();
  const sheetName = isDd ? 'DD Register' : 'UE Register';
  appendSheet(wb, [], sheetName, [
    columns.map((c) => c.label),
    ...rows.map((r) => registerRowToExport(r, columns)),
  ]);
  const fileType = isDd ? 'register_dd_excel' : 'register_ue_excel';
  const filename = buildExportFilename(config, fileType, { ext: 'xlsx' });
  XLSX.writeFile(wb, filename);
  return { filename };
}

export function exportDdRegister(data, config) {
  return exportRegisterSheet('dd', data, config);
}

export function exportUeRegister(data, config) {
  return exportRegisterSheet('ue', data, config);
}
