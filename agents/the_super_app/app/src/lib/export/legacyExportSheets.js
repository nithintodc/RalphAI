/**
 * Legacy App2.0 / App3.0 Excel sheet layout (superset baseline).
 * Matches `context/The Melt TODC Test L7 - 8 locs.xlsx` structure.
 */

import { PLATFORM_SECTIONS } from '../platforms';
import { buildFinancialSummaryTable } from '../engine/financialBreakdown';
import { buildNewCustomersSummary } from '../engine/newCustomers';
import { buildSlotAnalysis, getSlotTimeRange, LEGACY_SLOT_EXPORT_HEADERS_PVP, LEGACY_SLOT_EXPORT_HEADERS_YOY, SLOT_METRIC_TABLES } from '../engine/slots';
import { buildCorpTodcImpactRows, buildUeMarketingSummary } from '../engine/marketing';
import { resolveMarketingTables } from './marketingExport';
import { buildAnalysisScope } from '../utils/abStoreFilter';
import { formatCompactDateRange } from '../utils/dateUtils';
import {
  buildAlignedExportStoreTables,
  combinedExportStoreName,
  EXPORT_NA,
  exportStoreIdCells,
  exportStoreIdRowCells,
  legacyStoreHeadersPvp,
  legacyStoreHeadersYoy,
  buildStoreMappingExportBlock,
} from './storeExportLayout';
import { buildDdStoreIdToMerchantMap } from '../utils/storeCatalog';
import { ddMerchantStoreIdFromKey } from '../utils/storeDisplay';

const LEGACY_SUMMARY_METRICS = [
  { key: 'sales', label: 'Sales' },
  { key: 'payouts', label: 'Payouts' },
  { key: 'orders', label: 'Orders' },
  { key: 'newCustomers', label: 'New Customers' },
  { key: 'profitability', label: 'Profitability' },
  { key: 'aov', label: 'Average Check' },
];

const LEGACY_PLATFORM_LABELS = {
  combined: 'Combined',
  dd: 'DoorDash',
  ue: 'UberEats',
};

function isNum(v) {
  return v != null && v !== '' && Number.isFinite(Number(v));
}

function fmtUsd1(v) {
  if (v == null || v === EXPORT_NA) return v === EXPORT_NA ? EXPORT_NA : '';
  if (!isNum(v)) return '';
  return `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}`;
}

