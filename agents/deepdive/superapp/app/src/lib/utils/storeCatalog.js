/**
 * Store ID + display name catalogs and DD → UE mapping rows for the config screen.
 */

import { sanitizeStoreId } from '../parsers/ddFinancial';

function compareStoreIds(a, b) {
  const na = Number(a);
  const nb = Number(b);
  if (!Number.isNaN(na) && !Number.isNaN(nb) && String(a).trim() === String(na) && String(b).trim() === String(nb)) {
    return na - nb;
  }
  return String(a).localeCompare(String(b), undefined, { numeric: true });
}

function normalizeForMatch(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/®/g, '')
    .replace(/[^\w\s&]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Best unused UE store whose name overlaps the DD name (branch / address tokens). */
function bestUeMatchByName(ddName, ueCatalog, usedUeIds) {
  const dn = normalizeForMatch(ddName);
  if (!dn || dn === '—') return null;

  let best = null;
  let bestScore = 0;
  for (const ue of ueCatalog) {
    if (usedUeIds.has(ue.id)) continue;
    const un = normalizeForMatch(ue.name);
    if (!un || un === '—') continue;

    let score = 0;
    if (un === dn) score = 100;
    else if (un.includes(dn) || dn.includes(un)) score = 75;
    else {
      const dt = new Set(dn.split(' ').filter((w) => w.length > 3));
      const overlap = un.split(' ').filter((w) => w.length > 3 && dt.has(w)).length;
      if (overlap) score = 45 + overlap * 12;
    }
    if (score > bestScore) {
      bestScore = score;
      best = ue;
    }
  }
  return bestScore >= 45 ? best : null;
}

function formatUeOptionLabel(store) {
  if (!store) return '';
  return store.name !== '—' ? `${store.name} (${store.id})` : store.id;
}

/** DoorDash stores: merchant ID (map key), optional DD Store ID column, store name. */
export function buildDdStoreCatalog(rows) {
  const byKey = new Map();
  for (const row of rows || []) {
    const merchant = sanitizeStoreId(row.merchantStoreId);
    const ddStoreId = sanitizeStoreId(row.ddStoreId);
    const mapKey = merchant || ddStoreId || sanitizeStoreId(row.storeId);
    if (!mapKey) continue;
    const name = String(row.storeName ?? '').trim();
    if (!byKey.has(mapKey)) {
      byKey.set(mapKey, {
        id: mapKey,
        merchantStoreId: merchant || '—',
        ddStoreId: ddStoreId || '—',
        name: name || '—',
      });
    } else {
      const cur = byKey.get(mapKey);
      if (name && (cur.name === '—' || name.length > cur.name.length)) cur.name = name;
      if (merchant && cur.merchantStoreId === '—') cur.merchantStoreId = merchant;
      if (ddStoreId) cur.ddStoreId = ddStoreId;
    }
  }
  return [...byKey.values()].sort((a, b) => compareStoreIds(a.id, b.id));
}

/** Uber Eats stores: store ID + restaurant name. */
export function buildUeStoreCatalog(rows) {
  return buildStoreCatalog(rows, { idKey: 'storeId', nameKey: 'storeName' });
}

/** Unique stores from normalized financial rows (generic). */
export function buildStoreCatalog(rows, { idKey = 'storeId', nameKey = 'storeName' } = {}) {
  const byId = new Map();
  for (const row of rows || []) {
    const id = String(row[idKey] ?? '').trim();
    if (!id) continue;
    const name = String(row[nameKey] ?? '').trim();
    if (!byId.has(id)) {
      byId.set(id, name);
    } else if (name && !byId.get(id)) {
      byId.set(id, name);
    }
  }
  return [...byId.entries()]
    .map(([id, name]) => ({ id, name: name || '—' }))
    .sort((a, b) => compareStoreIds(a.id, b.id));
}

/**
 * One row per DoorDash store. Default UE target: saved map → same ID → positional pair (1↔1, 2↔2… on sorted lists).
 */
export function buildSuggestedMapRows(ddCatalog, ueCatalog, savedMap = {}, savedTagMap = {}) {
  const dd = [...ddCatalog].sort((a, b) => compareStoreIds(a.id, b.id));
  const ue = [...ueCatalog].sort((a, b) => compareStoreIds(a.id, b.id));
  const ueById = new Map(ue.map((s) => [s.id, s]));
  const usedUeIds = new Set();

  return dd.map((d, index) => {
    const positional = ue[index];
    let ueId =
      savedMap[d.id] != null && String(savedMap[d.id]).trim() !== ''
        ? String(savedMap[d.id]).trim()
        : null;

    if (ueId) {
      usedUeIds.add(ueId);
    } else if (ueById.has(d.id)) {
      ueId = d.id;
      usedUeIds.add(ueId);
    } else {
      const byName = bestUeMatchByName(d.name, ue, usedUeIds);
      if (byName) {
        ueId = byName.id;
        usedUeIds.add(ueId);
      } else if (positional && !usedUeIds.has(positional.id)) {
        ueId = positional.id;
        usedUeIds.add(ueId);
      } else {
        const fallback = ue.find((s) => !usedUeIds.has(s.id));
        ueId = fallback?.id ?? '';
        if (ueId) usedUeIds.add(ueId);
      }
    }

    const ueStore = ueById.get(ueId);
    const canonStoreId = ueId || d.id;
    return {
      ddId: d.id,
      merchantStoreId: d.merchantStoreId ?? d.id,
      ddStoreId: d.ddStoreId ?? '—',
      ddName: d.name,
      ueId,
      ueName: ueStore?.name ?? (ueId ? '—' : ''),
      tag: String(savedTagMap[canonStoreId] ?? '').trim(),
    };
  });
}

/** DD merchant store ID → UE store ID (only rows with both sides set). */
export function mapRowsToStoreMap(rows) {
  const out = {};
  for (const row of rows || []) {
    const ddId = String(row.ddId ?? '').trim();
    const ueId = String(row.ueId ?? '').trim();
    if (ddId && ueId) out[ddId] = ueId;
  }
  return out;
}

/** Canonical combined store ID -> Tag (e.g. A / B). */
export function mapRowsToTagMap(rows) {
  const out = {};
  for (const row of rows || []) {
    const tag = String(row.tag ?? '').trim();
    if (!tag) continue;
    const canonId = String(row.ueId || row.ddId || '').trim();
    if (!canonId) continue;
    out[canonId] = tag;
  }
  return out;
}

export function applyUeSelection(row, ueId, ueCatalog) {
  const id = String(ueId ?? '').trim();
  const ue = ueCatalog.find((s) => s.id === id);
  return {
    ...row,
    ueId: id,
    ueName: ue?.name ?? (id ? '—' : ''),
  };
}

export { formatUeOptionLabel };
