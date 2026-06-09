import { useDataStore } from '../../stores/dataStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import RankedBarChart from '../../components/charts/RankedBarChart';
import { fmt } from '../../lib/utils/formatters';
import { PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';

const METRIC_LABELS = {
  sales: 'Sales', payouts: 'Payouts', orders: 'Orders',
  profitability: 'Profitability', aov: 'Average Check (AOV)',
};

function renderVal(metric) {
  return (v) => {
    if (v == null) return '-';
    if (metric === 'profitability') return fmt.pct(v);
    if (metric === 'aov') return fmt.usd2(v);
    if (metric === 'orders') return fmt.int(v);
    return fmt.usd(v);
  };
}

function SummaryTable({ title, data, type = 'prepost' }) {
  if (!data || !data.length) return null;

  const columns = type === 'prepost' ? [
    { key: 'metric', label: 'Metric', sortable: false, labelCol: true, wrap: true, render: (v) => METRIC_LABELS[v] || v },
    { key: 'pre', label: 'Pre', wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'post', label: 'Post', wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'prevspost', label: 'Pre vs Post', delta: true, wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'lyPrevspost', label: 'LY Pre vs Post', delta: true, wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'growthPct', label: 'Growth%', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'lyGrowthPct', label: 'LY Growth%', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ] : [
    { key: 'metric', label: 'Metric', sortable: false, labelCol: true, wrap: true, render: (v) => METRIC_LABELS[v] || v },
    { key: 'postLY', label: 'LY Post', wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'post', label: 'Post', wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'yoy', label: 'YoY', delta: true, wrap: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'yoyPct', label: 'YoY%', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];

  return (
    <div>
      <h3 className="text-sm font-semibold text-[var(--text)] mb-2">{title}</h3>
      <SplitDataTable columns={columns} data={data} sortable={false} layout="full" dense />
    </div>
  );
}

/** Growth-rate bars per metric — Pre→Post and YoY side by side. */
function GrowthBars({ summary }) {
  const pvp = summary
    .filter((r) => r.growthPct != null)
    .map((r) => ({ label: METRIC_LABELS[r.metric] || r.metric, value: r.growthPct }));
  const yoy = summary
    .filter((r) => r.yoyPct != null)
    .map((r) => ({ label: METRIC_LABELS[r.metric] || r.metric, value: r.yoyPct }));
  if (!pvp.length && !yoy.length) return null;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {pvp.length > 0 && (
        <RankedBarChart
          title="Pre → Post growth by metric"
          subtitle="% change from the Pre to the Post period. Green = up, red = down."
          data={pvp}
          valueFormatter={fmt.delta}
        />
      )}
      {yoy.length > 0 && (
        <RankedBarChart
          title="Year-over-year growth by metric"
          subtitle="Post period vs the same period last year."
          data={yoy}
          valueFormatter={fmt.delta}
        />
      )}
    </div>
  );
}

export default function CompareScreen() {
  const { summaryTables } = useDataStore();
  const sections = PLATFORM_SECTIONS
    .map(section => ({ ...section, summary: summaryTables?.[section.key] || [] }))
    .filter(section => section.summary.length);

  return (
    <div className="space-y-6 max-w-full min-w-0 overflow-x-hidden">
      {sections.map(section => (
        <div key={section.key} className="space-y-4">
          <div className="flex items-center gap-2">
            {section.key === 'dd' && <PlatformLogo platform="dd" size={18} />}
            {section.key === 'ue' && <PlatformLogo platform="ue" size={18} />}
            <h2 className="text-base font-semibold text-[var(--text)]">{section.label}</h2>
          </div>
          <GrowthBars summary={section.summary} />
          <SummaryTable title={`${section.label} — Pre vs Post`} data={section.summary} type="prepost" />
          <SummaryTable title={`${section.label} — Year over Year`} data={section.summary} type="yoy" />
        </div>
      ))}
    </div>
  );
}
