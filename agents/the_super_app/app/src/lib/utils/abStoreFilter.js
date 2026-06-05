/** Scope analysis to mapped stores and optional A/B group filter. */

export function resolveCanonStoreId(storeId, platform, ddToUeStoreMap = {}) {
  const sid = String(storeId ?? '').trim();
  if (!sid) return '';
  if (platform === 'dd') return sid;
  for (const [ddId, ueId] of Object.entries(ddToUeStoreMap || {})) {
    if (String(ueId).trim() === sid) return String(ddId).trim();
  }
  return sid;
}

/** Canonical combined IDs present in the store map editor rows (deleted rows excluded). */
export function getIncludedStoreIdsFromMapRows(rows = []) {
  const ids = new Set();
  for (const row of rows) {
    const ddId = String(row.ddId ?? '').trim();
    const ueId = String(row.ueId ?? '').trim();
    const canon = ddId || ueId;
    if (canon) ids.add(canon);
  }
  return ids;
}

function storePassesScope(storeId, platform, { includedIds, tagMap, abGroupFilter, ddToUeStoreMap }) {
  const canon = resolveCanonStoreId(storeId, platform, ddToUeStoreMap);
  if (!canon) return false;
  if (includedIds && includedIds.size > 0 && !includedIds.has(canon)) return false;
  if (abGroupFilter && abGroupFilter !== 'all') {
    return String(tagMap[canon] || '').trim() === abGroupFilter;
  }
  return true;
}

export function filterPlatformStores(stores, platform, scope) {
  return (stores || []).filter((r) => storePassesScope(r.storeId, platform, scope));
}

export function filterCombinedStores(stores, scope) {
  return (stores || []).filter((r) => {
    const canon = String(r.storeId ?? '').trim();
    if (!canon) return false;
    if (scope.includedIds?.size > 0 && !scope.includedIds.has(canon)) return false;
    if (scope.abGroupFilter && scope.abGroupFilter !== 'all') {
      return String(scope.tagMap[canon] || '').trim() === scope.abGroupFilter;
    }
    return true;
  });
}

/** Merge mapping/tag scope into platform excluded-store lists. */
export function buildScopedExcludedStores(allStoreIds, platform, scope) {
  const excluded = [];
  for (const sid of allStoreIds || []) {
    if (!storePassesScope(sid, platform, scope)) excluded.push(sid);
  }
  return excluded;
}

export function getIncludedStoreIdsFromConfig(config = {}) {
  const ids = new Set(config.includedStoreIds || []);
  if (ids.size) return ids;
  const tagMap = config.storeTagMap || {};
  const ddMap = config.ddToUeStoreMap || {};
  for (const canonId of Object.keys(tagMap)) {
    if (canonId) ids.add(canonId);
  }
  for (const [ddId, ueId] of Object.entries(ddMap)) {
    const canon = String(ddId).trim() || (ueId && String(ueId).trim());
    if (canon) ids.add(canon);
  }
  return ids;
}

export function buildAnalysisScope(config, mapRows = null) {
  const tagMap = config.storeTagMap || {};
  const ddToUeStoreMap = config.ddToUeStoreMap || {};
  const abGroupFilter = config.abGroupFilter || 'all';
  const includedIds = mapRows
    ? getIncludedStoreIdsFromMapRows(mapRows)
    : getIncludedStoreIdsFromConfig(config);
  return { tagMap, ddToUeStoreMap, abGroupFilter, includedIds };
}

export function applyStoreTableScope(storeTables, scope) {
  if (!storeTables) return storeTables;
  return {
    dd: filterPlatformStores(storeTables.dd, 'dd', scope),
    ue: filterPlatformStores(storeTables.ue, 'ue', scope),
    combined: filterCombinedStores(storeTables.combined, scope),
  };
}
