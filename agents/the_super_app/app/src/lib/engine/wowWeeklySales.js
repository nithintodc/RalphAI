import { getWeek, getYear, startOfDay, endOfDay, addWeeks, endOfWeek, max, min } from 'date-fns';
import { filterExcludedDates, filterExcludedStores } from './aggregator';
import { resolveCanonStoreId, buildAnalysisScope } from '../utils/abStoreFilter';
import {
  getWowWeekRange,
  getWowAnchorDate,
  listWeeksInRange,
} from '../utils/analysisPeriodSelectors';
import { mergeAllUploadedBounds } from '../utils/uploadedDataBounds';
import { formatCompactDateRange } from '../utils/dateUtils';
import { STORE_TAG_LABELS } from '../export/exportSheetSummaries';
import {
  WOW_TABLE_METRICS,
  aggregateWowPeriodMetrics,
  buildMetricComparisons,
  lyRangeForWeek,
} from './wowMetrics';

function rowSales(row, platform) {
  if (platform === 'ue') return Number(row.sales) || 0;
  return Number(row.subtotal) || 0;
}

function passesStoreScope(row, platform, storeScope, scope) {
  const canon = resolveCanonStoreId(row.storeId, platform, scope.ddToUeStoreMap);
  if (!canon) return false;

  if (scope.includedIds?.size > 0 && !scope.includedIds.has(canon)) return false;

  if (storeScope === 'total') return true;
  if (storeScope === 'A' || storeScope === 'B') {
    return String(scope.tagMap?.[canon] || '').trim() === storeScope;
  }
  return canon === storeScope;
}

function ingestRows(rows, platform, config, scope, storeScope, weekStartsOn, buckets) {
  if (!rows?.length) return;

  const excludedStores = platform === 'dd' ? config.ddExcludedStores : config.ueExcludedStores;
  const excludedDates = platform === 'dd' ? config.ddExcludedDates : config.ueExcludedDates;

  let filtered = filterExcludedStores(rows, 'storeId', excludedStores || []);
  filtered = filterExcludedDates(filtered, 'date', excludedDates || []);

  for (const row of filtered) {
    if (!row?.date) continue;
    if (!passesStoreScope(row, platform, storeScope, scope)) continue;

    const d = startOfDay(row.date);
    const year = getYear(d);
    const week = getWeek(d, { weekStartsOn, firstWeekContainsDate: 1 });
    if (week < 1 || week > 53) continue;

    const key = `${year}|${week}`;
    buckets.set(key, (buckets.get(key) || 0) + rowSales(row, platform));
  }
}

/**
 * Weekly sales totals by calendar year and week index (1–52).
 * @param {'combined'|'dd'|'ue'} platform
 * @param {'total'|'A'|'B'|string} storeScope — canon store id for individual stores
 */
export function buildWowWeeklySalesSeries({
  ddFinancial,
  ueFinancial,
  config,
  platform = 'combined',
  storeScope = 'total',
  weekStartsOn = 1,
}) {
  const scope = buildAnalysisScope(config);
  const buckets = new Map();

  if (platform === 'dd' || platform === 'combined') {
    ingestRows(ddFinancial, 'dd', config, scope, storeScope, weekStartsOn, buckets);
  }
  if (platform === 'ue' || platform === 'combined') {
    ingestRows(ueFinancial, 'ue', config, scope, storeScope, weekStartsOn, buckets);
  }

  const years = [...new Set([...buckets.keys()].map((k) => Number(k.split('|')[0])))].sort((a, b) => a - b);
  const maxWeek = 52;
  const chartRows = [];

  for (let week = 1; week <= maxWeek; week += 1) {
    const point = { week };
    for (const year of years) {
      const val = buckets.get(`${year}|${week}`);
      point[`y${year}`] = val != null ? Math.round(val * 100) / 100 : null;
    }
    chartRows.push(point);
  }

  return { years, chartRows, maxWeek, weekStartsOn };
}

