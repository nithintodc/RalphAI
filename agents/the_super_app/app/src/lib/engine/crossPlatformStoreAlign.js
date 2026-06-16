import { round, cleanInfinity, safeDivide } from '../utils/safeMath';
import { addDerivedMetrics, addSpendMetricDeltas, buildCombinedStoreTables } from './metrics';
import { getDominantStorePlatform } from '../utils/storeMeta';

const METRICS = ['sales', 'payouts', 'orders'];
const WINDOWS = ['pre', 'post', 'preLY', 'postLY'];

function createZeroMetricBase(meta = {}) {
  const row = {
    storeId: meta.storeId || '',
    storeName: meta.storeName || '',
    ddStoreId: meta.ddStoreId || '',
    _ddStoreKey: meta._ddStoreKey || '',
    _ueStoreKey: meta._ueStoreKey || '',
    _crossPlatformPadding: meta._crossPlatformPadding || null,
  };
  for (const w of WINDOWS) {
    for (const m of METRICS) {
      row[`${w}_${m}`] = 0;
    }
    row[`${w}_mktSpend`] = 0;
    row[`${w}_adsSpend`] = 0;
    row[`${w}_promoSpend`] = 0;
  }
  return row;
}

function withDerivedZeroRow(meta) {
  const [row] = addDerivedMetrics([createZeroMetricBase(meta)]);
  return row;
}

function buildUeToDdIds(ddToUeStoreMap = {}) {
  const ueToDdIds = new Map();
  for (const [ddId, ueId] of Object.entries(ddToUeStoreMap || {})) {
    const ueKey = String(ueId ?? '').trim();
    const ddKey = String(ddId ?? '').trim();
    if (!ueKey || !ddKey) continue;
    if (!ueToDdIds.has(ueKey)) ueToDdIds.set(ueKey, []);
    ueToDdIds.get(ueKey).push(ddKey);
  }
  return ueToDdIds;
}