function fmtUsd2(v) {
  if (!isNum(v)) return '';
  return `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtInt(v) {
  if (!isNum(v)) return '';
  return Math.round(Number(v)).toLocaleString('en-US');
}

function fmtPct1(v) {
  if (v == null || v === EXPORT_NA) return v === EXPORT_NA ? EXPORT_NA : '';
  if (!isNum(v)) return '';
  return `${Number(v).toFixed(1)}%`;
}

function fmtRoas(v) {
  if (!isNum(v)) return '';
  return Number(v).toFixed(2);
}

function periodLabel(start, end) {
  return formatCompactDateRange(start, end) || '—';
}

function summaryRowByMetric(rows, metric) {
  return (rows || []).find((r) => r.metric === metric) || {};
}

function enrichSummaryWithNewCustomers(summaryRows, ncRow) {
  if (!ncRow) return summaryRows || [];
  const base = [...(summaryRows || [])];
  const ordersIdx = base.findIndex((r) => r.metric === 'orders');
  const insertAt = ordersIdx >= 0 ? ordersIdx + 1 : base.length;
  base.splice(insertAt, 0, ncRow);
  return base;
}

function legacySummaryTable1Rows(summaryRows) {
  return LEGACY_SUMMARY_METRICS.map(({ key, label }) => {
    const row = summaryRowByMetric(summaryRows, key);
    const isOrders = key === 'orders' || key === 'newCustomers';
    const isPct = key === 'profitability';
    const isAov = key === 'aov';
    const fmtVal = (v) => {
      if (!isNum(v)) return '';
      if (isOrders) return fmtInt(v);
      if (isPct) return fmtPct1(v);
      if (isAov) return fmtUsd1(v);
      return fmtUsd1(v);
    };
    return [
      label,
      fmtVal(row.pre),
      fmtVal(row.post),
      fmtVal(row.prevspost),
      fmtVal(row.lyPrevspost),
      fmtPct1(row.growthPct),
      fmtPct1(row.lyGrowthPct),
    ];
  }).filter((r) => r.some((c, i) => i > 0 && c !== ''));
}

function legacySummaryTable2Rows(summaryRows) {
  return LEGACY_SUMMARY_METRICS.map(({ key, label }) => {
    const row = summaryRowByMetric(summaryRows, key);
    const isOrders = key === 'orders' || key === 'newCustomers';
    const isPct = key === 'profitability';
    const isAov = key === 'aov';
    const fmtVal = (v) => {
      if (!isNum(v)) return '';
      if (isOrders) return fmtInt(v);
      if (isPct) return fmtPct1(v);
      if (isAov) return fmtUsd1(v);
      return fmtUsd1(v);
    };
    return [
      label,
      fmtVal(row.postLY),
      fmtVal(row.post),
      fmtVal(row.yoy),
      fmtPct1(row.yoyPct),
    ];
  }).filter((r) => r.some((c, i) => i > 0 && c !== ''));
}

function legacyStoreTable1Rows(stores, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant) {
  return (stores || []).map((row) => {
    const idCells = exportStoreIdRowCells(row, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant);
    const storeName = platform === 'combined'
      ? combinedExportStoreName(row, dominantPlatform)
      : (row._isNa ? EXPORT_NA : (String(row.storeName ?? '').trim() || EXPORT_NA));
    if (row._isNa) {
      return [...idCells, storeName, EXPORT_NA, EXPORT_NA, EXPORT_NA, EXPORT_NA, EXPORT_NA, EXPORT_NA];
    }
    return [
      ...idCells,
      storeName,
      fmtUsd1(row.pre_sales),
      fmtUsd1(row.post_sales),
      fmtUsd1(row.sales_prevspost),
      fmtUsd1(row.sales_ly_prevspost),
      fmtPct1(row.sales_growth_pct),
      fmtPct1(row.sales_ly_growth_pct),
    ];
  });
}

function legacyStoreTable2Rows(stores, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant) {
  return (stores || []).map((row) => {
    const idCells = exportStoreIdRowCells(row, platform, dominantPlatform, ddToUeStoreMap, ddStoreIdToMerchant);
    const storeName = platform === 'combined'
      ? combinedExportStoreName(row, dominantPlatform)
      : (row._isNa ? EXPORT_NA : (String(row.storeName ?? '').trim() || EXPORT_NA));
    if (row._isNa) {
      return [...idCells, storeName, EXPORT_NA, EXPORT_NA, EXPORT_NA, EXPORT_NA];
    }
    return [
      ...idCells,
      storeName,
      fmtUsd1(row.postLY_sales),
      fmtUsd1(row.post_sales),
      fmtUsd1(row.sales_yoy),
      fmtPct1(row.sales_yoy_pct),
    ];
  });
}

function appendLegacyTable(rows, title, headers, dataRows) {
  if (!dataRows?.length) return;
  if (rows.length) rows.push([]);
  rows.push([title]);
  rows.push(headers);
  rows.push(...dataRows);
}

function stitchSideBySide(leftRows, rightRows, gapCols = 5) {
  const leftWidth = Math.max(...leftRows.map((r) => r.length), 1);
  const rightWidth = Math.max(...rightRows.map((r) => r.length), 1);
  const height = Math.max(leftRows.length, rightRows.length);
  const out = [];
  for (let i = 0; i < height; i += 1) {
    const left = leftRows[i] || [];
    const right = rightRows[i] || [];
    const paddedLeft = [...left, ...Array(leftWidth - left.length).fill('')];
    out.push([...paddedLeft, ...Array(gapCols).fill(''), ...right]);
  }
  return out;
}

function buildSummaryMetricsBlock(data, config, summaryTables) {
  const combined = summaryTables?.combined || [];
  const sales = summaryRowByMetric(combined, 'sales');
  const orders = summaryRowByMetric(combined, 'orders');
  const payouts = summaryRowByMetric(combined, 'payouts');
  const nc = buildNewCustomersSummary(data, config)?.combined;

  const ddStores = (data.storeTables?.dd || []).length;
  const ueStores = (data.storeTables?.ue || []).length;

  const payoutPerStore = ddStores > 0 ? (payouts?.prevspost || 0) / ddStores : 0;

  const left = [
    ['Summary Metrics'],
    ['Metric', 'Value'],
    ['Active Stores', `DoorDash: ${ddStores}  |  UberEats: ${ueStores}`],
    ['Pre Period', periodLabel(config.ddPreStart || config.uePreStart, config.ddPreEnd || config.uePreEnd)],
    ['Post Period', periodLabel(config.ddPostStart || config.uePostStart, config.ddPostEnd || config.uePostEnd)],
    ['Sales Growth (Pre vs Post)', fmtPct1(sales.growthPct)],
    ['Sales Growth (YoY)', fmtPct1(sales.yoyPct)],
    ['Order Growth', fmtPct1(orders.growthPct)],
    ['New Customer Growth', nc ? fmtPct1(nc.growthPct) : ''],
    ['Payout Δ/Store', fmtUsd1(payoutPerStore)],
    ['Average Markup', ''],
    ['Pre TODC Growth YoY', ''],
  ];
  return left;
}

function buildSummaryTablesSheet(data, config) {
  const nc = buildNewCustomersSummary(data, config);
  const rows = [];
  const left = buildSummaryMetricsBlock(data, config, data.summaryTables);
  const right = buildStoreMappingExportBlock(data, config);
  rows.push(...stitchSideBySide(left, right, 5));

  for (const { key, label } of PLATFORM_SECTIONS) {
    let summary = data.summaryTables?.[key] || [];
    summary = enrichSummaryWithNewCustomers(summary, key === 'combined' ? nc?.combined : key === 'dd' ? nc?.dd : null);
    const t1 = legacySummaryTable1Rows(summary);
    const t2 = legacySummaryTable2Rows(summary);
    if (t1.length) {
      appendLegacyTable(
        rows,
        `${LEGACY_PLATFORM_LABELS[key]} Table 1: Current Year Pre vs Post Analysis`,
        ['Metric', 'Pre', 'Post', 'PrevsPost', 'LastYear Pre vs Post', 'Growth%', 'LY Growth%'],
        t1,
      );
    }
    if (t2.length) {
      appendLegacyTable(
        rows,
        `${LEGACY_PLATFORM_LABELS[key]} Table 2: Year-over-Year Analysis`,
        ['Metric', 'last year-post', 'post', 'YoY', 'YoY%'],
        t2,
      );
    }
  }
  return rows;
}

function buildStoreLevelTablesSheet(data, config) {
  const rows = [];
  const aligned = buildAlignedExportStoreTables(data.storeTables, config?.ddToUeStoreMap || {});
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const tableMap = {
    combined: aligned.combined,
    dd: aligned.dd,
    ue: aligned.ue,
  };

  for (const { key, label } of PLATFORM_SECTIONS) {
    const stores = tableMap[key] || [];
    const t1 = legacyStoreTable1Rows(stores, key, aligned.dominantPlatform, config?.ddToUeStoreMap || {}, ddStoreIdToMerchant);
    const t2 = legacyStoreTable2Rows(stores, key, aligned.dominantPlatform, config?.ddToUeStoreMap || {}, ddStoreIdToMerchant);
    if (t1.length) {
      appendLegacyTable(
        rows,
        `${LEGACY_PLATFORM_LABELS[key]} Table 1: Current Year Pre vs Post Analysis (Store-Level)`,
        legacyStoreHeadersPvp(key),
        t1,
      );
    }
    if (t2.length) {
      appendLegacyTable(
        rows,
        `${LEGACY_PLATFORM_LABELS[key]} Table 2: Year-over-Year Analysis (Store-Level)`,
        legacyStoreHeadersYoy(key),
        t2,
      );
    }
  }
  return rows;
}

function legacyCorpCampaignRows(sourceData, period = 'post') {
  return buildCorpTodcImpactRows(sourceData, period)
    .filter((r) => r.group === 'Corporate' || r.group === 'TODC' || r.group === 'Total')
    .map((r) => [
      r.group,
      fmtUsd2(r.sales),
      fmtInt(r.orders),
      fmtUsd2(r.spend),
      fmtRoas(r.roas),
      fmtUsd2(r.cpo),
      fmtUsd2(r.checkAfterPromo),
    ]);
}

const UE_MARKETING_HEADERS = ['Sales', 'Spend', 'ROAS', 'Cost Per Order', 'Check after Promo'];

function legacyUeMarketingRow(metrics) {
  if (!metrics) return null;
  return [[
    fmtUsd2(metrics.sales),
    fmtUsd2(metrics.spend),
    fmtRoas(metrics.roas),
    fmtUsd2(metrics.cpo),
    fmtUsd2(metrics.checkAfterPromo),
  ]];
}

function appendUeMarketingSections(rows, summary) {
  if (!summary) return;
  const postCombined = legacyUeMarketingRow(summary.combined?.post);
  if (postCombined) {
    appendLegacyTable(rows, 'Uber Eats marketing — Post period (combined)', UE_MARKETING_HEADERS, postCombined);
  }
  const preCombined = legacyUeMarketingRow(summary.combined?.pre);
  if (preCombined) {
    appendLegacyTable(rows, 'Uber Eats marketing — Pre period (combined)', UE_MARKETING_HEADERS, preCombined);
  }
  const promo = legacyUeMarketingRow(summary.promotion?.post);
  if (promo) {
    appendLegacyTable(rows, 'Uber Eats marketing — Promo (post)', UE_MARKETING_HEADERS, promo);
  }
  const ads = legacyUeMarketingRow(summary.sponsored?.post);
  if (ads) {
    appendLegacyTable(rows, 'Uber Eats marketing — Ads (post)', UE_MARKETING_HEADERS, ads);
  }
}

function appendCorpTodcPlatformSections(rows, tables, headers, platformLabel) {
  if (!tables?.combined?.corp) return;
  const combinedPost = legacyCorpCampaignRows(tables.combined, 'post');
  if (combinedPost.length) {
    appendLegacyTable(rows, `Corp vs TODC — ${platformLabel} — Post period (combined)`, headers, combinedPost);
  }
  const combinedPre = legacyCorpCampaignRows(tables.combined, 'pre');
  if (combinedPre.length) {
    appendLegacyTable(rows, `Corp vs TODC — ${platformLabel} — Pre period (combined)`, headers, combinedPre);
  }
  const promoRows = legacyCorpCampaignRows(tables.promotion, 'post');
  if (promoRows.length) {
    appendLegacyTable(rows, `Promotion: Corporate vs TODC — ${platformLabel} (post)`, headers, promoRows);
  }
  const adsRows = legacyCorpCampaignRows(tables.sponsored, 'post');
  if (adsRows.length) {
    appendLegacyTable(rows, `Sponsored Listing: Corporate vs TODC — ${platformLabel} (post)`, headers, adsRows);
  }
}

function buildCorporateVsTodcSheet(data, config) {
  const rows = [];
  const headers = ['Group', 'Sales', 'Orders', 'Spend', 'ROAS', 'Cost Per Order', 'Check after Promo'];
  const scope = buildAnalysisScope(config);

  const marketingTables = resolveMarketingTables(data, config);
  if (marketingTables?.bySource?.combined?.corp) {
    appendCorpTodcPlatformSections(rows, marketingTables.bySource, headers, 'DoorDash');
  }

  if (data.ueFinancial?.length && config.uePostStart && config.uePostEnd) {
    const ueSummary = buildUeMarketingSummary(data.ueFinancial, {
      preStart: config.uePreStart,
      preEnd: config.uePreEnd,
      postStart: config.uePostStart,
      postEnd: config.uePostEnd,
      excludedDates: config.ueExcludedDates || [],
      excludedStores: config.ueExcludedStores || [],
    }, scope);
    appendUeMarketingSections(rows, ueSummary);
  }

  return rows;
}

function legacySlotTable1Rows(slotRows, valueKind = 'usd') {
  const fmtVal = (v) => {
    if (valueKind === 'pct') return fmtPct1(v);
    if (valueKind === 'int') return fmtInt(v);
    if (valueKind === 'usd2') return fmtUsd2(v);
    return fmtUsd1(v);
  };
  return (slotRows || []).map((r) => [
    r.slot,
    getSlotTimeRange(r.slot),
    fmtVal(r.pre),
    fmtVal(r.post),
    fmtVal(r.prevspost),
    fmtPct1(r.growthPct),
    fmtVal(r.lyPrevspost),
    fmtPct1(r.lyGrowthPct),
  ]);
}

function legacySlotTable2Rows(slotRows) {
  return (slotRows || []).map((r) => [
    r.slot,
    getSlotTimeRange(r.slot),
    fmtUsd1(r.postLY ?? r.pre),
    fmtUsd1(r.post),
    fmtUsd1(r.yoy ?? r.prevspost),
    fmtPct1(r.yoyPct ?? r.growthPct),
  ]);
}

function buildPlatformSlotWiseSheet(data, config, platform) {
  const rawData = platform === 'ue' ? data.ueFinancial : data.ddFinancial;
  const prefix = platform === 'ue' ? 'ue' : 'dd';
  if (!rawData?.length) return [];

  const analysis = buildSlotAnalysis(rawData, {
    preStart: config[`${prefix}PreStart`],
    preEnd: config[`${prefix}PreEnd`],
    postStart: config[`${prefix}PostStart`],
    postEnd: config[`${prefix}PostEnd`],
    excludedDates: config[`${prefix}ExcludedDates`] || [],
    excludedStores: config[`${prefix}ExcludedStores`] || [],
    platform,
  });
  if (!analysis) return [];

  const rows = [];
  let tableNum = 1;
  for (const { key, title, valueKind } of SLOT_METRIC_TABLES) {
    const pvp = legacySlotTable1Rows(analysis[`${key}PrePost`], valueKind);
    const yoy = legacySlotTable2Rows(analysis[`${key}YoY`]);
    if (pvp.length) {
      appendLegacyTable(rows, `Table ${tableNum}: ${title} - Pre vs Post`, LEGACY_SLOT_EXPORT_HEADERS_PVP, pvp);
      tableNum += 1;
    }
    if (yoy.length) {
      appendLegacyTable(rows, `Table ${tableNum}: ${title} - Year over Year`, LEGACY_SLOT_EXPORT_HEADERS_YOY, yoy);
      tableNum += 1;
    }
  }
  return rows;
}

function legacyFinancialRow(row) {
  const isPct = String(row.Metric || '').includes('Profitability');
  const fmtVal = (v) => (isPct ? fmtPct1(v) : fmtUsd2(v));
  return [
    row.Metric,
    fmtVal(row.Pre),
    fmtVal(row.Post),
    fmtVal(row['Pre vs Post']),
    fmtPct1(row['Linear Growth%']),
    fmtVal(row['Last Year Pre']),
    fmtVal(row['Last Year Post']),
    fmtVal(row['LY Pre vs Post']),
    fmtPct1(row['LY Growth%']),
    fmtVal(row.YoY),
    fmtPct1(row['YoY%']),
  ];
}

function buildFinancialAggregateSheet(data, config) {
  const table = buildFinancialSummaryTable(data.ddFinancial, data.ueFinancial, config);
  if (!table.length) return [];
  return [
    ['Financial Summary (Aggregate)'],
    ['Metric', 'Pre', 'Post', 'Pre vs Post', 'Linear Growth%', 'Last Year Pre', 'Last Year Post', 'LY Pre vs Post', 'LY Growth%', 'YoY', 'YoY%'],
    ...table.map(legacyFinancialRow),
  ];
}

function buildFinancialBreakdownSheet(data, config) {
  const rows = [];
  const storeIds = [...new Set((data.storeTables?.combined || []).map((s) => s.storeId).filter(Boolean))].sort();
  for (const storeId of storeIds) {
    const table = buildFinancialSummaryTable(data.ddFinancial, data.ueFinancial, config, storeId);
    if (!table.length) continue;
    const merchantLabel = ddMerchantStoreIdFromKey(storeId, data.ddFinancial);
    appendLegacyTable(
      rows,
      `Store ${merchantLabel}`,
      ['Metric', 'Pre', 'Post', 'Pre vs Post', 'Linear Growth%', 'Last Year Pre', 'Last Year Post', 'LY Pre vs Post', 'LY Growth%', 'YoY', 'YoY%'],
      table.map(legacyFinancialRow),
    );
  }
  return rows;
}

function insightDirection(change) {
  if (change > 0) return 'Gain';
  if (change < 0) return 'Loss';
  return 'No Change';
}

function buildInsightsSheet(data, config) {
  const rows = [['Key Insights'], []];
  const combined = data.summaryTables?.combined || [];
  const nc = buildNewCustomersSummary(data, config)?.combined;
  let summaryRows = enrichSummaryWithNewCustomers(combined, nc);

  const platformInsights = LEGACY_SUMMARY_METRICS.map(({ key, label }) => {
    const row = summaryRowByMetric(summaryRows, key);
    const change = (row.post || 0) - (row.pre || 0);
    const pct = row.pre ? (change / row.pre) * 100 : 0;
    return {
      Metric: label,
      Pre: row.pre ?? '',
      Post: row.post ?? '',
      Change: change,
      'Change %': fmtPct1(pct),
      Direction: insightDirection(change),
    };
  }).sort((a, b) => Math.abs(b.Change) - Math.abs(a.Change));

  appendLegacyTable(rows, 'Platform – Major Loss/Gain (Pre vs Post)', ['Metric', 'Pre', 'Post', 'Change', 'Change %', 'Direction'], platformInsights.map((r) => [
    r.Metric, r.Pre, r.Post, Number(r.Change.toFixed(1)), r['Change %'], r.Direction,
  ]));

  const stores = data.storeTables?.combined || [];
  const ddToUe = config?.ddToUeStoreMap || {};
  const aligned = buildAlignedExportStoreTables(data.storeTables, ddToUe);
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const storeInsights = stores.map((s) => {
    const change = (s.post_sales || 0) - (s.pre_sales || 0);
    const pct = s.pre_sales ? (change / s.pre_sales) * 100 : 0;
    const [ddMerchantStoreId, ueStoreId] = exportStoreIdCells(
      s, 'combined', aligned.dominantPlatform, ddToUe, ddStoreIdToMerchant,
    );
    return ['Combined', ddMerchantStoreId, ueStoreId, Number((s.pre_sales || 0).toFixed(1)), Number((s.post_sales || 0).toFixed(1)), Number(change.toFixed(1)), fmtPct1(pct), insightDirection(change)];
  }).sort((a, b) => Math.abs(b[5]) - Math.abs(a[5]));
  appendLegacyTable(rows, 'Stores – Major Loss/Gain (Sales Pre vs Post)', ['Source', 'Merchant Store ID', 'Store ID (UE)', 'Pre', 'Post', 'Change', 'Change %', 'Direction'], storeInsights);

  const slotAnalysis = data.ddFinancial?.length
    ? buildSlotAnalysis(data.ddFinancial, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart: config.ddPostStart,
      postEnd: config.ddPostEnd,
      excludedDates: config.ddExcludedDates || [],
      excludedStores: config.ddExcludedStores || [],
      platform: 'dd',
    })
    : null;
  const slotInsights = (slotAnalysis?.salesPrePost || []).map((r) => {
    const change = (r.post || 0) - (r.pre || 0);
    const pct = r.pre ? (change / r.pre) * 100 : 0;
    return [r.slot, getSlotTimeRange(r.slot), Number((r.pre || 0).toFixed(1)), Number((r.post || 0).toFixed(1)), Number(change.toFixed(1)), fmtPct1(pct), insightDirection(change)];
  }).sort((a, b) => Math.abs(b[4]) - Math.abs(a[4]));
  if (slotInsights.length) {
    appendLegacyTable(rows, 'Slots – Major Loss/Gain (Sales Pre vs Post)', ['Slot', 'Slot time', 'Pre', 'Post', 'Change', 'Change %', 'Direction'], slotInsights);
  }

  const ddSales = summaryRowByMetric(data.summaryTables?.dd || [], 'sales');
  const ueSales = summaryRowByMetric(data.summaryTables?.ue || [], 'sales');
  const platformCompare = [
    ['DoorDash', Number((ddSales.pre || 0).toFixed(1)), Number((ddSales.post || 0).toFixed(1)), Number(((ddSales.post || 0) - (ddSales.pre || 0)).toFixed(1)), fmtPct1(ddSales.growthPct), insightDirection((ddSales.post || 0) - (ddSales.pre || 0))],
    ['UberEats', Number((ueSales.pre || 0).toFixed(1)), Number((ueSales.post || 0).toFixed(1)), Number(((ueSales.post || 0) - (ueSales.pre || 0)).toFixed(1)), fmtPct1(ueSales.growthPct), insightDirection((ueSales.post || 0) - (ueSales.pre || 0))],
  ];
  appendLegacyTable(rows, 'Post Period – Major Loss/Gain by Platform', ['Platform', 'Pre Period Sales', 'Post Period Sales', 'Change', 'Change %', 'Direction'], platformCompare);

  return rows;
}

/** @returns {{ name: string, rows: string[][] }[]} */
export function buildLegacyExportSheets(data, config) {
  return [
    { name: 'Summary Tables', rows: buildSummaryTablesSheet(data, config) },
    { name: 'Store-Level Tables', rows: buildStoreLevelTablesSheet(data, config) },
    { name: 'Corporate vs TODC', rows: buildCorporateVsTodcSheet(data, config) },
    { name: 'DD-slotWise', rows: buildPlatformSlotWiseSheet(data, config, 'dd') },
    { name: 'UE-slotWise', rows: buildPlatformSlotWiseSheet(data, config, 'ue') },
    { name: 'DD Financial-Aggregate', rows: buildFinancialAggregateSheet(data, config) },
    { name: 'DD Financial Breakdown', rows: buildFinancialBreakdownSheet(data, config) },
    { name: 'Insights', rows: buildInsightsSheet(data, config) },
  ];
}
