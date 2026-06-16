import { startOfDay, endOfDay, subYears } from 'date-fns';
import { filterExcludedDates, filterExcludedStores } from './aggregator';
import { resolveCanonStoreId, buildAnalysisScope } from '../utils/abStoreFilter';
import { classifyMarketingRow, buildMarketingStoreResolver } from '../utils/marketingStoreMatch';

export const WOW_TABLE_METRICS = [
  { key: 'sales', label: 'Sales', kind: 'usd' },
  { key: 'payouts', label: 'Payouts', kind: 'usd' },
  { key: 'orders', label: 'Orders', kind: 'int' },
  { key: 'aov', label: 'AOV', kind: 'usd2' },
  { key: 'newCustomers', label: 'New Customers', kind: 'int' },
  { key: 'adsSpend', label: 'Ads Spend', kind: 'usd' },
  { key: 'promoSpend', label: 'Promo Spend', kind: 'usd' },
];

function round2(n) {
  return Math.round(n * 100) / 100;
}

function passesScope(row, platform, storeScope, scope, storeIdField = 'storeId') {
  const canon = resolveCanonStoreId(row[storeIdField], platform, scope.ddToUeStoreMap);
  if (!canon) return false;
  if (scope.includedIds?.size > 0 && !scope.includedIds.has(canon)) return false;
  if (storeScope === 'total') return true;
  if (storeScope === 'A' || storeScope === 'B') {
    return String(scope.tagMap?.[canon] || '').trim() === storeScope;
  }
  return canon === storeScope;
}

function filterRows(rows, platform, config, scope, storeScope) {
  if (!rows?.length) return [];
  const excludedStores = platform === 'dd' ? config.ddExcludedStores : config.ueExcludedStores;
  const excludedDates = platform === 'dd' ? config.ddExcludedDates : config.ueExcludedDates;
  let filtered = filterExcludedStores(rows, 'storeId', excludedStores || []);
  filtered = filterExcludedDates(filtered, 'date', excludedDates || []);
  return filtered.filter((row) => passesScope(row, platform, storeScope, scope));
}

function inRange(date, start, end) {
  const d = startOfDay(date);
  return d >= startOfDay(start) && d <= endOfDay(end);
}

function aggregateDdFinancial(rows, start, end) {
  const rangeStart = startOfDay(start);
  const rangeEnd = endOfDay(end);
  const orderIds = new Set();
  let sales = 0;
  let payouts = 0;
  let adsSpend = 0;
  let promoSpend = 0;

  for (const row of rows) {
    if (!row?.date || !inRange(row.date, rangeStart, rangeEnd)) continue;
    sales += Number(row.subtotal) || 0;
    payouts += Number(row.netTotal) || 0;
    adsSpend += Math.abs(Number(row.marketingFees) || 0);
    promoSpend += Math.abs(Number(row.customerDiscounts) || 0);
    if (row.orderId) orderIds.add(row.orderId);
  }

  const orders = orderIds.size;
  return {
    sales: round2(sales),
    payouts: round2(payouts),
    orders,
    aov: orders > 0 ? round2(sales / orders) : 0,
    adsSpend: round2(adsSpend),
    promoSpend: round2(promoSpend),
    newCustomers: 0,
  };
}

function aggregateUeFinancial(rows, start, end) {
  const rangeStart = startOfDay(start);
  const rangeEnd = endOfDay(end);
  const orderIds = new Set();
  let sales = 0;
  let payouts = 0;
  let promoSpend = 0;
  let adsSpend = 0;
  let newCustomers = 0;

  for (const row of rows) {
    if (!row?.date || !inRange(row.date, rangeStart, rangeEnd)) continue;
    sales += Number(row.sales) || 0;
    payouts += Number(row.totalPayout) || 0;
    promoSpend += Math.abs(Number(row.offers) || 0) + Math.abs(Number(row.deliveryOffers) || 0);
    adsSpend += Number(row.adSpend) || 0;
    newCustomers += Number(row.newCustomers) || 0;
    if (row.orderId) orderIds.add(row.orderId);
  }

  const orders = orderIds.size;
  return {
    sales: round2(sales),
    payouts: round2(payouts),
    orders,
    aov: orders > 0 ? round2(sales / orders) : 0,
    adsSpend: round2(adsSpend),
    promoSpend: round2(promoSpend),
    newCustomers: Math.round(newCustomers),
  };
}

