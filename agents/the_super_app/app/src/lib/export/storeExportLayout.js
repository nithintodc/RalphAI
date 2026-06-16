/** Store ID / Store Name columns and aligned Combined / DD / UE export rows. */

import { getDominantStorePlatform } from '../utils/storeMeta';
import { buildDdStoreCatalog, buildDdStoreIdToMerchantMap, buildUeStoreCatalog } from '../utils/storeCatalog';
import { ddMerchantStoreId } from '../utils/storeDisplay';

export { getDominantStorePlatform };

export const EXPORT_NA = 'NA';

export const EXPORT_DD_MERCHANT_STORE_ID_HEADER = 'Merchant Store ID';
export const EXPORT_UE_STORE_ID_HEADER = 'Store ID (UE)';
export const EXPORT_STORE_ID_HEADERS = [EXPORT_DD_MERCHANT_STORE_ID_HEADER, EXPORT_UE_STORE_ID_HEADER];

const LEGACY_STORE_METRIC_HEADERS_PVP = [
  'Store Name',
  'Pre',
  'Post',
  'PrevsPost',
  'LastYear Pre vs Post',
  'Growth%',
  'LY Growth%',
];
const LEGACY_STORE_METRIC_HEADERS_YOY = [
  'Store Name',
  'last year-post',
  'post',
  'YoY',
  'YoY%',
];

export function exportStoreIdHeaders(platform) {
  if (platform === 'dd') return [EXPORT_DD_MERCHANT_STORE_ID_HEADER];
  if (platform === 'ue') return [EXPORT_UE_STORE_ID_HEADER];
  return EXPORT_STORE_ID_HEADERS;
}

export function legacyStoreHeadersPvp(platform) {
  return [...exportStoreIdHeaders(platform), ...LEGACY_STORE_METRIC_HEADERS_PVP];
}

export function legacyStoreHeadersYoy(platform) {
  return [...exportStoreIdHeaders(platform), ...LEGACY_STORE_METRIC_HEADERS_YOY];
}

/** @deprecated Use legacyStoreHeadersPvp(platform) */
export const LEGACY_STORE_HEADERS_PVP = legacyStoreHeadersPvp('combined');
/** @deprecated Use legacyStoreHeadersYoy(platform) */
export const LEGACY_STORE_HEADERS_YOY = legacyStoreHeadersYoy('combined');

function buildUeToDdMap(ddToUeStoreMap = {}) {
  const out = {};
  for (const [ddId, ueId] of Object.entries(ddToUeStoreMap)) {
    const ueKey = String(ueId ?? '').trim();
    if (ueKey) out[ueKey] = String(ddId).trim();
  }
  return out;
}

/** DoorDash Merchant Store ID for exports (not DD portal Store ID). */
export function exportDdMerchantStoreId(
  row,
  platform,
  dominantPlatform = 'dd',
  ueToDdMap = {},
  ddStoreIdToMerchant = null,
) {
  if (!row || row._isNa) return EXPORT_NA;
  const merchantMap = ddStoreIdToMerchant || new Map();

  if (platform === 'dd') {
    const id = ddMerchantStoreId(row, merchantMap);
    return id || EXPORT_NA;
  }

  if (platform === 'ue') {
    const ueId = String(row.storeId ?? '').trim();
    const ddKey = ueId && ueToDdMap[ueId];
    if (ddKey) {
      const id = ddMerchantStoreId({ storeId: ddKey, merchantStoreId: row.merchantStoreId }, merchantMap);
      return id || ddKey;
    }
    return EXPORT_NA;
  }

  const ddKey = String(row._ddStoreKey ?? (dominantPlatform === 'dd' ? row.storeId : '') ?? '').trim();
  const id = ddMerchantStoreId({ ...row, storeId: ddKey }, merchantMap);
  return id || ddKey || EXPORT_NA;
}

