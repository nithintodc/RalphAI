/**
 * Date/store bounds from uploads when financial ZIPs are not present (sales-only path).
 */
import { endOfMonth, startOfMonth, subMonths, max as dfMax, min as dfMin } from 'date-fns';
import { coerceDdSalesByOrderParsed, normalizeDdSalesByOrder } from '../parsers/ddSalesByOrder';
import { parseDate, minMaxDates } from './dateUtils';
import { getDateRange as getDdFinancialRange } from '../parsers/ddFinancial';
import { getDateRange as getUeFinancialRange } from '../parsers/ueFinancial';

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

export function hasAnyDdSales(ddSales) {
  if (!ddSales) return false;
  const bo = coerceDdSalesByOrderParsed(ddSales.byOrder);
  if (bo.data?.length) return true;
  if (ddSales.byTime?.data?.length) return true;
  if (ddSales.byStore?.data?.length) return true;
  return false;
}

export function getDdSalesDateRange(ddSales) {
  const dates = [];

  const orders = normalizeDdSalesByOrder(ddSales?.byOrder);
  for (const o of orders) {
    if (o.date) dates.push(o.date);
  }

  const byTime = ddSales?.byTime;
  if (byTime?.data?.length) {
    const columns = byTime.columns || Object.keys(byTime.data[0] || {});
    const dateCol = findCol(columns, [
      'Date',
      'date',
      'Timestamp local date',
      'Day',
    ]);
    const granCol = findCol(columns, ['Granularity', 'granularity']);
    for (const row of byTime.data) {
      if (dateCol) {
        const d = parseDate(row[dateCol]);
        if (d) dates.push(d);
      }
      if (granCol) {
        const g = String(row[granCol] || '').trim();
        const m = g.match(/(\d{1,2}\/\d{1,2}\/\d{4})/);
        if (m) {
          const d = parseDate(m[1]);
          if (d) dates.push(d);
        }
      }
    }
  }

  const byStore = ddSales?.byStore;
  if (byStore?.data?.length) {
    const columns = byStore.columns || Object.keys(byStore.data[0] || {});
    const startCol = findCol(columns, ['Start date', 'Start Date', 'start date']);
    const endCol = findCol(columns, ['End date', 'End Date', 'end date']);
    const dateCol = findCol(columns, ['Date', 'date']);
    for (const row of byStore.data) {
      if (startCol) {
        const d = parseDate(row[startCol]);
        if (d) dates.push(d);
      }
      if (endCol) {
        const d = parseDate(row[endCol]);
        if (d) dates.push(d);
      }
      if (dateCol) {
        const d = parseDate(row[dateCol]);
        if (d) dates.push(d);
      }
    }
  }

  return minMaxDates(dates);
}

export function getDdSalesStoreIds(ddSales) {
  const ids = new Set();
  for (const o of normalizeDdSalesByOrder(ddSales?.byOrder)) {
    if (o.storeId) ids.add(String(o.storeId));
  }
  const byStore = ddSales?.byStore;
  if (byStore?.data?.length) {
    const columns = byStore.columns || Object.keys(byStore.data[0] || {});
    const storeCol = findCol(columns, [
      'Merchant supplied store ID',
      'Store ID',
      'Store id',
      'Merchant Store ID',
    ]);
    for (const row of byStore.data) {
      const id = storeCol ? String(row[storeCol] || '').trim() : '';
      if (id) ids.add(id);
    }
  }
  return [...ids].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

/** DoorDash date span: financial rows first, else sales exports. */
export function getDdUploadedDateRange(ddFinancial, ddSales) {
  if (ddFinancial?.length) return getDdFinancialRange(ddFinancial);
  return getDdSalesDateRange(ddSales);
}

/** Suggested Pre/Post: latest calendar month = Post, prior month = Pre (clamped to data). */
export function suggestPrePostFromBounds(bounds) {
  const { min, max } = bounds || {};
  if (!min || !max) return null;

  const postEnd = dfMin([max, endOfMonth(max)]);
  const postStart = dfMax([min, startOfMonth(max)]);
  const preAnchor = subMonths(postStart, 1);
  const preEnd = dfMin([max, endOfMonth(preAnchor)]);
  const preStart = dfMax([min, startOfMonth(preAnchor)]);

  if (preStart > preEnd || postStart > postEnd) return null;
  return { preStart, preEnd, postStart, postEnd };
}

export function mergeAllUploadedBounds(ddFinancial, ueFinancial, ddSales) {
  const ranges = [];
  if (ddFinancial?.length) {
    const r = getDdFinancialRange(ddFinancial);
    if (r.min && r.max) ranges.push(r);
  } else {
    const r = getDdSalesDateRange(ddSales);
    if (r.min && r.max) ranges.push(r);
  }
  if (ueFinancial?.length) {
    const r = getUeFinancialRange(ueFinancial);
    if (r.min && r.max) ranges.push(r);
  }
  if (!ranges.length) return { min: null, max: null };
  const minT = Math.min(...ranges.map((r) => r.min.getTime()));
  const maxT = Math.max(...ranges.map((r) => r.max.getTime()));
  return { min: new Date(minT), max: new Date(maxT) };
}
