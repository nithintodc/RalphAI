import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import {
  buildSlotAnalysis,
  buildSlotTicketBucketAnalysis,
  SLOT_DISPLAY_METRICS,
} from '../../lib/engine/slots';
import { buildSlotSalesOrderAnalysis } from '../../lib/engine/slotSalesOrder';
import { normalizeDdSalesByOrder } from '../../lib/parsers/ddSalesByOrder';
import { normalizeUeOrdersForSlotView } from '../../lib/parsers/ueOrderSlots';
import SlotSalesOrderSection from '../../components/slots/SlotSalesOrderSection';
import { fmt } from '../../lib/utils/formatters';
import { DATA_PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';

function SlotTicketMixSummary({ summary, platformLabel }) {
  const { towardsLesserGcBaskets, towardsHigherTicket, roughlyUnchanged } = summary;
  const fmtList = (arr) => (arr.length ? arr.join(', ') : '—');
  return (
    <div className="card border-l-[3px] border-l-[var(--accent)]">
      <h3 className="text-sm font-semibold text-[var(--text)] mb-2">
        Ticket mix by slot — summary ({platformLabel})
      </h3>
      <p className="text-[11px] text-[var(--text-subtle)] mb-3 leading-relaxed">
        Same ticket-size buckets as Order Buckets. Within each time-of-day slot we compare how <strong>Post</strong>{' '}
        order share moves across buckets vs <strong>Pre</strong>.
      </p>
      <ul className="text-xs space-y-2.5 text-[var(--text-muted)] leading-snug">
        <li>
          <span className="font-semibold text-[var(--text)]">Lower ticket / lesser GC basket shift: </span>
          {fmtList(towardsLesserGcBaskets)}
        </li>
        <li>
          <span className="font-semibold text-[var(--text)]">Higher ticket / going forward: </span>
          {fmtList(towardsHigherTicket)}
        </li>
        <li>
          <span className="font-semibold text-[var(--text)]">Roughly unchanged / low volume: </span>
          {fmtList(roughlyUnchanged)}
        </li>
      </ul>
    </div>
  );
}

function SlotTicketBucketCharts({ bySlotCharts }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {bySlotCharts.map(({ slot, data }) => (
        <div key={slot} className="card">
          <h4 className="text-xs font-semibold text-[var(--text)] mb-3">{slot} — order count by ticket size</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data} barGap={1} margin={{ bottom: 36, left: 0, right: 4 }}>
              <XAxis
                dataKey="range"
                tick={{ fontSize: 8, fill: 'var(--text-muted)' }}
                axisLine={false}
                tickLine={false}
                interval={0}
                angle={-35}
                textAnchor="end"
                height={52}
              />
              <YAxis tick={{ fontSize: 10, fill: 'var(--text-subtle)' }} axisLine={false} tickLine={false} width={36} />
              <Tooltip
                contentStyle={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 11,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar dataKey="pre_orders" name="Pre" fill="var(--border-strong)" radius={[2, 2, 0, 0]} />
              <Bar dataKey="post_orders" name="Post" fill="var(--accent)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}

function renderSlotValue(valueKind, v) {
  if (v == null || Number.isNaN(v)) return '—';
  if (valueKind === 'pct') return fmt.pct(v);
  if (valueKind === 'int') return fmt.int(v);
  if (valueKind === 'usd2') return fmt.usd2(v);
  return fmt.usd(v);
}

function buildPvpColumns(spec) {
  const preLabel = spec.dailyAvg ? 'Pre (avg/day)' : 'Pre';
  const postLabel = spec.dailyAvg ? 'Post (avg/day)' : 'Post';
  return [
    { key: 'slot', label: 'Slot', sortable: false, labelCol: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'pre', label: preLabel, align: 'right', render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'post', label: postLabel, align: 'right', render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'prevspost', label: 'Pre vs Post Δ', align: 'right', delta: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'lyPrevspost', label: 'LY Pre vs Post Δ', align: 'right', delta: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'growthPct', label: 'Pre vs Post %', align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'lyGrowthPct', label: 'LY Growth%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ];
}

function buildYoyColumns(spec) {
  const lyLabel = spec.dailyAvg ? 'LY Post (avg/day)' : 'LY Post';
  const postLabel = spec.dailyAvg ? 'Post (avg/day)' : 'Post';
  return [
    { key: 'slot', label: 'Slot', sortable: false, labelCol: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'postLY', label: lyLabel, align: 'right', render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'post', label: postLabel, align: 'right', render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'yoy', label: 'YoY Δ', align: 'right', delta: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'yoyPct', label: 'YoY %', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ];
}

function buildPostColumns(spec) {
  const label = spec.dailyAvg ? 'Selected period (avg/day)' : 'Selected period';
  return [
    { key: 'slot', label: 'Slot', sortable: false, labelCol: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'post', label, align: 'right', render: (v) => renderSlotValue(spec.valueKind, v) },
  ];
}

export default function SlotsScreen() {
  const { ddFinancial, ueFinancial, ddSales } = useDataStore();
  const config = useConfigStore();
  const dateAnalysisMode = useConfigStore((s) => s.dateAnalysisMode);
  const {
    ddPreStart,
    ddPreEnd,
    ddPostStart,
    ddPostEnd,
    ddExcludedDates,
    uePreStart,
    uePreEnd,
    uePostStart,
    uePostEnd,
    ueExcludedDates,
  } = config;

  const isSingleMode = dateAnalysisMode === 'singleRange'
    || dateAnalysisMode === 'singleWeek'
    || dateAnalysisMode === 'singleMonth'
    || dateAnalysisMode === 'singleQuarter'
    || dateAnalysisMode === 'singleYear';

  const salesByOrder = useMemo(() => normalizeDdSalesByOrder(ddSales?.byOrder), [ddSales?.byOrder]);

  const salesOrderAnalysis = useMemo(() => {
    if (!salesByOrder.length || !ddPreStart || !ddPreEnd || !ddPostStart || !ddPostEnd) return null;
    return buildSlotSalesOrderAnalysis(salesByOrder, {
      preStart: ddPreStart,
      preEnd: ddPreEnd,
      postStart: ddPostStart,
      postEnd: ddPostEnd,
      excludedDates: ddExcludedDates,
    });
  }, [
    salesByOrder,
    ddPreStart,
    ddPreEnd,
    ddPostStart,
    ddPostEnd,
    ddExcludedDates,
  ]);

  const ueOrdersForSlots = useMemo(() => normalizeUeOrdersForSlotView(ueFinancial), [ueFinancial]);

  const ueSlotOrderAnalysis = useMemo(() => {
    if (!ueOrdersForSlots.length || !uePreStart || !uePreEnd || !uePostStart || !uePostEnd) return null;
    return buildSlotSalesOrderAnalysis(ueOrdersForSlots, {
      preStart: uePreStart,
      preEnd: uePreEnd,
      postStart: uePostStart,
      postEnd: uePostEnd,
      excludedDates: ueExcludedDates,
    });
  }, [
    ueOrdersForSlots,
    uePreStart,
    uePreEnd,
    uePostStart,
    uePostEnd,
    ueExcludedDates,
  ]);

  const analyses = useMemo(() => {
    const build = (platform, rawData) => {
      if (!rawData) return null;
      const isUe = platform === 'ue';
      const preStart = isUe ? uePreStart : ddPreStart;
      const preEnd = isUe ? uePreEnd : ddPreEnd;
      const postStart = isUe ? uePostStart : ddPostStart;
      const postEnd = isUe ? uePostEnd : ddPostEnd;
      const excludedDates = isUe ? ueExcludedDates : ddExcludedDates;
      if (!preStart || !preEnd || !postStart || !postEnd) return null;
      const analysis = buildSlotAnalysis(rawData, {
        preStart, preEnd, postStart, postEnd, excludedDates, platform,
      });
      const ticketBuckets = buildSlotTicketBucketAnalysis(rawData, {
        preStart, preEnd, postStart, postEnd, excludedDates, platform,
      });
      return { ...analysis, ticketBuckets };
    };

    return {
      dd: build('dd', ddFinancial),
      ue: build('ue', ueFinancial),
    };
  }, [
    ddFinancial,
    ueFinancial,
    ddPreStart,
    ddPreEnd,
    ddPostStart,
    ddPostEnd,
    ddExcludedDates,
    uePreStart,
    uePreEnd,
    uePostStart,
    uePostEnd,
    ueExcludedDates,
  ]);

  return (
    <div className="space-y-10">
      <p className="text-xs text-[var(--text-subtle)] leading-relaxed max-w-3xl">
        Slot metrics aggregate all orders in each day-part window across the selected period.
        Sales and Payouts are shown as <strong>daily averages</strong> (period total ÷ number of days).
        AOV is per order; Profitability is payouts ÷ sales.
        DoorDash dayparts use <strong>Order placed time</strong>; Uber Eats uses <strong>Order Accept Time</strong>.
      </p>

      {DATA_PLATFORM_SECTIONS.map(({ key, label }) => {
        const sa = analyses[key];
        const slotOrderAnalysis = key === 'dd' ? salesOrderAnalysis : key === 'ue' ? ueSlotOrderAnalysis : null;
        const showSlotOrder = !!slotOrderAnalysis;
        if (!sa && !showSlotOrder) return null;
        return (
          <div key={key} className="space-y-6">
            <div className="flex items-center gap-2">
              <PlatformLogo platform={key} size={18} />
              <h2 className="text-base font-semibold text-[var(--text)]">{label}</h2>
            </div>

            {sa && (
              <>
            {isSingleMode ? (
              <div className="space-y-4">
                {SLOT_DISPLAY_METRICS.map((spec) => (
                  <div key={`${key}-${spec.key}-post`} className="space-y-2">
                    <h3 className="text-sm font-semibold text-[var(--text)]">{spec.label}</h3>
                    <SplitDataTable
                      columns={buildPostColumns(spec)}
                      data={sa[`${spec.key}PrePost`] || []}
                      sortable={false}
                      dense
                    />
                  </div>
                ))}
              </div>
            ) : (
              <>
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-[var(--text)] border-b border-[var(--border)] pb-2">Pre vs Post</h3>
                  {SLOT_DISPLAY_METRICS.map((spec) => (
                    <div key={`${key}-${spec.key}-pvp`} className="space-y-2">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{spec.label}</h4>
                      <SplitDataTable
                        columns={buildPvpColumns(spec)}
                        data={sa[`${spec.key}PrePost`] || []}
                        sortable={false}
                        dense
                      />
                    </div>
                  ))}
                </div>

                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-[var(--text)] border-b border-[var(--border)] pb-2">Year over Year</h3>
                  {SLOT_DISPLAY_METRICS.map((spec) => (
                    <div key={`${key}-${spec.key}-yoy`} className="space-y-2">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{spec.label}</h4>
                      <SplitDataTable
                        columns={buildYoyColumns(spec)}
                        data={sa[`${spec.key}YoY`] || []}
                        sortable={false}
                        dense
                      />
                    </div>
                  ))}
                </div>
              </>
            )}

            {sa.ticketBuckets && (
              <div className="space-y-4 pt-2 border-t border-[var(--border)]">
                <SlotTicketMixSummary summary={sa.ticketBuckets.summary} platformLabel={label} />
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Order count by ticket size (per slot)</h3>
                  <SlotTicketBucketCharts bySlotCharts={sa.ticketBuckets.bySlotCharts} />
                </div>
              </div>
            )}
              </>
            )}

            {showSlotOrder && (
              <SlotSalesOrderSection
                analysis={slotOrderAnalysis}
                platformLabel={label}
                timeFieldLabel={key === 'ue' ? 'Order Accept Time' : 'Order placed time'}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