/** Uber Eats Store ID for exports. */
export function exportUeStoreId(row, platform, dominantPlatform = 'dd', ddToUeStoreMap = {}) {
  if (!row || row._isNa) return EXPORT_NA;

  if (platform === 'ue') {
    const id = String(row.storeId ?? '').trim();
    return id || EXPORT_NA;
  }

  if (platform === 'dd') {
    const ddKey = String(row.storeId ?? '').trim();
    const ueId = ddToUeStoreMap[ddKey];
    return ueId ? String(ueId).trim() : EXPORT_NA;
  }

  const ddKey = String(row._ddStoreKey ?? (dominantPlatform === 'dd' ? row.storeId : '') ?? '').trim();
  const ueKey = String(
    row._ueStoreKey
    ?? (dominantPlatform === 'ue' ? row.storeId : (ddToUeStoreMap[ddKey] ?? ''))
    ?? '',
  ).trim();
  return ueKey || EXPORT_NA;
}

/** Platform-aware store ID cells for export tables. */
export function exportStoreIdCells(
  row,
  platform,
  dominantPlatform = 'dd',
  ddToUeStoreMap = {},
  ddStoreIdToMerchant = null,
) {
  const ueToDd = buildUeToDdMap(ddToUeStoreMap);
  return [
    exportDdMerchantStoreId(row, platform, dominantPlatform, ueToDd, ddStoreIdToMerchant),
    exportUeStoreId(row, platform, dominantPlatform, ddToUeStoreMap),
  ];
}

/** One or two store ID columns matching exportStoreIdHeaders(platform). */
export function exportStoreIdRowCells(
  row,
  platform,
  dominantPlatform = 'dd',
  ddToUeStoreMap = {},
  ddStoreIdToMerchant = null,
) {
  const [ddMerchant, ueStore] = exportStoreIdCells(
    row,
    platform,
    dominantPlatform,
    ddToUeStoreMap,
    ddStoreIdToMerchant,
  );
  if (platform === 'dd') return [ddMerchant];
  if (platform === 'ue') return [ueStore];
  return [ddMerchant, ueStore];
}

/** @deprecated Prefer exportDdMerchantStoreId — legacy single column used DD portal Store ID. */
export function ddExportStoreId(row) {
  if (!row || row._isNa) return EXPORT_NA;
  return row.ddStoreId || row.storeId || '';
}

export function ueExportStoreId(row) {
  if (!row || row._isNa) return EXPORT_NA;
  return row.storeId || '';
}

export function exportStoreName(row) {
  if (!row || row._isNa) return EXPORT_NA;
  const name = String(row.storeName ?? '').trim();
  return name || EXPORT_NA;
}

export function combinedExportStoreId(row, dominantPlatform) {
  if (!row) return '';
  if (dominantPlatform === 'dd') return ddExportStoreId(row);
  return ueExportStoreId(row);
}

export function combinedExportStoreName(row, dominantPlatform) {
  if (!row) return '';
  return exportStoreName(row);
}

function emptyMetricRow(base = {}) {
  return {
    ...base,
    pre_sales: null,
    post_sales: null,
    sales_prevspost: null,
    sales_ly_prevspost: null,
    sales_growth_pct: null,
    sales_ly_growth_pct: null,
    postLY_sales: null,
    sales_yoy: null,
    sales_yoy_pct: null,
    _isNa: true,
  };
}

/**
 * Align DD / UE store rows to combined order for export.
 * Combined uses the dominant platform's store ID + name; missing mapped stores show NA.
 */
