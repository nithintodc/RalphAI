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

export const DD_BREAKDOWN_LINES = [
  { key: 'DD Sales', label: 'Sales', isSales: true },
  { key: 'DD Commission', label: 'Commission' },
  { key: 'DD Ads Spend', label: 'Ads spend' },
  { key: 'DD Promo Spend', label: 'Promo spend' },
  { key: 'DD Error Charges', label: 'Error charges' },
  { key: 'DD Adjustments', label: 'Adjustments' },
  { key: 'DD Payouts', label: 'Payouts' },
  { key: 'DD Profitability%', label: 'Profitability %', isProfitability: true },
];

export const UE_BREAKDOWN_LINES = [
  { key: 'UE Sales', label: 'Sales', isSales: true },
  { key: 'UE Error Charges', label: 'Error charges' },
  { key: 'UE Promo', label: 'Promo' },
  { key: 'UE Commissions', label: 'Commissions' },
  { key: 'UE Payouts', label: 'Payouts' },
  { key: 'UE Profitability%', label: 'Profitability %', isProfitability: true },
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

function computeDdWindowMetrics(ddRows) {
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

  const ddProf = ddSales !== 0 ? (ddPayouts / ddSales) * 100 : 0;

  return {
    'DD Sales': ddSales,
    'DD Commission': ddComm,
    'DD Ads Spend': ddAds,
    'DD Promo Spend': ddPromo,
    'DD Error Charges': ddErrors,
    'DD Adjustments': ddAdj,
    'DD Payouts': ddPayouts,
    'DD Profitability%': ddProf,
  };
}

function computeUeWindowMetrics(ueRows) {
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

  const ueProf = ueSales !== 0 ? (uePay / ueSales) * 100 : 0;

  return {
    'UE Sales': ueSales,
    'UE Error Charges': ueErr,
    'UE Promo': uePromo,
    'UE Commissions': ueComm,
    'UE Payouts': uePay,
    'UE Profitability%': ueProf,
  };
}

/** App2.0 / Monthly Reporter parity: `_compute_window_metrics` */
function computeWindowMetrics(ddRows, ueRows) {
  const dd = computeDdWindowMetrics(ddRows);
  const ue = computeUeWindowMetrics(ueRows);
  return {
    Sales: (dd['DD Sales'] || 0) + (ue['UE Sales'] || 0),
    ...dd,
    ...ue,
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

function buildPeriodTableRows(lines, metrics) {
  const salesLine = lines.find((l) => l.isSales);
  const salesVal = salesLine ? (metrics[salesLine.key] ?? 0) : 0;

  return lines.map((line) => {
    const value = metrics[line.key] ?? 0;
    let sharePct = null;
    if (line.isSales) sharePct = salesVal ? 100 : null;
    else if (!line.isProfitability && salesVal) sharePct = round1((value / salesVal) * 100);

    return {
      metric: line.label,
      value: line.isProfitability ? round1(value) : round2(value),
      sharePct,
      isProfitability: !!line.isProfitability,
    };
  });
}

function buildPvpTableRows(lines, preM, postM) {
  return lines.map((line) => {
    const pre = preM[line.key] ?? 0;
    const post = postM[line.key] ?? 0;
    let growthPct = null;
    if (line.isProfitability) {
      growthPct = round1(post - pre);
    } else if (pre !== 0) {
      growthPct = round1(((post - pre) / pre) * 100);
    }
    return {
      metric: line.label,
      pre: line.isProfitability ? round1(pre) : round2(pre),
      post: line.isProfitability ? round1(post) : round2(post),
      growthPct,
      isProfitability: !!line.isProfitability,
    };
  });
}

function buildYoyTableRows(lines, lyPostM, postM) {
  return lines.map((line) => {
    const lyPost = lyPostM[line.key] ?? 0;
    const post = postM[line.key] ?? 0;
    let yoyPct = null;
    if (line.isProfitability) {
      yoyPct = round1(post - lyPost);
    } else if (lyPost !== 0) {
      yoyPct = round1(((post - lyPost) / lyPost) * 100);
    }
    return {
      metric: line.label,
      lyPost: line.isProfitability ? round1(lyPost) : round2(lyPost),
      post: line.isProfitability ? round1(post) : round2(post),
      yoyPct,
      isProfitability: !!line.isProfitability,
    };
  });
}

function buildPlatformSection(platform, lines, windows, computeMetrics) {
  const preM = computeMetrics(windows.pre);
  const postM = computeMetrics(windows.post);
  const lyPreM = computeMetrics(windows.lyPre);
  const lyPostM = computeMetrics(windows.lyPost);

  return {
    platform,
    pre: buildPeriodTableRows(lines, preM),
    post: buildPeriodTableRows(lines, postM),
    lyPre: buildPeriodTableRows(lines, lyPreM),
    lyPost: buildPeriodTableRows(lines, lyPostM),
    pvp: buildPvpTableRows(lines, preM, postM),
    yoy: buildYoyTableRows(lines, lyPostM, postM),
  };
}

/**
 * DoorDash + Uber Eats breakdown sections (separate tables per platform).
 */
export function buildPlatformFinancialBreakdowns(ddFinancial, ueFinancial, config, storeId = null) {
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

  const sections = [];

  if (ddFinancial?.length && ddPreStart && ddPreEnd && ddPostStart && ddPostEnd) {
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
    sections.push(buildPlatformSection('dd', DD_BREAKDOWN_LINES, ddW, computeDdWindowMetrics));
  }

  const uePreS = uePreStart || ddPreStart;
  const uePreE = uePreEnd || ddPreEnd;
  const uePostS = uePostStart || ddPostStart;
  const uePostE = uePostEnd || ddPostEnd;

  if (ueFinancial?.length && uePreS && uePreE && uePostS && uePostE) {
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
    sections.push(buildPlatformSection('ue', UE_BREAKDOWN_LINES, ueW, computeUeWindowMetrics));
  }

  return sections;
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
  return metric === 'DD Profitability%' || metric === 'UE Profitability%' || metric === 'Profitability %';
}
