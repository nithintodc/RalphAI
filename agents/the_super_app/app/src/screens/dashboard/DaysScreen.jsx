import SlotOrderDimensionSection from '../../components/slots/SlotOrderDimensionSection';
import { useSlotOrderAnalyses } from '../../hooks/useSlotOrderAnalyses';
import { DATA_PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';

export default function DaysScreen() {
  const analyses = useSlotOrderAnalyses();
  const hasAny = DATA_PLATFORM_SECTIONS.some(({ key }) => analyses[key]);

  if (!hasAny) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Upload SALES_BY_ORDER (DoorDash) or Uber Eats financials to see day-level tables.</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <p className="text-xs text-[var(--text-subtle)] leading-relaxed max-w-3xl">
        Seven weekday rows · customer mix, item counts, and DashPass split aggregated by calendar day.
      </p>

      {DATA_PLATFORM_SECTIONS.map(({ key, label }) => {
        const analysis = analyses[key];
        if (!analysis) return null;
        return (
          <div key={key} className="space-y-6">
            <div className="flex items-center gap-2">
              <PlatformLogo platform={key} size={18} />
              <h2 className="text-base font-semibold text-[var(--text)]">{label}</h2>
            </div>
            <SlotOrderDimensionSection
              analysis={analysis}
              platformLabel={label}
              dimension="day"
              timeFieldLabel={key === 'ue' ? 'Order Accept Time' : 'Order received local time (fallback: Timestamp local time)'}
            />
          </div>
        );
      })}
    </div>
  );
}
