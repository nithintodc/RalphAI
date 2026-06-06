import { differenceInCalendarDays } from 'date-fns';
import { filterByDateRange, filterExcludedDates, groupBy } from './aggregator';
import { safeDivide, round } from '../utils/safeMath';
import { assignBucket, BUCKET_RANGES, classifyDdOrder, classifyUeOrder, sumDdOrderMarketingSignals } from './buckets';
import { isPresentTimeValue } from '../constants/orderTimeColumns';

const SLOT_RANGES = [
  { name: 'Overnight', min: 0, max: 299, range: '12:00 AM – 4:59 AM' },
  { name: 'Breakfast', min: 300, max: 659, range: '5:00 AM – 10:59 AM' },
  { name: 'Lunch', min: 660, max: 839, range: '11:00 AM – 1:59 PM' },
  { name: 'Afternoon', min: 840, max: 1019, range: '2:00 PM – 4:59 PM' },
  { name: 'Dinner', min: 1020, max: 1199, range: '5:00 PM – 7:59 PM' },
  { name: 'Late Night', min: 1200, max: 1439, range: '8:00 PM – 11:59 PM' },
];

/** @deprecated use SLOT_RANGES — kept for callers that referenced DD_SLOTS / UE_SLOTS */
const DD_SLOTS = SLOT_RANGES;
const UE_SLOTS = SLOT_RANGES;

export const SLOT_DEFINITIONS = SLOT_RANGES.map(({ name, range }) => ({ name, range }));

