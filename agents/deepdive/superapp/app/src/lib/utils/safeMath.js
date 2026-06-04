export function safeDivide(num, denom, fallback = 0) {
  if (!denom || denom === 0 || !isFinite(denom)) return fallback;
  const result = num / denom;
  if (!isFinite(result)) return fallback;
  return result;
}

export function growthPct(pre, post) {
  return safeDivide(post - pre, pre) * 100;
}

export function cleanInfinity(value, fallback = 0) {
  if (!isFinite(value) || isNaN(value)) return fallback;
  return value;
}

export function round(value, decimals = 1) {
  if (!isFinite(value) || isNaN(value)) return 0;
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

export function toNum(v, fallback = 0) {
  if (v == null || v === '') return fallback;
  const n = typeof v === 'string' ? parseFloat(v.replace(/[,$]/g, '')) : Number(v);
  return isNaN(n) ? fallback : n;
}
