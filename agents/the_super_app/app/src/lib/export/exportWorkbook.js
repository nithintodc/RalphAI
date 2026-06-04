import * as XLSX from 'xlsx';
import { format, subYears } from 'date-fns';
import { buildSlotAnalysis, SLOT_METRIC_TABLES } from '../engine/slots';
import { buildBucketAnalysis, buildOrderOriginMix } from '../engine/buckets';
import { buildOrderOriginAov, buildPayoutBridgePrePost, buildRevenueGrowthDrivers } from '../engine/diagnostics';
import { buildCorpVsTodcBySource, buildCampaignTable, MARKETING_SUMMARY_METRICS } from '../engine/marketing';
import { buildApp2BucketingPack, app2PackToSheetRows } from '../engine/app2Bucketing';
import { DATA_PLATFORM_SECTIONS, PLATFORM_SECTIONS } from '../platforms';
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
} from '../utils/opsProductPivot';

const METRIC_LABELS = {
  sales: 'Sales',
  payouts: 'Payouts',
  orders: 'Orders',
  profitability: 'Profitability',
  aov: 'Average Check',
};

const GOOGLE_SHEETS_EXPORT_URL = import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL;
const LOCAL_EXPORT_API_PORT = import.meta.env.VITE_LOCAL_EXPORT_API_PORT || '8765';

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
  return (summary || []).map(row => [
    METRIC_LABELS[row.metric] || row.metric,
    row.pre ?? 0,
    row.post ?? 0,
    row.prevspost ?? 0,
    row.lyPrevspost ?? 0,
    row.growthPct ?? 0,
  ]);
}

function summaryYoyRows(summary) {
  return (summary || []).map(row => [
    METRIC_LABELS[row.metric] || row.metric,
    row.postLY ?? 0,
    row.post ?? 0,
    row.yoy ?? 0,
    row.yoyPct ?? 0,
  ]);
}

function storeRows(stores) {
  return (stores || []).map(row => [
    row.storeId,
    row.pre_sales ?? 0,
    row.post_sales ?? 0,
    row.sales_prevspost ?? 0,
    row.sales_growth_pct ?? 0,
    row.postLY_sales ?? 0,
    row.sales_yoy ?? 0,
    row.sales_yoy_pct ?? 0,
    row.pre_payouts ?? 0,
    row.post_payouts ?? 0,
    row.payouts_growth_pct ?? 0,
    row.pre_orders ?? 0,
    row.post_orders ?? 0,
    row.orders_growth_pct ?? 0,
    row.post_aov ?? 0,
    row.post_profitability ?? 0,
  ]);
}

function marketingMetricPrePostRows(table, metricKey) {
  if (!table?.corp) return [];
  const keys = ['corp', 'todc', 'total'];
  return keys.map((k) => {
    const r = table[k];
    return [
      r.label,
      r[`${metricKey}Pre`],
      r[`${metricKey}Post`],
      r[`${metricKey}Pvp`],
      r[`${metricKey}PvpPct`],
    ];
  });
}

function marketingMetricYoyRows(table, metricKey) {
  if (!table?.corp) return [];
  const keys = ['corp', 'todc', 'total'];
  return keys.map((k) => {
    const r = table[k];
    return [
      r.label,
      r[`${metricKey}LyPost`],
      r[`${metricKey}Post`],
      r[`${metricKey}Yoy`],
      r[`${metricKey}YoyPct`],
    ];
  });
}

function campaignRows(campaigns) {
  return (campaigns || []).map(row => [
    row.campaignName,
    row.source,
    row.isSelfServe ? 'TODC' : 'Corporate',
    row.orders ?? 0,
    row.sales ?? 0,
    row.spend ?? 0,
    row.promoAov ?? 0,
    row.roas ?? 0,
    row.cpo ?? 0,
    row.checkAfterPromo ?? 0,
  ]);
}

function slotRows(rows) {
  return (rows || []).map(row => [
    row.slot,
    row.pre ?? row.postLY ?? 0,
    row.post ?? 0,
    row.prevspost ?? row.yoy ?? 0,
    row.growthPct ?? row.yoyPct ?? 0,
  ]);
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
    };
  }
  return Object.keys(out).length ? out : null;
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

