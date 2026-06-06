/**
 * App 2.0–style DoorDash bucketing: order-level prep → store × calendar × day-part rollups,
 * period aggregations, Pre vs Post / YoY diffs, and day-part × GC bucket summaries.
 * Ported from App2.0/bucketing_analysis.py and App2.0/export_functions.py helpers.
 */
import { format, startOfWeek, endOfWeek, subYears } from 'date-fns';
import { isPresentTimeValue } from '../constants/orderTimeColumns';
import { filterByDateRange, filterExcludedDates, groupBy } from './aggregator';
import { parseTimeToMinutes, getSlotTimeRange, SLOT_TIME_COLUMN_LABEL } from './slots';
import { round } from '../utils/safeMath';

export const APP2_DAY_PARTS = [
  'Overnight',
  'Breakfast',
  'Lunch',
  'Afternoon',
  'Dinner',
  'Late night',
];

export const APP2_GC_COLS = [
  'GC $0-15',
  'GC $15-20',
  'GC $20-25',
  'GC $25-30',
  'GC $30-$35',
  'GC $35-$40',
  'GC $40+',
];

export const APP2_MERCHANT_STORE_COL = 'Merchant Store ID';

const STORE_COL = APP2_MERCHANT_STORE_COL;

const BUCKET_METRIC_COLS = [
  'Sales',
  'Payouts',
  'Mkt Spend',
  'Customer Discounts',
  'Orders',
  ...APP2_GC_COLS,
  'Count of Orders Mktg Driven',
];

function normStoreKey(val) {
  if (val == null || val === '') return '';
  const n = Number(val);
  if (!Number.isNaN(n) && String(val).trim() !== '') return String(Math.trunc(n));
  return String(val).trim();
}

function weekRangeLabel(d) {
  if (!d || Number.isNaN(d.getTime?.())) return '';
  const mon = startOfWeek(d, { weekStartsOn: 1 });
  const sun = endOfWeek(d, { weekStartsOn: 1 });
  return `${format(mon, 'dd/MM')} - ${format(sun, 'dd/MM')}`;
}

function gcBucket(subtotal) {
  if (subtotal == null || subtotal < 0) return null;
  const s = Number(subtotal);
  if (s < 15) return 'GC $0-15';
  if (s < 20) return 'GC $15-20';
  if (s < 25) return 'GC $20-25';
  if (s < 30) return 'GC $25-30';
  if (s < 35) return 'GC $30-$35';
  if (s < 40) return 'GC $35-$40';
  return 'GC $40+';
}

function isMktgDrivenOrder(mkt, disc) {
  const m = Number(mkt) || 0;
  const d = Number(disc) || 0;
  return m !== 0 || d !== 0;
}

function hourFromTimeStr(timeStr) {
  const mins = parseTimeToMinutes(timeStr);
  if (mins < 0) return -1;
  return Math.floor(mins / 60);
}

export function assignApp2DayPart(hour) {
  const h = hour == null || hour < 0 ? -1 : Math.floor(hour);
  if (h < 0) return 'Unknown';
  if (h < 5) return APP2_DAY_PARTS[0];
  if (h < 11) return APP2_DAY_PARTS[1];
  if (h < 14) return APP2_DAY_PARTS[2];
  if (h < 17) return APP2_DAY_PARTS[3];
  if (h < 20) return APP2_DAY_PARTS[4];
  return APP2_DAY_PARTS[5];
}

function dayNameEn(d) {
  return format(d, 'EEEE');
}

/**
 * Order-level rows for one date window (App2 load_and_prepare semantics).
 */
