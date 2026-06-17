/**
 * Fast snapshot after Pre vs Post analysis — stores, daily sales extremes, slot sales.
 */
import { buildSlotAnalysis } from './slots';
import { getPlatformDailyExtremes } from './diagnostics';

export function getStoresLeastGrowth(storeData, count = 5) {
  if (!storeData?.length) return [];
  const eligible = storeData.filter(
    (s) => s.sales_growth_pct != null && Number.isFinite(s.sales_growth_pct),
  );
  return [...eligible]
    .sort((a, b) => (a.sales_growth_pct || 0) - (b.sales_growth_pct || 0))
    .slice(0, Math.max(1, count));
}

export function getSlotsLowestSales(rawData, slotConfig, count = 3) {
  const { preStart, postStart } = slotConfig || {};
  if (!rawData?.length || !preStart || !postStart) return [];

  const analysis = buildSlotAnalysis(rawData, slotConfig);
  const rows = analysis?.salesPrePost || [];
  return [...rows]
    .sort((a, b) => (a.post || 0) - (b.post || 0))
    .slice(0, Math.max(1, count))
    .map((r) => ({ slot: r.slot, sales: r.post || 0 }));
}

function sliceDateExtremes(extremes, count) {
  if (!extremes) return { top: [], low: [] };
  return {
    top: (extremes.top || []).slice(0, count),
    low: (extremes.low || []).slice(0, count),
  };
}

function buildPlatformInsights(platform, data, config, limits) {
  const prefix = platform === 'ue' ? 'ue' : 'dd';
  const financial = platform === 'ue' ? data.ueFinancial : data.ddFinancial;
  if (!financial?.length) return null;

  const preStart = config[`${prefix}PreStart`];
  const preEnd = config[`${prefix}PreEnd`];
  const postStart = config[`${prefix}PostStart`];
  const postEnd = config[`${prefix}PostEnd`];
  const excludedDates = config[`${prefix}ExcludedDates`] || [];
  const excludedStores = config[`${prefix}ExcludedStores`] || [];

  if (!preStart || !preEnd || !postStart || !postEnd) return null;

  const stores = data.storeTables?.[platform] || [];

  return {
    storesLeastGrowth: getStoresLeastGrowth(stores, limits.storeCount),
    dates: {
      pre: sliceDateExtremes(
        getPlatformDailyExtremes(financial, platform, preStart, preEnd, excludedDates),
        limits.dateCount,
      ),
      post: sliceDateExtremes(
        getPlatformDailyExtremes(financial, platform, postStart, postEnd, excludedDates),
        limits.dateCount,
      ),
    },
    slotsLowestSales: getSlotsLowestSales(financial, {
      preStart,
      preEnd,
      postStart,
      postEnd,
      excludedDates,
      excludedStores,
      platform,
    }, limits.slotCount),
  };
}

/** Snapshot for Overview after Pre vs Post analysis. */
export function buildPrePostQuickInsights(data, config, limits = {}) {
  const {
    dateCount = 3,
    storeCount = 5,
    slotCount = 3,
  } = limits;

  if (!config?.ddPreStart && !config?.uePreStart) return null;

  const resolved = { dateCount, storeCount, slotCount };
  const payload = {
    dd: buildPlatformInsights('dd', data, config, resolved),
    ue: buildPlatformInsights('ue', data, config, resolved),
  };

  if (!payload.dd && !payload.ue) return null;
  return payload;
}
