/** Canonical DoorDash / Uber Eats time columns for slots and period filters. */

import { parseDate } from '../utils/dateUtils';

export const FINANCIAL_ORDER_TIME_COL = 'Order received local time';
export const FINANCIAL_ORDER_TIME_FALLBACK_COL = 'Timestamp local time';
export const SALES_BY_ORDER_TIME_COL = 'Order placed time';
export const DD_FINANCIAL_DATE_COL = 'Timestamp local date';
export const UE_FINANCIAL_DATE_COL = 'Order Date';
export const UE_SLOT_TIME_COL = 'Order Accept Time';

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

/** DD slots: Order received local time, fallback Timestamp local time. */
export function resolveDdSlotTime(row, orderReceivedTimeCol, timestampLocalTimeCol) {
  const received = orderReceivedTimeCol ? row[orderReceivedTimeCol] : null;
  if (isPresentTimeValue(received)) return received;
  const fallback = timestampLocalTimeCol ? row[timestampLocalTimeCol] : null;
  return isPresentTimeValue(fallback) ? fallback : null;
}

/**
 * DD financial period date — Timestamp local date when present; otherwise the calendar
 * date from Timestamp local time (simplified exports often omit the date column).
 */
export function resolveDdFinancialDate(row, dateCol, timestampLocalTimeCol) {
  if (dateCol) {
    const fromDateCol = parseDate(row[dateCol]);
    if (fromDateCol) return fromDateCol;
  }
  const ts = timestampLocalTimeCol ? row[timestampLocalTimeCol] : null;
  if (!isPresentTimeValue(ts)) return null;
  const datePart = String(ts).trim().split(/\s+/)[0];
  return parseDate(datePart);
}
