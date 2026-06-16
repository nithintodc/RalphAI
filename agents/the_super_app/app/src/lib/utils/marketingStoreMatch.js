import { sanitizeStoreId } from '../parsers/ddFinancial';
import { buildDdStoreIdToMerchantMap } from './storeCatalog';

/**
 * Resolve DoorDash marketing row Store ID → canonical merchant store ID (store map key).
 */
export function buildMarketingStoreResolver(ddFinancial) {
  const toMerchant = buildDdStoreIdToMerchantMap(ddFinancial);
  return (rawStoreId) => {
    const sid = sanitizeStoreId(rawStoreId);
    if (!sid) return '';
    return toMerchant.get(sid) || sid;
  };
}

/**
 * Classify a marketing row into corp (B/Non-TODC), todc (A), unmapped, or excluded.
 */
export function classifyMarketingRow(row, scope, resolveMarketingStoreId) {
  const canon = resolveMarketingStoreId(row?.storeId);
  if (!canon) return 'unmapped';

  if (scope?.includedIds?.size > 0 && !scope.includedIds.has(canon)) {
    return 'excluded';
  }

  const tag = String(scope?.tagMap?.[canon] || '').trim();
  if (tag === 'A') return 'todc';
  if (tag === 'B') return 'corp';
  return 'unmapped';
}

export function filterMarketingRowsByClass(rows, bucket, scope, resolveMarketingStoreId) {
  return (rows || []).filter((row) => classifyMarketingRow(row, scope, resolveMarketingStoreId) === bucket);
}
