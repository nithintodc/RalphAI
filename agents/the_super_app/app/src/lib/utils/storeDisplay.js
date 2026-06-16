/**
 * Display helpers for store identifiers — prefer Merchant Store ID for DD financial data.
 */

import { buildDdStoreCatalog, buildDdStoreIdToMerchantMap } from './storeCatalog';

export const DD_MERCHANT_STORE_ID_LABEL = 'Merchant Store ID';
export const UE_STORE_ID_LABEL = 'Store ID';

export function storeIdColumnLabel(platformKey) {
  if (platformKey === 'dd' || platformKey === 'combined') return DD_MERCHANT_STORE_ID_LABEL;
  return UE_STORE_ID_LABEL;
}

/** Resolve Merchant Store ID from a DD store row (store tables, spotlight, etc.). */
export function ddMerchantStoreId(row, ddStoreIdToMerchant) {
  if (!row) return '';
  const merchant = String(row.merchantStoreId ?? '').trim();
  if (merchant) return merchant;

  const storeId = String(row.storeId ?? '').trim();
  if (storeId && ddStoreIdToMerchant?.get?.(storeId)) {
    return ddStoreIdToMerchant.get(storeId);
  }

  const ddStoreId = String(row.ddStoreId ?? '').trim();
  if (ddStoreId && ddStoreIdToMerchant?.get?.(ddStoreId)) {
    return ddStoreIdToMerchant.get(ddStoreId);
  }

  return storeId || ddStoreId;
}

/** Platform-aware store label for tables and charts. */
export function displayStoreId(row, platformKey, ddStoreIdToMerchant) {
  if (platformKey === 'ue') return String(row?.storeId ?? '').trim();

  if (platformKey === 'combined') {
    const ddKey = String(row?._ddStoreKey ?? row?.storeId ?? '').trim();
    return ddMerchantStoreId({ ...row, storeId: ddKey }, ddStoreIdToMerchant) || ddKey;
  }

  return ddMerchantStoreId(row, ddStoreIdToMerchant);
}

/** Lookup display label when only the internal storeId key is available (e.g. Topbar filters). */
export function ddMerchantStoreIdFromKey(storeId, ddFinancial) {
  const key = String(storeId ?? '').trim();
  if (!key || !ddFinancial?.length) return key;

  const map = buildDdStoreIdToMerchantMap(ddFinancial);
  if (map.has(key)) return map.get(key);

  const catalog = buildDdStoreCatalog(ddFinancial);
  const hit = catalog.find((s) => s.id === key || s.merchantStoreId === key || s.ddStoreId === key);
  if (hit?.merchantStoreId && hit.merchantStoreId !== '—') return hit.merchantStoreId;

  return key;
}

export function buildDdStoreIdToMerchantMapFromFinancial(ddFinancial) {
  return buildDdStoreIdToMerchantMap(ddFinancial);
}
