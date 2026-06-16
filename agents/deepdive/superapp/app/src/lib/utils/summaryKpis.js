/** Hero KPI cards from combined summary table rows (Overview / App 2.0 drawer). */
export function buildSummaryKpis(summary = []) {
  const get = (m) => summary.find((r) => r.metric === m);
  const s = get('sales');
  const p = get('payouts');
  const o = get('orders');
  const prof = get('profitability');
  const aov = get('aov');
  return [
    { id: 'sales', label: 'Sales', value: s?.post, format: 'usd', delta: s?.growthPct, yoy: s?.yoyPct },
    { id: 'payouts', label: 'Payouts', value: p?.post, format: 'usd', delta: p?.growthPct, yoy: p?.yoyPct },
    { id: 'orders', label: 'Orders', value: o?.post, format: 'int', delta: o?.growthPct, yoy: o?.yoyPct },
    { id: 'aov', label: 'AOV', value: aov?.post, format: 'usd2', delta: aov?.growthPct, yoy: aov?.yoyPct },
    { id: 'prof', label: 'Profitability', value: prof?.post, format: 'pct', delta: prof?.growthPct, yoy: prof?.yoyPct },
  ];
}

/** DoorDash store count — denominator for portfolio payout per store. */
export function ddStoreCount(storeTables) {
  return storeTables?.dd?.length || 0;
}

/** Combined payouts ÷ DD store count for a given window (pre | post | prevspost). */
export function payoutPerStore(payoutsRow, ddCount, window = 'post') {
  if (!payoutsRow || !ddCount) return null;
  const key = window === 'pre' ? 'pre' : window === 'prevspost' ? 'prevspost' : 'post';
  return (payoutsRow[key] ?? 0) / ddCount;
}

/** Combined summary payouts ÷ DD store count (canonical payout per store). */
export function combinedPayoutPerStore(summaryTables, storeTables, window = 'post') {
  const payouts = summaryTables?.combined?.find((r) => r.metric === 'payouts');
  return payoutPerStore(payouts, ddStoreCount(storeTables), window);
}

/** @deprecated Use combinedPayoutPerStore. */
export function meanPayoutPerStore(summaryTables, storeTables, window = 'post') {
  return combinedPayoutPerStore(summaryTables, storeTables, window);
}
