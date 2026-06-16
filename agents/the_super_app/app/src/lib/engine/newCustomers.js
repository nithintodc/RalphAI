import { filterByDateRange, filterExcludedDates } from './aggregator';
import { getLastYearDates } from '../utils/dateUtils';
import { round, cleanInfinity, safeDivide } from '../utils/safeMath';
import { buildAnalysisScope } from '../utils/abStoreFilter';
import { classifyMarketingRow, buildMarketingStoreResolver } from '../utils/marketingStoreMatch';

function passesIncludedScope(canon, scope) {
  if (!canon) return false;
  if (scope.includedIds?.size > 0 && !scope.includedIds.has(canon)) return false;
  return true;
}

function windowTotalMarketing(rows, start, end, excludedDates, scope, resolveMarketingStoreId) {
  if (!rows?.length || !start || !end) return 0;
  let filtered = filterByDateRange(rows, 'date', start, end);
  filtered = filterExcludedDates(filtered, 'date', excludedDates || []);

  return filtered.reduce((sum, row) => {
    const bucket = classifyMarketingRow(row, scope, resolveMarketingStoreId);
    if (bucket === 'excluded') return sum;
    return sum + (Number(row.newCustomers) || 0);
  }, 0);
}

function windowTotalUeFinancial(rows, start, end, excludedDates, scope, resolveStoreId) {
  if (!rows?.length || !start || !end) return 0;
  let filtered = filterByDateRange(rows, 'date', start, end);
  filtered = filterExcludedDates(filtered, 'date', excludedDates || []);

  return filtered.reduce((sum, row) => {
    const canon = resolveStoreId(row.storeId);
    if (!passesIncludedScope(canon, scope)) return sum;
    return sum + (Number(row.newCustomers) || 0);
  }, 0);
}

function buildMarketingWindowTotals(rows, cfg, scope, resolveMarketingStoreId) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [] } = cfg;
  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);
  const count = (s, e) => windowTotalMarketing(rows, s, e, excludedDates, scope, resolveMarketingStoreId);
  return {
    pre: preStart && preEnd ? count(preStart, preEnd) : 0,
    post: count(postStart, postEnd),
    preLY: preStart && preEnd ? count(lyPre.start, lyPre.end) : 0,
    postLY: count(lyPost.start, lyPost.end),
  };
}

function buildUeWindowTotals(rows, cfg, scope, resolveStoreId) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [] } = cfg;
  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);
  const count = (s, e) => windowTotalUeFinancial(rows, s, e, excludedDates, scope, resolveStoreId);
  return {
    pre: preStart && preEnd ? count(preStart, preEnd) : 0,
    post: count(postStart, postEnd),
    preLY: preStart && preEnd ? count(lyPre.start, lyPre.end) : 0,
    postLY: count(lyPost.start, lyPost.end),
  };
}

function totalsToSummaryRow(totals) {
  const { pre, post, preLY, postLY } = totals;
  if (!pre && !post && !preLY && !postLY) return null;
  const prevspost = post - pre;
  const lyPrevspost = postLY - preLY;
  const yoy = post - postLY;
  return {
    metric: 'newCustomers',
    pre: round(pre),
    post: round(post),
    preLY: round(preLY),
    postLY: round(postLY),
    prevspost: round(prevspost),
    lyPrevspost: round(lyPrevspost),
    yoy: round(yoy),
    growthPct: round(cleanInfinity(safeDivide(prevspost, pre) * 100)),
    lyGrowthPct: round(cleanInfinity(safeDivide(lyPrevspost, preLY) * 100)),
    yoyPct: round(cleanInfinity(safeDivide(yoy, postLY) * 100)),
  };
}

/**
 * Combined DD (marketing promotion) + UE (financial "New customers" column) totals per window.
 * DD promotion rows are mapped to store tags via the store map (A=TODC, B=Non-TODC).
 */
export function buildNewCustomersSummary(data, config) {
  const scope = buildAnalysisScope(config);
  const resolveMarketingStoreId = buildMarketingStoreResolver(data?.ddFinancial);

  const ddCfg = {
    preStart: config.ddPreStart,
    preEnd: config.ddPreEnd,
    postStart: config.ddPostStart,
    postEnd: config.ddPostEnd,
    excludedDates: config.ddExcludedDates || [],
  };
  const ueCfg = {
    preStart: config.uePreStart,
    preEnd: config.uePreEnd,
    postStart: config.uePostStart,
    postEnd: config.uePostEnd,
    excludedDates: config.ueExcludedDates || [],
  };

  const promo = data?.ddMarketing?.promotion;
  const ddRow = promo?.length && ddCfg.postStart
    ? totalsToSummaryRow(buildMarketingWindowTotals(promo, ddCfg, scope, resolveMarketingStoreId))
    : null;

  const ueFin = data?.ueFinancial;
  const ueRow = ueFin?.length && ueCfg.postStart
    ? totalsToSummaryRow(buildUeWindowTotals(ueFin, ueCfg, scope, resolveMarketingStoreId))
    : null;

  if (!ddRow && !ueRow) return null;

  const combined = totalsToSummaryRow({
    pre: (ddRow?.pre || 0) + (ueRow?.pre || 0),
    post: (ddRow?.post || 0) + (ueRow?.post || 0),
    preLY: (ddRow?.preLY || 0) + (ueRow?.preLY || 0),
    postLY: (ddRow?.postLY || 0) + (ueRow?.postLY || 0),
  });

  return { combined, dd: ddRow, ue: ueRow };
}