export function prepareApp2OrderRows(ddFinancial, start, end, excludedDates = []) {
  if (!ddFinancial?.length || !start || !end) return [];
  let data = filterByDateRange(ddFinancial, 'date', start, end);
  data = filterExcludedDates(data, 'date', excludedDates);
  const rows = data;
  const byOrder = groupBy(rows, 'orderId');
  const prepared = [];
  for (const [, orderRows] of byOrder) {
    if (!orderRows?.length) continue;
    const r0 = orderRows[0];
    if (!r0.orderId) continue;
    if (!isPresentTimeValue(r0.time)) continue;
    const subtotal = orderRows.reduce((s, r) => s + (Number(r.subtotal) || 0), 0);
    const netTotal = orderRows.reduce((s, r) => s + (Number(r.netTotal) || 0), 0);
    const mkt = orderRows.reduce((s, r) => s + (Number(r.marketingFees) || 0), 0);
    const disc = orderRows.reduce((s, r) => s + (Number(r.customerDiscounts) || 0), 0);
    const orderTime = r0.time;
    const hour = hourFromTimeStr(orderTime);
    const dayPart = assignApp2DayPart(hour);
    const d = r0.date instanceof Date ? r0.date : new Date(r0.date);
    if (Number.isNaN(d.getTime())) continue;
    const orderDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const month = format(orderDate, 'yyyy-MM');
    const week = weekRangeLabel(orderDate);
    const dateStr = format(orderDate, 'yyyy-MM-dd');
    const dayName = dayNameEn(orderDate);
    prepared.push({
      [STORE_COL]: String(r0.storeId || '').trim(),
      _subtotal: subtotal,
      _net: netTotal,
      _mkt: mkt,
      _disc: disc,
      Month: month,
      Week: week,
      Date: dateStr,
      Day: dayName,
      'Day part': dayPart,
      _mkt_driven: isMktgDrivenOrder(mkt, disc) ? 1 : 0,
      _gc: gcBucket(subtotal),
    });
  }
  return prepared;
}

function keyJoin(parts) {
  return parts.map((p) => String(p ?? '')).join('\x00');
}

/**
 * Store × Month × Week × Date × Day × Day part rollup (aggregate_slot_table).
 */
export function aggregateApp2SlotTable(prepared, storeOperator = {}) {
  const keys = [STORE_COL, 'Month', 'Week', 'Date', 'Day', 'Day part'];
  const map = new Map();

  for (const o of prepared) {
    const k = keyJoin(keys.map((f) => o[f]));
    if (!map.has(k)) {
      map.set(k, {
        [STORE_COL]: o[STORE_COL],
        Operator: storeOperator[normStoreKey(o[STORE_COL])] || '',
        Month: o.Month,
        Week: o.Week,
        Date: o.Date,
        Day: o.Day,
        'Day part': o['Day part'],
        Sales: 0,
        Payouts: 0,
        'Mkt Spend': 0,
        'Customer Discounts': 0,
        Orders: 0,
        'Count of Orders Mktg Driven': 0,
        ...Object.fromEntries(APP2_GC_COLS.map((c) => [c, 0])),
      });
    }
    const g = map.get(k);
    g.Sales += o._subtotal;
    g.Payouts += o._net;
    g['Mkt Spend'] += o._mkt;
    g['Customer Discounts'] += o._disc;
    g.Orders += 1;
    g['Count of Orders Mktg Driven'] += o._mkt_driven;
    if (o._gc && g[o._gc] !== undefined) g[o._gc] += 1;
  }

  const out = [...map.values()].map((row) => {
    const sales = row.Sales;
    const payouts = row.Payouts;
    const orders = row.Orders;
    const prof = Math.abs(sales) > 1e-9 ? round((payouts / sales) * 100, 1) : null;
    const aov = orders > 0 ? round(sales / orders, 1) : null;
    return {
      ...row,
      Sales: round(sales, 1),
      Payouts: round(payouts, 1),
      'Mkt Spend': round(row['Mkt Spend'], 1),
      'Customer Discounts': round(row['Customer Discounts'], 1),
      'Profitability_%': prof,
      AOV: aov,
    };
  });

  out.sort((a, b) => {
    const sa = String(a[STORE_COL]).localeCompare(String(b[STORE_COL]));
    if (sa !== 0) return sa;
    const da = String(a.Date).localeCompare(String(b.Date));
    if (da !== 0) return da;
    return String(a['Day part']).localeCompare(String(b['Day part']));
  });
  return out;
}

