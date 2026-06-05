/** Store ID / Store Name columns and aligned Combined / DD / UE export rows. */

import { getDominantStorePlatform } from '../utils/storeMeta';
import { buildDdStoreCatalog, buildUeStoreCatalog } from '../utils/storeCatalog';

export { getDominantStorePlatform };

export const EXPORT_NA = 'NA';

export const LEGACY_STORE_HEADERS_PVP = ['Store ID', 'Store Name', 'Pre', 'Post', 'PrevsPost', 'LastYear Pre vs Post', 'Growth%'];
export const LEGACY_STORE_HEADERS_YOY = ['Store ID', 'Store Name', 'last year-post', 'post', 'YoY', 'YoY%'];

/** DoorDash export Store ID column — prefer DD platform ID. */
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
  const ddMap = new Map((storeTables?.dd || []).map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ueMap = new Map((storeTables?.ue || []).map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ddPrimary = getDominantStorePlatform(ddMap.size, ueMap.size);

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

export function legacyStoreIdCell(row, platform) {
  if (platform === 'dd') return ddExportStoreId(row);
  if (platform === 'ue') return ueExportStoreId(row);
  return row?.storeId ?? '';
}

function catalogDdStoreId(ddCat, ddRow, ddKey) {
  if (ddCat?.ddStoreId && ddCat.ddStoreId !== '—') return ddCat.ddStoreId;
  if (ddRow?.ddStoreId) return ddRow.ddStoreId;
  return ddKey || '';
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
      catalogDdStoreId(ddCat, ddRow, ddKey),
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
    ['DD Store ID', 'DD Store Name', 'UE Store ID', 'UE Store Name'],
    ...dataRows,
  ];
}
