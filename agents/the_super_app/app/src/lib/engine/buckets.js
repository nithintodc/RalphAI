import { filterByDateRange, filterExcludedDates, groupBy } from './aggregator';
import { safeDivide, round } from '../utils/safeMath';

export const BUCKET_RANGES = [
  { label: '$0-5', min: 0, max: 5.99 },
  { label: '$6-10', min: 6, max: 10.99 },
  { label: '$11-15', min: 11, max: 15.99 },
  { label: '$16-20', min: 16, max: 20.99 },
  { label: '$21-25', min: 21, max: 25.99 },
  { label: '$26-30', min: 26, max: 30.99 },
  { label: '$31-35', min: 31, max: 35.99 },
  { label: '$36-40', min: 36, max: 40.99 },
  { label: '$41-45', min: 41, max: 45.99 },
  { label: '$46-50', min: 46, max: 50.99 },
  { label: '$50+', min: 51, max: Infinity },
];

/** Ads fee must be strictly greater than this (|mkt fees| > threshold). */
export const DD_ADS_FEE_THRESHOLD = 0.99;
const ZERO_EPS = 0.005;

export function assignBucket(subtotal) {
  if (subtotal < 0) return null;
  return BUCKET_RANGES.find(b => subtotal >= b.min && subtotal <= b.max)?.label || null;
}

function isMarketingZero(value) {
  return Math.abs(value || 0) < ZERO_EPS;
}

function absMoney(value) {
  return Math.abs(value || 0);
}

/**
 * Sum DD marketing signals for one order (all financial line items).
 * Historical fields are null when that column was not in the export.
 */
export function sumDdOrderMarketingSignals(rows) {
  let marketingFees = 0;
  let customerDiscountsYou = 0;
  let customerDiscountsDoorDash = 0;
  let customerDiscountsThirdParty = 0;
  let marketingFeesHistorical = null;
  let adFeeHistorical = null;
  let hasHistCol = false;
  let hasAdHistCol = false;

  for (const r of rows || []) {
    marketingFees += r.marketingFees || 0;
    customerDiscountsYou += r.customerDiscounts || 0;
    customerDiscountsDoorDash += r.customerDiscountsDoorDash || 0;
    customerDiscountsThirdParty += r.customerDiscountsThirdParty || 0;
    if (r.marketingFeesHistorical != null) {
      hasHistCol = true;
      marketingFeesHistorical = (marketingFeesHistorical || 0) + (r.marketingFeesHistorical || 0);
    }
    if (r.adFeeHistorical != null) {
      hasAdHistCol = true;
      adFeeHistorical = (adFeeHistorical || 0) + (r.adFeeHistorical || 0);
    }
  }

  return {
    marketingFees,
    customerDiscountsYou,
    customerDiscountsDoorDash,
    customerDiscountsThirdParty,
    marketingFeesHistorical: hasHistCol ? marketingFeesHistorical : null,
    adFeeHistorical: hasAdHistCol ? adFeeHistorical : null,
  };
}

/** Sum all marketing discount columns for one order (absolute total). */
export function sumPromoDiscountsFromRows(rows) {
  let total = 0;
  for (const r of rows || []) {
    total += Math.abs(r.customerDiscounts || 0);
    total += Math.abs(r.customerDiscountsDoorDash || 0);
    total += Math.abs(r.customerDiscountsThirdParty || 0);
  }
  return total;
}

/**
 * Classify DD order: organic, promo, ads, or promo_ads.
 * @param {object} signals — from sumDdOrderMarketingSignals
 */
export function classifyDdOrder(signals) {
  const mktAbs = absMoney(signals.marketingFees);
  const cdYou = absMoney(signals.customerDiscountsYou);
  const cdDd = absMoney(signals.customerDiscountsDoorDash);
  const cd3p = absMoney(signals.customerDiscountsThirdParty);

  const hasHistCol = signals.marketingFeesHistorical != null;
  const hasAdHistCol = signals.adFeeHistorical != null;
  const histMkt = hasHistCol ? absMoney(signals.marketingFeesHistorical) : 0;
  const adHist = hasAdHistCol ? absMoney(signals.adFeeHistorical) : 0;

  if (
    isMarketingZero(signals.marketingFees)
    && cdYou === 0
    && cdDd === 0
    && cd3p === 0
    && (!hasHistCol || histMkt === 0)
    && (!hasAdHistCol || adHist === 0)
  ) {
    return 'organic';
  }

  const hasPromoSignal = cdYou > 0 || cdDd > 0 || cd3p > 0 || (hasHistCol && histMkt > 0);
  const hasAdsSignal = mktAbs > DD_ADS_FEE_THRESHOLD;

  if (hasAdsSignal && hasPromoSignal) return 'promo_ads';
  if (hasAdsSignal) return 'ads';
  if (hasPromoSignal) return 'promo';
  if (mktAbs > 0) return 'ads';
  return 'organic';
}

/** @deprecated Use classifyDdOrder(sumDdOrderMarketingSignals(rows)). */
export function classifyOrder(marketingFees, customerDiscounts) {
  const discInputs = Array.isArray(customerDiscounts) ? customerDiscounts : [customerDiscounts];
  return classifyDdOrder({
    marketingFees,
    customerDiscountsYou: discInputs[0] || 0,
    customerDiscountsDoorDash: discInputs[1] || 0,
    customerDiscountsThirdParty: discInputs[2] || 0,
    marketingFeesHistorical: null,
    adFeeHistorical: null,
  });
}

