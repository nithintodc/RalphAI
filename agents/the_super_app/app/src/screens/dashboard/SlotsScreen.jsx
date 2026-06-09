import GroupedBarChart from '../../components/charts/GroupedBarChart';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { SLOT_CORE_METRICS } from '../../lib/engine/slots';
import { buildSlotPvpColumns, buildSlotYoyColumns } from '../../lib/slots/slotTableColumns';
import { useSlotFinancialAnalyses } from '../../hooks/useSlotFinancialAnalyses';
import { DATA_PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';
import { formatByKind } from '../../lib/utils/formatters';
import { SERIES } from '../../components/charts/chartTheme';

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

/** Pre vs Post comparison of each core metric, by day-part slot — at-a-glance view. */
function SlotMetricCharts({ sa }) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {SLOT_CORE_METRICS.map((spec) => {
        const rows = sa[`${spec.key}PrePost`] || [];
        if (!rows.length) return null;
        const fmtVal = (v) => formatByKind(spec.valueKind, v);
        const title = `${spec.label} — Pre vs Post by slot${spec.dailyAvg ? ' (avg/day)' : ''}`;
        return (
          <GroupedBarChart
            key={`${spec.key}-chart`}
            title={title}
            data={rows}
            xKey="slot"
            height={260}
            valueFormatter={fmtVal}
            series={[
              { key: 'pre', name: 'Pre', color: SERIES.pre },
              { key: 'post', name: 'Post', color: SERIES.post },
            ]}
          />
        );
      })}
    </div>
  );
}

function SlotTicketBucketCharts({ bySlotCharts }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {bySlotCharts.map(({ slot, data }) => (
        <GroupedBarChart
          key={slot}
          title={`${slot} — ticket-size mix`}
          data={data}
          xKey="range"
          height={300}
          angle={-35}
          smallTicks
          shareLabels
          labelSeriesKeys={['post_orders']}
          valueFormatter={(v) => formatByKind('int', v)}
          series={[
            { key: 'pre_orders', name: 'Pre', color: SERIES.pre, labelFill: 'var(--text-subtle)' },
            { key: 'post_orders', name: 'Post', color: SERIES.post },
          ]}
        />
      ))}
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
                Pre vs Post by slot
              </h3>
              <SlotMetricCharts sa={sa} />
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
                    layout="full"
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
                    layout="full"
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
