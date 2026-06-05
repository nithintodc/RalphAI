import { filterByDateRange, filterExcludedDates, groupBy } from './aggregator';
import { safeDivide, round } from '../utils/safeMath';
import { assignBucket, BUCKET_RANGES, classifyOrder, sumPromoDiscountsFromRows } from './buckets';

const SLOT_RANGES = [
  { name: 'Overnight', min: 0, max: 299 },
  { name: 'Breakfast', min: 300, max: 659 },
  { name: 'Lunch', min: 660, max: 839 },
  { name: 'Afternoon', min: 840, max: 1019 },
  { name: 'Dinner', min: 1020, max: 1199 },
  { name: 'Late Night', min: 1200, max: 1439 },
];

const DD_SLOTS = SLOT_RANGES;
const UE_SLOTS = SLOT_RANGES;

export const SLOT_NAMES = ['Overnight', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late Night'];
export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** Row keys on `buildSlotAnalysis` for DataTable columns + formatting. */
export const SLOT_METRIC_TABLES = [
  { key: 'sales', title: 'Sales', valueKind: 'usd' },
  { key: 'orders', title: 'Orders', valueKind: 'int' },
  { key: 'payouts', title: 'Payouts', valueKind: 'usd' },
  { key: 'mktSpend', title: 'Mkt spend', valueKind: 'usd' },
  { key: 'adsSpend', title: 'Ads spend', valueKind: 'usd' },
  { key: 'organicOrders', title: 'Organic orders', valueKind: 'int' },
  { key: 'promoOrders', title: 'Promo-driven orders', valueKind: 'int' },
  { key: 'adsOrders', title: 'Ads-driven orders', valueKind: 'int' },
  { key: 'bothOrders', title: 'Both-driven orders', valueKind: 'int' },
  { key: 'aov', title: 'AOV', valueKind: 'usd2' },
];

export function parseTimeToMinutes(timeStr) {
  if (!timeStr) return -1;
  const str = String(timeStr).trim();
  const parts = str.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?/i);
  if (!parts) return -1;
  let hours = parseInt(parts[1], 10);
  const mins = parseInt(parts[2], 10);
  const ampm = parts[4];
  if (ampm) {
    if (ampm.toUpperCase() === 'PM' && hours !== 12) hours += 12;
    if (ampm.toUpperCase() === 'AM' && hours === 12) hours = 0;
  }
  return hours * 60 + mins;
}

export function getSlot(timeStr, platform = 'dd') {
  const minutes = parseTimeToMinutes(timeStr);
  if (minutes < 0) return 'Unknown';
  const slots = platform === 'ue' ? UE_SLOTS : DD_SLOTS;
  const slot = slots.find((s) => minutes >= s.min && minutes <= s.max);
  return slot ? slot.name : 'Unknown';
}

function buildDdOrdersWithSlots(rawData, timeField) {
  const rows = rawData.filter((r) => !r.transactionType || r.transactionType === 'Order');
  const byOrder = groupBy(rows, 'orderId');
  const out = [];
  for (const [orderId, rs] of byOrder) {
    if (!orderId) continue;
    const t = rs[0][timeField];
    const slot = getSlot(t, 'dd');
    if (!SLOT_NAMES.includes(slot)) continue;
    const sales = rs.reduce((s, r) => s + (r.subtotal || 0), 0);
    const payouts = rs.reduce((s, r) => s + (r.netTotal || 0), 0);
    const mktFees = rs.reduce((s, r) => s + (r.marketingFees || 0), 0);
    const cd = rs.reduce((s, r) => s + (r.customerDiscounts || 0), 0);
    const cdDd = rs.reduce((s, r) => s + (r.customerDiscountsDoorDash || 0), 0);
    const cd3p = rs.reduce((s, r) => s + (r.customerDiscountsThirdParty || 0), 0);
    const promoDiscount = sumPromoDiscountsFromRows(rs);
    const adsSpend = mktFees;
    const mktSpend = Math.abs(mktFees) + Math.abs(cd) + Math.abs(cdDd) + Math.abs(cd3p);
    const orderType = classifyOrder(mktFees, promoDiscount);
    const bucket = assignBucket(sales);
    out.push({
      orderId,
      date: rs[0].date,
      slot,
      sales,
      bucket,
      payouts,
      adsSpend,
      mktSpend,
      orderType,
    });
  }
  return out;
}

