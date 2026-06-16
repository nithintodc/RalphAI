import { filterByDateRange, filterExcludedDates, filterExcludedStores, groupBy } from './aggregator';
import { safeDivide, growthPct, round } from '../utils/safeMath';
import { classifyMarketingRow } from '../utils/marketingStoreMatch';
import { resolveCanonStoreId } from '../utils/abStoreFilter';

const MARKETING_GROUP_KEYS = ['corp', 'todc', 'unmapped', 'total'];

/** Metrics shown in Corp vs TODC summary (order matches UI / export). */
export const MARKETING_SUMMARY_METRICS = [
  { key: 'orders', kind: 'int', label: 'Orders' },
  { key: 'sales', kind: 'usd', label: 'Sales' },
  { key: 'spend', kind: 'usd', label: 'Spend' },
  { key: 'promoAov', kind: 'usd2', label: 'Promo AOV' },
  { key: 'roas', kind: 'roas', label: 'ROAS' },
  { key: 'cpo', kind: 'usd2', label: 'Cost/Order' },
  { key: 'checkAfterPromo', kind: 'usd2', label: 'Check After Promo' },
];

/** Single-period Corp vs TODC / campaign tables (columns in this order). */
export const MARKETING_IMPACT_METRICS = [
  { key: 'sales', kind: 'usd', label: 'Sales' },
  { key: 'orders', kind: 'int', label: 'Orders' },
  { key: 'spend', kind: 'usd', label: 'Spend' },
  { key: 'roas', kind: 'roas', label: 'ROAS' },
  { key: 'cpo', kind: 'usd2', label: 'Cost Per Order' },
  { key: 'checkAfterPromo', kind: 'usd2', label: 'Check after Promo' },
];

export function sliceMarketingPct(n, pct = 0.10) {
  if (!n) return 0;
  return Math.max(1, Math.ceil(n * pct));
}

/** Corp / TODC / Unmapped / Total rows for one period (`pre` or `post`). */
export function buildCorpTodcImpactRows(sourceData, period = 'post') {
  if (!sourceData?.corp) return [];
  const suffix = period === 'pre' ? 'Pre' : 'Post';
  return MARKETING_GROUP_KEYS
    .filter((key) => {
      if (key === 'unmapped') {
        const r = sourceData.unmapped;
        if (!r) return false;
        return MARKETING_IMPACT_METRICS.some((m) => (r[`${m.key}${suffix}`] || 0) !== 0);
      }
      return true;
    })
    .map((key) => {
      const r = sourceData[key];
      return {
        group: r.label,
        sales: r[`sales${suffix}`],
        orders: r[`orders${suffix}`],
        spend: r[`spend${suffix}`],
        roas: r[`roas${suffix}`],
        cpo: r[`cpo${suffix}`],
        checkAfterPromo: r[`checkAfterPromo${suffix}`],
        _total: key === 'total',
      };
    });
}

export function filterCampaignsBySource(campaigns, source) {
  return (campaigns || []).filter((c) => c.source === source);
}

/** `kind`: topRoas | topSpend | poorRoas */
export function buildCampaignHighlights(campaigns, kind, pct = 0.10) {
  const eligible = (campaigns || []).filter((c) => (c.spend || 0) > 0);
  const n = sliceMarketingPct(eligible.length, pct);
  if (!n) return [];
  if (kind === 'topRoas') {
    return [...eligible].sort((a, b) => (b.roas || 0) - (a.roas || 0)).slice(0, n);
  }
  if (kind === 'topSpend') {
    return [...eligible].sort((a, b) => (b.spend || 0) - (a.spend || 0)).slice(0, n);
  }
  if (kind === 'poorRoas') {
    return [...eligible].sort((a, b) => (a.roas || 0) - (b.roas || 0)).slice(0, n);
  }
  return [];
}

function shiftYear(d) {
  const x = new Date(d);
  x.setFullYear(x.getFullYear() - 1);
  return x;
}

function calcGroup(rows) {
  const orders = rows.reduce((s, r) => s + (r.orders || 0), 0);
  const sales = rows.reduce((s, r) => s + (r.sales || 0), 0);
  const spend = rows.reduce((s, r) => s + Math.abs(r.spend || 0), 0);
  const promoAov = round(safeDivide(sales, orders), 2);
  const cpo = round(safeDivide(spend, orders), 2);
  return {
    orders: Math.round(orders),
    sales: round(sales),
    spend: round(spend),
    roas: round(safeDivide(sales, spend), 2),
    cpo,
    promoAov,
    checkAfterPromo: round(promoAov - cpo, 2),
  };
}