function sumMetricsInto(target, row) {
  for (const c of BUCKET_METRIC_COLS) {
    if (row[c] != null) target[c] = (target[c] || 0) + Number(row[c]);
  }
}

export function bucketAggRows(rows, groupKeys) {
  const map = new Map();
  for (const row of rows) {
    const k = keyJoin(groupKeys.map((f) => row[f]));
    if (!map.has(k)) {
      const base = {};
      for (const key of groupKeys) base[key] = row[key];
      for (const c of BUCKET_METRIC_COLS) base[c] = 0;
      map.set(k, base);
    }
    sumMetricsInto(map.get(k), row);
  }
  return [...map.values()].map((r) => {
    const sales = r.Sales || 0;
    const payouts = r.Payouts || 0;
    const orders = r.Orders || 0;
    return {
      ...r,
      Sales: round(sales, 1),
      Payouts: round(payouts, 1),
      'Mkt Spend': round(r['Mkt Spend'] || 0, 1),
      'Customer Discounts': round(r['Customer Discounts'] || 0, 1),
      'Profitability_%': Math.abs(sales) > 1e-9 ? round((payouts / sales) * 100, 1) : null,
      AOV: orders > 0 ? round(sales / orders, 1) : null,
    };
  });
}

function outerKeys(postA, preA, groupKeys) {
  const s = new Set();
  for (const r of postA) s.add(keyJoin(groupKeys.map((k) => r[k])));
  for (const r of preA) s.add(keyJoin(groupKeys.map((k) => r[k])));
  return [...s];
}

export function bucketDiffTable(postRows, preRows, groupKeys) {
  if (!postRows?.length && !preRows?.length) return [];
  const postA = bucketAggRows(postRows || [], groupKeys);
  const preA = bucketAggRows(preRows || [], groupKeys);
  const postMap = new Map(postA.map((r) => [keyJoin(groupKeys.map((k) => r[k])), r]));
  const preMap = new Map(preA.map((r) => [keyJoin(groupKeys.map((k) => r[k])), r]));
  const mCols = [...BUCKET_METRIC_COLS];
  const rows = [];
  for (const k of outerKeys(postA, preA, groupKeys)) {
    const pr = postMap.get(k) || {};
    const pe = preMap.get(k) || {};
    const row = {};
    for (const key of groupKeys) {
      row[key] = pr[key] ?? pe[key] ?? '';
    }
    for (const m of mCols) {
      const postV = Number(pr[m]) || 0;
      const preV = Number(pe[m]) || 0;
      const diff = postV - preV;
      const pct = preV !== 0 ? round((diff / preV) * 100, 1) : 0;
      row[`${m}_Pre`] = round(preV, 2);
      row[`${m}_Post`] = round(postV, 2);
      row[`${m}_Diff`] = round(diff, 2);
      row[`${m}_%`] = round(pct, 1);
    }
    const sPost = row.Sales_Post ?? 0;
    const pPost = row.Payouts_Post ?? 0;
    const oPost = row.Orders_Post ?? 0;
    const sPre = row.Sales_Pre ?? 0;
    const pPre = row.Payouts_Pre ?? 0;
    const oPre = row.Orders_Pre ?? 0;
    row['Profitability_%_Pre'] = sPre ? round((pPre / sPre) * 100, 1) : 0;
    row['Profitability_%_Post'] = sPost ? round((pPost / sPost) * 100, 1) : 0;
    row.AOV_Pre = oPre ? round(sPre / oPre, 1) : 0;
    row.AOV_Post = oPost ? round(sPost / oPost, 1) : 0;
    row['Profitability_%_Diff'] = round(row['Profitability_%_Post'] - row['Profitability_%_Pre'], 1);
    row['Profitability_%_%'] = '';
    row.AOV_Diff = round(row.AOV_Post - row.AOV_Pre, 1);
    row['AOV_%'] = oPre && sPre ? round(((row.AOV_Post - row.AOV_Pre) / row.AOV_Pre) * 100, 1) : 0;
    rows.push(row);
  }
  return rows;
}

