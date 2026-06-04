import DataTable from '../../components/ui/DataTable';
import SummaryKpiStrip from '../../components/ui/SummaryKpiStrip';
import { useApp2Pack } from '../../hooks/useApp2Pack';
import { columnsFromObjects } from '../../lib/engine/app2Bucketing';

function SectionTitle({ children }) {
  return (
    <h3 className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider mt-6 mb-2">
      {children}
    </h3>
  );
}

export default function App2BucketingScreen() {
  const { pack, combinedSummary } = useApp2Pack();

  return (
    <div className="space-y-6">
      {combinedSummary.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">Combined summary metrics</h2>
          <SummaryKpiStrip summary={combinedSummary} />
        </section>
      )}

      {pack?.empty ? (
        <div className="card">
          <p className="text-sm text-[var(--text-muted)] leading-relaxed">
            Load DoorDash financial data and set Pre/Post periods in the top bar. App 2.0 rollups use the same hour
            bands and GC buckets as the legacy Python export.
          </p>
        </div>
      ) : (
        <section className="space-y-2">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">AITF bucketing</h2>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5 leading-relaxed">
              Store-level Sales, Payouts, AOV, and Mkt Spend by period, plus slot bridges and day-part × GC tables
              aligned with <code className="text-[10px]">App2.0/export_functions.py</code>.
            </p>
          </div>

          <SectionTitle>By store × period (Sales · Payouts · AOV · Mkt Spend)</SectionTitle>
          <DataTable columns={columnsFromObjects(pack.byPeriod)} data={pack.byPeriod} maxHeight="360px" />

          <SectionTitle>By slot × period</SectionTitle>
          <DataTable columns={columnsFromObjects(pack.bySlotPeriod)} data={pack.bySlotPeriod} maxHeight="360px" />

          <SectionTitle>Daypart GC — Post</SectionTitle>
          <DataTable columns={columnsFromObjects(pack.daypartGcPost)} data={pack.daypartGcPost} maxHeight="280px" />

          <SectionTitle>Daypart GC — Delta (Post − Pre)</SectionTitle>
          <DataTable columns={columnsFromObjects(pack.daypartGcDelta)} data={pack.daypartGcDelta} maxHeight="280px" />
        </section>
      )}
    </div>
  );
}