export function buildAlignedExportStoreTables(storeTables, ddToUeStoreMap = {}) {
  const combined = storeTables?.combined || [];
  const ddRows = storeTables?.dd || [];
  const ueRows = storeTables?.ue || [];
  const ddMap = new Map(ddRows.map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ueMap = new Map(ueRows.map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ddPrimary = getDominantStorePlatform(ddMap.size, ueMap.size);

  if (ddRows.length === combined.length && ueRows.length === combined.length && combined.length > 0) {
    return { combined, dd: ddRows, ue: ueRows, dominantPlatform: ddPrimary ? 'dd' : 'ue' };
  }

  const aligned = { combined, dd: [], ue: [], dominantPlatform: ddPrimary ? 'dd' : 'ue' };

  for (const cRow of combined) {
    const ddKey = String(cRow._ddStoreKey ?? (ddPrimary ? cRow.storeId : '') ?? '').trim();
    const ueKey = String(
      cRow._ueStoreKey
      ?? (ddPrimary ? (ddToUeStoreMap[ddKey] ?? '') : cRow.storeId)
      ?? '',
    ).trim();

    const ddRow = ddKey ? ddMap.get(ddKey) : null;
    const ueRow = ueKey ? ueMap.get(ueKey) : null;

    aligned.dd.push(ddRow || emptyMetricRow({ storeId: EXPORT_NA, storeName: EXPORT_NA }));
    aligned.ue.push(ueRow || emptyMetricRow({ storeId: EXPORT_NA, storeName: EXPORT_NA }));
  }

  return aligned;
}

export function legacyStoreIdCell(row, platform, dominantPlatform = 'dd', ddToUeStoreMap = {}) {
  const [ddId] = exportStoreIdCells(row, platform, dominantPlatform, ddToUeStoreMap);
  return ddId;
}

function catalogDdMerchantStoreId(ddCat, ddRow, ddKey, ddStoreIdToMerchant) {
  if (ddCat?.merchantStoreId && ddCat.merchantStoreId !== '—') return ddCat.merchantStoreId;
  const id = ddMerchantStoreId(
    { storeId: ddKey, merchantStoreId: ddRow?.merchantStoreId ?? ddCat?.merchantStoreId, ddStoreId: ddRow?.ddStoreId ?? ddCat?.ddStoreId },
    ddStoreIdToMerchant,
  );
  return id || ddKey || '';
}

function catalogStoreName(catalogName, rowName) {
  const name = String(catalogName ?? rowName ?? '').trim();
  return name && name !== '—' ? name : '';
}

/** One row per mapped store: DD Store ID, DD Store Name, UE Store ID, UE Store Name. */
export function buildStoreMappingExportRows(data, config) {
  const combined = data?.storeTables?.combined || [];
  const ddMap = new Map((data?.storeTables?.dd || []).map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ueMap = new Map((data?.storeTables?.ue || []).map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ddToUe = config?.ddToUeStoreMap || {};
  const ddCatalog = buildDdStoreCatalog(data?.ddFinancial);
  const ueCatalog = buildUeStoreCatalog(data?.ueFinancial);
  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(data?.ddFinancial);
  const ddCatById = new Map(ddCatalog.map((d) => [d.id, d]));
  const ueCatById = new Map(ueCatalog.map((u) => [u.id, u]));

  const rows = [];
  const seen = new Set();

  const addRow = (ddKey, ueKey) => {
    const key = `${ddKey}\0${ueKey}`;
    if (seen.has(key)) return;
    seen.add(key);
    const ddCat = ddKey ? ddCatById.get(ddKey) : null;
    const ueCat = ueKey ? ueCatById.get(ueKey) : null;
    const ddRow = ddKey ? ddMap.get(ddKey) : null;
    const ueRow = ueKey ? ueMap.get(ueKey) : null;
    rows.push([
      catalogDdMerchantStoreId(ddCat, ddRow, ddKey, ddStoreIdToMerchant),
      catalogStoreName(ddCat?.name, ddRow?.storeName),
      ueKey || '',
      catalogStoreName(ueCat?.name, ueRow?.storeName),
    ]);
  };

  if (combined.length) {
    for (const cRow of combined) {
      const ddKey = String(cRow._ddStoreKey ?? cRow.storeId ?? '').trim();
      const ueKey = String(cRow._ueStoreKey ?? ddToUe[ddKey] ?? '').trim();
      addRow(ddKey, ueKey);
    }
    return rows;
  }

  for (const dd of ddCatalog) {
    const ueKey = String(ddToUe[dd.id] ?? '').trim();
    addRow(dd.id, ueKey);
  }
  return rows;
}

/** Side panel block for Summary Tables export. */
export function buildStoreMappingExportBlock(data, config) {
  const dataRows = buildStoreMappingExportRows(data, config);
  return [
    ['Store mapping (DoorDash ↔ Uber Eats)'],
    ['Merchant Store ID', 'DD Store Name', 'UE Store ID', 'UE Store Name'],
    ...dataRows,
  ];
}
