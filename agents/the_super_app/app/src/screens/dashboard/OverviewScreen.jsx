import { useMemo } from 'react';
import { format } from 'date-fns';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import SummaryKpiStrip from '../../components/ui/SummaryKpiStrip';
import { fmt } from '../../lib/utils/formatters';
import { PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';
import RankedBarChart from '../../components/charts/RankedBarChart';
import {
  getStarAndDecliningStores,
  getPlatformDailyExtremes,
  getSlotSpotlight,
  getWeekdaySpotlight,
} from '../../lib/engine/diagnostics';

const MOVEMENT_METRICS = [
  { key: 'sales', label: 'Sales' },
  { key: 'payouts', label: 'Payouts' },
  { key: 'orders', label: 'Orders' },
  { key: 'aov', label: 'AOV' },
  { key: 'profitability', label: 'Profitability' },
];

const PLATFORM_VIEWS = [
  { key: 'combined', label: 'Combined', platform: 'combined', logo: null },
  { key: 'dd', label: 'DoorDash', platform: 'dd', logo: 'dd' },
  { key: 'ue', label: 'Uber Eats', platform: 'ue', logo: 'ue' },
];

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
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md">
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

function GrowthTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-[var(--text)] mb-1">{label}</p>
      {payload.map((entry) => (
        <p key={String(entry.dataKey)} className="flex justify-between gap-6 tnum">
          <span style={{ color: entry.color }}>{entry.name}</span>
          <span className="font-medium text-[var(--text)]">{entry.payload?.formatted ?? entry.value}</span>
        </p>
      ))}
    </div>
  );
}

function formatMetricValue(metricKey, v) {
  if (v == null || Number.isNaN(v)) return '—';
  if (metricKey === 'orders') return fmt.int(v);
  if (metricKey === 'profitability') return fmt.pct(v);
  if (metricKey === 'aov') return fmt.usd2(v);
  return fmt.usd(v);
}

function capitalize(s) {
  return String(s || '').charAt(0).toUpperCase() + String(s || '').slice(1);
}

function formatDayOnly(date) {
  if (!date) return '';
  return format(date, 'MMM d');
}

