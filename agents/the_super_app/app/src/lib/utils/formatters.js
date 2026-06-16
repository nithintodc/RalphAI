export const fmt = {
  usd: (v) => '$' + Math.round(v).toLocaleString('en-US'),
  usd2: (v) => '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  usdK: (v) => v >= 1e6 ? '$' + (v / 1e6).toFixed(2) + 'M' : v >= 1e3 ? '$' + (v / 1e3).toFixed(0) + 'K' : '$' + Math.round(v),
  dec2: (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  int: (v) => Math.round(v).toLocaleString('en-US'),
  pct: (v) => Number(v).toFixed(1) + '%',
  pct0: (v) => Math.round(v) + '%',
  x: (v) => Number(v).toFixed(2) + '×',
  delta: (v) => (v >= 0 ? '+' : '') + Number(v).toFixed(1) + '%',
};

/** UI cell formatter by value kind (usd, usd2, int, pct, roas, dec2). */
export function formatByKind(kind, v) {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—';
  switch (kind) {
    case 'usd': return fmt.usd(v);
    case 'usd2': return fmt.usd2(v);
    case 'num2': return fmt.dec2(v);
    case 'dec2': return fmt.dec2(v);
    case 'int': return fmt.int(v);
    case 'pct': return fmt.pct(v);
    case 'roas': return fmt.x(v);
    default: return String(v);
  }
}

export function formatValue(v, format) {
  if (v == null || isNaN(v)) return '-';
  return fmt[format]?.(v) ?? String(v);
}

/** Signed absolute change (Pre vs Post delta) for KPI cards. */
export function formatSignedDelta(value, format) {
  if (value == null || Number.isNaN(value)) return '—';
  const n = Number(value);
  const abs = Math.abs(n);
  const sign = n > 0 ? '+' : n < 0 ? '-' : '';
  switch (format) {
    case 'usd':
      return `${sign}$${Math.round(abs).toLocaleString('en-US')}`;
    case 'usd2':
      return `${sign}$${abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    case 'int':
      return (n > 0 ? '+' : '') + Math.round(n).toLocaleString('en-US');
    case 'pp':
      return `${sign || '+'}${abs.toFixed(1)} pp`;
    default:
      return String(n);
  }
}

export function formatPrePostRange(pre, post, format) {
  const kind = format === 'pp' ? 'pct' : format;
  return `${formatValue(pre, kind)} → ${formatValue(post, kind)}`;
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

function isEmptyExportVal(v) {
  return v == null || v === '' || (typeof v === 'number' && Number.isNaN(v));
}

/** Cell formatters for spreadsheet / Google Sheets export (strings with units). */
export const xf = {
  pct: (v) => (isEmptyExportVal(v) ? '' : fmt.pct(v)),
  deltaPct: (v) => (isEmptyExportVal(v) ? '' : fmt.delta(v)),
  pp: (v) => {
    if (isEmptyExportVal(v)) return '';
    const n = Number(v);
    return `${n >= 0 ? '+' : ''}${n.toFixed(1)} pp`;
  },
  usd: (v) => (isEmptyExportVal(v) ? '' : fmt.usd(v)),
  usd2: (v) => (isEmptyExportVal(v) ? '' : fmt.usd2(v)),
  int: (v) => (isEmptyExportVal(v) ? '' : fmt.int(v)),
  roas: (v) => (isEmptyExportVal(v) ? '' : fmt.x(v)),
};

export function exportByKind(kind, v) {
  if (isEmptyExportVal(v)) return '';
  switch (kind) {
    case 'pct': return xf.pct(v);
    case 'int': return xf.int(v);
    case 'usd2': return xf.usd2(v);
    case 'usd': return xf.usd(v);
    case 'roas': return xf.roas(v);
    default: return v;
  }
}

export function exportSummaryMetric(v, metric) {
  const kind = metric === 'profitability' ? 'pct'
    : metric === 'orders' ? 'int'
      : metric === 'aov' ? 'usd2'
        : 'usd';
  return exportByKind(kind, v);
}

export function exportStoreSpecValue(spec, v) {
  return exportByKind(
    spec.id === 'profitability' ? 'pct'
      : spec.id === 'orders' ? 'int'
        : spec.id === 'aov' ? 'usd2'
          : 'usd',
    v,
  );
}