export function daypartGcOrderTable(aggTbl) {
  const gcCols = [...APP2_GC_COLS];
  if (!aggTbl?.length) {
    const empty = { 'Day part': 'Grand Total', Orders: 0 };
    for (const c of gcCols) empty[c] = 0;
    return [empty];
  }
  const parts = bucketAggRows(aggTbl, ['Day part']);
  const byPart = new Map(parts.map((p) => [p['Day part'], p]));
  const out = [];
  for (const dp of APP2_DAY_PARTS) {
    const r = byPart.get(dp);
    const row = { 'Day part': dp };
    for (const c of gcCols) row[c] = r ? Math.round(Number(r[c]) || 0) : 0;
    row.Orders = r ? Math.round(Number(r.Orders) || 0) : 0;
    out.push(row);
  }
  const unk = byPart.get('Unknown');
  if (unk) {
    const row = { 'Day part': 'Unknown' };
    for (const c of gcCols) row[c] = Math.round(Number(unk[c]) || 0);
    row.Orders = Math.round(Number(unk.Orders) || 0);
    out.push(row);
  }
  const total = { 'Day part': 'Grand Total' };
  for (const c of gcCols) total[c] = out.reduce((s, r) => s + (Number(r[c]) || 0), 0);
  total.Orders = out.reduce((s, r) => s + (Number(r.Orders) || 0), 0);
  out.push(total);
  return out;
}

export function daypartDeltaTables(postTbl, preTbl) {
  const gcCols = [...APP2_GC_COLS, 'Orders'];
  const preMap = new Map((preTbl || []).map((r) => [r['Day part'], r]));
  const allDp = [...new Set([...(postTbl || []).map((r) => r['Day part']), ...preMap.keys()])];
  const orderDp = (dp) => {
    const order = [...APP2_DAY_PARTS, 'Unknown', 'Grand Total'];
    const i = order.indexOf(dp);
    return i >= 0 ? i : 50;
  };
  allDp.sort((a, b) => orderDp(a) - orderDp(b));
  const delta = [];
  const pct = [];
  for (const dp of allDp) {
    const pr = (postTbl || []).find((r) => r['Day part'] === dp) || {};
    const pe = preMap.get(dp) || {};
    const dRow = { 'Day part': dp };
    const pRow = { 'Day part': dp };
    for (const c of gcCols) {
      const pv = Number(pr[c]) || 0;
      const rv = Number(pe[c]) || 0;
      const d = pv - rv;
      dRow[c] = Math.round(d);
      pRow[c] = rv !== 0 ? round((d / rv) * 100, 1) : pv !== 0 ? 100 : 0;
    }
    delta.push(dRow);
    pct.push(pRow);
  }
  return { delta, pct };
}

function sortedStoreIds(aggTbl) {
  return [...new Set(aggTbl.map((r) => String(r[STORE_COL] ?? '')))].filter(Boolean).sort((a, b) =>
    a.localeCompare(b, undefined, { numeric: true }),
  );
}

