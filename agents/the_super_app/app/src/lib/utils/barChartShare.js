/** Add *_pct fields: each bar value as % of total for that series across rows. */
export function addBarSharePct(rows, valueKeys) {
  const keys = Array.isArray(valueKeys) ? valueKeys : [valueKeys];
  const totals = {};
  for (const k of keys) {
    totals[k] = (rows || []).reduce((s, r) => s + (Number(r[k]) || 0), 0);
  }
  return (rows || []).map((r) => {
    const extra = {};
    for (const k of keys) {
      const v = Number(r[k]) || 0;
      extra[`${k}_pct`] = totals[k] > 0 ? (v / totals[k]) * 100 : 0;
    }
    return { ...r, ...extra };
  });
}

export function barShareLabel(pct) {
  const n = Number(pct);
  if (!Number.isFinite(n) || n <= 0) return '';
  return `${n.toFixed(1)}%`;
}