function MetricMovementChart({ title, points, metricKey, changePct, changeLabel }) {
  const chartData = points.map((p) => ({
    ...p,
    formatted: formatMetricValue(metricKey, p.value),
  }));
  const stroke = (changePct ?? 0) >= 0 ? 'var(--positive)' : 'var(--negative)';

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 min-w-0">
      <p className="text-xs font-semibold text-[var(--text)] mb-2">{title}</p>
      <ResponsiveContainer width="100%" height={132}>
        <LineChart data={chartData} margin={{ top: 12, right: 12, left: 4, bottom: 4 }}>
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--text-subtle)' }}
            width={44}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => {
              if (metricKey === 'profitability') return `${Math.round(v)}%`;
              return compactAxisTick(v);
            }}
          />
          <Tooltip content={<GrowthTooltip />} />
          <Line type="monotone" dataKey="value" stroke={stroke} strokeWidth={2.5} dot={{ r: 5, fill: stroke, strokeWidth: 0 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
      <p className={`text-[10px] tnum font-semibold mt-1 ${(changePct ?? 0) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
        {changeLabel}: {fmt.delta(changePct ?? 0)}
      </p>
    </div>
  );
}

function GrowthSpotlightRow({ id, pct, tone }) {
  const isPositive = (pct || 0) >= 0;
  const toneClass = tone === 'star'
    ? (isPositive ? 'text-[var(--positive)]' : 'text-[var(--text)]')
    : 'text-[var(--negative)]';
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-[var(--border)] last:border-0 text-xs">
      <span className="text-[var(--text)] font-medium truncate">{id}</span>
      <span className={`tnum font-semibold whitespace-nowrap ${toneClass}`}>{fmt.delta(pct ?? 0)}</span>
    </div>
  );
}

function DayRow({ day, tone, value, valueFmt = 'usd' }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-[var(--border)] last:border-0 text-xs">
      <span className="text-[var(--text)] font-medium whitespace-nowrap">{day}</span>
      <span className={`tnum font-semibold whitespace-nowrap ${tone === 'top' ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
        {valueFmt === 'usd' ? fmt.usd(value ?? 0) : fmt.delta(value ?? 0)}
      </span>
    </div>
  );
}

function DateExtremesBlock({ title, extremes }) {
  if (!extremes?.top?.length && !extremes?.low?.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</p>
      <div className="grid grid-cols-2 gap-x-4">
        <div>
          <p className="text-[10px] font-semibold uppercase text-[var(--positive)] mb-0.5">Top days</p>
          {extremes.top.map((d) => <DayRow key={`t-${d.dateKey}`} day={formatDayOnly(d.date)} tone="top" value={d.sales} />)}
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase text-[var(--negative)] mb-0.5">Low days</p>
          {extremes.low.map((d) => <DayRow key={`l-${d.dateKey}`} day={formatDayOnly(d.date)} tone="low" value={d.sales} />)}
        </div>
      </div>
    </div>
  );
}

function WeekdayExtremesBlock({ title, extremes }) {
  if (!extremes?.top?.length && !extremes?.low?.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</p>
      <div className="grid grid-cols-2 gap-x-4">
        <div>
          <p className="text-[10px] font-semibold uppercase text-[var(--positive)] mb-0.5">Top weekdays</p>
          {extremes.top.map((d) => <DayRow key={`wt-${d.day}`} day={d.day} tone="top" value={d.sales} />)}
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase text-[var(--negative)] mb-0.5">Low weekdays</p>
          {extremes.low.map((d) => <DayRow key={`wl-${d.day}`} day={d.day} tone="low" value={d.sales} />)}
        </div>
      </div>
    </div>
  );
}

function MetricMovementSection({ label, logo, movementRows, suffix }) {
  if (!movementRows.length) return null;
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        {logo && <PlatformLogo platform={logo} size={18} />}
        <h3 className="text-sm font-semibold text-[var(--text)]">{label}</h3>
      </div>

      <section className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text)]">Pre vs Post — by metric</h4>
          <p className="text-[10px] text-[var(--text-subtle)] mt-0.5">
            Line shows movement from Pre to Post ({suffix})
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {movementRows.map((row) => {
            const meta = MOVEMENT_METRICS.find((m) => m.key === row.metric);
            return (
              <MetricMovementChart
                key={`pvp-${suffix}-${row.metric}`}
                title={meta?.label ?? capitalize(row.metric)}
                metricKey={row.metric}
                points={[{ label: 'Pre', value: row.pre }, { label: 'Post', value: row.post }]}
                changePct={row.growthPct}
                changeLabel="Pre vs Post"
              />
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text)]">Year over Year — by metric</h4>
          <p className="text-[10px] text-[var(--text-subtle)] mt-0.5">
            Line shows movement from LY Post to Post ({suffix})
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {movementRows.map((row) => {
            const meta = MOVEMENT_METRICS.find((m) => m.key === row.metric);
            return (
              <MetricMovementChart
                key={`yoy-${suffix}-${row.metric}`}
                title={meta?.label ?? capitalize(row.metric)}
                metricKey={row.metric}
                points={[{ label: 'LY Post', value: row.postLY }, { label: 'Post', value: row.post }]}
                changePct={row.yoyPct}
                changeLabel="YoY"
              />
            );
          })}
        </div>
      </section>
    </div>
  );
}

export default function OverviewScreen() {
  const { summaryTables, storeTables, ddFinancial, ueFinancial } = useDataStore();
  const config = useConfigStore();

  const summarySections = useMemo(
    () => PLATFORM_SECTIONS
      .map((section) => ({ ...section, summary: summaryTables?.[section.key] || [] }))
      .filter((section) => section.summary.length),
    [summaryTables],
  );

  const combinedSummary = useMemo(() => summaryTables?.combined || [], [summaryTables]);

  const prePostBars = useMemo(() => (
    combinedSummary.filter((r) => ['sales', 'payouts', 'orders'].includes(r.metric)).map((r) => ({
      metric: capitalize(r.metric),
      Pre: r.pre,
      Post: r.post,
    }))
  ), [combinedSummary]);

  const platformInsights = useMemo(() => {
    return PLATFORM_VIEWS.map((pv) => {
      const summary = summaryTables?.[pv.key] || [];
      const order = MOVEMENT_METRICS.map((m) => m.key);
      const movementRows = summary
        .filter((r) => order.includes(r.metric))
        .sort((a, b) => order.indexOf(a.metric) - order.indexOf(b.metric));

      const stores = storeTables?.[pv.key] || [];
      const storeSpotlight = getStarAndDecliningStores(stores);

      const prefix = pv.platform === 'combined' ? 'dd' : pv.platform;
      const preStart = config[`${prefix}PreStart`];
      const preEnd = config[`${prefix}PreEnd`];
      const postStart = config[`${prefix}PostStart`];
      const postEnd = config[`${prefix}PostEnd`];
      const excluded = config[`${prefix}ExcludedDates`] || [];

      let preExtremes = { top: [], low: [] };
      let postExtremes = { top: [], low: [] };
      let slotSpotlight = { stars: [], declining: [], count: 0 };
      let weekdaySpotlight = { top: [], low: [] };

      if (pv.platform === 'combined') {
        preExtremes = getPlatformDailyExtremes(
          { ddFinancial, ueFinancial, ddExcludedDates: config.ddExcludedDates, ueExcludedDates: config.ueExcludedDates },
          'combined',
          preStart,
          preEnd,
        );
        postExtremes = getPlatformDailyExtremes(
          { ddFinancial, ueFinancial, ddExcludedDates: config.ddExcludedDates, ueExcludedDates: config.ueExcludedDates },
          'combined',
          postStart,
          postEnd,
        );
        weekdaySpotlight = getWeekdaySpotlight(
          ddFinancial,
          'combined',
          postStart,
          postEnd,
          config.ddExcludedDates,
          ueFinancial,
        );
      } else {
        const financial = pv.platform === 'dd' ? ddFinancial : ueFinancial;
        if (financial?.length) {
          preExtremes = getPlatformDailyExtremes(financial, pv.platform, preStart, preEnd, excluded);
          postExtremes = getPlatformDailyExtremes(financial, pv.platform, postStart, postEnd, excluded);
          slotSpotlight = getSlotSpotlight(financial, config, pv.platform);
          weekdaySpotlight = getWeekdaySpotlight(financial, pv.platform, postStart, postEnd, excluded);
        }
      }

      return {
        ...pv,
        movementRows,
        storeSpotlight,
        preExtremes,
        postExtremes,
        slotSpotlight,
        weekdaySpotlight,
        hasDateData: preExtremes.top.length || preExtremes.low.length || postExtremes.top.length || postExtremes.low.length,
        hasSlotData: slotSpotlight.stars.length || slotSpotlight.declining.length,
        hasWeekdayData: weekdaySpotlight.top.length || weekdaySpotlight.low.length,
      };
    }).filter((p) => p.movementRows.length > 0 || p.storeSpotlight.count > 0 || p.hasDateData);
  }, [summaryTables, storeTables, ddFinancial, ueFinancial, config]);

  return (
    <div className="space-y-6 min-w-0">
      <div className="space-y-5">
        {summarySections.map((section) => (
          <section key={section.key} className="space-y-2 min-w-0">
            <div className="flex items-center gap-2">
              {section.key === 'dd' && <PlatformLogo platform="dd" size={18} />}
              {section.key === 'ue' && <PlatformLogo platform="ue" size={18} />}
              <h2 className="text-sm font-semibold text-[var(--text)]">{section.label}</h2>
            </div>
            <SummaryKpiStrip summary={section.summary} />
          </section>
        ))}
      </div>

      {prePostBars.length > 0 && (
        <div className="card min-w-0">
          <h3 className="text-sm font-semibold text-[var(--text)] mb-4">Pre vs Post Comparison (Combined)</h3>
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
      )}

      {platformInsights.map((p) => (
        <div key={p.key} className="space-y-6 pt-2 border-t border-[var(--border)]">
          <MetricMovementSection
            label={p.label}
            logo={p.logo}
            movementRows={p.movementRows}
            suffix={p.label}
          />

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 min-w-0">
            {(p.storeSpotlight.stars.length > 0 || p.storeSpotlight.declining.length > 0) ? (
              <RankedBarChart
                className="min-w-0"
                title={`Store Spotlight — ${p.label}`}
                subtitle={`Top & low ${p.storeSpotlight.count || 0} store${p.storeSpotlight.count === 1 ? '' : 's'} by Pre→Post sales growth.`}
                data={[...p.storeSpotlight.stars, ...p.storeSpotlight.declining].map((s) => ({
                  label: s.storeId,
                  value: s.sales_growth_pct,
                }))}
                valueFormatter={fmt.delta}
              />
            ) : (
              <div className="card min-w-0">
                <h3 className="text-sm font-semibold text-[var(--text)] mb-1">Store Spotlight — {p.label}</h3>
                <p className="text-xs text-[var(--text-subtle)]">No store-level growth data.</p>
              </div>
            )}

            <div className="card min-w-0 flex flex-col max-h-[min(480px,70vh)]">
              <h3 className="text-sm font-semibold text-[var(--text)] mb-1 shrink-0">Date Spotlight — {p.label}</h3>
              <p className="text-[10px] text-[var(--text-subtle)] mb-3 shrink-0">
                Top &amp; low sales days (10% of days)
              </p>
              <div className="overflow-y-auto min-h-0 flex-1 space-y-4">
                {p.hasDateData ? (
                  <>
                    <DateExtremesBlock title="Post period" extremes={p.postExtremes} />
                    <DateExtremesBlock title="Pre period" extremes={p.preExtremes} />
                  </>
                ) : (
                  <p className="text-xs text-[var(--text-subtle)]">Upload financial data to see daily highlights.</p>
                )}
              </div>
            </div>
          </div>

          {(p.hasSlotData || p.hasWeekdayData) && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 min-w-0">
              {p.hasSlotData && (
                <div className="card min-w-0">
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-1">Slot Spotlight — {p.label}</h3>
                  <p className="text-[10px] text-[var(--text-subtle)] mb-3">
                    Dayparts with highest / lowest Pre→Post sales growth
                  </p>
                  <div className="grid grid-cols-2 gap-x-4">
                    <div>
                      <p className="text-[10px] font-semibold uppercase text-[var(--positive)] mb-1">Top slots</p>
                      {p.slotSpotlight.stars.map((s) => (
                        <GrowthSpotlightRow key={`ss-${p.key}-${s.storeId}`} id={s.storeId} pct={s.sales_growth_pct} tone="star" />
                      ))}
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold uppercase text-[var(--negative)] mb-1">Declining slots</p>
                      {p.slotSpotlight.declining.map((s) => (
                        <GrowthSpotlightRow key={`sd-${p.key}-${s.storeId}`} id={s.storeId} pct={s.sales_growth_pct} tone="decline" />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {p.hasWeekdayData && (
                <div className="card min-w-0">
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-1">Weekday Spotlight — {p.label}</h3>
                  <p className="text-[10px] text-[var(--text-subtle)] mb-3">
                    Best &amp; worst weekdays by sales (Post period)
                  </p>
                  <WeekdayExtremesBlock title="Post period" extremes={p.weekdaySpotlight} />
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
