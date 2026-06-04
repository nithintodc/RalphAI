import { filterByDateRange, filterExcludedDates } from './aggregator';
import { getLastYearDates } from '../utils/dateUtils';
import { round, cleanInfinity, safeDivide } from '../utils/safeMath';

function windowTotal(rows, start, end, excludedDates) {
  if (!rows?.length || !start || !end) return 0;
  let filtered = filterByDateRange(rows, 'date', start, end);
  filtered = filterExcludedDates(filtered, 'date', excludedDates || []);
  return filtered.reduce((s, r) => s + (Number(r.newCustomers) || 0), 0);
}

function buildWindowTotals(rows, cfg) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [] } = cfg;
  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);
  return {
    pre: windowTotal(rows, preStart, preEnd, excludedDates),
    post: windowTotal(rows, postStart, postEnd, excludedDates),
    preLY: windowTotal(rows, lyPre.start, lyPre.end, excludedDates),
    postLY: windowTotal(rows, lyPost.start, lyPost.end, excludedDates),
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
 * DD uses all promotion rows in range (not filtered by financial store selection).
 */
export function buildNewCustomersSummary(data, config) {
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
  const ddRow = promo?.length && ddCfg.preStart
    ? totalsToSummaryRow(buildWindowTotals(promo, ddCfg))
    : null;

  const ueFin = data?.ueFinancial;
  const ueRow = ueFin?.length && ueCfg.preStart
    ? totalsToSummaryRow(buildWindowTotals(ueFin, ueCfg))
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
