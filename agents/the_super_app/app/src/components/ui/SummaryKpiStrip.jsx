import { useMemo } from 'react';
import KpiCard from './KpiCard';
import { buildSummaryKpis } from '../../lib/utils/summaryKpis';

export default function SummaryKpiStrip({ summary, sectionKey, storeTables, compact = false }) {
  const kpis = useMemo(
    () => buildSummaryKpis(summary, { sectionKey, storeTables }),
    [summary, sectionKey, storeTables],
  );
  if (!summary?.length) return null;

  const sixCols = kpis.length > 5;
  const colClass = compact
    ? (sixCols ? 'grid-cols-2 sm:grid-cols-3 xl:grid-cols-6' : 'grid-cols-2 sm:grid-cols-3 xl:grid-cols-5')
    : (sixCols ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-6' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5');

  return (
    <div className={`grid min-w-0 gap-2 sm:gap-3 ${colClass}`}>
      {kpis.map((k) => (
        <KpiCard
          key={k.id}
          label={k.label}
          value={k.value}
          format={k.format}
          pre={k.pre}
          post={k.post}
          rangeFormat={k.rangeFormat}
          delta={k.delta}
          yoyDelta={k.yoy}
          compact={compact}
        />
      ))}
    </div>
  );
}
