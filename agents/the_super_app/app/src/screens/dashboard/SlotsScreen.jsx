import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import BarShareLabels from '../../components/charts/BarShareLabels';
import { addBarSharePct } from '../../lib/utils/barChartShare';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { SLOT_CORE_METRICS } from '../../lib/engine/slots';
import { buildSlotPvpColumns, buildSlotYoyColumns } from '../../lib/slots/slotTableColumns';
import { useSlotFinancialAnalyses } from '../../hooks/useSlotFinancialAnalyses';
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
        Order share by ticket-size bucket within each day-part slot · Pre vs Post.
      </p>
      <ul className="text-xs space-y-2.5 text-[var(--text-muted)] leading-snug">
        <li>
          <span className="font-semibold text-[var(--text)]">Lower ticket shift: </span>
          {fmtList(towardsLesserGcBaskets)}
        </li>
        <li>
          <span className="font-semibold text-[var(--text)]">Higher ticket shift: </span>
          {fmtList(towardsHigherTicket)}
        </li>
        <li>
          <span className="font-semibold text-[var(--text)]">Roughly unchanged: </span>
          {fmtList(roughlyUnchanged)}
        </li>
      </ul>
    </div>
  );
}

function SlotTicketBucketCharts({ bySlotCharts }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {bySlotCharts.map(({ slot, data }) => {
        const chartData = addBarSharePct(data, ['pre_orders', 'post_orders']);
        return (
          <div key={slot} className="card">
            <h4 className="text-xs font-semibold text-[var(--text)] mb-3">{slot} — ticket-size mix</h4>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} barGap={1} margin={{ top: 18, bottom: 36, left: 0, right: 4 }}>
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
                <Bar dataKey="pre_orders" name="Pre" fill="var(--border-strong)" radius={[2, 2, 0, 0]}>
                  <BarShareLabels dataKey="pre_orders" fill="var(--text-subtle)" />
                </Bar>
                <Bar dataKey="post_orders" name="Post" fill="var(--accent)" radius={[2, 2, 0, 0]}>
                  <BarShareLabels dataKey="post_orders" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        );
      })}
    </div>
  );
}

export default function SlotsScreen() {
  const analyses = useSlotFinancialAnalyses();

  const hasAny = DATA_PLATFORM_SECTIONS.some(({ key }) => analyses[key]);

  if (!hasAny) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Upload financial data and set Pre + Post dates to see slot growth tables.</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <p className="text-xs text-[var(--text-subtle)] leading-relaxed max-w-3xl">
        Six day-part slots (Overnight → Late Night). Sales and Payouts are <strong>daily averages</strong>.
        AOV and Orders are period totals per slot. Ticket-size charts show mix shift Pre vs Post.
      </p>

      {DATA_PLATFORM_SECTIONS.map(({ key, label }) => {
        const sa = analyses[key];
        if (!sa) return null;
        return (
          <div key={key} className="space-y-6">
            <div className="flex items-center gap-2">
              <PlatformLogo platform={key} size={18} />
              <h2 className="text-base font-semibold text-[var(--text)]">{label}</h2>
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-[var(--text)] border-b border-[var(--border)] pb-2">
                Pre vs Post growth
              </h3>
              {SLOT_CORE_METRICS.map((spec) => (
                <div key={`${key}-${spec.key}-pvp`} className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{spec.label}</h4>
                  <SplitDataTable
                    columns={buildSlotPvpColumns(spec)}
                    data={sa[`${spec.key}PrePost`] || []}
                    sortable={false}
                    dense
                  />
                </div>
              ))}
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-[var(--text)] border-b border-[var(--border)] pb-2">
                Year over year growth
              </h3>
              {SLOT_CORE_METRICS.map((spec) => (
                <div key={`${key}-${spec.key}-yoy`} className="space-y-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{spec.label}</h4>
                  <SplitDataTable
                    columns={buildSlotYoyColumns(spec)}
                    data={sa[`${spec.key}YoY`] || []}
                    sortable={false}
                    dense
                  />
                </div>
              ))}
            </div>

            {sa.ticketBuckets && (
              <div className="space-y-4 pt-2 border-t border-[var(--border)]">
                <SlotTicketMixSummary summary={sa.ticketBuckets.summary} platformLabel={label} />
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Ticket-size mix by slot</h3>
                  <SlotTicketBucketCharts bySlotCharts={sa.ticketBuckets.bySlotCharts} />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
