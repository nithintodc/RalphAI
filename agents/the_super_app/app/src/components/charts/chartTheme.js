/**
 * Shared chart styling tokens so every recharts chart in the app reads the same
 * and respects the light/dark CSS variables. Use these instead of inlining styles.
 */

export const TOOLTIP_STYLE = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 12,
  boxShadow: 'var(--shadow-md)',
};

export const TOOLTIP_LABEL_STYLE = { color: 'var(--text)', fontWeight: 600, marginBottom: 2 };
export const TOOLTIP_ITEM_STYLE = { color: 'var(--text-muted)' };

export const AXIS_TICK = { fontSize: 11, fill: 'var(--text-subtle)' };
export const AXIS_TICK_SM = { fontSize: 9, fill: 'var(--text-muted)' };
export const LEGEND_STYLE = { fontSize: 11 };
export const GRID = 'var(--border)';

/** Pre vs Post convention used across the app (matches existing bar charts). */
export const SERIES = {
  pre: 'var(--border-strong)',
  post: 'var(--accent)',
};

/** Sign-based colors, aligned with delta cells (--positive / --negative). */
export const POS = 'var(--positive)';
export const NEG = 'var(--negative)';
export const WARN = 'var(--warning)';

/** Categorical palette for pies / stacked / scatter — readable in light & dark. */
export const CATEGORICAL = [
  'var(--accent)',
  '#6366F1',
  '#F59E0B',
  '#EC4899',
  '#0EA5E9',
  '#84CC16',
  '#A855F7',
  '#14B8A6',
];

/** Pick a sign-based color for a numeric value (0 → muted). */
export function signColor(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return 'var(--border-strong)';
  return n > 0 ? POS : NEG;
}
