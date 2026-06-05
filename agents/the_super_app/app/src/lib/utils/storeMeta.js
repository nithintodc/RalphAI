/** Store name + platform ID lookups from normalized financial rows. */

export function getDominantStorePlatform(ddCount, ueCount) {
  return ddCount >= ueCount ? 'dd' : 'ue';
}

export function buildStoreMetaLookup(rawData) {
  const byStoreId = new Map();
  for (const row of rawData || []) {
    const id = String(row.storeId ?? '').trim();
    if (!id) continue;
    const cur = byStoreId.get(id) || { storeName: '', ddStoreId: '' };
    const name = String(row.storeName ?? '').trim();
    const ddId = String(row.ddStoreId ?? '').trim();
    if (name && (!cur.storeName || name.length > cur.storeName.length)) cur.storeName = name;
    if (ddId) cur.ddStoreId = ddId;
    byStoreId.set(id, cur);
  }
  return byStoreId;
}