export function storeDaypartGcOrderTable(aggTbl, storeIds = null) {
  const gcCols = [...APP2_GC_COLS];
  const stores = storeIds ?? sortedStoreIds(aggTbl);
  const g = new Map();
  for (const row of aggTbl) {
    const sid = String(row[STORE_COL] ?? '');
    const dp = row['Day part'] ?? '';
    const k = `${sid}\x00${dp}`;
    if (!g.has(k)) {
      g.set(k, Object.fromEntries(gcCols.map((c) => [c, 0])));
      g.get(k).Orders = 0;
    }
    const cell = g.get(k);
    for (const c of gcCols) cell[c] += Number(row[c]) || 0;
    cell.Orders += Number(row.Orders) || 0;
  }
  const rows = [];
  for (const sid of stores) {
    for (const dp of APP2_DAY_PARTS) {
      const cell = g.get(`${sid}\x00${dp}`) || { ...Object.fromEntries(gcCols.map((c) => [c, 0])), Orders: 0 };
      rows.push({ [STORE_COL]: sid, 'Day part': dp, ...cell });
    }
    const unk = g.get(`${sid}\x00Unknown`);
    if (unk && (unk.Orders > 0 || gcCols.some((c) => unk[c]))) {
      rows.push({ [STORE_COL]: sid, 'Day part': 'Unknown', ...unk });
    }
  }
  const total = { [STORE_COL]: 'Grand Total', 'Day part': '' };
  for (const c of gcCols) total[c] = aggTbl.reduce((s, r) => s + (Number(r[c]) || 0), 0);
  total.Orders = aggTbl.reduce((s, r) => s + (Number(r.Orders) || 0), 0);
  rows.push(total);
  return rows;
}

export function storeDaypartDeltaTables(postTbl, preTbl) {
  const gcCols = [...APP2_GC_COLS, 'Orders'];
  const keys = [STORE_COL, 'Day part'];
  const keyFn = (r) => keyJoin(keys.map((k) => r[k]));
  const preMap = new Map(preTbl.map((r) => [keyFn(r), r]));
  const postKeys = new Set(postTbl.map(keyFn));
  const preKeys = new Set(preTbl.map(keyFn));
  const allKeys = [...new Set([...postKeys, ...preKeys])];
  const delta = [];
  const pct = [];
  for (const k of allKeys) {
    const pr = postTbl.find((r) => keyFn(r) === k) || {};
    const pe = preMap.get(k) || {};
    const dRow = { [STORE_COL]: pr[STORE_COL] ?? pe[STORE_COL], 'Day part': pr['Day part'] ?? pe['Day part'] };
    const pRow = { ...dRow };
    for (const c of gcCols) {
      const pv = Number(pr[c]) || 0;
      const rv = Number(pe[c]) || 0;
      const d = pv - rv;
      dRow[c] = Math.round(d);
      pRow[c] = rv !== 0 ? round((d / rv) * 100, 1) : pv !== 0 ? 100 : 0;
    }
    delta.push(dRow);
    pct.push(pRow);
  }
  const orderDp = (dp) => {
    const order = [...APP2_DAY_PARTS, 'Unknown', ''];
    const i = order.indexOf(dp);
    return i >= 0 ? i : 999;
  };
  delta.sort((a, b) => {
    const gt = (x) => (String(x[STORE_COL]) === 'Grand Total' ? 1 : 0);
    if (gt(a) !== gt(b)) return gt(a) - gt(b);
    const sa = String(a[STORE_COL]).localeCompare(String(b[STORE_COL]), undefined, { numeric: true });
    if (sa !== 0) return sa;
    return orderDp(a['Day part']) - orderDp(b['Day part']);
  });
  pct.sort((a, b) => {
    const gt = (x) => (String(x[STORE_COL]) === 'Grand Total' ? 1 : 0);
    if (gt(a) !== gt(b)) return gt(a) - gt(b);
    const sa = String(a[STORE_COL]).localeCompare(String(b[STORE_COL]), undefined, { numeric: true });
    if (sa !== 0) return sa;
    return orderDp(a['Day part']) - orderDp(b['Day part']);
  });
  return { delta, pct };
}

function concatWithPeriod(aggTables, groupFn) {
  const parts = [];
  for (const [label, tbl] of Object.entries(aggTables)) {
    if (!tbl?.length) continue;
    const agg = groupFn(tbl);
    for (const row of agg) parts.push({ Period: label, ...row });
  }
  return parts;
}

/**
 * Full pack for UI + export: Pre / Post / LY Pre / LY Post slot tables and derived summaries.
 */
