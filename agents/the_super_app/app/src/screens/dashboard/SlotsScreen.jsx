import GroupedBarChart from '../../components/charts/GroupedBarChart';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { SLOT_CORE_METRICS, lyBlankDueToExclusions, hasDdFinancialForSlots } from '../../lib/engine/slots';
import { buildSlotPvpColumns, buildSlotYoyColumns } from '../../lib/slots/slotTableColumns';
import { useSlotFinancialAnalyses } from '../../hooks/useSlotFinancialAnalyses';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
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
  const ddFinancial = useDataStore((s) => s.ddFinancial);
  const ueFinancial = useDataStore((s) => s.ueFinancial);
  const config = useConfigStore();
  const analyses = useSlotFinancialAnalyses();

  const ueLyBlockedByExclusions = lyBlankDueToExclusions(
    ueFinancial,
    config.uePreStart,
    config.uePreEnd,
    config.uePostStart,
    config.uePostEnd,
    config.ueExcludedDates,
  );
  const ddLyBlockedByExclusions = lyBlankDueToExclusions(
    ddFinancial,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
  );

  const hasAny = DATA_PLATFORM_SECTIONS.some(({ key }) => analyses[key]);
  const ddFinancialMissingTimes = !!ddFinancial?.length && !hasDdFinancialForSlots(ddFinancial);

  if (!hasAny) {
    return (
      <div className="card text-center py-12 space-y-2">
        <p className="text-[var(--text-muted)]">
          Slots are built from <strong>financial data</strong> (DD: order received time · UE: order accept time).
          Upload a financial export and set Pre + Post dates.
        </p>
        {ddFinancialMissingTimes && (
          <p className="text-xs text-[var(--text-subtle)]">
            Your DoorDash financial file has no usable order-received times. Upload the original portal zip —
            CSVs opened and re-saved in Excel lose the time-of-day component.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <p className="text-xs text-[var(--text-subtle)] leading-relaxed max-w-3xl">
        Six day-part slots (Overnight → Late Night). DoorDash slots use <strong>order received time</strong> from the
        financial export; Uber Eats uses order accept time. Sales, orders, payouts, and AOV are period totals per slot.
        Ticket-size charts show mix shift Pre vs Post.
      </p>

      {ddFinancialMissingTimes && (
        <div className="card border-l-[3px] border-l-amber-500/80 bg-amber-500/5 text-xs text-[var(--text-muted)] leading-relaxed max-w-3xl">
          <strong className="text-[var(--text)]">DoorDash slot tables unavailable.</strong>{' '}
          The uploaded financial file has no usable order-received times (this happens when the CSV was opened and
          re-saved in Excel/WPS, which strips the hour). Re-upload the original zip from the DoorDash portal.
        </div>
      )}

      {ddLyBlockedByExclusions && (
        <div className="card border-l-[3px] border-l-amber-500/80 bg-amber-500/5 text-xs text-[var(--text-muted)] leading-relaxed max-w-3xl">
          <strong className="text-[var(--text)]">DoorDash last-year columns are hidden by excluded dates.</strong>{' '}
          Your excluded-date list is removing all rows from the prior-year Pre/Post windows. Clear excluded dates on
          the Config screen, or turn off &quot;Sync date exclusions&quot; if Uber Eats should keep last year.
        </div>
      )}

      {analyses.dd && analyses.dd.lyCoverage && !analyses.dd.lyCoverage.hasAny && !ddLyBlockedByExclusions && (
        <div className="card border-l-[3px] border-l-amber-500/80 bg-amber-500/5 text-xs text-[var(--text-muted)] leading-relaxed max-w-3xl">
          <strong className="text-[var(--text)]">DoorDash last-year columns are empty.</strong>{' '}
          LY Pre vs Post and YoY need financial rows from the same calendar months one year earlier
          (e.g. Apr–May 2025 when comparing Apr–May 2026). Re-export financials with a longer date range if needed.
        </div>
      )}

      {ueLyBlockedByExclusions && (
        <div className="card border-l-[3px] border-l-amber-500/80 bg-amber-500/5 text-xs text-[var(--text-muted)] leading-relaxed max-w-3xl">
          <strong className="text-[var(--text)]">Uber Eats last-year columns are hidden by excluded dates.</strong>{' '}
          {config.ueExcludedDates.length} excluded date{config.ueExcludedDates.length === 1 ? '' : 's'} remove all
          rows from Apr/May 2025 (the prior-year windows for your current periods). Clear UE excluded dates on the
          Config screen, or disable &quot;Sync date exclusions&quot; if those exclusions should apply to DoorDash only.
        </div>
      )}

      {analyses.ue && analyses.ue.lyCoverage && !analyses.ue.lyCoverage.hasAny && !ueLyBlockedByExclusions && (
        <div className="card border-l-[3px] border-l-amber-500/80 bg-amber-500/5 text-xs text-[var(--text-muted)] leading-relaxed max-w-3xl">
          <strong className="text-[var(--text)]">Uber Eats last-year columns are empty.</strong>{' '}
          UE slots need financial rows from the same calendar months one year earlier in your uploaded CSV
          (e.g. Apr–May 2025 when comparing Apr–May 2026). Re-upload the combined export and confirm the Upload
          screen shows both years (this file should show ~65,972 rows with 2025 and 2026 counts).
        </div>
      )}

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
