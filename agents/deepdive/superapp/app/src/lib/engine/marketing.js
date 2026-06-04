import { filterByDateRange, filterExcludedDates, groupBy } from './aggregator';
import { safeDivide, growthPct, round } from '../utils/safeMath';

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

function filterPeriod(promotionData, sponsoredData, start, end, excludedDates) {
  let promo = filterByDateRange(promotionData || [], 'date', start, end);
  promo = filterExcludedDates(promo, 'date', excludedDates);
  let sponsored = filterByDateRange(sponsoredData || [], 'date', start, end);
  sponsored = filterExcludedDates(sponsored, 'date', excludedDates);
  const allData = [...promo, ...sponsored];
  const corp = calcGroup(allData.filter(r => !r.isSelfServe));
  const todc = calcGroup(allData.filter(r => r.isSelfServe));
  const total = calcGroup(allData);
  return { corp: { label: 'Corporate', ...corp }, todc: { label: 'TODC', ...todc }, total: { label: 'Total', ...total } };
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
  return { corp: delta('corp'), todc: delta('todc'), total: delta('total') };
}

export function buildCorpVsTodcTable(promotionData, sponsoredData, postStart, postEnd, excludedDates = []) {
  return filterPeriod(promotionData, sponsoredData, postStart, postEnd, excludedDates);
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
    total: buildExtendedGroupRow(preTable, postTable, lyPreTable, lyPostTable, 'total'),
  };
}

function buildMultiPeriodForSource(promotionData, sponsoredData, dateConfig) {
  const {
    preStart, preEnd, postStart, postEnd, excludedDates = [],
  } = dateConfig;

  const hasPre = !!(preStart && preEnd);
  const postTable = filterPeriod(promotionData, sponsoredData, postStart, postEnd, excludedDates);
  const preTable = hasPre ? filterPeriod(promotionData, sponsoredData, preStart, preEnd, excludedDates) : null;
  const lyPostTable = filterPeriod(
    promotionData,
    sponsoredData,
    shiftYear(postStart),
    shiftYear(postEnd),
    excludedDates,
  );
  const lyPreTable = hasPre
    ? filterPeriod(
      promotionData,
      sponsoredData,
      shiftYear(preStart),
      shiftYear(preEnd),
      excludedDates,
    )
    : null;

  const merged = mergeMultiPeriod(preTable, postTable, lyPreTable, lyPostTable);
  return { ...merged, meta: { hasPre } };
}

/**
 * @param {object} dateConfig — { preStart, preEnd, postStart, postEnd, excludedDates }
 *   Pre window optional; if missing, Pre / LY Pre / ΔPvP columns are zeroed (set Pre period for PvP).
 */
export function buildCorpVsTodcBySource(promotionData, sponsoredData, dateConfig) {
  return {
    promotion: buildMultiPeriodForSource(promotionData, [], dateConfig),
    sponsored: buildMultiPeriodForSource([], sponsoredData, dateConfig),
    combined: buildMultiPeriodForSource(promotionData, sponsoredData, dateConfig),
  };
}

export function buildCorpVsTodcPrePost(promotionData, sponsoredData, preStart, preEnd, postStart, postEnd, excludedDates = []) {
  const buildForSource = (promo, spons) => {
    const pre = filterPeriod(promo, spons, preStart, preEnd, excludedDates);
    const post = filterPeriod(promo, spons, postStart, postEnd, excludedDates);
    return { pre, post, compare: addDeltas(pre, post) };
  };
  return {
    combined: buildForSource(promotionData, sponsoredData),
    promotion: buildForSource(promotionData, []),
    sponsored: buildForSource([], sponsoredData),
  };
}

export function buildCampaignTable(promotionData, sponsoredData, postStart, postEnd) {
  const promo = filterByDateRange(promotionData || [], 'date', postStart, postEnd);
  const sponsored = filterByDateRange(sponsoredData || [], 'date', postStart, postEnd);
  const all = [...promo, ...sponsored];

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