/** Build store scope options for the WoW filter (total, A/B groups, individual stores). */
export function buildWowStoreScopeOptions(storeTables, config) {
  const combined = storeTables?.combined || [];
  const tagMap = config.storeTagMap || {};
  const stores = combined
    .map((r) => ({
      id: String(r.storeId || '').trim(),
      label: r.storeName || r.merchantStoreId || r.storeId || '',
      tag: String(tagMap[r.storeId] || '').trim(),
    }))
    .filter((s) => s.id)
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));

  const hasA = stores.some((s) => s.tag === 'A');
  const hasB = stores.some((s) => s.tag === 'B');

  return { stores, hasA, hasB };
}

function filterFinancialRows(rows, platform, config) {
  if (!rows?.length) return [];
  const excludedStores = platform === 'dd' ? config.ddExcludedStores : config.ueExcludedStores;
  const excludedDates = platform === 'dd' ? config.ddExcludedDates : config.ueExcludedDates;
  let filtered = filterExcludedStores(rows, 'storeId', excludedStores || []);
  filtered = filterExcludedDates(filtered, 'date', excludedDates || []);
  return filtered;
}

function metricsInDateRange({
  ddFinancial,
  ueFinancial,
  ddMarketing,
  config,
  platform,
  scope,
  storeScope,
  start,
  end,
}) {
  return aggregateWowPeriodMetrics({
    ddFinancial,
    ueFinancial,
    ddMarketing,
    config,
    platform,
    storeScope,
    start,
    end,
  });
}

function salesInDateRange(rows, platform, start, end, scope, tagFilter, storeIdFilter = null) {
  const rangeStart = startOfDay(start);
  const rangeEnd = endOfDay(end);
  let total = 0;

  for (const row of rows) {
    if (!row?.date) continue;
    const d = startOfDay(row.date);
    if (d < rangeStart || d > rangeEnd) continue;

    const canon = resolveCanonStoreId(row.storeId, platform, scope.ddToUeStoreMap);
    if (!canon) continue;
    if (scope.includedIds?.size > 0 && !scope.includedIds.has(canon)) continue;
    if (tagFilter && String(scope.tagMap?.[canon] || '').trim() !== tagFilter) continue;
    if (storeIdFilter && canon !== storeIdFilter) continue;

    total += rowSales(row, platform);
  }
  return Math.round(total * 100) / 100;
}

function buildWeekColumnsFromRange(rangeStart, rangeEnd, bounds, weekStartsOn) {
  const weeks = listWeeksInRange(rangeStart, rangeEnd, bounds, weekStartsOn);
  return weeks.map((week, i) => ({
    key: `w${i + 1}`,
    label: `W${i + 1}`,
    weekIndex: i,
    start: week.start,
    end: week.end,
    rangeLabel: formatCompactDateRange(week.start, week.end),
  }));
}

function computeTotalSalesInRange(args) {
  return metricsInDateRange(args).sales;
}

/**
 * WoW rows for every business week in the analysis range — all metrics with WoW and YoY.
 */
export function buildWowAnalysisRangeTable({
  ddFinancial,
  ueFinancial,
  ddMarketing,
  config,
  platform = 'combined',
  storeScope = 'total',
  weekStartsOn = 1,
  rangeStart,
  rangeEnd,
}) {
  const bounds = mergeAllUploadedBounds(ddFinancial, ueFinancial, null);
  const weeks = listWeeksInRange(rangeStart, rangeEnd, bounds, weekStartsOn);
  const shared = {
    ddFinancial,
    ueFinancial,
    ddMarketing,
    config,
    platform,
    storeScope,
  };

  const rows = weeks.map((week, i) => {
    const current = metricsInDateRange({ ...shared, start: week.start, end: week.end });

    let priorStart = null;
    let priorEnd = null;
    if (i > 0) {
      priorStart = weeks[i - 1].start;
      priorEnd = weeks[i - 1].end;
    } else if (week.weekStart) {
      const prevWeekStart = addWeeks(week.weekStart, -1);
      priorStart = max([startOfDay(bounds.min), startOfDay(prevWeekStart)]);
      priorEnd = min([endOfDay(bounds.max), endOfDay(endOfWeek(prevWeekStart, { weekStartsOn }))]);
    }

    const prior = priorStart && priorEnd && priorStart <= priorEnd
      ? metricsInDateRange({ ...shared, start: priorStart, end: priorEnd })
      : null;

    const ly = lyRangeForWeek(week.start, week.end);
    const lyMetrics = metricsInDateRange({ ...shared, start: ly.start, end: ly.end });

    return {
      id: week.id,
      label: week.label,
      start: week.start,
      end: week.end,
      rangeLabel: formatCompactDateRange(week.start, week.end),
      metrics: buildMetricComparisons(current, prior, lyMetrics),
    };
  });

  return { rows, metrics: WOW_TABLE_METRICS, weekStartsOn, rangeStart, rangeEnd };
}

