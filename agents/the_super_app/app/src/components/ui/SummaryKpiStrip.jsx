import { useMemo } from 'react';
import KpiCard from './KpiCard';
import { buildSummaryKpis } from '../../lib/utils/summaryKpis';

export default function SummaryKpiStrip({ summary, compact = false, hint = 'Post vs Pre' }) {
  const kpis = useMemo(() => buildSummaryKpis(summary), [summary]);
  if (!summary?.length) return null;

  return (
    <div className={`grid gap-2 ${compact ? 'grid-cols-2 sm:grid-cols-3 xl:grid-cols-5' : 'grid-cols-5 gap-4'}`}>
      {kpis.map((k) => (
        <KpiCard
          key={k.id}
          label={k.label}
          value={k.value}
          format={k.format}
          delta={k.delta}
          yoyDelta={k.yoy}
          hint={hint}
          compact={compact}
        />
      ))}
    </div>
  );
}
