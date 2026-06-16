import { filterByDateRange, filterExcludedDates, filterExcludedStores } from '../engine/aggregator';
import { getLastYearDates } from './dateUtils';

const WINDOWS = ['pre', 'post', 'preLY', 'postLY'];

function compareStoreIds(a, b) {
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

function filterWindow(data, dateField, start, end, excludedDates, excludedStores) {
  let filtered = filterByDateRange(data, dateField, start, end);
  filtered = filterExcludedDates(filtered, dateField, excludedDates);
  filtered = filterExcludedStores(filtered, 'storeId', excludedStores);
  return filtered;
}

/** Store is active in a window when it has sales or at least one order. */
function isActiveStoreRow(row, salesField = 'subtotal', orderField = 'orderId') {
  const sales = Number(row[salesField]) || 0;
  if (sales > 0) return true;
  const oid = String(row[orderField] ?? '').trim();
  return !!oid;
}

/**
 * Active store IDs per period window from raw financial rows.
 * A store with only zero-sales rows in a period is treated as unavailable.
 */
export function getActiveStoreIdsByPeriod(financialRows, config, { salesField = 'subtotal', orderField = 'orderId' } = {}) {
  const { preStart, preEnd, postStart, postEnd, excludedDates = [], excludedStores = [] } = config;
  if (!financialRows?.length || !preStart || !preEnd || !postStart || !postEnd) return null;

  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);

  const ranges = {
    pre: { start: preStart, end: preEnd },
    post: { start: postStart, end: postEnd },
    preLY: lyPre,
    postLY: lyPost,
  };

  const sets = {};
  for (const [name, { start, end }] of Object.entries(ranges)) {
    const filtered = filterWindow(financialRows, 'date', start, end, excludedDates, excludedStores);
    const ids = new Set();
    for (const row of filtered) {
      if (!isActiveStoreRow(row, salesField, orderField)) continue;
      const id = String(row.storeId ?? '').trim();
      if (id) ids.add(id);
    }
    sets[name] = ids;
  }
  return sets;
}

function isActiveInMergedWindow(row, window) {
  return (Number(row[`${window}_orders`]) || 0) > 0 || (Number(row[`${window}_sales`]) || 0) > 0;
}

/** Active store IDs from merged platform store rows (after periodEngine). */
export function getActiveStoreIdsFromPlatformRows(storeRows) {
  const sets = {};
  for (const win of WINDOWS) {
    const ids = new Set();
    for (const row of storeRows || []) {
      const id = String(row.storeId ?? '').trim();
      if (!id || !isActiveInMergedWindow(row, win)) continue;
      ids.add(id);
    }
    sets[win] = ids;
  }
  return sets;
}

function intersectSets(a, b) {
  const out = new Set();
  for (const id of a) {
    if (b.has(id)) out.add(id);
  }
  return out;
}

function diffSets(from, other) {
  return [...from].filter((id) => !other.has(id)).sort(compareStoreIds);
}

function computePairComparison(leftSet, rightSet, leftLabel, rightLabel) {
  const common = intersectSets(leftSet, rightSet);
  const excludedFromLeft = diffSets(leftSet, rightSet);
  const excludedFromRight = diffSets(rightSet, leftSet);
  return {
    leftLabel,
    rightLabel,
    leftCount: leftSet.size,
    rightCount: rightSet.size,
    commonCount: common.size,
    commonIds: common,
    excludedFromLeft,
    excludedFromRight,
    needsAlignment:
      leftSet.size !== rightSet.size
      || excludedFromLeft.length > 0
      || excludedFromRight.length > 0,
  };
}

/**
 * Build common-store sets and exclusion metadata for Pre/Post, LY Pre/Post, and YoY.
 */
export function buildStorePeriodAlignment(activeSets) {
  if (!activeSets) return null;

  const pvp = computePairComparison(activeSets.pre, activeSets.post, 'Pre', 'Post');
  const lyPvp = computePairComparison(activeSets.preLY, activeSets.postLY, 'LY Pre', 'LY Post');
  const yoy = computePairComparison(activeSets.post, activeSets.postLY, 'Post', 'LY Post');

  return { pvp, lyPvp, yoy, activeSets };
}

export function buildStorePeriodAlignmentFromRows(storeRows) {
  return buildStorePeriodAlignment(getActiveStoreIdsFromPlatformRows(storeRows));
}

export function filterStoreRowsByIds(storeRows, idSet) {
  if (!idSet?.size) return [];
  return (storeRows || []).filter((row) => idSet.has(String(row.storeId ?? '').trim()));
}

/** Store IDs to exclude so only Pre ∩ Post common stores remain in analysis. */
export function buildPeriodExcludedStores(allStoreIds, alignment) {
  if (!alignment?.pvp?.commonIds?.size) return [];
  const common = alignment.pvp.commonIds;
  return (allStoreIds || [])
    .map((id) => String(id ?? '').trim())
    .filter((id) => id && !common.has(id));
}

export function mergeExcludedStores(manualExcluded = [], periodExcluded = []) {
  return [...new Set([...(manualExcluded || []), ...(periodExcluded || [])])];
}

function formatExclusionList(ids, periodLabel) {
  if (!ids?.length) return '';
  const list = ids.join(', ');
  const noun = ids.length === 1 ? 'store' : 'stores';
  return `${list} excluded from ${periodLabel} (${noun} not available or 0 sales in ${periodLabel})`;
}

function formatPairNote(pair, comparisonLabel) {
  const n = pair.commonCount;
  if (!pair.needsAlignment) {
    return `Comparing ${n} store${n === 1 ? '' : 's'} in ${pair.leftLabel} to ${n} store${n === 1 ? '' : 's'} in ${pair.rightLabel}${comparisonLabel ? ` (${comparisonLabel})` : ''}.`;
  }

  const parts = [];
  if (pair.excludedFromLeft.length) parts.push(formatExclusionList(pair.excludedFromLeft, pair.leftLabel));
  if (pair.excludedFromRight.length) parts.push(formatExclusionList(pair.excludedFromRight, pair.rightLabel));

  let msg = `Comparing ${n} store${n === 1 ? '' : 's'} in ${pair.leftLabel} to ${n} store${n === 1 ? '' : 's'} in ${pair.rightLabel}`;
  if (comparisonLabel) msg += ` (${comparisonLabel})`;
  if (parts.length) msg += `. Exclusion: ${parts.join('; ')}.`;
  else msg += '.';
  return msg;
}

/** Human-readable notes for UI banners (Pre/Post, LY Pre/Post, YoY). */
export function formatStoreComparisonNotes(alignment) {
  if (!alignment) return [];
  const notes = [];
  notes.push(formatPairNote(alignment.pvp, 'Pre vs Post'));
  if (alignment.lyPvp.needsAlignment) {
    notes.push(formatPairNote(alignment.lyPvp, 'LY Pre vs LY Post'));
  }
  if (alignment.yoy.needsAlignment) {
    notes.push(formatPairNote(alignment.yoy, 'YoY'));
  }
  return notes;
}

/** Counts of active stores (sales/orders > 0) per window — for config UI. */
export function countActiveStoreIdsByPeriod(financialRows, config, options) {
  const sets = getActiveStoreIdsByPeriod(financialRows, config, options);
  if (!sets) return null;
  return {
    pre: sets.pre.size,
    post: sets.post.size,
    preLY: sets.preLY.size,
    postLY: sets.postLY.size,
  };
}
