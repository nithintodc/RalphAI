/** Hero KPI cards from combined summary table rows (Overview / App 2.0 drawer). */
function rowToKpi(row, { id, label, format, deltaFormat }) {
  if (!row) return null;
  return {
    id: id || row.metric,
    label,
    value: row.prevspost,
    pre: row.pre,
    post: row.post,
    format: deltaFormat || format,
    rangeFormat: format,
    delta: row.growthPct,
    yoy: row.yoyPct,
  };
}

/** Active DoorDash store count (exclusions already applied in storeTables). */
export function ddStoreCount(storeTables) {
  return storeTables?.dd?.length || 0;
}

/** Active Uber Eats store count (exclusions already applied in storeTables). */
export function ueStoreCount(storeTables) {
  return storeTables?.ue?.length || 0;
}

/** Denominator for Payout Δ/Store — DD stores for combined & DD, UE stores for UE. */
export function storeCountForPayoutKpi(sectionKey, storeTables) {
  if (sectionKey === 'ue') return ueStoreCount(storeTables);
  if (sectionKey === 'combined' || sectionKey === 'dd') return ddStoreCount(storeTables);
  return 0;
}

/** Payout delta (Post − Pre) ÷ store count. */
export function payoutDeltaPerStore(payoutsRow, storeCount) {
  if (!payoutsRow || !storeCount) return null;
  return (payoutsRow.prevspost ?? 0) / storeCount;
}

/** Per-section payout Δ/store using the correct platform store count. */
export function payoutDeltaPerStoreForSection(summaryTables, storeTables, sectionKey) {
  const payouts = summaryTables?.[sectionKey]?.find((r) => r.metric === 'payouts');
  return payoutDeltaPerStore(payouts, storeCountForPayoutKpi(sectionKey, storeTables));
}

/** @deprecated Use payoutDeltaPerStoreForSection(..., 'combined'). */
export function combinedPayoutPerStore(summaryTables, storeTables) {
  return payoutDeltaPerStoreForSection(summaryTables, storeTables, 'combined');
}

export function buildSummaryKpis(summary = [], { sectionKey, storeTables } = {}) {
  const get = (m) => summary.find((r) => r.metric === m);
  const s = get('sales');
  const p = get('payouts');
  const o = get('orders');
  const prof = get('profitability');
  const aov = get('aov');

  const kpis = [
    rowToKpi(s, { label: 'Sales', format: 'usd' }),
    rowToKpi(p, { label: 'Payouts', format: 'usd' }),
    rowToKpi(o, { label: 'Orders', format: 'int' }),
    rowToKpi(aov, { label: 'AOV', format: 'usd2' }),
    rowToKpi(prof, { id: 'prof', label: 'Profitability', format: 'pct', deltaFormat: 'pp' }),
  ].filter(Boolean);

  const storeCount = storeCountForPayoutKpi(sectionKey, storeTables);
  if (['combined', 'dd', 'ue'].includes(sectionKey) && p && storeCount > 0) {
    kpis.push({
      id: 'payoutsPerStore',
      label: 'Payout Δ/Store',
      value: p.prevspost / storeCount,
      pre: p.pre / storeCount,
      post: p.post / storeCount,
      format: 'usd2',
      rangeFormat: 'usd2',
      delta: p.growthPct,
      yoy: p.yoyPct,
    });
  }

  return kpis;
}

/** @deprecated Use payoutDeltaPerStoreForSection — kept for import compatibility. */
export function meanPayoutPerStore(summaryTables, storeTables) {
  return combinedPayoutPerStore(summaryTables, storeTables);
}
