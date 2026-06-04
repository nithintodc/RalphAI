import * as XLSX from 'xlsx';
import { format, subYears } from 'date-fns';
import { buildSlotAnalysis, SLOT_METRIC_TABLES } from '../engine/slots';
import { buildSlotSalesOrderAnalysis, slotSalesOrderExportHeaders, slotSalesOrderExportRow, dashPassExportHeaders, dashPassExportRow, orderVolumeExportHeaders, orderVolumeExportRow } from '../engine/slotSalesOrder';
import { buildDdRegister, buildUeRegister, registerRowToExport, DD_REGISTER_COLUMNS, UE_REGISTER_COLUMNS } from '../engine/register';
import { normalizeDdSalesByOrder } from '../parsers/ddSalesByOrder';
import { normalizeUeOrdersForSlotView } from '../parsers/ueOrderSlots';
import { buildBucketAnalysis, buildOrderOriginMix } from '../engine/buckets';
import { buildOrderOriginAov, buildPayoutBridgePrePost, buildRevenueGrowthDrivers } from '../engine/diagnostics';
import { buildCorpVsTodcBySource, buildCampaignTable, MARKETING_SUMMARY_METRICS } from '../engine/marketing';
import { DATA_PLATFORM_SECTIONS, PLATFORM_SECTIONS } from '../platforms';
import { getStarAndDecliningStores, getAllStoresDailyExtremes } from '../engine/diagnostics';
import { growthPct, round, safeDivide } from '../utils/safeMath';
import { xf, exportByKind, exportSummaryMetric, exportStoreSpecValue } from '../utils/formatters';
import { parseDate, getLastYearDates, isInRange } from '../utils/dateUtils';
import {
  pivotDowntimeByStore,
  pivotDowntimeByDimension,
  pivotCountByStore,
  pivotStoreByDatePeriod,
  pickCategoryColumn,
  pickStoreColumn,
  inferCategoricalColumns,
  pivotProductByStore,
  pivotStoreByProduct,
  pivotOneWaySum,
  pickProductColumn,
  pickColumnByRegexOrder,
  pickErrorChargeColumn,
} from '../utils/opsProductPivot';

const QTY_PATTERNS = [/units?\s*sold/i, /quantity/i, /\bqty\b/i, /orders/i, /count/i];
const DATE_NAME_RE = /(^|[^a-z])date([^a-z]|$)|order\s*date|business\s*date|^day$/i;

const STORE_METRIC_SPECS = [
  { id: 'sales', label: 'Sales', preKey: 'pre_sales', postKey: 'post_sales', postLyKey: 'postLY_sales', deltaKey: 'sales_prevspost', lyDeltaKey: 'sales_ly_prevspost', yoyDeltaKey: 'sales_yoy', deltaPctKey: 'sales_growth_pct', lyDeltaPctKey: 'sales_ly_growth_pct', yoyPctKey: 'sales_yoy_pct' },
  { id: 'payouts', label: 'Payouts', preKey: 'pre_payouts', postKey: 'post_payouts', postLyKey: 'postLY_payouts', deltaKey: 'payouts_prevspost', lyDeltaKey: 'payouts_ly_prevspost', yoyDeltaKey: 'payouts_yoy', deltaPctKey: 'payouts_growth_pct', lyDeltaPctKey: 'payouts_ly_growth_pct', yoyPctKey: 'payouts_yoy_pct' },
  { id: 'orders', label: 'Orders', preKey: 'pre_orders', postKey: 'post_orders', postLyKey: 'postLY_orders', deltaKey: 'orders_prevspost', lyDeltaKey: 'orders_ly_prevspost', yoyDeltaKey: 'orders_yoy', deltaPctKey: 'orders_growth_pct', lyDeltaPctKey: 'orders_ly_growth_pct', yoyPctKey: 'orders_yoy_pct' },
  { id: 'aov', label: 'AOV', preKey: 'pre_aov', postKey: 'post_aov', postLyKey: 'postLY_aov', deltaKey: 'aov_prevspost', lyDeltaKey: 'aov_ly_prevspost', yoyDeltaKey: 'aov_yoy', deltaPctKey: 'aov_growth_pct', lyDeltaPctKey: 'aov_ly_growth_pct', yoyPctKey: 'aov_yoy_pct' },
  { id: 'mktSpend', label: 'Marketing Spend', platforms: ['dd'], preKey: 'pre_mktSpend', postKey: 'post_mktSpend', postLyKey: 'postLY_mktSpend', deltaKey: 'mktSpend_prevspost', lyDeltaKey: 'mktSpend_ly_prevspost', yoyDeltaKey: 'mktSpend_yoy', deltaPctKey: 'mktSpend_growth_pct', lyDeltaPctKey: 'mktSpend_ly_growth_pct', yoyPctKey: 'mktSpend_yoy_pct' },
  { id: 'profitability', label: 'Profitability %', preKey: 'pre_profitability', postKey: 'post_profitability', postLyKey: 'postLY_profitability', deltaKey: 'prof_prevspost', lyDeltaKey: 'prof_ly_prevspost', yoyDeltaKey: 'prof_yoy', deltaPctKey: 'prof_growth_pct', lyDeltaPctKey: 'prof_ly_growth_pct', yoyPctKey: 'prof_yoy_pct' },
];