export function buildApp2BucketingPack(ddFinancial, config) {
  const excluded = config.ddExcludedDates || [];
  if (!ddFinancial?.length || !config.ddPreStart || !config.ddPostStart) {
    return { empty: true, aggTables: {} };
  }

  const windows = {
    Pre: { start: config.ddPreStart, end: config.ddPreEnd },
    Post: { start: config.ddPostStart, end: config.ddPostEnd },
    'LY Pre': { start: subYears(config.ddPreStart, 1), end: subYears(config.ddPreEnd, 1) },
    'LY Post': { start: subYears(config.ddPostStart, 1), end: subYears(config.ddPostEnd, 1) },
  };

  const aggTables = {};
  for (const [label, w] of Object.entries(windows)) {
    if (!w.start || !w.end) continue;
    const prep = prepareApp2OrderRows(ddFinancial, w.start, w.end, excluded);
    if (prep.length) aggTables[label] = aggregateApp2SlotTable(prep, {});
  }

  if (!Object.keys(aggTables).length) {
    return { empty: true, aggTables: {} };
  }

  const byPeriod = concatWithPeriod(aggTables, (tbl) => bucketAggRows(tbl, [STORE_COL]));
  const bySlotPeriod = concatWithPeriod(aggTables, (tbl) => bucketAggRows(tbl, [STORE_COL, 'Day part']));
  const allRows = Object.values(aggTables).flat();
  const byDay = bucketAggRows(allRows, [STORE_COL, 'Day']);

  let slotPreVsPost = [];
  let slotYoY = [];
  let daySlotPreVsPost = [];
  let daySlotYoY = [];
  if (aggTables.Post && aggTables.Pre) {
    slotPreVsPost = bucketDiffTable(aggTables.Post, aggTables.Pre, [STORE_COL, 'Day part']);
    daySlotPreVsPost = bucketDiffTable(aggTables.Post, aggTables.Pre, [STORE_COL, 'Day', 'Day part']);
  }
  if (aggTables.Post && aggTables['LY Post']) {
    slotYoY = bucketDiffTable(aggTables.Post, aggTables['LY Post'], [STORE_COL, 'Day part']);
    daySlotYoY = bucketDiffTable(aggTables.Post, aggTables['LY Post'], [STORE_COL, 'Day', 'Day part']);
  }

  let daypartGcPost = [];
  let daypartGcPre = [];
  let daypartGcDelta = [];
  let daypartGcDeltaPct = [];
  let storeDaypartGcPost = [];
  let storeDaypartGcPre = [];
  let storeDaypartGcDelta = [];
  let storeDaypartGcDeltaPct = [];

  if (aggTables.Post && aggTables.Pre) {
    daypartGcPost = daypartGcOrderTable(aggTables.Post);
    daypartGcPre = daypartGcOrderTable(aggTables.Pre);
    const d = daypartDeltaTables(daypartGcPost, daypartGcPre);
    daypartGcDelta = d.delta;
    daypartGcDeltaPct = d.pct;

    const storesUnion = [
      ...new Set([...sortedStoreIds(aggTables.Post), ...sortedStoreIds(aggTables.Pre)]),
    ].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    storeDaypartGcPost = storeDaypartGcOrderTable(aggTables.Post, storesUnion);
    storeDaypartGcPre = storeDaypartGcOrderTable(aggTables.Pre, storesUnion);
    const sd = storeDaypartDeltaTables(storeDaypartGcPost, storeDaypartGcPre);
    storeDaypartGcDelta = sd.delta;
    storeDaypartGcDeltaPct = sd.pct;
  }

  return {
    empty: false,
    aggTables,
    byPeriod,
    bySlotPeriod,
    byDay,
    slotPreVsPost,
    slotYoY,
    daySlotPreVsPost,
    daySlotYoY,
    daypartGcPost,
    daypartGcPre,
    daypartGcDelta,
    daypartGcDeltaPct,
    storeDaypartGcPost,
    storeDaypartGcPre,
    storeDaypartGcDelta,
    storeDaypartGcDeltaPct,
  };
}

function slotColumnKey(keys) {
  return keys.find((k) => k === 'slot' || k === 'Day part') || null;
}

