/** Column keys that represent change / growth (not absolute period values). */
const DELTA_KEY_RE = /growth|pvp|yoy|prevspost|lygrowth|_change$|^change$|^delta$|Δ/i;

export function numericDelta(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const s = String(value).trim();
  if (!s || s === '—' || s === '-') return null;
  const n = Number(s.replace(/[%×,+\s]/g, ''));
  return Number.isFinite(n) ? n : null;
}

export function isDeltaColumn(col, sampleRow) {
  if (col?.delta === false) return false;
  if (col?.delta === true || col?.deltaTone === true) return true;
  const key = col?.key || '';
  if (!DELTA_KEY_RE.test(key)) return false;
  const n = numericDelta(sampleRow?.[key]);
  return n != null;
}

export function deltaCellClass(value) {
  const n = numericDelta(value);
  if (n == null || n === 0) return '';
  if (n > 0) return 'delta-cell-positive';
  return 'delta-cell-negative';
}
