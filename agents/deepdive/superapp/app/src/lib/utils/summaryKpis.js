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

/** Mean total payout across stores (portfolio average payout per store). */
export function meanPayoutPerStore(stores = [], window = 'post') {
  if (!stores.length) return null;
  const key = `${window}_payouts`;
  const total = stores.reduce((sum, row) => sum + (row[key] || 0), 0);
  return total / stores.length;
}
