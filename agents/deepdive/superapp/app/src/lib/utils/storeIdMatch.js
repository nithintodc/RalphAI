/**
 * Canonical store ID: National Store ID (Airtable) = Merchant Store ID (DD) = Store ID (UE).
 */

export function normalizeStoreIdKeys(id) {
  const s = String(id ?? '').trim();
  if (!s || /^null$/i.test(s)) return [];
  const keys = new Set([s]);
  const num = Number(s);
  if (Number.isFinite(num) && !Number.isNaN(num)) {
    keys.add(String(num));
    keys.add(String(Math.round(num)));
  }
  return [...keys];
}

function metricsPayload(row) {
  return {
    sales: row.post_sales,
    payouts: row.post_payouts,
    aov: row.post_aov,
    profitability: row.post_profitability,
  };
}

/** Lookup map for map popups — keys all alias forms of each store ID. */
export function buildStoreMetricsLookup(storeTables) {
  const metrics = {};
  const assign = (id, row) => {
    const payload = metricsPayload(row);
    for (const key of normalizeStoreIdKeys(id)) {
      if (key) metrics[key] = payload;
    }
  };

  // DD / UE first, combined last so merged totals win.
  for (const row of storeTables?.dd || []) assign(row.storeId, row);
  for (const row of storeTables?.ue || []) assign(row.storeId, row);
  for (const row of storeTables?.combined || []) assign(row.storeId, row);

  return metrics;
}