function rawObjectRows(records, maxColumns = 30) {
  if (!isPresent(records)) return null;
  const headers = Object.keys(records[0] || {}).slice(0, maxColumns);
  return {
    headers,
    rows: records.map(record => headers.map(key => record[key] ?? '')),
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

function buildProductMixExportRows(data) {
  const rows = [];
  const ddProductMix = data.ddProductMix || [];
  const columns = objectColumns(ddProductMix);
  const productStore = pivotProductByStore(ddProductMix, columns, { maxStoreCols: 26 });
  const storeProduct = pivotStoreByProduct(ddProductMix, columns, { maxProductCols: 26 });
  const valueCol = productStore.valueCol || storeProduct.valueCol;

  addBlock(rows, 'Product × Store', matrixToRows('Product', productStore.rowProducts, productStore.colStores, productStore.matrix));
  addBlock(rows, 'Store × Product', matrixToRows('Store', storeProduct.rowStores, storeProduct.colProducts, storeProduct.matrix));

  if (valueCol) {
    const byStore = pivotOneWaySum(ddProductMix, productStore.storeCol, valueCol);
    addSection(rows, `By store (total ${valueCol})`, ['Store', 'Total'], byStore.keys.map((k, i) => [k, byStore.values[i]]));
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
  const runtimeHost = typeof window !== 'undefined' && window.location?.hostname
    ? window.location.hostname
    : 'localhost';
  const fallbackLocalUrl = `http://${runtimeHost}:${LOCAL_EXPORT_API_PORT}/export`;
  const targetUrl = GOOGLE_SHEETS_EXPORT_URL || fallbackLocalUrl;

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
      ['Metric', 'Pre', 'Post', 'Pre vs Post', 'LY Pre vs Post', 'Growth%'],
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
      `${label}: Store-Level Performance`,
      storeHeaders,
      storeRows(data.storeTables?.[key] || []),
    );
  }

  const diagnosticsRows = [];
  addSection(
    diagnosticsRows,
    'Revenue Growth Contribution',
    ['Driver', 'Formula', 'Sales Impact', 'Contribution%'],
    buildRevenueGrowthDrivers(data.summaryTables?.combined || []).map(row => [
      row.driver,
      row.formula,
      row.value,
      row.contributionPct,
    ]),
  );
  addSection(
    diagnosticsRows,
    'Order Origin and AOV Mix (DoorDash Post Period)',
    ['Segment', 'Orders', 'Order Share%', 'Sales', 'Sales Share%', 'AOV'],
    buildOrderOriginAov(data.ddFinancial, config).map(row => [
      row.segment,
      row.orders,
      row.orderSharePct,
      row.sales,
      row.salesSharePct,
      row.aov,
    ]),
  );
  const payoutFunnelExportRows = buildPayoutBridgePrePost(data.ddFinancial, config).rows.map((row) => [
    row.step,
    row.effectLabel,
    row.ownership,
    row.type,
    row.valuePre ?? '',
    row.value,
    row.valueDelta ?? '',
    row.valueDeltaPct ?? '',
    row.runningPre ?? '',
    row.running,
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
  addBlock(fullRows, 'Store-Level Tables', storeLevelRows);
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
  const prePostHeaders = ['Group', 'Pre', 'Post', 'Pre vs Post', 'Pre vs Post %'];
  const yoyHeaders = ['Group', 'LY Post', 'Post', 'YoY', 'YoY %'];
  const marketingSources = [
    { title: 'Combined: Corporate vs TODC', table: marketingTables?.bySource?.combined },
    { title: 'Promotion: Corporate vs TODC', table: marketingTables?.bySource?.promotion },
    { title: 'Sponsored Listing: Corporate vs TODC', table: marketingTables?.bySource?.sponsored },
  ];
  for (const source of marketingSources) {
    for (const metric of MARKETING_SUMMARY_METRICS) {
      addSection(
        marketingRows,
        `${source.title} - ${metric.label} (Pre vs Post)`,
        prePostHeaders,
        marketingMetricPrePostRows(source.table, metric.key),
      );
      addSection(
        marketingRows,
        `${source.title} - ${metric.label} (YoY)`,
        yoyHeaders,
        marketingMetricYoyRows(source.table, metric.key),
      );
    }
  }
  addSection(marketingRows, 'Campaign Performance', ['Campaign', 'Source', 'Type', 'Orders', 'Sales', 'Spend', 'Promo AOV', 'ROAS', 'Cost per Order', 'Check After Promo'], campaignRows(marketingTables?.campaigns));
  appendReportSheet(wb, sheets, 'Marketing', marketingRows);

  const slotSheetRows = [];
  for (const { key, label } of DATA_PLATFORM_SECTIONS) {
    const analysis = buildPlatformSlotAnalysis(data, config, key);
    const rows = [];
    for (const { key, title } of SLOT_METRIC_TABLES) {
      addSection(
        rows,
        `${title} - Pre vs Post`,
        ['Slot', 'Pre', 'Post', 'Pre vs Post', 'Growth%'],
        slotRows(analysis?.[`${key}PrePost`]),
      );
      addSection(
        rows,
        `${title} - Year over Year`,
        ['Slot', 'LY Post', 'Post', 'YoY', 'YoY%'],
        slotRows(analysis?.[`${key}YoY`]),
      );
    }
    addBlock(slotSheetRows, `${label} Slot Analysis`, rows);
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
      (entry?.buckets || []).map(row => [
        row.range,
        row.pre_orders,
        row.post_orders,
        row.orders_change,
        row.orders_growth_pct,
        row.pre_sales,
        row.post_sales,
        row.sales_growth_pct,
      ]),
    );
    addSection(
      bucketRows,
      `${label} Order Origin Mix`,
      ['Origin', 'Share%', 'Count'],
      (entry?.mix || []).map(row => [row.label, row.value, row.count]),
    );
  }
  appendReportSheet(wb, sheets, 'Bucket', bucketRows);

  const opsRows = buildOperationsExportRows(data);
  appendReportSheet(wb, sheets, 'Operations', opsRows);

  const productMixRows = buildProductMixExportRows(data);
  appendReportSheet(wb, sheets, 'Product Mix', productMixRows);

  const app2Pack = buildApp2BucketingPack(data.ddFinancial, config);
  appendReportSheet(wb, sheets, 'App2 AITF', app2PackToSheetRows(app2Pack));

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