export const SLOT_NAMES = ['Overnight', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late Night'];
export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export const SLOT_TIME_COLUMN_LABEL = 'Slot time';

const SLOT_TIME_BY_NAME = Object.fromEntries(SLOT_RANGES.map(({ name, range }) => [name, range]));

/** Time window for a day-part name (also matches when embedded in a longer label). */
export function getSlotTimeRange(slotName) {
  if (slotName == null || slotName === '') return '';
  const s = String(slotName).trim();
  if (SLOT_TIME_BY_NAME[s]) return SLOT_TIME_BY_NAME[s];
  const lower = s.toLowerCase();
  for (const name of SLOT_NAMES) {
    if (lower === name.toLowerCase()) return SLOT_TIME_BY_NAME[name];
  }
  for (const name of SLOT_NAMES) {
    if (s.includes(name)) return SLOT_TIME_BY_NAME[name];
  }
  return '';
}

export const SLOT_EXPORT_HEADERS_PVP = ['Slot', 'Slot time', 'Pre', 'Post', 'Pre vs Post', 'Growth%'];
export const SLOT_EXPORT_HEADERS_YOY = ['Slot', 'Slot time', 'LY Post', 'Post', 'YoY', 'YoY%'];
export const LEGACY_SLOT_EXPORT_HEADERS_PVP = ['Slot', 'Slot time', 'Pre', 'Post', 'Pre vs Post', 'Growth%'];
export const LEGACY_SLOT_EXPORT_HEADERS_YOY = ['Slot', 'Slot time', 'Last year post', 'Post', 'YoY', 'Growth%'];

/** Primary slot tables — daily avg for $ metrics; AOV and profitability are ratios. */
export const SLOT_DISPLAY_METRICS = [
  { key: 'sales', label: 'Sales', valueKind: 'usd', dailyAvg: true },
  { key: 'payouts', label: 'Payouts', valueKind: 'usd', dailyAvg: true },
  { key: 'aov', label: 'AOV', valueKind: 'usd2', dailyAvg: false },
  { key: 'profitability', label: 'Profitability %', valueKind: 'pct', dailyAvg: false },
];

/** Slots screen — Pre/Post and YoY growth tables only. */
export const SLOT_CORE_METRICS = [
  { key: 'sales', label: 'Sales', valueKind: 'usd', dailyAvg: true },
  { key: 'payouts', label: 'Payouts', valueKind: 'usd', dailyAvg: true },
  { key: 'aov', label: 'AOV', valueKind: 'usd2', dailyAvg: false },
  { key: 'orders', label: 'Orders', valueKind: 'int', dailyAvg: false },
];

/** Row keys on `buildSlotAnalysis` for export / extended views. */
export const SLOT_METRIC_TABLES = [
  ...SLOT_DISPLAY_METRICS.map(({ key, label, valueKind }) => ({ key, title: label, valueKind })),
  { key: 'orders', title: 'Orders', valueKind: 'int' },
  { key: 'mktSpend', title: 'Mkt spend', valueKind: 'usd' },
  { key: 'adsSpend', title: 'Ads spend', valueKind: 'usd' },
  { key: 'organicOrders', title: 'Organic orders', valueKind: 'int' },
  { key: 'promoOrders', title: 'Promo-driven orders', valueKind: 'int' },
  { key: 'adsOrders', title: 'Ads-driven orders', valueKind: 'int' },
  { key: 'bothOrders', title: 'Both-driven orders', valueKind: 'int' },
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
  const rows = rawData;
  const byOrder = groupBy(rows, 'orderId');
  const out = [];
  for (const [orderId, rs] of byOrder) {
    if (!orderId) continue;
    const t = rs[0][timeField];
    if (!isPresentTimeValue(t)) continue;
    const slot = getSlot(t, 'dd');
    if (!SLOT_NAMES.includes(slot)) continue;
    const sales = rs.reduce((s, r) => s + (r.subtotal || 0), 0);
    const payouts = rs.reduce((s, r) => s + (r.netTotal || 0), 0);
    const mktFees = rs.reduce((s, r) => s + (r.marketingFees || 0), 0);
    const cd = rs.reduce((s, r) => s + (r.customerDiscounts || 0), 0);
    const cdDd = rs.reduce((s, r) => s + (r.customerDiscountsDoorDash || 0), 0);
    const cd3p = rs.reduce((s, r) => s + (r.customerDiscountsThirdParty || 0), 0);
    const mktSignals = sumDdOrderMarketingSignals(rs);
    const adsSpend = mktFees;
    const mktSpend = Math.abs(mktFees) + Math.abs(cd) + Math.abs(cdDd) + Math.abs(cd3p);
    const orderType = classifyDdOrder(mktSignals);
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
    const off = rs.reduce((s, r) => s + Math.abs(r.offers || 0), 0);
    const mktAdj = rs.reduce((s, r) => s + Math.abs(r.marketingAdjustment || 0), 0);
    const adsSpend = mktAdj;
    const mktSpend = Math.abs(off) + Math.abs(mktAdj);
    const orderType = classifyUeOrder(off, mktAdj);
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

function inclusiveDayCount(start, end) {
  if (!start || !end) return 1;
  return Math.max(1, differenceInCalendarDays(end, start) + 1);
}

function shiftYear(date, years = -1) {
  const d = new Date(date);
  d.setFullYear(d.getFullYear() + years);
  return d;
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
    profitability: 0,
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
    agg.profitability = round(safeDivide(agg.payouts, agg.sales) * 100);
    slotData[name] = agg;
  }
  return slotData;
}

function roundMetric(metricKey, v) {
  if (metricKey === 'aov') return round(v, 2);
  if (metricKey === 'profitability') return round(v);
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

function slotMetricValue(agg, metricKey, dayCount, dailyAvg) {
  if (metricKey === 'profitability') {
    return round(safeDivide(agg.payouts, agg.sales) * 100);
  }
  let v = agg[metricKey] || 0;
  if (dailyAvg && dayCount > 0 && (metricKey === 'sales' || metricKey === 'payouts')) {
    v = safeDivide(v, dayCount);
  }
  return roundMetric(metricKey, v);
}

function mapPrePost(metricKey, pre, post, preLY, postLY, dayCounts, dailyAvg) {
  const { preDays, postDays, preLyDays, postLyDays } = dayCounts;
  return SLOT_NAMES.map((s) => {
    const a = slotMetricValue(pre[s], metricKey, preDays, dailyAvg);
    const b = slotMetricValue(post[s], metricKey, postDays, dailyAvg);
    const lyPre = slotMetricValue(preLY[s], metricKey, preLyDays, dailyAvg);
    const lyPost = slotMetricValue(postLY[s], metricKey, postLyDays, dailyAvg);
    const diff = roundMetric(metricKey, b - a);
    const lyDiff = roundMetric(metricKey, lyPost - lyPre);
    return {
      slot: s,
      pre: a,
      post: b,
      prevspost: diff,
      lyPrevspost: lyDiff,
      growthPct: round(safeDivide(diff, a) * 100),
      lyGrowthPct: round(safeDivide(lyDiff, lyPre) * 100),
    };
  });
}

function mapYoY(metricKey, postLY, post, dayCounts, dailyAvg) {
  const { postLyDays, postDays } = dayCounts;
  return SLOT_NAMES.map((s) => {
    const ly = slotMetricValue(postLY[s], metricKey, postLyDays, dailyAvg);
    const b = slotMetricValue(post[s], metricKey, postDays, dailyAvg);
    const diff = roundMetric(metricKey, b - ly);
    return {
      slot: s,
      postLY: ly,
      post: b,
      yoy: diff,
      yoyPct: round(safeDivide(diff, ly) * 100),
    };
  });
}

const METRIC_KEYS = SLOT_METRIC_TABLES.map((m) => m.key);
const DISPLAY_METRIC_CONFIG = Object.fromEntries(
  SLOT_DISPLAY_METRICS.map((m) => [m.key, m]),
);

export function buildSlotAnalysis(rawData, config) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [], platform = 'dd', timeField = 'time' } = config;

  const orderList = platform === 'ue'
    ? buildUeOrdersWithSlots(rawData, timeField)
    : buildDdOrdersWithSlots(rawData, timeField);

  const pre = buildWindowFromOrders(orderList, preStart, preEnd, excludedDates);
  const post = buildWindowFromOrders(orderList, postStart, postEnd, excludedDates);
  const preLY = buildWindowFromOrders(orderList, shiftYear(preStart), shiftYear(preEnd), excludedDates);
  const postLY = buildWindowFromOrders(orderList, shiftYear(postStart), shiftYear(postEnd), excludedDates);

  const dayCounts = {
    preDays: inclusiveDayCount(preStart, preEnd),
    postDays: inclusiveDayCount(postStart, postEnd),
    preLyDays: inclusiveDayCount(shiftYear(preStart), shiftYear(preEnd)),
    postLyDays: inclusiveDayCount(shiftYear(postStart), shiftYear(postEnd)),
  };

  const out = {};
  for (const k of METRIC_KEYS) {
    const dailyAvg = DISPLAY_METRIC_CONFIG[k]?.dailyAvg ?? false;
    out[`${k}PrePost`] = mapPrePost(k, pre, post, preLY, postLY, dayCounts, dailyAvg);
    out[`${k}YoY`] = mapYoY(k, postLY, post, dayCounts, dailyAvg);
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