function buildUeOrdersWithSlots(rawData, timeField) {
  const byOrder = groupBy(rawData, 'orderId');
  const out = [];
  for (const [orderId, rs] of byOrder) {
    if (!orderId) continue;
    const t = rs[0][timeField];
    const slot = getSlot(t, 'ue');
    if (!SLOT_NAMES.includes(slot)) continue;
    const sales = rs.reduce((s, r) => s + (r.sales || 0), 0);
    const payouts = rs.reduce((s, r) => s + (r.totalPayout || 0), 0);
    const mp = rs.reduce((s, r) => s + (r.marketplaceFee || 0), 0);
    const off = rs.reduce((s, r) => s + (r.offers || 0), 0);
    const adsSpend = mp;
    const mktSpend = Math.abs(mp) + Math.abs(off);
    const orderType = classifyOrder(mp, off);
    const bucket = assignBucket(sales);
    out.push({
      orderId,
      date: rs[0].date,
      slot,
      sales,
      bucket,
      payouts,
      adsSpend,
      mktSpend,
      orderType,
    });
  }
  return out;
}

function emptySlotAgg() {
  return {
    sales: 0,
    payouts: 0,
    orders: 0,
    adsSpend: 0,
    mktSpend: 0,
    organicOrders: 0,
    promoOrders: 0,
    adsOrders: 0,
    bothOrders: 0,
    aov: 0,
  };
}

function buildWindowFromOrders(orderList, start, end, excludedDates) {
  let filtered = filterByDateRange(orderList, 'date', start, end);
  filtered = filterExcludedDates(filtered, 'date', excludedDates);
  const bySlot = groupBy(filtered, 'slot');
  const slotData = {};
  for (const name of SLOT_NAMES) {
    const ords = bySlot.get(name) || [];
    const agg = emptySlotAgg();
    for (const o of ords) {
      agg.sales += o.sales;
      agg.payouts += o.payouts;
      agg.adsSpend += o.adsSpend;
      agg.mktSpend += o.mktSpend;
    }
    agg.orders = ords.length;
    for (const o of ords) {
      if (o.orderType === 'organic') agg.organicOrders += 1;
      else if (o.orderType === 'promo') agg.promoOrders += 1;
      else if (o.orderType === 'ads') agg.adsOrders += 1;
      else if (o.orderType === 'promo_ads') agg.bothOrders += 1;
    }
    agg.aov = round(safeDivide(agg.sales, agg.orders), 2);
    slotData[name] = agg;
  }
  return slotData;
}

function roundMetric(metricKey, v) {
  if (metricKey === 'aov') return round(v, 2);
  if (
    metricKey === 'orders'
    || metricKey === 'organicOrders'
    || metricKey === 'promoOrders'
    || metricKey === 'adsOrders'
    || metricKey === 'bothOrders'
  ) {
    return Math.round(v);
  }
  return round(v, 0);
}

function mapPrePost(metricKey, pre, post) {
  return SLOT_NAMES.map((s) => {
    const a = pre[s][metricKey] || 0;
    const b = post[s][metricKey] || 0;
    const diff = b - a;
    return {
      slot: s,
      pre: roundMetric(metricKey, a),
      post: roundMetric(metricKey, b),
      prevspost: roundMetric(metricKey, diff),
      growthPct: round(safeDivide(diff, a) * 100),
    };
  });
}

function mapYoY(metricKey, postLY, post) {
  return SLOT_NAMES.map((s) => {
    const ly = postLY[s][metricKey] || 0;
    const b = post[s][metricKey] || 0;
    const diff = b - ly;
    return {
      slot: s,
      postLY: roundMetric(metricKey, ly),
      post: roundMetric(metricKey, b),
      yoy: roundMetric(metricKey, diff),
      yoyPct: round(safeDivide(diff, ly) * 100),
    };
  });
}

const METRIC_KEYS = SLOT_METRIC_TABLES.map((m) => m.key);

export function buildSlotAnalysis(rawData, config) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [], platform = 'dd', timeField = 'time' } = config;

  const orderList = platform === 'ue'
    ? buildUeOrdersWithSlots(rawData, timeField)
    : buildDdOrdersWithSlots(rawData, timeField);

  const lyPost = { start: new Date(postStart), end: new Date(postEnd) };
  lyPost.start.setFullYear(lyPost.start.getFullYear() - 1);
  lyPost.end.setFullYear(lyPost.end.getFullYear() - 1);

  const pre = buildWindowFromOrders(orderList, preStart, preEnd, excludedDates);
  const post = buildWindowFromOrders(orderList, postStart, postEnd, excludedDates);
  const postLY = buildWindowFromOrders(orderList, lyPost.start, lyPost.end, excludedDates);

  const out = {};
  for (const k of METRIC_KEYS) {
    out[`${k}PrePost`] = mapPrePost(k, pre, post);
    out[`${k}YoY`] = mapYoY(k, postLY, post);
  }

  return out;
}