function buildCrossPlatformEntities(ddList, ueList, ddToUeStoreMap = {}) {
  const map = ddToUeStoreMap && typeof ddToUeStoreMap === 'object' && !Array.isArray(ddToUeStoreMap)
    ? ddToUeStoreMap
    : {};
  const ueMap = new Map(ueList.map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const coveredUeKeys = new Set();
  const entities = [];

  for (const ddRow of ddList) {
    const ddKey = String(ddRow.storeId ?? '').trim();
    if (!ddKey) continue;
    const ueKey = String(map[ddKey] ?? '').trim();
    const ueRow = ueKey ? ueMap.get(ueKey) : null;
    if (ueKey) coveredUeKeys.add(ueKey);
    entities.push({ ddKey, ueKey, ddRow, ueRow });
  }

  for (const ueRow of ueList) {
    const ueKey = String(ueRow.storeId ?? '').trim();
    if (!ueKey || coveredUeKeys.has(ueKey)) continue;
    entities.push({ ddKey: '', ueKey, ddRow: null, ueRow });
  }

  return entities;
}

function paddedDdRow(entity) {
  if (entity.ddRow) return entity.ddRow;
  const ueRow = entity.ueRow;
  return withDerivedZeroRow({
    storeId: entity.ueKey,
    storeName: ueRow?.storeName || entity.ueKey,
    ddStoreId: '',
    _ddStoreKey: '',
    _ueStoreKey: entity.ueKey,
    _crossPlatformPadding: 'ue-on-dd',
  });
}

function paddedUeRow(entity) {
  if (entity.ueRow) return entity.ueRow;
  const ddRow = entity.ddRow;
  return withDerivedZeroRow({
    storeId: entity.ueKey || entity.ddKey,
    storeName: ddRow?.storeName || entity.ddKey,
    ddStoreId: ddRow?.ddStoreId || '',
    _ddStoreKey: entity.ddKey,
    _ueStoreKey: entity.ueKey,
    _crossPlatformPadding: 'dd-on-ue',
  });
}

function sumCombinedParts(dd, ue, rowMeta) {
  const row = { ...rowMeta };
  for (const m of METRICS) {
    for (const w of WINDOWS) {
      row[`${w}_${m}`] = (dd?.[`${w}_${m}`] || 0) + (ue?.[`${w}_${m}`] || 0);
    }
  }

  for (const m of METRICS) {
    row[`${m}_prevspost`] = round(row[`post_${m}`] - row[`pre_${m}`]);
    row[`${m}_ly_prevspost`] = round(row[`postLY_${m}`] - row[`preLY_${m}`]);
    row[`${m}_yoy`] = round(row[`post_${m}`] - row[`postLY_${m}`]);
    row[`${m}_growth_pct`] = round(cleanInfinity(safeDivide(row[`${m}_prevspost`], row[`pre_${m}`]) * 100));
    row[`${m}_ly_growth_pct`] = round(cleanInfinity(safeDivide(row[`${m}_ly_prevspost`], row[`preLY_${m}`]) * 100));
    row[`${m}_yoy_pct`] = round(cleanInfinity(safeDivide(row[`${m}_yoy`], row[`postLY_${m}`]) * 100));
  }

  for (const w of WINDOWS) {
    row[`${w}_mktSpend`] = (dd?.[`${w}_mktSpend`] || 0) + (ue?.[`${w}_mktSpend`] || 0);
    row[`${w}_adsSpend`] = (dd?.[`${w}_adsSpend`] || 0) + (ue?.[`${w}_adsSpend`] || 0);
    row[`${w}_promoSpend`] = (dd?.[`${w}_promoSpend`] || 0) + (ue?.[`${w}_promoSpend`] || 0);
    row[`${w}_aov`] = round(safeDivide(row[`${w}_sales`], row[`${w}_orders`]), 2);
    row[`${w}_avg_payout`] = round(safeDivide(row[`${w}_payouts`], row[`${w}_orders`]), 2);
    row[`${w}_profitability`] = round(safeDivide(row[`${w}_payouts`], row[`${w}_sales`]) * 100);
  }

  row.aov_prevspost = round(row.post_aov - row.pre_aov, 2);
  row.aov_ly_prevspost = round(row.postLY_aov - row.preLY_aov, 2);
  row.aov_growth_pct = round(cleanInfinity(safeDivide(row.aov_prevspost, row.pre_aov) * 100));
  row.aov_ly_growth_pct = round(cleanInfinity(safeDivide(row.aov_ly_prevspost, row.preLY_aov) * 100));
  row.avg_payout_prevspost = round(row.post_avg_payout - row.pre_avg_payout, 2);
  row.avg_payout_ly_prevspost = round(row.postLY_avg_payout - row.preLY_avg_payout, 2);
  row.prof_prevspost = round(row.post_profitability - row.pre_profitability);
  row.prof_ly_prevspost = round(row.postLY_profitability - row.preLY_profitability);

  for (const metric of ['mktSpend', 'adsSpend', 'promoSpend']) {
    addSpendMetricDeltas(row, metric);
  }

  return row;
}

function combinedMeta(entity, ddPrimary) {
  const { ddKey, ueKey, ddRow, ueRow } = entity;
  if (ddKey && (ddPrimary || !ueKey)) {
    return {
      storeId: ddKey,
      storeName: ddRow?.storeName || ueRow?.storeName || '',
      ddStoreId: ddRow?.ddStoreId || '',
      _ddStoreKey: ddKey,
      _ueStoreKey: ueKey,
    };
  }
  return {
    storeId: ueKey,
    storeName: ueRow?.storeName || ddRow?.storeName || '',
    ddStoreId: ddRow?.ddStoreId || '',
    _ddStoreKey: ddKey,
    _ueStoreKey: ueKey,
  };
}

function entitySortKey(entity) {
  const postSales = (entity.ddRow?.post_sales || 0) + (entity.ueRow?.post_sales || 0);
  return postSales;
}

/**
 * Pad DD / UE store tables so each platform shows the full union:
 * - DD table: all DD stores + UE-only stores (0 DD metrics, UE name copied)
 * - UE table: all UE stores + DD-only stores (0 UE metrics, DD name copied)
 * - Combined: one row per union entity (DD + UE metrics summed)
 */
export function alignCrossPlatformStoreTables(ddStoreData, ueStoreData, ddToUeStoreMap = {}) {
  const ddList = ddStoreData || [];
  const ueList = ueStoreData || [];

  if (!ddList.length || !ueList.length) {
    return {
      dd: ddList,
      ue: ueList,
      combined: buildCombinedStoreTables(ddList, ueList, ddToUeStoreMap),
      crossPlatform: null,
    };
  }

  const entities = buildCrossPlatformEntities(ddList, ueList, ddToUeStoreMap);
  const ddPrimary = getDominantStorePlatform(ddList.length, ueList.length) === 'dd';
  const sorted = [...entities].sort((a, b) => entitySortKey(b) - entitySortKey(a));

  const dd = sorted.map((e) => paddedDdRow(e));
  const ue = sorted.map((e) => paddedUeRow(e));
  const combined = sorted.map((e) => {
    const ddPart = e.ddRow || createZeroMetricBase({
      storeId: e.ddKey,
      storeName: e.ddRow?.storeName || '',
      ddStoreId: e.ddRow?.ddStoreId || '',
      _ddStoreKey: e.ddKey,
      _ueStoreKey: e.ueKey,
    });
    const uePart = e.ueRow || createZeroMetricBase({
      storeId: e.ueKey,
      storeName: e.ueRow?.storeName || '',
      _ddStoreKey: e.ddKey,
      _ueStoreKey: e.ueKey,
    });
    return sumCombinedParts(ddPart, uePart, combinedMeta(e, ddPrimary));
  });

  const mappedCount = entities.filter((e) => e.ddRow && e.ueRow).length;
  const ddOnlyCount = entities.filter((e) => e.ddRow && !e.ueRow).length;
  const ueOnlyCount = entities.filter((e) => !e.ddRow && e.ueRow).length;

  return {
    dd,
    ue,
    combined,
    crossPlatform: {
      totalUnion: entities.length,
      mappedCount,
      ddOnlyCount,
      ueOnlyCount,
      ddNativeCount: ddList.length,
      ueNativeCount: ueList.length,
    },
  };
}

export function formatCrossPlatformStoreNote(crossPlatform) {
  if (!crossPlatform) return null;
  const {
    ddNativeCount, ueNativeCount, mappedCount, ddOnlyCount, ueOnlyCount, totalUnion,
  } = crossPlatform;
  const segments = [
    `Store-level tables align ${totalUnion} union row${totalUnion === 1 ? '' : 's'} (${mappedCount} on both platforms`,
  ];
  if (ddOnlyCount) segments[0] += `, ${ddOnlyCount} DoorDash-only`;
  if (ueOnlyCount) segments[0] += `, ${ueOnlyCount} Uber Eats-only`;
  segments[0] += ').';
  segments.push(
    `DoorDash view: ${ddNativeCount} native store${ddNativeCount === 1 ? '' : 's'}`
    + (ueOnlyCount ? ` + ${ueOnlyCount} Uber Eats-only row${ueOnlyCount === 1 ? '' : 's'} at 0 DD sales` : '')
    + '.',
  );
  segments.push(
    `Uber Eats view: ${ueNativeCount} native store${ueNativeCount === 1 ? '' : 's'}`
    + (ddOnlyCount ? ` + ${ddOnlyCount} DoorDash-only row${ddOnlyCount === 1 ? '' : 's'} at 0 UE sales` : '')
    + '.',
  );
  return segments.join(' ');
}
