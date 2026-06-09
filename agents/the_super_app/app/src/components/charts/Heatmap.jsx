/**
 * Pure CSS-grid heatmap (recharts has no clean heatmap primitive).
 * Color intensity interpolates --surface-2 → --accent by value / max.
 *
 * Props:
 *  - rows: [{ key, label }]
 *  - cols: [{ key, label }]
 *  - getValue: (rowKey, colKey) => number | null
 *  - format: (v) => string for the cell text (default rounded int)
 *  - max: optional fixed max for the color scale (default = data max)
 *  - title, subtitle, className
 *  - accent: CSS color for the high end (default var(--accent))
 *  - unit: appended in the cell tooltip
 */
export default function Heatmap({
  rows = [],
  cols = [],
  getValue,
  format = (v) => (v == null ? '' : Math.round(v).toLocaleString('en-US')),
  max,
  title,
  subtitle,
  className = '',
  accent = 'var(--accent)',
  unit = '',
}) {
  const values = [];
  for (const r of rows) for (const c of cols) {
    const v = getValue(r.key, c.key);
    if (v != null && Number.isFinite(Number(v))) values.push(Number(v));
  }
  const hi = max ?? (values.length ? Math.max(...values) : 0);

  const cellBg = (v) => {
    if (v == null || !Number.isFinite(Number(v)) || hi <= 0) return 'var(--surface-2)';
    const pct = Math.max(0, Math.min(1, Number(v) / hi));
    return `color-mix(in srgb, ${accent} ${Math.round(pct * 100)}%, var(--surface-2))`;
  };
  const cellText = (v) => {
    if (v == null || !Number.isFinite(Number(v)) || hi <= 0) return 'var(--text-subtle)';
    return Number(v) / hi > 0.55 ? '#fff' : 'var(--text-muted)';
  };

  const gridCols = `minmax(4rem, 9rem) repeat(${cols.length}, minmax(0, 1fr))`;

  return (
    <div className={`card ${className}`}>
      {title && <h3 className="text-sm font-semibold text-[var(--text)] mb-1">{title}</h3>}
      {subtitle && <p className="text-[11px] text-[var(--text-subtle)] mb-3 leading-relaxed">{subtitle}</p>}
      <div className="overflow-x-auto">
        <div className="min-w-[32rem]">
          {/* header */}
          <div className="grid gap-1 mb-1" style={{ gridTemplateColumns: gridCols }}>
            <div />
            {cols.map((c) => (
              <div key={c.key} className="text-[10px] font-medium text-[var(--text-subtle)] text-center truncate px-0.5">
                {c.label}
              </div>
            ))}
          </div>
          {/* rows */}
          <div className="space-y-1">
            {rows.map((r) => (
              <div key={r.key} className="grid gap-1 items-center" style={{ gridTemplateColumns: gridCols }}>
                <div className="text-[11px] font-medium text-[var(--text-muted)] truncate pr-1">{r.label}</div>
                {cols.map((c) => {
                  const v = getValue(r.key, c.key);
                  return (
                    <div
                      key={c.key}
                      title={`${r.label} · ${c.label}: ${v == null ? '—' : format(v)}${unit}`}
                      className="tnum text-center text-[10px] font-semibold rounded py-1.5 leading-none"
                      style={{ background: cellBg(v), color: cellText(v) }}
                    >
                      {v == null ? '·' : format(v)}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