function emptyGroup(label) {
  return {
    label,
    orders: 0,
    sales: 0,
    spend: 0,
    roas: 0,
    cpo: 0,
    promoAov: 0,
    checkAfterPromo: 0,
  };
}

function isMarketingRowIncluded(row, scope, resolveMarketingStoreId) {
  if (!scope || !resolveMarketingStoreId) return true;
  return classifyMarketingRow(row, scope, resolveMarketingStoreId) !== 'excluded';
}

/** Corp vs TODC split uses DD `Is self serve campaign` (false=Corporate, true=TODC). Scope only filters stores. */
function filterPeriod(promotionData, sponsoredData, start, end, excludedDates, scope, resolveMarketingStoreId) {
  if (!start || !end) {
    return {
      corp: emptyGroup('Corporate'),
      todc: emptyGroup('TODC'),
      unmapped: emptyGroup('Unmapped'),
      total: emptyGroup('Total'),
    };
  }

  let promo = filterByDateRange(promotionData || [], 'date', start, end);
  promo = filterExcludedDates(promo, 'date', excludedDates);
  let sponsored = filterByDateRange(sponsoredData || [], 'date', start, end);
  sponsored = filterExcludedDates(sponsored, 'date', excludedDates);
  const allData = [...promo, ...sponsored];
  const included = allData.filter((row) => isMarketingRowIncluded(row, scope, resolveMarketingStoreId));

  const bucket = (key) => included.filter((row) => {
    if (key === 'corp') return !row.isSelfServe;
    if (key === 'todc') return !!row.isSelfServe;
    return false;
  });

  const corp = calcGroup(bucket('corp'));
  const todc = calcGroup(bucket('todc'));
  const unmapped = emptyGroup('Unmapped');
  const total = calcGroup(included);

  return {
    corp: { label: 'Corporate', ...corp },
    todc: { label: 'TODC', ...todc },
    unmapped: { label: 'Unmapped', ...unmapped },
    total: { label: 'Total', ...total },
  };
}

function addDeltas(pre, post) {
  const delta = (group) => {
    const preG = pre[group];
    const postG = post[group];
    return {
      ...postG,
      pre_orders: preG.orders, pre_sales: preG.sales, pre_spend: preG.spend, pre_roas: preG.roas, pre_cpo: preG.cpo,
      orders_g: growthPct(preG.orders, postG.orders),
      sales_g: growthPct(preG.sales, postG.sales),
      spend_g: growthPct(preG.spend, postG.spend),
      roas_delta: round(postG.roas - preG.roas, 2),
      cpo_delta: round(postG.cpo - preG.cpo, 2),
    };
  };
  return { corp: delta('corp'), todc: delta('todc'), unmapped: delta('unmapped'), total: delta('total') };
}

export function buildCorpVsTodcTable(promotionData, sponsoredData, postStart, postEnd, excludedDates = [], scope, resolveMarketingStoreId) {
  return filterPeriod(promotionData, sponsoredData, postStart, postEnd, excludedDates, scope, resolveMarketingStoreId);
}

function getGroupField(table, groupKey, field) {
  if (!table || !table[groupKey]) return 0;
  const v = table[groupKey][field];
  return v == null || Number.isNaN(v) ? 0 : v;
}

/** Decimal places for stored period values (orders are integers). */
function metricDecimals(metricKey) {
  if (metricKey === 'orders') return 0;
  if (['promoAov', 'cpo', 'checkAfterPromo', 'roas'].includes(metricKey)) return 2;
  return 0;
}

function snapMetric(metricKey, v) {
  if (metricKey === 'orders') return Math.round(v);
  return round(v, metricDecimals(metricKey));
}

function buildExtendedGroupRow(preTable, postTable, lyPreTable, lyPostTable, groupKey) {
  const label = postTable[groupKey]?.label || lyPostTable[groupKey]?.label || preTable?.[groupKey]?.label || groupKey;
  const row = { label };

  for (const { key } of MARKETING_SUMMARY_METRICS) {
    const pr = getGroupField(preTable, groupKey, key);
    const po = getGroupField(postTable, groupKey, key);
    const lpr = getGroupField(lyPreTable, groupKey, key);
    const lpo = getGroupField(lyPostTable, groupKey, key);
    const pvp = po - pr;
    const yoy = po - lpo;

    row[`${key}Pre`] = snapMetric(key, pr);
    row[`${key}Post`] = snapMetric(key, po);
    row[`${key}LyPre`] = snapMetric(key, lpr);
    row[`${key}LyPost`] = snapMetric(key, lpo);
    row[`${key}Pvp`] = snapMetric(key, pvp);
    row[`${key}PvpPct`] = round(growthPct(pr, po), 1);
    row[`${key}Yoy`] = snapMetric(key, yoy);
    row[`${key}YoyPct`] = round(growthPct(lpo, po), 1);
  }

  return row;
}