const BUCKET_ORDER = BUCKET_RANGES.map((b) => b.label);

/** Min combined Pre+Post orders in a slot to classify ticket-mix shift vs noise. */
const SLOT_BUCKET_MIN_ORDERS = 15;

/**
 * Compare Pre vs Post order shares across ticket buckets (low index = smaller subtotal bands).
 * Negative score ⇒ Post gains relative share in lower buckets (mix shifting toward smaller tickets / "lesser GC").
 * Positive ⇒ mix shifting toward higher buckets.
 */
function classifyTicketMixShift(preCountsByIdx, postCountsByIdx) {
  const preTotal = preCountsByIdx.reduce((a, c) => a + c, 0);
  const postTotal = postCountsByIdx.reduce((a, c) => a + c, 0);
  if (preTotal + postTotal < SLOT_BUCKET_MIN_ORDERS) return 'neutral';

  let score = 0;
  for (let i = 0; i < BUCKET_ORDER.length; i++) {
    const prePct = preTotal > 0 ? preCountsByIdx[i] / preTotal : 0;
    const postPct = postTotal > 0 ? postCountsByIdx[i] / postTotal : 0;
    score += (postPct - prePct) * i;
  }
  const n = BUCKET_ORDER.length;
  const thresh = 0.07 * Math.max(1, n / 2);
  if (score < -thresh) return 'lesser';
  if (score > thresh) return 'forward';
  return 'neutral';
}

/**
 * Per time-of-day slot: order counts by ticket-size bucket (same bands as Order Buckets), Pre vs Post,
 * plus a summary of which slots show mix shifting downscale vs upscale.
 */
export function buildSlotTicketBucketAnalysis(rawData, config) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [], platform = 'dd', timeField = 'time' } = config;

  const orderList = platform === 'ue'
    ? buildUeOrdersWithSlots(rawData, timeField)
    : buildDdOrdersWithSlots(rawData, timeField);

  let preOrders = filterByDateRange(orderList, 'date', preStart, preEnd);
  preOrders = filterExcludedDates(preOrders, 'date', excludedDates);
  let postOrders = filterByDateRange(orderList, 'date', postStart, postEnd);
  postOrders = filterExcludedDates(postOrders, 'date', excludedDates);

  function countsForSlot(orders, slotName) {
    const arr = new Array(BUCKET_ORDER.length).fill(0);
    for (const o of orders) {
      if (o.slot !== slotName || !o.bucket) continue;
      const idx = BUCKET_ORDER.indexOf(o.bucket);
      if (idx >= 0) arr[idx] += 1;
    }
    return arr;
  }

  const towardsLesser = [];
  const towardsHigher = [];
  const roughlyFlat = [];

  const bySlotCharts = SLOT_NAMES.map((slot) => {
    const preC = countsForSlot(preOrders, slot);
    const postC = countsForSlot(postOrders, slot);
    const barData = BUCKET_RANGES.map((b, i) => ({
      range: b.label,
      pre_orders: preC[i],
      post_orders: postC[i],
    }));
    const dir = classifyTicketMixShift(preC, postC);
    if (dir === 'lesser') towardsLesser.push(slot);
    else if (dir === 'forward') towardsHigher.push(slot);
    else roughlyFlat.push(slot);
    return { slot, data: barData };
  });

  return {
    bySlotCharts,
    summary: {
      towardsLesserGcBaskets: towardsLesser,
      towardsHigherTicket: towardsHigher,
      roughlyUnchanged: roughlyFlat,
    },
  };
}

export function buildHeatmapData(rawData, config) {
  const { postStart, postEnd, excludedDates = [], platform = 'dd', timeField = 'time' } = config;
  const salesField = platform === 'dd' ? 'subtotal' : 'sales';
  let data = filterByDateRange(rawData, 'date', postStart, postEnd);
  data = filterExcludedDates(data, 'date', excludedDates);

  const matrix = Array.from({ length: 7 }, () => Array(6).fill(0));
  let maxVal = 0;

  for (const r of data) {
    const dayIdx = r.date ? ((r.date.getDay() + 6) % 7) : -1;
    const slot = getSlot(r[timeField], platform);
    const slotIdx = SLOT_NAMES.indexOf(slot);
    if (dayIdx >= 0 && slotIdx >= 0) {
      matrix[dayIdx][slotIdx] += r[salesField] || 0;
      maxVal = Math.max(maxVal, matrix[dayIdx][slotIdx]);
    }
  }

  if (maxVal > 0) {
    for (let i = 0; i < 7; i++) {
      for (let j = 0; j < 6; j++) {
        matrix[i][j] = round(matrix[i][j] / maxVal, 2);
      }
    }
  }

  return matrix;
}
