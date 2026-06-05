import { parseDate } from '../utils/dateUtils';
import { toNum } from '../utils/safeMath';
import { getSlot, DAY_NAMES } from '../engine/slots';
import { SALES_BY_ORDER_TIME_COL, findExactColumn, isPresentTimeValue } from '../constants/orderTimeColumns';

function normalizeColHeader(col) {
  return String(col ?? '')
    .replace(/\uFEFF/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

function findCol(columns, variations) {
  const normCols = columns.map((c) => ({ raw: c, norm: normalizeColHeader(c) }));
  for (const v of variations) {
    const vn = normalizeColHeader(v);
    const hit = normCols.find(({ norm }) => norm === vn);
    if (hit) return hit.raw;
  }
  for (const v of variations) {
    const vn = normalizeColHeader(v);
    const hit = normCols.find(({ norm }) => norm.includes(vn) || vn.includes(norm));
    if (hit) return hit.raw;
  }
  return null;
}

export function normalizeDashPass(raw) {
  if (raw == null || raw === '') return null;
  const s = String(raw).trim().toLowerCase();
  if (s === 'true' || s === 'yes' || s === '1') return true;
  if (s === 'false' || s === 'no' || s === '0') return false;
  return null;
}

export function normalizeCustomerType(raw) {
  const s = String(raw ?? '').trim().toLowerCase();
  if (!s) return 'unknown';
  if (s === 'new' || s.includes('new customer')) return 'new';
  if (s === 'repeat' || s.includes('repeat') || s.includes('existing')) return 'repeat';
  if (s === 'unknown' || s === 'unknow') return 'unknown';
  return 'unknown';
}

function dayLabel(date) {
  if (!date) return null;
  const idx = (date.getDay() + 6) % 7;
  return DAY_NAMES[idx] ?? null;
}

/** Accept `{ data, columns }` from zipHandler or a legacy bare row array from an old upload bug. */
export function coerceDdSalesByOrderParsed(parsed) {
  if (!parsed) return { data: [], columns: [] };
  if (Array.isArray(parsed)) {
    const data = parsed;
    return { data, columns: data[0] ? Object.keys(data[0]) : [] };
  }
  const data = parsed.data ?? [];
  const columns = parsed.columns || (data[0] ? Object.keys(data[0]) : []);
  return { data, columns };
}

/**
 * Normalize DoorDash SALES_BY_ORDER export rows for slot / day-slot analytics.
 * Uses Order placed date + Order placed time for daypart; Customer type + item count when present.
 */
export function normalizeDdSalesByOrder(parsed) {
  const { data: rows, columns } = coerceDdSalesByOrderParsed(parsed);
  if (!rows?.length) return [];

  const dateCol = findCol(columns, [
    'Order placed date',
    'Order Placed Date',
    'order placed date',
  ]);
  const timeCol = findExactColumn(columns, SALES_BY_ORDER_TIME_COL);
  const orderCol = findCol(columns, [
    'DoorDash order ID',
    'DoorDash Order ID',
    'Order ID',
    'order id',
  ]);
  const customerCol = findCol(columns, [
    'Customer type',
    'Customer Type',
    'customer type',
  ]);
  const itemCol = findCol(columns, [
    'Item count',
    'Item Count',
    'Total item count',
    'Total Item Count',
    'Items in order',
    'Number of items',
  ]);
  const dashPassCol = findCol(columns, [
    'Is DashPass',
    'Is Dashpass',
    'DashPass',
    'is dashpass',
  ]);
  const errorChargeCol = findCol(columns, ['Error charge', 'Error Charge', 'error charge']);
  const storeCol = findCol(columns, [
    'Merchant supplied store ID',
    'Merchant Supplied Store ID',
    'Store ID',
    'store id',
  ]);
  const cancelledCol = findCol(columns, ['Was Cancelled', 'Was cancelled', 'Is cancelled', 'Is Cancelled']);

  const normalizeOrderId = (id) => String(id || '').trim().toUpperCase();

  const out = [];
  for (const row of rows) {
    if (!row) continue;
    if (cancelledCol && String(row[cancelledCol] || '').trim().toLowerCase() === 'true') continue;

    const date = dateCol ? parseDate(row[dateCol]) : null;
    const time = timeCol ? row[timeCol] : null;
    if (!isPresentTimeValue(time)) continue;
    const orderId = orderCol ? normalizeOrderId(row[orderCol]) : '';
    const storeId = storeCol ? String(row[storeCol] || '').trim() : '';
    if (!date || !storeId) continue;

    const slot = getSlot(time, 'dd');
    const day = dayLabel(date);
    if (!day) continue;

    out.push({
      orderId,
      storeId,
      date,
      time,
      slot,
      day,
      customerType: customerCol ? normalizeCustomerType(row[customerCol]) : 'unknown',
      itemCount: itemCol ? toNum(row[itemCol]) : 0,
      isDashPass: dashPassCol ? normalizeDashPass(row[dashPassCol]) : null,
      errorCharge: errorChargeCol ? Math.abs(toNum(row[errorChargeCol])) : 0,
    });
  }
  return out;
}