function buildRecentWeekColumns(anchorDate, weekStartsOn, weekCount = 4) {
  const columns = [];
  for (let i = 0; i < weekCount; i += 1) {
    const weekIndex = i - (weekCount - 1);
    const { start, end } = getWowWeekRange(anchorDate, weekIndex, weekStartsOn);
    columns.push({
      key: `w${i + 1}`,
      label: `Week ${i + 1}`,
      weekIndex,
      start,
      end,
      rangeLabel: formatCompactDateRange(start, end),
    });
  }
  return columns;
}

function buildSingleGroupTable({
  stores,
  tag,
  weekColumns,
  ddFinancial,
  ueFinancial,
  ddMarketing,
  config,
  platform,
  scope,
  metricKey = 'sales',
}) {
  const taggedStores = stores.filter((s) => s.tag === tag);

  const rows = taggedStores.map((store) => {
    const weeks = {};
    for (const col of weekColumns) {
      const m = aggregateWowPeriodMetrics({
        ddFinancial,
        ueFinancial,
        ddMarketing,
        config,
        platform,
        storeScope: store.id,
        start: col.start,
        end: col.end,
      });
      weeks[col.key] = m[metricKey] ?? 0;
    }
    return { id: store.id, label: store.label, weeks };
  });

  const totals = {};
  const averages = {};
  for (const col of weekColumns) {
    const sum = rows.reduce((acc, row) => acc + (row.weeks[col.key] || 0), 0);
    totals[col.key] = Math.round(sum * 100) / 100;
    averages[col.key] = rows.length
      ? Math.round((sum / rows.length) * 100) / 100
      : 0;
  }

  return {
    tag,
    title: `Group ${tag} (${STORE_TAG_LABELS[tag] || tag} stores)`,
    rows,
    totals,
    averages,
    weekColumns,
    storeCount: rows.length,
    metricKey,
  };
}

/**
 * WoW group tables: A (TODC) and B (Non-TODC) with business weeks in range per store.
 */
export function buildWowGroupSalesTables({
  ddFinancial,
  ueFinancial,
  ddMarketing,
  config,
  storeTables,
  platform = 'combined',
  weekStartsOn = 1,
  weekCount = 4,
  rangeStart = null,
  rangeEnd = null,
  metricKey = 'sales',
}) {
  const scope = buildAnalysisScope(config);
  const { stores } = buildWowStoreScopeOptions(storeTables, config);
  const bounds = mergeAllUploadedBounds(ddFinancial, ueFinancial, null);
  const anchor = getWowAnchorDate(bounds);
  const weekColumns = rangeStart && rangeEnd
    ? buildWeekColumnsFromRange(rangeStart, rangeEnd, bounds, weekStartsOn)
    : buildRecentWeekColumns(anchor, weekStartsOn, weekCount);

  const shared = {
    ddFinancial,
    ueFinancial,
    ddMarketing,
    config,
    platform,
    scope,
    weekColumns,
    metricKey,
  };

  return {
    weekColumns,
    weekStartsOn,
    anchor,
    metricKey,
    groupA: buildSingleGroupTable({ ...shared, stores, tag: 'A' }),
    groupB: buildSingleGroupTable({ ...shared, stores, tag: 'B' }),
  };
}
