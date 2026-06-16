import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import DataTable from '../../components/ui/DataTable';
import SummaryKpiStrip from '../../components/ui/SummaryKpiStrip';
import { fmt } from '../../lib/utils/formatters';
import { combinedPayoutPerStore } from '../../lib/utils/summaryKpis';
import { PLATFORM_SECTIONS } from '../../lib/platforms';
import { getTopMovers } from '../../lib/engine/diagnostics';

/** Y-axis is shared across sales, payouts, and orders — no currency prefix (amounts differ in unit). */
function compactAxisTick(v) {
  if (v == null || !Number.isFinite(v)) return '';
  const abs = Math.abs(v);
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return String(Math.round(v));
}

function PrePostTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const metricKey = String(row.metric || '').toLowerCase();
  const formatValue = (val) => {
    if (val == null || Number.isNaN(val)) return '—';
    if (metricKey === 'orders') return fmt.int(val);
    return fmt.usd(val);
  };

  return (
    <div
      className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md"
      style={{ fontSize: 12 }}
    >
      <p className="font-semibold text-[var(--text)] mb-1">{label}</p>
      {payload.map((entry) => (
        <p key={String(entry.dataKey)} className="flex justify-between gap-6 tnum">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="font-medium text-[var(--text)]">{formatValue(entry.value)}</span>
        </p>
      ))}
    </div>
  );
}

export default function OverviewScreen() {
  const { summaryTables, storeTables } = useDataStore();

  const summarySections = useMemo(
    () => PLATFORM_SECTIONS
      .map((section) => ({
        ...section,
        summary: summaryTables?.[section.key] || [],
      }))
      .filter((section) => section.summary.length),
    [summaryTables],
  );

  const summary = useMemo(() => summaryTables?.combined || [], [summaryTables]);
  const stores = useMemo(() => storeTables?.combined || [], [storeTables]);

  const movers = useMemo(() => getTopMovers(stores, 5), [stores]);

  const payoutPerStoreSummary = useMemo(
    () => ({
      pre: combinedPayoutPerStore(summaryTables, storeTables, 'pre'),
      post: combinedPayoutPerStore(summaryTables, storeTables, 'post'),
    }),
    [summaryTables, storeTables],
  );

  const prePostBars = useMemo(() => {
    return summary.filter(r => ['sales', 'payouts', 'orders'].includes(r.metric)).map(r => ({
      metric: r.metric.charAt(0).toUpperCase() + r.metric.slice(1),
      Pre: r.pre,
      Post: r.post,
    }));
  }, [summary]);

  const payoutByStoreRows = useMemo(() => {
    if (!stores.length) return [];
    return [...stores].sort((a, b) => (b.post_payouts || 0) - (a.post_payouts || 0));
  }, [stores]);

  const payoutByStoreCols = [
    { key: 'storeId', label: 'Store', sortable: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'pre_payouts', label: 'Pre', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'post_payouts', label: 'Post', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'pre_avg_payout', label: 'Avg/Order (Pre)', align: 'right', sortable: true, render: (v) => fmt.usd2(v || 0) },
    { key: 'post_avg_payout', label: 'Avg/Order (Post)', align: 'right', sortable: true, render: (v) => fmt.usd2(v || 0) },
    { key: 'payouts_growth_pct', label: 'PvP %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v ?? 0) },
    { key: 'payouts_yoy_pct', label: 'YoY %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v ?? 0) },
  ];

  return (
    <div className="space-y-6">
      {/* Hero KPIs — Combined, DoorDash, UberEats */}
      <div className="space-y-5">
        {summarySections.map((section) => (
          <section key={section.key} className="space-y-2">
            <div className="flex items-center gap-2">
              {section.key === 'dd' && <span className="platform-dot dd" />}
              {section.key === 'ue' && <span className="platform-dot ue" />}
              <h2 className="text-sm font-semibold text-[var(--text)]">{section.label}</h2>
            </div>
            <SummaryKpiStrip summary={section.summary} />
          </section>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Pre vs Post Chart */}
        <div className="card col-span-2">
          <h3 className="text-sm font-semibold text-[var(--text)] mb-4">Pre vs Post Comparison</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={prePostBars} barGap={4}>
              <XAxis dataKey="metric" tick={{ fontSize: 12, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-subtle)' }} axisLine={false} tickLine={false} tickFormatter={compactAxisTick} />
              <Tooltip content={<PrePostTooltip />} />
              <Bar dataKey="Pre" fill="var(--border-strong)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Post" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top Movers */}
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--text)] mb-3">Top Movers</h3>
          <div className="mb-4">
            <p className="text-[10px] font-semibold uppercase text-[var(--positive)] mb-1">Highest Growth</p>
            {movers.up.slice(0, 5).map(s => (
              <div key={s.storeId} className="flex items-center justify-between py-1 text-xs">
                <span className="text-[var(--text)] truncate mr-2">{s.storeId}</span>
                <span className="text-[var(--positive)] tnum font-medium whitespace-nowrap">+{s.sales_growth_pct?.toFixed(1)}%</span>
              </div>
            ))}
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase text-[var(--negative)] mb-1">Largest Decline</p>
            {movers.down.slice(0, 5).map(s => (
              <div key={s.storeId} className="flex items-center justify-between py-1 text-xs">
                <span className="text-[var(--text)] truncate mr-2">{s.storeId}</span>
                <span className="text-[var(--negative)] tnum font-medium whitespace-nowrap">{s.sales_growth_pct?.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {payoutByStoreRows.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Payouts by store</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Combined view (DoorDash + Uber Eats when store IDs are mapped). Same Pre / Post windows as the period selector.
              {payoutPerStoreSummary.post != null && (
                <>
                  {' '}
                  Payout per store — Pre: {fmt.usd(payoutPerStoreSummary.pre)} · Post: {fmt.usd(payoutPerStoreSummary.post)}.
                </>
              )}
            </p>
          </div>
          <DataTable columns={payoutByStoreCols} data={payoutByStoreRows} maxHeight="min(360px, 45vh)" />
        </section>
      )}
    </div>
  );
}