const METRIC_LABELS = {
  sales: 'Sales',
  payouts: 'Payouts',
  orders: 'Orders',
  profitability: 'Profitability',
  aov: 'Average Check',
};

const GOOGLE_SHEETS_EXPORT_URL = import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL;

/** Same-origin export API (RalphAI FastAPI; /api is proxied in dev). */
function defaultExportUrl() {
  if (typeof window === 'undefined') return null;
  return `${window.location.origin}/api/export`;
}

function timestamp() {
  return format(new Date(), 'yyyyMMdd_HHmmss');
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

function appendReportSheet(wb, sheetDefs, name, rows) {
  appendSheet(
    wb,
    sheetDefs,
    name,
    rows.length ? rows : [[`No ${name.toLowerCase()} report data available for this export.`]],
  );
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

function storeRows(stores) {
  return (stores || []).map((row) => [
    row.storeId,
    xf.usd(row.pre_sales),
    xf.usd(row.post_sales),
    xf.usd(row.sales_prevspost),
    xf.deltaPct(row.sales_growth_pct),
    xf.usd(row.postLY_sales),
    xf.usd(row.sales_yoy),
    xf.deltaPct(row.sales_yoy_pct),
    xf.usd(row.pre_payouts),
    xf.usd(row.post_payouts),
    xf.deltaPct(row.payouts_growth_pct),
    xf.int(row.pre_orders),
    xf.int(row.post_orders),
    xf.deltaPct(row.orders_growth_pct),
    xf.usd2(row.post_aov),
    xf.pct(row.post_profitability),
  ]);
}

function storeMetricPvpRows(stores, spec) {
  return (stores || []).map((row) => [
    row.storeId,
    exportStoreSpecValue(spec, row[spec.preKey]),
    exportStoreSpecValue(spec, row[spec.postKey]),
    exportStoreSpecValue(spec, row[spec.deltaKey]),
    exportStoreSpecValue(spec, row[spec.lyDeltaKey]),
    xf.deltaPct(row[spec.deltaPctKey]),
    xf.deltaPct(row[spec.lyDeltaPctKey]),
  ]);
}

function storeMetricYoyRows(stores, spec) {
  return (stores || []).map((row) => [
    row.storeId,
    exportStoreSpecValue(spec, row[spec.postLyKey]),
    exportStoreSpecValue(spec, row[spec.postKey]),
    exportStoreSpecValue(spec, row[spec.yoyDeltaKey]),
    xf.deltaPct(row[spec.yoyPctKey]),
  ]);
}

function buildStoresExportRows(data) {
  const rows = [];
  for (const { key, label } of PLATFORM_SECTIONS) {
    const stores = data.storeTables?.[key] || [];
    if (!stores.length) continue;
    for (const spec of storeSpecsForPlatform(key)) {
      addSection(
        rows,
        `${label} — ${spec.label} (Pre vs Post)`,
        ['Store ID', 'Pre', 'Post', 'Pre vs Post Δ', 'LY Pre vs Post Δ', 'Pre vs Post %', 'LY Growth%'],
        storeMetricPvpRows(stores, spec),
      );
      addSection(
        rows,
        `${label} — ${spec.label} (YoY)`,
        ['Store ID', 'LY Post', 'Post', 'YoY Δ', 'YoY %'],
        storeMetricYoyRows(stores, spec),
      );
    }
  }
  return rows;
}

function buildOverviewExportRows(data, config) {
  const rows = [];
  const stores = data.storeTables?.combined || [];
  const spotlight = getStarAndDecliningStores(stores);
  addSection(
    rows,
    'Store Spotlight — Star stores',
    ['Store ID', 'Sales Growth%'],
    (spotlight.stars || []).map((s) => [s.storeId, xf.deltaPct(s.sales_growth_pct)]),
  );
  addSection(
    rows,
    'Store Spotlight — Declining stores',
    ['Store ID', 'Sales Growth%'],
    (spotlight.declining || []).map((s) => [s.storeId, xf.deltaPct(s.sales_growth_pct)]),
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

function storeSpecsForPlatform(platformKey) {
  return STORE_METRIC_SPECS.filter((spec) => !spec.platforms || spec.platforms.includes(platformKey));
}

function metricDecimals(metricKey) {
  if (metricKey === 'orders') return 0;
  if (['promoAov', 'cpo', 'checkAfterPromo', 'roas'].includes(metricKey)) return 2;
  return 0;
}

function marketingPostImpactRows(table) {
  if (!table?.corp) return [];
  return [table.corp, table.todc, table.total].map((r) => [
    r.label,
    xf.usd(r.salesPost),
    xf.usd(r.spendPost),
    xf.usd2(r.promoAovPost),
    xf.usd2(r.cpoPost),
    xf.usd2(r.checkAfterPromoPost),
  ]);
}

function marketingMetricPrePostRows(table, metricKey, metricKind) {
  if (!table?.corp) return [];
  const keys = ['corp', 'todc', 'total'];
  return keys.map((k) => {
    const r = table[k];
    const lyPrevspost = round((r[`${metricKey}LyPost`] ?? 0) - (r[`${metricKey}LyPre`] ?? 0), metricDecimals(metricKey));
    const lyGrowthPct = round(growthPct(r[`${metricKey}LyPre`], r[`${metricKey}LyPost`]), 1);
    return [
      r.label,
      exportByKind(metricKind, r[`${metricKey}Pre`]),
      exportByKind(metricKind, r[`${metricKey}Post`]),
      exportByKind(metricKind, r[`${metricKey}Pvp`]),
      exportByKind(metricKind, lyPrevspost),
      xf.deltaPct(r[`${metricKey}PvpPct`]),
      xf.deltaPct(lyGrowthPct),
    ];
  });
}

function marketingMetricYoyRows(table, metricKey, metricKind) {
  if (!table?.corp) return [];
  const keys = ['corp', 'todc', 'total'];
  return keys.map((k) => {
    const r = table[k];
    return [
      r.label,
      exportByKind(metricKind, r[`${metricKey}LyPost`]),
      exportByKind(metricKind, r[`${metricKey}Post`]),
      exportByKind(metricKind, r[`${metricKey}Yoy`]),
      xf.deltaPct(r[`${metricKey}YoyPct`]),
    ];
  });
}

function campaignRows(campaigns) {
  return (campaigns || []).map((row) => [
    row.campaignName,
    row.source,
    row.isSelfServe ? 'TODC' : 'Corporate',
    xf.int(row.orders),
    xf.usd(row.sales),
    xf.usd(row.spend),
    xf.usd2(row.promoAov),
    xf.roas(row.roas),
    xf.usd2(row.cpo),
    xf.usd2(row.checkAfterPromo),
  ]);
}

function slotRows(rows, valueKind) {
  const val = (v) => exportByKind(valueKind, v);
  return (rows || []).map((row) => [
    row.slot,
    val(row.pre ?? row.postLY),
    val(row.post),
    val(row.prevspost ?? row.yoy),
    xf.deltaPct(row.growthPct ?? row.yoyPct),
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

function marketingTablesNeedRebuild(tables) {
  const c = tables?.bySource?.combined?.corp;
  return !c || c.ordersPre === undefined;
}

function buildMarketingSections(data, config) {
  if (
    (data.marketingTables?.bySource || data.marketingTables?.campaigns)
    && !marketingTablesNeedRebuild(data.marketingTables)
  ) {
    return data.marketingTables;
  }

  const promotion = data.ddMarketing?.promotion;
  const sponsored = data.ddMarketing?.sponsored;
  if ((!promotion && !sponsored) || !config.ddPostStart || !config.ddPostEnd) {
    return null;
  }

  return {
    bySource: buildCorpVsTodcBySource(
      promotion,
      sponsored,
      {
        preStart: config.ddPreStart,
        preEnd: config.ddPreEnd,
        postStart: config.ddPostStart,
        postEnd: config.ddPostEnd,
        excludedDates: config.ddExcludedDates || [],
      },
    ),
    campaigns: buildCampaignTable(promotion, sponsored, config.ddPostStart, config.ddPostEnd),
  };
}

function objectColumns(rows) {
  return rows?.[0] ? Object.keys(rows[0]) : [];
}

function matrixToRows(rowHeaderLabel, rowKeys, colKeys, matrix) {
  if (!rowKeys?.length || !colKeys?.length || !matrix?.length) return [];
  const headers = [rowHeaderLabel, ...colKeys, 'Total'];
  const body = rowKeys.map((rk, i) => {
    const vals = matrix[i] || [];
    const total = vals.reduce((s, v) => s + Number(v || 0), 0);
    return [rk, ...vals, total];
  });
  return [headers, ...body];
}

function buildOperationsExportRows(data) {
  const rows = [];
  const downtimeRows = data.ddOps?.byStore?.downtime?.data || [];
  const downtimeCols = objectColumns(downtimeRows);
  const downtimePivot = pivotDowntimeByStore(downtimeRows, downtimeCols);
  addSection(
    rows,
    'Downtime by store',
    ['Store', 'Days', 'Hours', 'Minutes', 'Total (min)', 'Rows'],
    (downtimePivot.rows || []).map((r) => [r.store, r.days, r.hours, r.minutes, r.totalMinutes, r.lineCount]),
  );

  const storeColEarly = pickStoreColumn(downtimeCols);
  const categoryCol =
    pickCategoryColumn(downtimeCols, [storeColEarly].filter(Boolean))
    || inferCategoricalColumns(downtimeRows, downtimeCols, { exclude: [storeColEarly].filter(Boolean), maxUniq: 90 })[0]?.col
    || null;
  const downtimeByCategory = categoryCol
    ? pivotDowntimeByDimension(downtimeRows, downtimeCols, categoryCol)
    : null;
  addSection(
    rows,
    `Downtime by category${categoryCol ? ` (${categoryCol})` : ''}`,
    ['Bucket', 'Days', 'Hours', 'Minutes', 'Total (min)', 'Rows'],
    (downtimeByCategory?.rows || []).map((r) => [r.label, r.days, r.hours, r.minutes, r.totalMinutes, r.lineCount]),
  );

  const cancelRows = data.ddOps?.byStore?.cancellations?.data || [];
  const cancelPivot = pivotCountByStore(cancelRows, objectColumns(cancelRows));
  addSection(
    rows,
    'Cancellations by store',
    ['Store', 'Count'],
    (cancelPivot.rows || []).map((r) => [r.store, r.rowCount]),
  );

  const missRows = data.ddOps?.byStore?.missingIncorrect?.data || [];
  const missPivot = pivotCountByStore(missRows, objectColumns(missRows));
  addSection(
    rows,
    'Missing / incorrect by store',
    ['Store', 'Count'],
    (missPivot.rows || []).map((r) => [r.store, r.rowCount]),
  );

  const timeAggRows = data.ddOps?.byTime?.aggregate?.data || [];
  const timePivot = pivotStoreByDatePeriod(timeAggRows, objectColumns(timeAggRows), { maxCols: 36 });
  addBlock(rows, 'Operations quality over time (pivot)', matrixToRows('Store', timePivot.rowStores, timePivot.colProducts, timePivot.matrix));

  const timeByStoreRows = data.ddOps?.byTime?.byStore?.data || [];
  const timeByStorePivot = pivotStoreByDatePeriod(timeByStoreRows, objectColumns(timeByStoreRows), { maxCols: 28 });
  addBlock(rows, 'By store (time export) — pivot', matrixToRows('Store', timeByStorePivot.rowStores, timeByStorePivot.colProducts, timeByStorePivot.matrix));

  const bo = data.ddOps?.byOrder;
  const orderSheets = [
    ['Avoidable wait', bo?.avoidableWait?.data || []],
    ['Cancelled orders', bo?.cancelled?.data || []],
    ['Missing / incorrect', bo?.missingIncorrect?.data || []],
  ];
  for (const [label, blockRows] of orderSheets) {
    const p = pivotCountByStore(blockRows, objectColumns(blockRows));
    addSection(rows, `${label} — by store`, ['Store', 'Count'], (p.rows || []).map((r) => [r.store, r.rowCount]));
  }

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

function buildProductPeriodRows(ddProductMix, columns, config) {
  const productCol = pickProductColumn(columns);
  const valueCol = columns.find((c) => /sales|revenue|amount|payout/i.test(String(c))) || null;
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
    .sort((a, b) => b.post - a.post)
    .map((p) => [p.product, xf.usd(p.pre), xf.usd(p.post), xf.usd(p.postLY), xf.deltaPct(p.growthPct)]);
}

function buildProductHighlightRows(ddProductMix, columns) {
  const productCol = pickProductColumn(columns);
  const salesCol = columns.find((c) => /sales|revenue|amount|payout/i.test(String(c))) || null;
  const qtyCol = pickColumnByRegexOrder(columns, QTY_PATTERNS);
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

function buildProductMixExportRows(data, config) {
  const rows = [];
  const ddProductMix = data.ddProductMix || [];
  const columns = objectColumns(ddProductMix);
  const productStore = pivotProductByStore(ddProductMix, columns, { maxStoreCols: 26 });
  const storeProduct = pivotStoreByProduct(ddProductMix, columns, { maxProductCols: 26 });
  const valueCol = productStore.valueCol || storeProduct.valueCol;

  addBlock(rows, 'Product × Store', matrixToRows('Product', productStore.rowProducts, productStore.colStores, productStore.matrix));
  addBlock(rows, 'Store × Product', matrixToRows('Store', storeProduct.rowStores, storeProduct.colProducts, storeProduct.matrix));

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

  const periodRows = buildProductPeriodRows(ddProductMix, columns, config);
  if (periodRows.length) {
    addSection(rows, 'By product (Pre / Post / LY)', ['Product', 'Pre', 'Post', 'LY Post', 'Growth %'], periodRows);
  } else if (valueCol) {
    const byProduct = pivotOneWaySum(ddProductMix, productStore.productCol, valueCol);
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

function buildDailyRows(records, platform, config) {
  if (!isPresent(records)) return [];
  const prefix = platform === 'ue' ? 'ue' : 'dd';
  const start = config[`${prefix}PreStart`];
  const end = config[`${prefix}PostEnd`];
  const grouped = new Map();

  for (const row of filterWindow(records, start, end, config[`${prefix}ExcludedDates`] || [])) {
    const date = dateValue(row.date);
    const storeId = String(row.storeId ?? '');
    const key = `${date}|${storeId}`;
    const current = grouped.get(key) || {
      platform: platform === 'ue' ? 'UberEats' : 'DoorDash',
      date,
      storeId,
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
    .map(row => [row.platform, row.date, row.storeId, row.sales, row.payouts, row.orders.size]);
}

function metricValue(row, platform, metric) {
  if (metric === 'Sales') return platform === 'ue' ? Number(row.sales || 0) : Number(row.subtotal || 0);
  if (metric === 'Payouts') return platform === 'ue' ? Number(row.totalPayout || 0) : Number(row.netTotal || 0);
  return row.orderId;
}

function buildPeriodPivot(records, platform, metric, start, end, excludedDates = []) {
  const rows = filterWindow(records, start, end, excludedDates);
  const dates = new Set();
  const stores = new Set();
  const grouped = new Map();

  for (const row of rows) {
    const date = dateValue(row.date);
    const storeId = String(row.storeId ?? '');
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
  const definitions = [
    { platform: 'dd', label: 'DoorDash', records: data.ddFinancial, excludedDates: config.ddExcludedDates || [] },
    { platform: 'ue', label: 'UberEats', records: data.ueFinancial, excludedDates: config.ueExcludedDates || [] },
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
        { title: `Pre ${currentYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, preStart, preEnd, def.excludedDates) },
        { title: `Post ${currentYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, postStart, postEnd, def.excludedDates) },
        { title: `Pre ${lastYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, lyPreStart, lyPreEnd, def.excludedDates) },
        { title: `Post ${lastYear}`, rows: buildPeriodPivot(def.records, def.platform, metric, lyPostStart, lyPostEnd, def.excludedDates) },
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
  const targetUrl = GOOGLE_SHEETS_EXPORT_URL || defaultExportUrl();

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

  const summaryRows = [];
  for (const { key, label } of PLATFORM_SECTIONS) {
    const summary = data.summaryTables?.[key] || [];
    addSection(
      summaryRows,
      `${label} Table 1: Current Year Pre vs Post Analysis`,
      ['Metric', 'Pre', 'Post', 'Pre vs Post', 'LY Pre vs Post', 'Growth%', 'LY Growth%'],
      summaryPrePostRows(summary),
    );
    addSection(
      summaryRows,
      `${label} Table 2: Year-over-Year Analysis`,
      ['Metric', 'LY Post', 'Post', 'YoY', 'YoY%'],
      summaryYoyRows(summary),
    );
  }

  const storeLevelRows = [];
  const storeHeaders = [
    'Store ID',
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
      storeHeaders,
      storeRows(data.storeTables?.[key] || []),
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
  appendReportSheet(wb, sheets, 'Full', fullRows);

  const dateRows = [];
  addApp2DatePivotSections(dateRows, data, config);
  addSection(
    dateRows,
    'DoorDash Daily Store Export',
    ['Platform', 'Date', 'Store ID', 'Sales', 'Payouts', 'Orders'],
    buildDailyRows(data.ddFinancial, 'dd', config),
  );
  addSection(
    dateRows,
    'UberEats Daily Store Export',
    ['Platform', 'Date', 'Store ID', 'Sales', 'Payouts', 'Orders'],
    buildDailyRows(data.ueFinancial, 'ue', config),
  );
  appendReportSheet(wb, sheets, 'Date', dateRows);

  const marketingTables = buildMarketingSections(data, config);
  const marketingRows = [];
  const prePostHeaders = ['Group', 'Pre', 'Post', 'Pre vs Post Δ', 'LY Pre vs Post Δ', 'Pre vs Post %', 'LY Growth%'];
  const yoyHeaders = ['Group', 'LY Post', 'Post', 'YoY Δ', 'YoY %'];
  const postImpactHeaders = ['Group', 'Sales', 'Spend', 'Promo AOV', 'Cost / Order', 'Check After Promo'];
  const marketingSources = [
    { title: 'Promotions', table: marketingTables?.bySource?.promotion },
    { title: 'Sponsored Listings', table: marketingTables?.bySource?.sponsored },
  ];
  for (const source of marketingSources) {
    addSection(
      marketingRows,
      `${source.title} — Post-period impact`,
      postImpactHeaders,
      marketingPostImpactRows(source.table),
    );
    for (const metric of MARKETING_SUMMARY_METRICS) {
      addSection(
        marketingRows,
        `${source.title} — ${metric.label} (Pre vs Post)`,
        prePostHeaders,
        marketingMetricPrePostRows(source.table, metric.key, metric.kind),
      );
      addSection(
        marketingRows,
        `${source.title} — ${metric.label} (YoY)`,
        yoyHeaders,
        marketingMetricYoyRows(source.table, metric.key, metric.kind),
      );
    }
  }
  addSection(marketingRows, 'Campaign Performance', ['Campaign', 'Source', 'Type', 'Orders', 'Sales', 'Spend', 'Promo AOV', 'ROAS', 'Cost per Order', 'Check After Promo'], campaignRows(marketingTables?.campaigns));
  appendReportSheet(wb, sheets, 'Marketing', marketingRows);

  const slotSheetRows = [];
  for (const { key, label } of DATA_PLATFORM_SECTIONS) {
    const analysis = buildPlatformSlotAnalysis(data, config, key);
    const rows = [];
    for (const { key, title, valueKind } of SLOT_METRIC_TABLES) {
      addSection(
        rows,
        `${title} - Pre vs Post`,
        ['Slot', 'Pre', 'Post', 'Pre vs Post', 'Growth%'],
        slotRows(analysis?.[`${key}PrePost`], valueKind),
      );
      addSection(
        rows,
        `${title} - Year over Year`,
        ['Slot', 'LY Post', 'Post', 'YoY', 'YoY%'],
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

  appendReportSheet(wb, sheets, 'Slot', slotSheetRows);

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
  appendReportSheet(wb, sheets, 'Bucket', bucketRows);

  const storesRows = buildStoresExportRows(data);
  appendReportSheet(wb, sheets, 'Stores', storesRows);

  const opsRows = buildOperationsExportRows(data);
  appendReportSheet(wb, sheets, 'Operations', opsRows);

  const productMixRows = buildProductMixExportRows(data, config);
  appendReportSheet(wb, sheets, 'Product Mix', productMixRows);

  const ddRegister = buildDdRegister(data, config);
  if (ddRegister.length) {
    appendReportSheet(wb, sheets, 'DD Register', [
      DD_REGISTER_COLUMNS.map((c) => c.label),
      ...ddRegister.map((r) => registerRowToExport(r, DD_REGISTER_COLUMNS)),
    ]);
  }

  const ueRegister = buildUeRegister(data, config);
  if (ueRegister.length) {
    appendReportSheet(wb, sheets, 'UE Register', [
      UE_REGISTER_COLUMNS.map((c) => c.label),
      ...ueRegister.map((r) => registerRowToExport(r, UE_REGISTER_COLUMNS)),
    ]);
  }

  const filename = `analysis_all_reports_${timestamp()}.xlsx`;
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
  const prefix = isDd ? 'dd_register' : 'ue_register';
  const filename = `${prefix}_${timestamp()}.xlsx`;
  XLSX.writeFile(wb, filename);
  return { filename };
}

export function exportDdRegister(data, config) {
  return exportRegisterSheet('dd', data, config);
}

export function exportUeRegister(data, config) {
  return exportRegisterSheet('ue', data, config);
}