function aggregateDdPromotion(rows, start, end, scope, storeScope, resolveMarketingStoreId) {
  const rangeStart = startOfDay(start);
  const rangeEnd = endOfDay(end);
  let newCustomers = 0;
  for (const row of rows || []) {
    if (!row?.date || !inRange(row.date, rangeStart, rangeEnd)) continue;

    const bucket = classifyMarketingRow(row, scope, resolveMarketingStoreId);
    if (bucket === 'excluded') continue;

    if (storeScope === 'total') {
      // include all non-excluded
    } else if (storeScope === 'A') {
      if (bucket !== 'todc') continue;
    } else if (storeScope === 'B') {
      if (bucket !== 'corp') continue;
    } else {
      const canon = resolveMarketingStoreId(row.storeId);
      if (canon !== storeScope) continue;
    }

    newCustomers += Number(row.newCustomers) || 0;
  }
  return Math.round(newCustomers);
}

function mergePartial(a, b) {
  const orders = (a.orders || 0) + (b.orders || 0);
  const sales = round2((a.sales || 0) + (b.sales || 0));
  return {
    sales,
    payouts: round2((a.payouts || 0) + (b.payouts || 0)),
    orders,
    aov: orders > 0 ? round2(sales / orders) : 0,
    adsSpend: round2((a.adsSpend || 0) + (b.adsSpend || 0)),
    promoSpend: round2((a.promoSpend || 0) + (b.promoSpend || 0)),
    newCustomers: Math.round((a.newCustomers || 0) + (b.newCustomers || 0)),
  };
}

/**
 * Combined / platform-scoped metrics for one inclusive date range.
 */
export function aggregateWowPeriodMetrics({
  ddFinancial,
  ueFinancial,
  ddMarketing,
  config,
  platform = 'combined',
  storeScope = 'total',
  start,
  end,
}) {
  if (!start || !end) {
    return Object.fromEntries(WOW_TABLE_METRICS.map((m) => [m.key, 0]));
  }

  const scope = buildAnalysisScope(config);
  const resolveMarketingStoreId = buildMarketingStoreResolver(ddFinancial);
  let merged = {
    sales: 0,
    payouts: 0,
    orders: 0,
    aov: 0,
    newCustomers: 0,
    adsSpend: 0,
    promoSpend: 0,
  };

  if (platform === 'dd' || platform === 'combined') {
    const ddRows = filterRows(ddFinancial, 'dd', config, scope, storeScope);
    const ddPart = aggregateDdFinancial(ddRows, start, end);
    ddPart.newCustomers = aggregateDdPromotion(
      ddMarketing?.promotion,
      start,
      end,
      scope,
      storeScope,
      resolveMarketingStoreId,
    );
    merged = mergePartial(merged, ddPart);
  }

  if (platform === 'ue' || platform === 'combined') {
    const ueRows = filterRows(ueFinancial, 'ue', config, scope, storeScope);
    const uePart = aggregateUeFinancial(ueRows, start, end);
    merged = mergePartial(merged, uePart);
  }

  return merged;
}

export function compareWowMetric(current, prior) {
  const value = current ?? 0;
  const priorValue = prior != null ? prior : null;
  const delta = priorValue != null ? round2(value - priorValue) : null;
  const growthPct = priorValue != null && priorValue !== 0
    ? round2(((value - priorValue) / priorValue) * 100)
    : null;
  return { value, prior: priorValue, delta, growthPct };
}

export function buildMetricComparisons(currentMetrics, priorMetrics, lyMetrics) {
  const out = {};
  for (const { key } of WOW_TABLE_METRICS) {
    out[key] = {
      ...compareWowMetric(currentMetrics[key], priorMetrics?.[key]),
      ly: lyMetrics?.[key] ?? null,
      ...(() => {
        const yoy = compareWowMetric(currentMetrics[key], lyMetrics?.[key]);
        return { yoyDelta: yoy.delta, yoyPct: yoy.growthPct };
      })(),
    };
  }
  return out;
}

export function lyRangeForWeek(weekStart, weekEnd) {
  return {
    start: subYears(weekStart, 1),
    end: subYears(weekEnd, 1),
  };
}
