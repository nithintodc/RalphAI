import { filterByDateRange, filterExcludedDates, filterExcludedStores } from './aggregator';
import { getLastYearDates } from '../utils/dateUtils';

const FINANCIAL_METRICS = [
  'Sales',
  'DD Sales',
  'DD Commission',
  'DD Ads Spend',
  'DD Promo Spend',
  'DD Error Charges',
  'DD Adjustments',
  'DD Payouts',
  'DD Profitability%',
  'UE Sales',
  'UE Error Charges',
  'UE Promo',
  'UE Commissions',
  'UE Payouts',
  'UE Profitability%',
];

function round2(n) {
  return Math.round(n * 100) / 100;
}

function round1(n) {
  return Math.round(n * 10) / 10;
}

function filterWindow(data, start, end, excludedDates, excludedStores, storeId) {
  if (!data?.length || !start || !end) return [];
  let filtered = filterByDateRange(data, 'date', start, end);
  filtered = filterExcludedDates(filtered, 'date', excludedDates);
  filtered = filterExcludedStores(filtered, 'storeId', excludedStores);
  if (storeId != null && storeId !== '') {
    const sid = String(storeId);
    filtered = filtered.filter((r) => String(r.storeId) === sid);
  }
  return filtered;
}

function loadWindows(data, preStart, preEnd, postStart, postEnd, excludedDates, excludedStores, storeId) {
  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);
  return {
    pre: filterWindow(data, preStart, preEnd, excludedDates, excludedStores, storeId),
    post: filterWindow(data, postStart, postEnd, excludedDates, excludedStores, storeId),
    lyPre: filterWindow(data, lyPre.start, lyPre.end, excludedDates, excludedStores, storeId),
    lyPost: filterWindow(data, lyPost.start, lyPost.end, excludedDates, excludedStores, storeId),
  };
}

/** App2.0 / Monthly Reporter parity: `_compute_window_metrics` */
function computeWindowMetrics(ddRows, ueRows) {
  let ddSales = 0;
  let ddComm = 0;
  let ddAds = 0;
  let ddPromo = 0;
  let ddErrors = 0;
  let ddAdj = 0;
  let ddPayouts = 0;

  for (const r of ddRows || []) {
    ddSales += Number(r.subtotal) || 0;
    ddComm += Math.abs(Number(r.commission) || 0);
    ddAds += Math.abs(Number(r.marketingFees) || 0);
    ddPromo += Math.abs(Number(r.customerDiscounts) || 0);
    ddErrors += Math.abs(Number(r.errorCharges) || 0);
    ddAdj += Math.abs(Number(r.adjustments) || 0);
    ddPayouts += Number(r.netTotal) || 0;
  }

  let ueSales = 0;
  let ueErr = 0;
  let uePromo = 0;
  let ueComm = 0;
  let uePay = 0;

  for (const r of ueRows || []) {
    ueSales += Number(r.sales) || 0;
    ueErr += Number(r.orderErrorAdjustments) || 0;
    uePromo += Number(r.offers) || 0;
    ueComm += Math.abs(Number(r.marketplaceFee) || 0);
    uePay += Number(r.totalPayout) || 0;
  }

  const ddProf = ddSales !== 0 ? (ddPayouts / ddSales) * 100 : 0;
  const ueProf = ueSales !== 0 ? (uePay / ueSales) * 100 : 0;

  return {
    Sales: ddSales + ueSales,
    'DD Sales': ddSales,
    'DD Commission': ddComm,
    'DD Ads Spend': ddAds,
    'DD Promo Spend': ddPromo,
    'DD Error Charges': ddErrors,
    'DD Adjustments': ddAdj,
    'DD Payouts': ddPayouts,
    'DD Profitability%': ddProf,
    'UE Sales': ueSales,
    'UE Error Charges': ueErr,
    'UE Promo': uePromo,
    'UE Commissions': ueComm,
    'UE Payouts': uePay,
    'UE Profitability%': ueProf,
  };
}

function buildSummaryRows(preM, postM, lyPreM, lyPostM) {
  return FINANCIAL_METRICS.map((m) => {
    const pre = preM[m] ?? 0;
    const post = postM[m] ?? 0;
    const lyPre = lyPreM[m] ?? 0;
    const lyPost = lyPostM[m] ?? 0;
    const pvp = post - pre;
    const lyPvp = lyPost - lyPre;
    const yoy = post - lyPost;
    const linear = pre !== 0 ? (pvp / pre) * 100 : 0;
    const lyLinear = lyPre !== 0 ? (lyPvp / lyPre) * 100 : 0;
    const yoyG = lyPost !== 0 ? (yoy / lyPost) * 100 : 0;
    return {
      Metric: m,
      Pre: round2(pre),
      Post: round2(post),
      'Pre vs Post': round2(pvp),
      'Linear Growth%': round1(linear),
      'Last Year Pre': round2(lyPre),
      'Last Year Post': round2(lyPost),
      'LY Pre vs Post': round2(lyPvp),
      'LY Linear %': round1(lyLinear),
      YoY: round2(yoy),
      'YoY%': round1(yoyG),
    };
  });
}

/**
 * Financial Summary table (App2.0 `build_financial_summary_table`).
 * Uses parsed Super App financial rows and config date windows.
 */
export function buildFinancialSummaryTable(ddFinancial, ueFinancial, config, storeId = null) {
  const {
    ddPreStart,
    ddPreEnd,
    ddPostStart,
    ddPostEnd,
    uePreStart,
    uePreEnd,
    uePostStart,
    uePostEnd,
    ddExcludedDates = [],
    ueExcludedDates = [],
    ddExcludedStores = [],
    ueExcludedStores = [],
  } = config || {};

  if (!ddPreStart || !ddPreEnd || !ddPostStart || !ddPostEnd) {
    return [];
  }

  const ddW = loadWindows(
    ddFinancial,
    ddPreStart,
    ddPreEnd,
    ddPostStart,
    ddPostEnd,
    ddExcludedDates,
    ddExcludedStores,
    storeId,
  );

  const uePreS = uePreStart || ddPreStart;
  const uePreE = uePreEnd || ddPreEnd;
  const uePostS = uePostStart || ddPostStart;
  const uePostE = uePostEnd || ddPostEnd;

  const ueW = loadWindows(
    ueFinancial,
    uePreS,
    uePreE,
    uePostS,
    uePostE,
    ueExcludedDates,
    ueExcludedStores,
    storeId,
  );

  const preM = computeWindowMetrics(ddW.pre, ueW.pre);
  const postM = computeWindowMetrics(ddW.post, ueW.post);
  const lyPreM = computeWindowMetrics(ddW.lyPre, ueW.lyPre);
  const lyPostM = computeWindowMetrics(ddW.lyPost, ueW.lyPost);

  return buildSummaryRows(preM, postM, lyPreM, lyPostM);
}

export function isProfitabilityMetric(metric) {
  return metric === 'DD Profitability%' || metric === 'UE Profitability%';
}
