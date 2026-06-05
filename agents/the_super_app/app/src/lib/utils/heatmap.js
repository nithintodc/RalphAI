/** Background tint for table heatmaps (higher = worse for ops metrics). */
export function heatBackground(value, min, max, { higherIsWorse = true } = {}) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0 || max <= min) return undefined;
  const t = Math.max(0, Math.min(1, (n - min) / (max - min)));
  const alpha = 0.08 + t * 0.42;
  if (higherIsWorse) return `rgba(220, 38, 38, ${alpha})`;
  return `rgba(22, 163, 74, ${alpha})`;
}

export function minMaxNumeric(values) {
  const nums = values.filter((v) => Number.isFinite(v) && v > 0);
  if (!nums.length) return { min: 0, max: 0 };
  return { min: Math.min(...nums), max: Math.max(...nums) };
}

export function matrixValueRange(matrix) {
  const flat = [];
  for (const row of matrix || []) {
    for (const v of row || []) {
      const n = Number(v);
      if (Number.isFinite(n) && n > 0) flat.push(n);
    }
  }
  return minMaxNumeric(flat);
}
