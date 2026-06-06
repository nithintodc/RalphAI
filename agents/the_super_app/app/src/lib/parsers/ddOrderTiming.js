import { parseDate } from '../utils/dateUtils';
import { coerceDdSalesByOrderParsed, normalizeDdSalesByOrder } from './ddSalesByOrder';

export function normalizeOrderId(id) {
  return String(id || '').trim().toUpperCase();
}

function isMissingTime(raw) {
  if (raw == null || raw === '') return true;
  const s = String(raw).trim();
  return !s || /^null$/i.test(s);
}

/** Sales by order → order ID → { date, time } (order placed). */
export function buildDdOrderPlacedLookup(salesOrders) {
  const map = new Map();
  for (const o of salesOrders || []) {
    const id = normalizeOrderId(o.orderId);
    if (!id || !o.date) continue;
    map.set(id, { date: o.date, time: o.time ?? null });
  }
  return map;
}

function resolvePlacedFromRow(row) {
  const recv = row.orderReceivedTime;
  if (!isMissingTime(recv)) {
    const parsed = parseDate(recv);
    return {
      date: parsed || row.date,
      time: recv,
    };
  }
  return null;
}

/**
 * Align DD financial rows to order-placed date/time (legacy helper).
 * Financial KPIs and register period filters use `Timestamp local date` on each row's `date` field instead.
 */
export function applyDdOrderPlacedTiming(ddRows, salesParsed) {
  if (!ddRows?.length) return ddRows || [];
  const sales = normalizeDdSalesByOrder(coerceDdSalesByOrderParsed(salesParsed));
  const lookup = buildDdOrderPlacedLookup(sales);

  return ddRows.map((row) => {
    const fromSales = row.orderId ? lookup.get(normalizeOrderId(row.orderId)) : null;
    if (fromSales) {
      return { ...row, date: fromSales.date, time: fromSales.time };
    }
    const fromRecv = resolvePlacedFromRow(row);
    if (fromRecv) {
      return { ...row, date: fromRecv.date, time: fromRecv.time };
    }
    return row;
  });
}