function mergeMultiPeriod(preTable, postTable, lyPreTable, lyPostTable) {
  return {
    corp: buildExtendedGroupRow(preTable, postTable, lyPreTable, lyPostTable, 'corp'),
    todc: buildExtendedGroupRow(preTable, postTable, lyPreTable, lyPostTable, 'todc'),
    unmapped: buildExtendedGroupRow(preTable, postTable, lyPreTable, lyPostTable, 'unmapped'),
    total: buildExtendedGroupRow(preTable, postTable, lyPreTable, lyPostTable, 'total'),
  };
}

function buildMultiPeriodForSource(promotionData, sponsoredData, dateConfig, scope, resolveMarketingStoreId) {
  const {
    preStart, preEnd, postStart, postEnd, excludedDates = [],
  } = dateConfig;

  const hasPre = !!(preStart && preEnd);
  const scopeArgs = [scope, resolveMarketingStoreId];
  const postTable = filterPeriod(promotionData, sponsoredData, postStart, postEnd, excludedDates, ...scopeArgs);
  const preTable = hasPre
    ? filterPeriod(promotionData, sponsoredData, preStart, preEnd, excludedDates, ...scopeArgs)
    : null;
  const lyPostTable = filterPeriod(
    promotionData,
    sponsoredData,
    shiftYear(postStart),
    shiftYear(postEnd),
    excludedDates,
    ...scopeArgs,
  );
  const lyPreTable = hasPre
    ? filterPeriod(
      promotionData,
      sponsoredData,
      shiftYear(preStart),
      shiftYear(preEnd),
      excludedDates,
      ...scopeArgs,
    )
    : null;

  const merged = mergeMultiPeriod(preTable, postTable, lyPreTable, lyPostTable);
  return { ...merged, meta: { hasPre } };
}

/**
 * @param {object} dateConfig — { preStart, preEnd, postStart, postEnd, excludedDates }
 * @param {object} scope — from buildAnalysisScope(config)
 * @param {function} resolveMarketingStoreId — from buildMarketingStoreResolver(ddFinancial)
 */
export function buildCorpVsTodcBySource(promotionData, sponsoredData, dateConfig, scope = null, resolveMarketingStoreId = null) {
  return {
    promotion: buildMultiPeriodForSource(promotionData, [], dateConfig, scope, resolveMarketingStoreId),
    sponsored: buildMultiPeriodForSource([], sponsoredData, dateConfig, scope, resolveMarketingStoreId),
    combined: buildMultiPeriodForSource(promotionData, sponsoredData, dateConfig, scope, resolveMarketingStoreId),
  };
}

/** UE financial marketing totals (no Corporate vs TODC on Uber Eats). */
function isUeMarketingRowIncluded(row, scope) {
  if (!scope?.includedIds?.size) return true;
  const canon = resolveCanonStoreId(row?.storeId, 'ue', scope?.ddToUeStoreMap);
  if (!canon) return true;
  return scope.includedIds.has(canon);
}

function ueMarketingSpend(row, kind = 'combined') {
  const promo = Math.abs(row.offers || 0) + Math.abs(row.deliveryOffers || 0);
  const ads = Number(row.adSpend) || 0;
  if (kind === 'promotion') return promo;
  if (kind === 'sponsored') return ads;
  return promo + ads;
}

function prepareUeMarketingRows(ueFinancial, start, end, excludedDates, excludedStores, scope, kind) {
  if (!start || !end || !ueFinancial?.length) return [];
  let rows = filterByDateRange(ueFinancial, 'date', start, end);
  rows = filterExcludedDates(rows, 'date', excludedDates);
  rows = filterExcludedStores(rows, 'storeId', excludedStores);
  return rows.filter((row) => {
    if (!isUeMarketingRowIncluded(row, scope)) return false;
    return ueMarketingSpend(row, kind) > 0;
  });
}

