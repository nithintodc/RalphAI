import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
  LineChart, Line,
} from 'recharts';
import Heatmap from '../charts/Heatmap';
import ChartCard from '../charts/ChartCard';
import { DAY_NAMES, SLOT_NAMES } from '../../lib/engine/slots';
import { fmt } from '../../lib/utils/formatters';
import {
  TOOLTIP_STYLE, TOOLTIP_LABEL_STYLE, LEGEND_STYLE, AXIS_TICK, GRID, CATEGORICAL, SERIES,
} from '../charts/chartTheme';

const MIX_COLORS = { new: CATEGORICAL[0], repeat: CATEGORICAL[1], unknown: 'var(--border-strong)' };

/** Charts for the day-dimension order analysis (Post period). */
function DayCharts({ rows, showCustomerItems, hasDashPass }) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {showCustomerItems && (
        <ChartCard
          title="Customer mix by weekday"
          subtitle="Share of orders that are new vs repeat vs unknown (Post period)."
          height={260}
        >
          <BarChart data={rows} stackOffset="expand" margin={{ top: 16, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
            <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} />
            <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={40} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelStyle={TOOLTIP_LABEL_STYLE}
              cursor={{ fill: 'var(--surface-2)', opacity: 0.5 }}
              formatter={(v, name) => [fmt.int(v), name]}
            />
            <Legend wrapperStyle={LEGEND_STYLE} />
            <Bar dataKey="newCount" name="New" stackId="m" fill={MIX_COLORS.new} />
            <Bar dataKey="repeatCount" name="Repeat" stackId="m" fill={MIX_COLORS.repeat} />
            <Bar dataKey="unknownCount" name="Unknown" stackId="m" fill={MIX_COLORS.unknown} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartCard>
      )}

      {showCustomerItems && (
        <ChartCard
          title="Average items per order by weekday"
          subtitle="Basket complexity across the week (Post period)."
          height={260}
        >
          <LineChart data={rows} margin={{ top: 16, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
            <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} />
            <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={40} domain={[0, 'auto']} />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v) => [fmt.dec2(v), 'Items/order']} />
            <Line type="monotone" dataKey="avgItemsPerOrder" stroke="var(--accent)" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ChartCard>
      )}

      {hasDashPass && (
        <ChartCard
          title="DashPass penetration by weekday"
          subtitle="% of orders placed by DashPass members (Post period)."
          height={260}
          className={showCustomerItems ? '' : 'xl:col-span-2'}
        >
          <BarChart data={rows} margin={{ top: 16, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
            <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} />
            <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={40} tickFormatter={(v) => `${Math.round(v)}%`} />
            <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v) => [fmt.pct(v), 'DashPass']} />
            <Bar dataKey="dashPassPct" name="DashPass %" fill={SERIES.post} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartCard>
      )}
    </div>
  );
}

/** Day × slot heatmaps (Post period). */
function DaySlotHeatmaps({ rows, showCustomerItems, hasDashPass }) {
  const byCell = {};
  for (const r of rows) byCell[`${r.day}|${r.slot}`] = r;
  const rowDefs = DAY_NAMES.map((d) => ({ key: d, label: d }));
  const colDefs = SLOT_NAMES.map((s) => ({ key: s, label: s }));
  const val = (field) => (day, slot) => {
    const r = byCell[`${day}|${slot}`];
    return r && r[field] != null ? r[field] : null;
  };

  return (
    <div className="grid grid-cols-1 gap-4">
      <Heatmap
        title="Order volume — day × slot"
        subtitle="Where orders concentrate across the week and day-parts (Post period)."
        rows={rowDefs}
        cols={colDefs}
        getValue={val('orders')}
      />
      {showCustomerItems && (
        <Heatmap
          title="New-customer share — day × slot"
          subtitle="% of orders from new customers (Post period). Darker = more new customers."
          rows={rowDefs}
          cols={colDefs}
          getValue={val('newPct')}
          max={100}
          format={(v) => `${Math.round(v)}%`}
          unit=""
        />
      )}
      {hasDashPass && (
        <Heatmap
          title="DashPass penetration — day × slot"
          subtitle="% of orders from DashPass members (Post period)."
          rows={rowDefs}
          cols={colDefs}
          getValue={val('dashPassPct')}
          max={100}
          format={(v) => `${Math.round(v)}%`}
        />
      )}
    </div>
  );
}

/**
 * Visual summary above the day / day×slot tables.
 * @param {'day'|'daySlot'} dimension
 */
export default function SlotOrderCharts({ analysis, dimension }) {
  if (!analysis) return null;
  const showCustomerItems = analysis.hasCustomerType || analysis.hasItemCount;
  const hasDashPass = !!analysis.hasDashPass;
  const rows = analysis.post?.[dimension] || [];
  if (!rows.length) return null;
  if (!showCustomerItems && !hasDashPass && dimension === 'day') {
    // order-volume only: a single weekday bar is still useful
    return (
      <ChartCard title="Orders by weekday" subtitle="Post period." height={240}>
        <BarChart data={rows} margin={{ top: 16, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
          <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={44} />
          <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} formatter={(v) => [fmt.int(v), 'Orders']} />
          <Bar dataKey="orders" name="Orders" fill={SERIES.post} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ChartCard>
    );
  }

  return dimension === 'daySlot'
    ? <DaySlotHeatmaps rows={rows} showCustomerItems={showCustomerItems} hasDashPass={hasDashPass} />
    : <DayCharts rows={rows} showCustomerItems={showCustomerItems} hasDashPass={hasDashPass} />;
}
