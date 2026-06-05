/** Canonical DoorDash order-time columns for slot / day-part assignment. */

export const FINANCIAL_ORDER_TIME_COL = 'Order received local time';
export const SALES_BY_ORDER_TIME_COL = 'Order placed time';

export function findExactColumn(columns, exactName) {
  const target = String(exactName).trim().toLowerCase();
  for (const col of columns || []) {
    if (String(col).trim().toLowerCase() === target) return col;
  }
  return null;
}

export function isPresentTimeValue(value) {
  if (value == null || value === undefined) return false;
  const s = String(value).trim();
  return !!s && !/^null$/i.test(s) && s !== '—' && s.toLowerCase() !== 'nan';
}
