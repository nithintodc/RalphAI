import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import ChartCard from './ChartCard';
import BarShareLabels from './BarShareLabels';
import { addBarSharePct } from '../../lib/utils/barChartShare';
import {
  TOOLTIP_STYLE, TOOLTIP_LABEL_STYLE, AXIS_TICK, AXIS_TICK_SM, LEGEND_STYLE, GRID,
} from './chartTheme';

/**
 * Self-contained grouped/comparison bar chart in a ChartCard.
 *
 * Props:
 *  - data: row objects
 *  - xKey: category field
 *  - series: [{ key, name, color }] — one bar group per entry
 *  - valueFormatter: (v) => string for tooltip values (and labels if shareLabels off)
 *  - shareLabels: when true, label bars with each value's % of its series total
 *  - labelSeriesKeys: only label these series keys (default: all when shareLabels on)
 *  - angle: x tick rotation (use -35 for crowded buckets)
 *  - height, title, subtitle, className, right, legend (default true)
 */
export default function GroupedBarChart({
  data,
  xKey,
  series = [],
  valueFormatter,
  shareLabels = false,
  labelSeriesKeys,
  angle = 0,
  height = 300,
  title,
  subtitle,
  className = '',
  right,
  legend = true,
  smallTicks = false,
}) {
  const seriesKeys = series.map((s) => s.key);
  const chartData = shareLabels ? addBarSharePct(data || [], seriesKeys) : (data || []);
  const labelled = labelSeriesKeys || seriesKeys;
  const rotated = angle !== 0;

  return (
    <ChartCard title={title} subtitle={subtitle} height={height} className={className} right={right}>
      <BarChart
        data={chartData}
        barGap={2}
        margin={{ top: 20, right: 8, left: 0, bottom: rotated ? 36 : 4 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey={xKey}
          tick={smallTicks ? AXIS_TICK_SM : AXIS_TICK}
          axisLine={false}
          tickLine={false}
          interval={0}
          angle={angle}
          textAnchor={rotated ? 'end' : 'middle'}
          height={rotated ? 52 : 24}
        />
        <YAxis
          tick={AXIS_TICK}
          axisLine={false}
          tickLine={false}
          width={44}
          tickFormatter={valueFormatter}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          labelStyle={TOOLTIP_LABEL_STYLE}
          cursor={{ fill: 'var(--surface-2)', opacity: 0.5 }}
          formatter={valueFormatter ? (v, name) => [valueFormatter(v), name] : undefined}
        />
        {legend && <Legend wrapperStyle={LEGEND_STYLE} />}
        {series.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[3, 3, 0, 0]}>
            {shareLabels && labelled.includes(s.key) && (
              <BarShareLabels dataKey={s.key} fill={s.labelFill} />
            )}
          </Bar>
        ))}
      </BarChart>
    </ChartCard>
  );
}