/**
 * Uber Eats: Marketplace Fee is standard commission on most orders, not ad spend.
 * Promo = Offers on items; Ads = Marketing Adjustment (when present).
 */
export function classifyUeOrder(offers, marketingAdjustment) {
  const EPSILON = 0.01;
  const hasPromo = Math.abs(offers || 0) >= EPSILON;
  const hasAds = Math.abs(marketingAdjustment || 0) >= EPSILON;
  if (hasPromo && hasAds) return 'promo_ads';
  if (hasPromo) return 'promo';
  if (hasAds) return 'ads';
  return 'organic';
}

function buildOrderLevel(records, platform = 'dd') {
  const src = records;
  const orderGroups = groupBy(src, 'orderId');
  const out = [];
  for (const [orderId, rows] of orderGroups) {
    if (!orderId) continue;
    const sales = platform === 'ue'
      ? rows.reduce((s, r) => s + (r.sales || 0), 0)
      : rows.reduce((s, r) => s + (r.subtotal || 0), 0);
    const payouts = platform === 'ue'
      ? rows.reduce((s, r) => s + (r.totalPayout || 0), 0)
      : rows.reduce((s, r) => s + (r.netTotal || 0), 0);
    const marketingFees = platform === 'ue'
      ? rows.reduce((s, r) => s + (r.marketplaceFee || 0), 0)
      : rows.reduce((s, r) => s + (r.marketingFees || 0), 0);
    const customerDiscounts = platform === 'ue'
      ? rows.reduce((s, r) => s + Math.abs(r.offers || 0), 0)
      : sumPromoDiscountsFromRows(rows);
    const marketingAdjustment = platform === 'ue'
      ? rows.reduce((s, r) => s + Math.abs(r.marketingAdjustment || 0), 0)
      : 0;
    const orderType = platform === 'ue'
      ? classifyUeOrder(customerDiscounts, marketingAdjustment)
      : classifyDdOrder(sumDdOrderMarketingSignals(rows));
    out.push({
      orderId,
      date: rows[0].date,
      storeId: rows[0].storeId,
      sales,
      payouts,
      marketingFees,
      customerDiscounts,
      marketingAdjustment,
      bucket: assignBucket(sales),
      orderType,
    });
  }
  return out;
}

export function buildBucketAnalysis(financialRows, config) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [], platform = 'dd' } = config;
  const orderLevel = buildOrderLevel(financialRows, platform);

  const buildWindow = (data, start, end) => {
    let filtered = filterByDateRange(data, 'date', start, end);
    filtered = filterExcludedDates(filtered, 'date', excludedDates);
    const bucketGroups = groupBy(filtered.filter(r => r.bucket), 'bucket');
    return BUCKET_RANGES.map(b => {
      const rows = bucketGroups.get(b.label) || [];
      const sales = rows.reduce((s, r) => s + (r.sales || 0), 0);
      const orderCount = rows.length;
      return {
        range: b.label,
        orders: orderCount,
        sales: round(sales),
        aov: round(safeDivide(sales, orderCount), 2),
        promoOrders: rows.filter(r => r.orderType === 'promo' || r.orderType === 'promo_ads').length,
        adsOrders: rows.filter(r => r.orderType === 'ads' || r.orderType === 'promo_ads').length,
        organicOrders: rows.filter(r => r.orderType === 'organic').length,
      };
    });
  };

  const pre = buildWindow(orderLevel, preStart, preEnd);
  const post = buildWindow(orderLevel, postStart, postEnd);

  const comparison = BUCKET_RANGES.map((b, i) => ({
    range: b.label,
    pre_orders: pre[i].orders,
    post_orders: post[i].orders,
    pre_sales: pre[i].sales,
    post_sales: post[i].sales,
    pre_aov: pre[i].aov,
    post_aov: post[i].aov,
    orders_change: post[i].orders - pre[i].orders,
    orders_growth_pct: round(safeDivide(post[i].orders - pre[i].orders, pre[i].orders) * 100),
    sales_change: round(post[i].sales - pre[i].sales),
    sales_growth_pct: round(safeDivide(post[i].sales - pre[i].sales, pre[i].sales) * 100),
  }));

  return comparison;
}

export function buildOrderOriginMix(financialRows, postStart, postEnd, excludedDates = [], platform = 'dd') {
  let data = filterByDateRange(financialRows, 'date', postStart, postEnd);
  data = filterExcludedDates(data, 'date', excludedDates);
  const orders = buildOrderLevel(data, platform);
  let organic = 0, promo = 0, ads = 0, promoAds = 0;

  for (const row of orders) {
    const type = row.orderType;
    if (type === 'organic') organic++;
    else if (type === 'promo') promo++;
    else if (type === 'ads') ads++;
    else promoAds++;
  }

  const total = organic + promo + ads + promoAds || 1;
  return [
    { id: 'organic', label: 'Organic', value: round((organic / total) * 100), count: organic, color: 'var(--accent)' },
    { id: 'promo', label: 'Promo-driven', value: round((promo / total) * 100), count: promo, color: '#A78BFA' },
    { id: 'ads', label: 'Ads-driven', value: round((ads / total) * 100), count: ads, color: '#F59E0B' },
    { id: 'promo_ads', label: 'Promo + Ads', value: round((promoAds / total) * 100), count: promoAds, color: '#2563EB' },
  ];
}
