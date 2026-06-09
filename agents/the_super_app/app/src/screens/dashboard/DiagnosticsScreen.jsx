import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { AlertTriangle, Info } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import {
  buildOrderOriginAov,
  buildPayoutBridgePrePost,
  buildRevenueGrowthDrivers,
  buildSalesWaterfall,
  detectExceptions,
} from '../../lib/engine/diagnostics';
import { fmt } from '../../lib/utils/formatters';
import { PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';
import RankedBarChart from '../../components/charts/RankedBarChart';
import { POS, NEG, TOOLTIP_STYLE, TOOLTIP_LABEL_STYLE, AXIS_TICK, GRID } from '../../components/charts/chartTheme';
import { CartesianGrid, LabelList } from 'recharts';

function buildWaterfallChart(waterfall) {
  if (!waterfall.length) return [];
  let running = 0;
  return waterfall.map((item) => {
    if (item.type === 'start') {
      running = item.value;
      return { ...item, base: 0, val: item.value };
    }
    if (item.type === 'end') {
      return { ...item, base: 0, val: item.value };
    }
    const base = running;
    running += item.value;
    return { ...item, base: item.value >= 0 ? base : base + item.value, val: Math.abs(item.value) };
  });
}

const salesWaterfallColumns = [
  {
    key: 'label',
    label: 'Step',
    labelCol: true,
    render: (v) => <span className="font-medium">{v}</span>,
  },
  {
    key: 'value',
    label: 'Amount',
    align: 'right',
    delta: true,
    render: (v, row) => {
      if (row.type === 'start' || row.type === 'end') return fmt.usd(v);
      return (
        <span className={v >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}>
          {v >= 0 ? '+' : ''}{fmt.usd(v)}
        </span>
      );
    },
  },
  {
    key: 'type',
    label: 'Role',
    render: (v) => {
      const label = v === 'start' ? 'Baseline' : v === 'end' ? 'Result' : 'Driver';
      return <span className="text-xs text-[var(--text-muted)]">{label}</span>;
    },
  },
];

const growthColumns = [
  { key: 'driver', label: 'Driver', render: (v) => <span className="font-medium">{v}</span> },
  { key: 'formula', label: 'Formula' },
  { key: 'value', label: 'Sales Impact', align: 'right', delta: true, render: (v) => fmt.usd(v) },
  { key: 'contributionPct', label: 'Contribution%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
];

const originColumns = [
  { key: 'segment', label: 'Segment', render: (v) => <span className="font-medium">{v}</span> },
  { key: 'orders', label: 'Orders', align: 'right', render: (v) => fmt.int(v) },
  { key: 'orderSharePct', label: 'Order Share', align: 'right', render: (v) => fmt.pct(v) },
  { key: 'sales', label: 'Sales', align: 'right', render: (v) => fmt.usd(v) },
  { key: 'salesSharePct', label: 'Sales Share', align: 'right', render: (v) => fmt.pct(v) },
  { key: 'aov', label: 'AOV', align: 'right', render: (v) => fmt.usd2(v) },
];

function PlatformDiagnosis({
  section,
  summary,
  ddFinancial,
  config,
  showDdExtras,
}) {
  const waterfall = useMemo(() => buildSalesWaterfall(summary), [summary]);
  const exceptions = useMemo(() => detectExceptions(summary), [summary]);
  const growthDrivers = useMemo(() => buildRevenueGrowthDrivers(summary), [summary]);
  const waterfallChart = useMemo(() => buildWaterfallChart(waterfall), [waterfall]);
  const orderOrigin = useMemo(
    () => (showDdExtras ? buildOrderOriginAov(ddFinancial, config) : []),
    [showDdExtras, ddFinancial, config],
  );
  const payoutFunnel = useMemo(
    () => (showDdExtras ? buildPayoutBridgePrePost(ddFinancial, config) : { hasPre: false, rows: [] }),
    [showDdExtras, ddFinancial, config],
  );

  const dash = (v, fn) => (v == null ? '—' : fn(v));

  const payoutPostColumns = [
    { key: 'step', label: 'Step', labelCol: true, render: (v) => <span className="font-medium">{v}</span> },
    {
      key: 'effectLabel',
      label: 'Effect',
      wrap: true,
      render: (v) => <span className="text-[11px] text-[var(--text-muted)] leading-snug">{v}</span>,
    },
    { key: 'ownership', label: 'Owner', render: (v) => <span className="text-xs">{v}</span> },
    { key: 'type', label: 'Type', render: (v) => <span className="capitalize text-xs">{v}</span> },
    { key: 'value', label: 'Post ($)', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'running', label: 'Running (Post)', align: 'right', render: (v) => fmt.usd(v) },
  ];

  const payoutPreColumns = [
    { key: 'step', label: 'Step', labelCol: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'valuePre', label: 'Pre ($)', align: 'right', render: (v) => dash(v, fmt.usd) },
    { key: 'valueDelta', label: 'Δ $', align: 'right', delta: true, render: (v) => dash(v, fmt.usd) },
    { key: 'valueDeltaPct', label: 'Δ %', align: 'right', delta: true, render: (v) => (v == null ? '—' : fmt.delta(v)) },
    { key: 'runningPre', label: 'Running (Pre)', align: 'right', render: (v) => dash(v, fmt.usd) },
  ];

  if (!summary?.length) return null;

  return (
    <section className="space-y-6 max-w-full overflow-x-hidden">
      <div className="flex items-center gap-2 pt-2 border-t border-[var(--border)] first:border-0 first:pt-0">
        {section.key === 'dd' && <PlatformLogo platform="dd" size={18} />}
        {section.key === 'ue' && <PlatformLogo platform="ue" size={18} />}
        <h2 className="text-base font-semibold text-[var(--text)]">{section.label}</h2>
      </div>

      {exceptions.length > 0 && (
        <div className="space-y-2">
          {exceptions.map((e, i) => (
            <div key={i} className={`card flex items-start gap-3 py-3 ${e.type === 'warning' ? 'border-[var(--warning)]' : 'border-[var(--info)]'}`}>
              {e.type === 'warning' ? <AlertTriangle size={16} className="text-[var(--warning)] mt-0.5" /> : <Info size={16} className="text-[var(--info)] mt-0.5" />}
              <div>
                <p className="text-sm font-medium text-[var(--text)]">{e.message}</p>
                <p className="text-xs text-[var(--text-muted)]">{e.metric}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card max-w-full overflow-hidden">
        <h3 className="text-sm font-semibold text-[var(--text)] mb-1">Sales Decomposition (Pre → Post)</h3>
        <p className="text-[11px] text-[var(--text-subtle)] mb-4">
          How each driver moved sales from the Pre baseline to the Post result.
        </p>
        {waterfall.length > 0 ? (
          <div className="space-y-5 max-w-full">
            {waterfallChart.length > 0 && (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={waterfallChart}
                  barCategoryGap="22%"
                  margin={{ top: 24, right: 8, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11, fill: 'var(--text-muted)' }}
                    axisLine={false}
                    tickLine={false}
                    interval={0}
                  />
                  <YAxis
                    width={56}
                    tick={AXIS_TICK}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => fmt.usdK(v)}
                  />
                  <Tooltip
                    formatter={(v) => fmt.usd(v)}
                    cursor={{ fill: 'var(--surface-2)', opacity: 0.5 }}
                    contentStyle={TOOLTIP_STYLE}
                    labelStyle={TOOLTIP_LABEL_STYLE}
                  />
                  <Bar dataKey="base" stackId="a" fill="transparent" />
                  <Bar dataKey="val" stackId="a" radius={[4, 4, 0, 0]}>
                    {waterfallChart.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={
                          entry.type === 'start' || entry.type === 'end'
                            ? 'var(--accent)'
                            : entry.type === 'pos'
                              ? POS
                              : NEG
                        }
                      />
                    ))}
                    <LabelList
                      dataKey="value"
                      position="top"
                      formatter={(v) => fmt.usdK(v)}
                      style={{ fontSize: 9, fill: 'var(--text-muted)', fontWeight: 600 }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            <DataTable
              columns={salesWaterfallColumns}
              data={waterfall}
              sortable={false}
              layout="full"
              dense
            />
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)] text-center py-8">No data available for decomposition</p>
        )}
      </div>

      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--text)] mb-3">Key Metrics Change</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
          {summary.map((row) => (
            <div key={row.metric} className="p-3 rounded-lg bg-[var(--surface-2)]">
              <div className="text-xs text-[var(--text-muted)] capitalize">{row.metric}</div>
              <div className="text-lg font-semibold tnum text-[var(--text)]">
                {row.metric === 'profitability' ? fmt.pct(row.post) : row.metric === 'aov' ? fmt.usd2(row.post) : row.metric === 'orders' ? fmt.int(row.post) : fmt.usd(row.post)}
              </div>
              <div className={`text-xs tnum font-medium ${row.growthPct >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
                {fmt.delta(row.growthPct)} PvP
              </div>
            </div>
          ))}
        </div>
      </div>

      {growthDrivers.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-[var(--text)]">Revenue Growth Contribution</h3>
          <RankedBarChart
            subtitle="Each driver's share of the Pre→Post sales change. Green = lifted sales, red = dragged."
            data={growthDrivers.map((d) => ({ label: d.driver, value: d.contributionPct }))}
            valueFormatter={fmt.delta}
          />
          <DataTable columns={growthColumns} data={growthDrivers} sortable={false} layout="full" dense />
        </div>
      )}

      {showDdExtras && orderOrigin.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Order Origin and AOV Mix (DoorDash Post Period)</h3>
          <DataTable columns={originColumns} data={orderOrigin} sortable={false} layout="tight" dense />
        </div>
      )}

      {showDdExtras && payoutFunnel.rows.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Sales → payout funnel (DoorDash)</h3>
          <div className="text-xs text-[var(--text-muted)] space-y-2 mb-3">
            <p>
              <span className="font-medium text-[var(--text)]">How to read this:</span> you start with{' '}
              <strong>subtotal (sales)</strong>. Each <strong>cost</strong> row <strong>subtracts</strong> its dollar amount from the
              running payout; each <strong>credit</strong> row <strong>adds</strong> to it. The <strong>calculated net total</strong> is
              the payout after all steps; <strong>actual net total</strong> is what DoorDash put in the file; <strong>variance</strong> is
              the small gap between them.
            </p>
            {!payoutFunnel.hasPre && (
              <p className="text-[var(--warning)]">Set Pre and Post periods in the top bar to see Pre columns, Δ $, and Δ %.</p>
            )}
          </div>
          <div className="space-y-4 max-w-full">
            <div>
              <h4 className="text-xs font-medium text-[var(--text-muted)] mb-2">Post-period funnel</h4>
              <DataTable
                columns={payoutPostColumns}
                data={payoutFunnel.rows}
                sortable={false}
                maxHeight="min(50vh, 420px)"
                layout="tight"
                dense
                bare
              />
            </div>
            {payoutFunnel.hasPre && (
              <div>
                <h4 className="text-xs font-medium text-[var(--text-muted)] mb-2">Pre vs Post change</h4>
                <DataTable
                  columns={payoutPreColumns}
                  data={payoutFunnel.rows}
                  sortable={false}
                  maxHeight="min(50vh, 420px)"
                  layout="tight"
                  dense
                  bare
                />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

export default function DiagnosticsScreen() {
  const { summaryTables, ddFinancial } = useDataStore();
  const config = useConfigStore();

  const sections = useMemo(
    () => PLATFORM_SECTIONS
      .map((section) => ({
        ...section,
        summary: summaryTables?.[section.key] || [],
      }))
      .filter((section) => section.summary.length),
    [summaryTables],
  );

  if (!sections.length) {
    return (
      <p className="text-sm text-[var(--text-muted)] text-center py-12">
        No summary data available. Upload financials and set analysis periods.
      </p>
    );
  }

  return (
    <div className="space-y-10 max-w-full overflow-x-hidden">
      {sections.map((section) => (
        <PlatformDiagnosis
          key={section.key}
          section={section}
          summary={section.summary}
          ddFinancial={ddFinancial}
          config={config}
          showDdExtras={section.key === 'dd'}
        />
      ))}
    </div>
  );
}
