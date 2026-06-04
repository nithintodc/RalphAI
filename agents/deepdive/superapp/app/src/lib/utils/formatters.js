export const fmt = {
  usd: (v) => '$' + Math.round(v).toLocaleString('en-US'),
  usd2: (v) => '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  usdK: (v) => v >= 1e6 ? '$' + (v / 1e6).toFixed(2) + 'M' : v >= 1e3 ? '$' + (v / 1e3).toFixed(0) + 'K' : '$' + Math.round(v),
  int: (v) => Math.round(v).toLocaleString('en-US'),
  pct: (v) => Number(v).toFixed(1) + '%',
  pct0: (v) => Math.round(v) + '%',
  x: (v) => Number(v).toFixed(2) + '×',
  delta: (v) => (v >= 0 ? '+' : '') + Number(v).toFixed(1) + '%',
};

export function formatValue(v, format) {
  if (v == null || isNaN(v)) return '-';
  return fmt[format]?.(v) ?? String(v);
}

export function formatMetricValue(value, metric) {
  if (value == null || isNaN(value)) return '-';
  switch (metric) {
    case 'sales': case 'payouts': case 'spend': case 'promo': case 'ads':
    case 'corpSpend': case 'todcSpend':
      return fmt.usd(value);
    case 'orders': case 'newCustomers':
      return fmt.int(value);
    case 'aov': case 'cpo':
      return fmt.usd2(value);
    case 'profitability':
      return fmt.pct(value);
    case 'roas':
      return fmt.x(value);
    default:
      return typeof value === 'number' ? value.toFixed(1) : String(value);
  }
}
