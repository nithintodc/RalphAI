import { filterByDateRange, filterExcludedDates } from '../engine/aggregator';
import { getLastYearDates } from './dateUtils';

function countUniqueStoreIds(rows, storeField = 'storeId') {
  const ids = new Set();
  for (const r of rows) {
    const id = String(r[storeField] ?? '').trim();
    if (id) ids.add(id);
  }
  return ids.size;
}

function filterWindow(data, dateField, start, end, excludedDates) {
  let filtered = filterByDateRange(data, dateField, start, end);
  filtered = filterExcludedDates(filtered, dateField, excludedDates);
  return filtered;
}

/**
 * Count distinct store IDs in Pre, Post, LY Pre, and LY Post windows.
 */
export function countStoreIdsByPeriod(financialRows, config) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [] } = config;
  if (!financialRows?.length || !preStart || !preEnd || !postStart || !postEnd) return null;

  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);

  const windows = {
    pre: { start: preStart, end: preEnd },
    post: { start: postStart, end: postEnd },
    preLY: lyPre,
    postLY: lyPost,
  };

  const counts = {};
  for (const [name, { start, end }] of Object.entries(windows)) {
    const filtered = filterWindow(financialRows, 'date', start, end, excludedDates);
    counts[name] = countUniqueStoreIds(filtered);
  }
  return counts;
}

export const STORE_PERIOD_LABELS = {
  pre: 'Pre',
  post: 'Post',
  preLY: 'LY Pre',
  postLY: 'LY Post',
};