function exportKeysWithSlotTime(keys, slotKey) {
  if (!slotKey || !keys.includes(slotKey)) return keys;
  const out = [];
  for (const k of keys) {
    out.push(k);
    if (k === slotKey) out.push(SLOT_TIME_COLUMN_LABEL);
  }
  return out;
}

function exportRowWithSlotTime(row, keys, slotKey) {
  const out = [];
  for (const k of keys) {
    out.push(row[k]);
    if (k === slotKey) out.push(getSlotTimeRange(row[k]));
  }
  return out;
}

function pushObjectSection(target, title, objects, maxRows = 50000) {
  if (!objects?.length) return;
  if (target.length) target.push([]);
  target.push([title]);
  const baseKeys = Object.keys(objects[0]);
  const slotKey = slotColumnKey(baseKeys);
  const keys = exportKeysWithSlotTime(baseKeys, slotKey);
  target.push(keys);
  const slice = objects.slice(0, maxRows);
  for (const o of slice) target.push(exportRowWithSlotTime(o, baseKeys, slotKey));
  if (objects.length > maxRows) {
    target.push([`… truncated at ${maxRows} rows (${objects.length} total)`]);
  }
}

/**
 * Flat rows[][] for one XLSX sheet (App2.0 export parity).
 */
export function app2PackToSheetRows(pack) {
  if (!pack || pack.empty) {
    return [['No App 2.0 bucketing data (DoorDash financial orders in configured periods required).']];
  }
  const target = [];
  pushObjectSection(target, 'By Period (store × Period)', pack.byPeriod);
  pushObjectSection(target, 'By Slot-Period (store × Day part × Period)', pack.bySlotPeriod);
  pushObjectSection(target, 'By Day (store × Day, all periods combined)', pack.byDay);
  pushObjectSection(target, 'Slot Pre vs Post', pack.slotPreVsPost);
  pushObjectSection(target, 'Slot YoY (Post vs LY Post)', pack.slotYoY);
  pushObjectSection(target, 'Day-Slot Pre vs Post', pack.daySlotPreVsPost);
  pushObjectSection(target, 'Day-Slot YoY', pack.daySlotYoY);
  pushObjectSection(target, 'Daypart GC — Post', pack.daypartGcPost);
  pushObjectSection(target, 'Daypart GC — Pre', pack.daypartGcPre);
  pushObjectSection(target, 'Daypart GC — Delta', pack.daypartGcDelta);
  pushObjectSection(target, 'Daypart GC — Delta %', pack.daypartGcDeltaPct);
  pushObjectSection(target, 'Store Daypart GC — Post', pack.storeDaypartGcPost);
  pushObjectSection(target, 'Store Daypart GC — Pre', pack.storeDaypartGcPre);
  pushObjectSection(target, 'Store Daypart GC — Delta', pack.storeDaypartGcDelta);
  pushObjectSection(target, 'Store Daypart GC — Delta %', pack.storeDaypartGcDeltaPct);
  pushObjectSection(target, 'Detail — Post period (store × date × day part)', pack.aggTables?.Post || []);
  return target;
}

export function columnsFromObjects(rows, labelMap = {}) {
  if (!rows?.length) {
    return [{ key: '_empty', label: '—', sortable: false }];
  }
  const keys = Object.keys(rows[0]);
  const slotKey = slotColumnKey(keys);
  const cols = [];
  for (const key of keys) {
    cols.push({
      key,
      label: labelMap[key] || key,
      align: typeof rows[0][key] === 'number' ? 'right' : 'left',
      sortable: true,
      labelCol: key === slotKey || key === STORE_COL,
    });
    if (key === slotKey) {
      cols.push({
        key: 'slotTime',
        label: SLOT_TIME_COLUMN_LABEL,
        align: 'left',
        sortable: false,
        labelCol: true,
        wrap: true,
        render: (_, row) => getSlotTimeRange(row[key]),
      });
    }
  }
  return cols;
}
