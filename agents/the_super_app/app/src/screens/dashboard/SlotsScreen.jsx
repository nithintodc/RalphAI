import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import {
  buildSlotAnalysis,
  buildHeatmapData,
  buildSlotTicketBucketAnalysis,
  SLOT_NAMES,
  DAY_NAMES,
  SLOT_METRIC_TABLES,
} from '../../lib/engine/slots';
import { fmt } from '../../lib/utils/formatters';
import { DATA_PLATFORM_SECTIONS } from '../../lib/platforms';

function Heatmap({ data }) {
  if (!data || !data.length) return null;
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--text)] mb-3">Sales Heatmap (Post Period)</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="py-2 px-3 text-left text-[var(--text-muted)]" />
              {SLOT_NAMES.map(s => <th key={s} className="py-2 px-3 text-center text-[var(--text-muted)]">{s}</th>)}
            </tr>
          </thead>
          <tbody>
            {DAY_NAMES.map((day, i) => (
              <tr key={day}>
                <td className="py-2 px-3 font-medium text-[var(--text)]">{day}</td>
                {data[i]?.map((val, j) => {
                  const opacity = Math.max(0.05, val);
                  return (
                    <td key={j} className="py-2 px-3 text-center">
                      <div
                        className="w-full h-8 rounded-md flex items-center justify-center text-[10px] font-medium"
                        style={{ background: `rgba(5, 150, 105, ${opacity})`, color: opacity > 0.5 ? 'white' : 'var(--text)' }}
                      >
                        {(val * 100).toFixed(0)}%
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SlotTicketMixSummary({ summary, platformLabel }) {
  const { towardsLesserGcBaskets, towardsHigherTicket, roughlyUnchanged } = summary;
  const fmt = (arr) => (arr.length ? arr.join(', ') : '—');
  return (
    <div className="card border-l-[3px] border-l-[var(--accent)]">
      <h3 className="text-sm font-semibold text-[var(--text)] mb-2">
        Ticket mix by slot — summary ({platformLabel})
      </h3>
      <p className="text-[11px] text-[var(--text-subtle)] mb-3 leading-relaxed">
        Same ticket-size buckets as Order Buckets. Within each time-of-day slot we compare how <strong>Post</strong>{' '}
        order share moves across buckets vs <strong>Pre</strong>. When Post gains in smaller-ticket buckets and loses in
        larger ones, we label that slot as shifting toward <strong>lower GC / smaller tickets</strong>; the opposite is{' '}
        <strong>higher ticket / mix moving upscale</strong>.
      </p>
      <ul className="text-xs space-y-2.5 text-[var(--text-muted)] leading-snug">
        <li>
          <span className="font-semibold text-[var(--text)]">Lower ticket / lesser GC basket shift: </span>
          {fmt(towardsLesserGcBaskets)}
        </li>
        <li>
          <span className="font-semibold text-[var(--text)]">Higher ticket / going forward: </span>
          {fmt(towardsHigherTicket)}
        </li>
        <li>
          <span className="font-semibold text-[var(--text)]">Roughly unchanged / low volume: </span>
          {fmt(roughlyUnchanged)}
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

export default function SlotsScreen() {
  const { ddFinancial, ueFinancial } = useDataStore();
  const config = useConfigStore();
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
      const heatmap = buildHeatmapData(rawData, {
        postStart, postEnd, excludedDates, platform,
      });
      const ticketBuckets = buildSlotTicketBucketAnalysis(rawData, {
        preStart, preEnd, postStart, postEnd, excludedDates, platform,
      });
      return { ...analysis, heatmap, ticketBuckets };
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

  const renderSlotValue = (valueKind, v) => {
    if (v == null || Number.isNaN(v)) return '—';
    if (valueKind === 'int') return fmt.int(v);
    if (valueKind === 'usd2') return fmt.usd2(v);
    return fmt.usd(v);
  };

  const slotColumns = (type, valueKind) => [
    { key: 'slot', label: 'Slot', sortable: false },
    {
      key: type === 'yoy' ? 'postLY' : 'pre',
      label: type === 'yoy' ? 'LY Post' : 'Pre',
      align: 'right',
      render: (v) => renderSlotValue(valueKind, v),
    },
    { key: 'post', label: 'Post', align: 'right', render: (v) => renderSlotValue(valueKind, v) },
    {
      key: type === 'yoy' ? 'yoy' : 'prevspost',
      label: type === 'yoy' ? 'YoY' : 'Pre vs Post',
      align: 'right',
      delta: true,
      render: (v) => renderSlotValue(valueKind, v),
    },
    {
      key: type === 'yoy' ? 'yoyPct' : 'growthPct',
      label: type === 'yoy' ? 'YoY%' : 'Growth%',
      align: 'right',
      delta: true,
      render: (v) => fmt.delta(v),
    },
  ];

  return (
    <div className="space-y-8">
      {DATA_PLATFORM_SECTIONS.map(({ key, label }) => {
        const sa = analyses[key];
        if (!sa) return null;
        return (
          <div key={key} className="space-y-6">
            <div className="flex items-center gap-2">
              <span className={`platform-dot ${key}`} />
              <h2 className="text-base font-semibold text-[var(--text)]">{label}</h2>
            </div>

            <Heatmap data={sa.heatmap} />

            {sa.ticketBuckets && (
              <div className="space-y-4">
                <SlotTicketMixSummary summary={sa.ticketBuckets.summary} platformLabel={label} />
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Order count by ticket size (per slot)</h3>
                  <SlotTicketBucketCharts bySlotCharts={sa.ticketBuckets.bySlotCharts} />
                </div>
              </div>
            )}

            {SLOT_METRIC_TABLES.map(({ key, title, valueKind }) => (
              <div key={key} className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-2">{title} — Pre vs Post</h3>
                  <DataTable
                    columns={slotColumns('prepost', valueKind)}
                    data={sa[`${key}PrePost`] || []}
                    sortable={false}
                  />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-2">{title} — YoY</h3>
                  <DataTable
                    columns={slotColumns('yoy', valueKind)}
                    data={sa[`${key}YoY`] || []}
                    sortable={false}
                  />
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
