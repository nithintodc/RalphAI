import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, LabelList, CartesianGrid } from 'recharts';
import ChartCard from './ChartCard';
import {
  TOOLTIP_STYLE, TOOLTIP_LABEL_STYLE, AXIS_TICK, GRID, signColor,
} from './chartTheme';

/**
 * Horizontal ranked bar chart. Bars colored green/red by sign (or a fixed color),
 * sorted descending by value. Good for "top / declining" rankings.
 *
 * Props:
 *  - data: rows; uses `labelKey` for category, `valueKey` for magnitude
 *  - labelKey (default 'label'), valueKey (default 'value')
 *  - valueFormatter: (v) => string for axis/labels/tooltip
 *  - color: fixed bar color; omit to color by sign (positive/negative)
 *  - topN: keep only the N rows with largest |value| (default all)
 *  - barLabels: show formatted value at bar end (default true)
 *  - height auto-derives from row count unless provided
 */
export default function RankedBarChart({
  data = [],
  labelKey = 'label',
  valueKey = 'value',
  valueFormatter = (v) => v,
  color,
  topN,
  barLabels = true,
  height,
  title,
  subtitle,
  className = '',
}) {
  const sorted = [...data]
    .filter((r) => r && r[valueKey] != null && Number.isFinite(Number(r[valueKey])))
    .sort((a, b) => Math.abs(Number(b[valueKey])) - Math.abs(Number(a[valueKey])));
  const rows = topN ? sorted.slice(0, topN) : sorted;
  const h = height ?? Math.max(160, rows.length * 30 + 40);

  return (
    <ChartCard title={title} subtitle={subtitle} height={h} className={className}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis type="number" tick={AXIS_TICK} axisLine={false} tickLine={false} tickFormatter={valueFormatter} />
        <YAxis
          type="category"
          dataKey={labelKey}
          tick={{ ...AXIS_TICK, fill: 'var(--text-muted)' }}
          axisLine={false}
          tickLine={false}
          width={150}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
          cursor={{ fill: 'var(--surface-2)', opacity: 0.5 }}
          formatter={(v) => [valueFormatter(v), '']}
        />
        <Bar dataKey={valueKey} radius={[0, 3, 3, 0]} isAnimationActive={false}>
          {rows.map((r, i) => (
            <Cell key={i} fill={color || signColor(r[valueKey])} />
          ))}
          {barLabels && (
            <LabelList
              dataKey={valueKey}
              position="right"
              formatter={valueFormatter}
              style={{ fontSize: 10, fill: 'var(--text-muted)', fontWeight: 600 }}
            />
          )}
        </Bar>
      </BarChart>
    </ChartCard>
  );
}