function calcUeMarketingTotals(rows, kind) {
  const orderIds = new Set();
  let sales = 0;
  let spend = 0;
  for (const row of rows) {
    const rowSpend = ueMarketingSpend(row, kind);
    if (rowSpend <= 0) continue;
    spend += rowSpend;
    sales += Number(row.sales) || 0;
    if (row.orderId) orderIds.add(String(row.orderId));
  }
  const orders = orderIds.size;
  const promoAov = round(safeDivide(sales, orders), 2);
  const cpo = round(safeDivide(spend, orders), 2);
  return {
    sales: round(sales),
    spend: round(spend),
    roas: round(safeDivide(sales, spend), 2),
    cpo,
    checkAfterPromo: round(promoAov - cpo, 2),
  };
}

function ueMarketingTotalsForWindow(ueFinancial, start, end, excludedDates, excludedStores, scope, kind) {
  if (!start || !end) return null;
  const rows = prepareUeMarketingRows(ueFinancial, start, end, excludedDates, excludedStores, scope, kind);
  if (!rows.length) return null;
  return calcUeMarketingTotals(rows, kind);
}

/** Uber Eats marketing from financial orders — aggregate promo + ads (no Corp/TODC split). */
export function buildUeMarketingSummary(ueFinancial, dateConfig, scope = null) {
  if (!ueFinancial?.length) return null;
  const {
    preStart, preEnd, postStart, postEnd, excludedDates = [], excludedStores = [],
  } = dateConfig;
  const hasPre = !!(preStart && preEnd);

  return {
    meta: { hasPre },
    combined: {
      post: ueMarketingTotalsForWindow(
        ueFinancial, postStart, postEnd, excludedDates, excludedStores, scope, 'combined',
      ),
      pre: hasPre
        ? ueMarketingTotalsForWindow(
          ueFinancial, preStart, preEnd, excludedDates, excludedStores, scope, 'combined',
        )
        : null,
    },
    promotion: {
      post: ueMarketingTotalsForWindow(
        ueFinancial, postStart, postEnd, excludedDates, excludedStores, scope, 'promotion',
      ),
    },
    sponsored: {
      post: ueMarketingTotalsForWindow(
        ueFinancial, postStart, postEnd, excludedDates, excludedStores, scope, 'sponsored',
      ),
    },
  };
}

export function buildCorpVsTodcPrePost(promotionData, sponsoredData, preStart, preEnd, postStart, postEnd, excludedDates = [], scope = null, resolveMarketingStoreId = null) {
  const buildForSource = (promo, spons) => {
    const scopeArgs = [scope, resolveMarketingStoreId];
    const pre = filterPeriod(promo, spons, preStart, preEnd, excludedDates, ...scopeArgs);
    const post = filterPeriod(promo, spons, postStart, postEnd, excludedDates, ...scopeArgs);
    return { pre, post, compare: addDeltas(pre, post) };
  };
  return {
    combined: buildForSource(promotionData, sponsoredData),
    promotion: buildForSource(promotionData, []),
    sponsored: buildForSource([], sponsoredData),
  };
}

export function buildCampaignTable(promotionData, sponsoredData, postStart, postEnd, scope = null, resolveMarketingStoreId = null) {
  const promo = filterByDateRange(promotionData || [], 'date', postStart, postEnd);
  const sponsored = filterByDateRange(sponsoredData || [], 'date', postStart, postEnd);
  let all = [...promo, ...sponsored];

  if (scope && resolveMarketingStoreId) {
    all = all.filter((row) => classifyMarketingRow(row, scope, resolveMarketingStoreId) !== 'excluded');
  }

  const groups = groupBy(all, 'campaignId');
  const campaigns = [];

  for (const [id, rows] of groups) {
    if (!id) continue;
    const orders = rows.reduce((s, r) => s + (r.orders || 0), 0);
    const sales = rows.reduce((s, r) => s + (r.sales || 0), 0);
    const spend = rows.reduce((s, r) => s + Math.abs(r.spend || 0), 0);
    const promoAov = round(safeDivide(sales, orders), 2);
    const cpo = round(safeDivide(spend, orders), 2);
    campaigns.push({
      campaignId: id,
      campaignName: rows[0]?.campaignName || id,
      source: rows[0]?.source || 'unknown',
      isSelfServe: rows[0]?.isSelfServe,
      orders: Math.round(orders),
      sales: round(sales),
      spend: round(spend),
      roas: round(safeDivide(sales, spend), 2),
      cpo,
      promoAov,
      checkAfterPromo: round(promoAov - cpo, 2),
    });
  }

  return campaigns.sort((a, b) => b.sales - a.sales);
}
