import { filterByDateRange, filterExcludedDates } from './aggregator';
import { safeDivide, round } from '../utils/safeMath';
import { SLOT_NAMES, DAY_NAMES, getSlotTimeRange, SLOT_TIME_COLUMN_LABEL } from './slots';

function aggregateBucket(orders) {
  const n = orders.length;
  let newCount = 0;
  let repeatCount = 0;
  let unknownCount = 0;
  let totalItems = 0;
  let dashPassCount = 0;
  let nonDashPassCount = 0;
  for (const o of orders) {
    if (o.customerType === 'new') newCount += 1;
    else if (o.customerType === 'repeat') repeatCount += 1;
    else unknownCount += 1;
    totalItems += Number(o.itemCount) || 0;
    if (o.isDashPass === true) dashPassCount += 1;
    else if (o.isDashPass === false) nonDashPassCount += 1;
  }
  const pct = (c) => round(safeDivide(c, n) * 100, 1);
  return {
    orders: n,
    newCount,
    repeatCount,
    unknownCount,
    newPct: pct(newCount),
    repeatPct: pct(repeatCount),
    unknownPct: pct(unknownCount),
    dashPassCount,
    nonDashPassCount,
    dashPassPct: pct(dashPassCount),
    nonDashPassPct: pct(nonDashPassCount),
    totalItems: Math.round(totalItems),
    avgItemsPerOrder: round(safeDivide(totalItems, n), 2),
  };
}

function filterWindow(orders, start, end, excludedDates) {
  let filtered = filterByDateRange(orders, 'date', start, end);
  filtered = filterExcludedDates(filtered, 'date', excludedDates);
  return filtered;
}

function buildSlotRows(orders) {
  const bySlot = new Map(SLOT_NAMES.map((s) => [s, []]));
  for (const o of orders) {
    if (!SLOT_NAMES.includes(o.slot)) continue;
    bySlot.get(o.slot).push(o);
  }
  return SLOT_NAMES.map((slot) => ({
    slot,
    ...aggregateBucket(bySlot.get(slot) || []),
  }));
}

function buildDayRows(orders) {
  const byDay = new Map(DAY_NAMES.map((d) => [d, []]));
  for (const o of orders) {
    if (o.day) byDay.get(o.day).push(o);
  }
  return DAY_NAMES.map((day) => ({
    day,
    ...aggregateBucket(byDay.get(day) || []),
  })).filter((r) => r.orders > 0);
}

function buildDaySlotRows(orders) {
  const rows = [];
  for (const day of DAY_NAMES) {
    for (const slot of SLOT_NAMES) {
      const bucket = orders.filter((o) => o.day === day && o.slot === slot);
      rows.push({
        day,
        slot,
        label: `${day} · ${slot}`,
        ...aggregateBucket(bucket),
      });
    }
  }
  return rows.filter((r) => r.orders > 0);
}

/**
 * Customer-type mix + item counts from SALES_BY_ORDER, aggregated by slot and by day×slot.
 */
export function buildSlotSalesOrderAnalysis(normalizedOrders, config) {
  const {
    preStart,
    preEnd,
    postStart,
    postEnd,
    excludedDates = [],
  } = config;

  if (!normalizedOrders?.length || !preStart || !preEnd || !postStart || !postEnd) {
    return null;
  }

  const preOrders = filterWindow(normalizedOrders, preStart, preEnd, excludedDates);
  const postOrders = filterWindow(normalizedOrders, postStart, postEnd, excludedDates);

  return {
    pre: {
      slot: buildSlotRows(preOrders),
      day: buildDayRows(preOrders),
      daySlot: buildDaySlotRows(preOrders),
    },
    post: {
      slot: buildSlotRows(postOrders),
      day: buildDayRows(postOrders),
      daySlot: buildDaySlotRows(postOrders),
    },
    hasCustomerType: normalizedOrders.some((o) => o.customerType !== 'unknown'),
    hasItemCount: normalizedOrders.some((o) => (o.itemCount || 0) > 0),
    hasDashPass: normalizedOrders.some((o) => o.isDashPass != null),
  };
}

export const SLOT_SALES_ORDER_EXPORT_METRICS = [
  { key: 'orders', label: 'Orders' },
  { key: 'newCount', label: 'New' },
  { key: 'newPct', label: 'New %' },
  { key: 'repeatCount', label: 'Repeat' },
  { key: 'repeatPct', label: 'Repeat %' },
  { key: 'unknownCount', label: 'Unknown' },
  { key: 'unknownPct', label: 'Unknown %' },
  { key: 'totalItems', label: 'Total items' },
  { key: 'avgItemsPerOrder', label: 'Avg items / order' },
];

export const DASHPASS_EXPORT_METRICS = [
  { key: 'orders', label: 'Orders' },
  { key: 'dashPassCount', label: 'DashPass' },
  { key: 'dashPassPct', label: 'DashPass %' },
  { key: 'nonDashPassCount', label: 'Non-DashPass' },
  { key: 'nonDashPassPct', label: 'Non-DashPass %' },
];

export function slotSalesOrderExportHeaders() {
  return ['Row', SLOT_TIME_COLUMN_LABEL, ...SLOT_SALES_ORDER_EXPORT_METRICS.map((c) => c.label)];
}

export function slotSalesOrderExportRow(label, row) {
  const slotTime = row?.slot ? getSlotTimeRange(row.slot) : getSlotTimeRange(label);
  return [label, slotTime, ...SLOT_SALES_ORDER_EXPORT_METRICS.map((c) => row?.[c.key] ?? '')];
}

export function dashPassExportHeaders() {
  return ['Row', SLOT_TIME_COLUMN_LABEL, ...DASHPASS_EXPORT_METRICS.map((c) => c.label)];
}

export function dashPassExportRow(label, row) {
  const slotTime = row?.slot ? getSlotTimeRange(row.slot) : getSlotTimeRange(label);
  return [label, slotTime, ...DASHPASS_EXPORT_METRICS.map((c) => row?.[c.key] ?? '')];
}

export function orderVolumeExportHeaders() {
  return ['Row', SLOT_TIME_COLUMN_LABEL, 'Orders'];
}

export function orderVolumeExportRow(label, row) {
  const slotTime = row?.slot ? getSlotTimeRange(row.slot) : getSlotTimeRange(label);
  return [label, slotTime, row?.orders ?? ''];
}
