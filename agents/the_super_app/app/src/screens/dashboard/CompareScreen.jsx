import { useDataStore } from '../../stores/dataStore';
import DataTable from '../../components/ui/DataTable';
import { fmt } from '../../lib/utils/formatters';
import { PLATFORM_SECTIONS } from '../../lib/platforms';

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
    { key: 'metric', label: 'Metric', sortable: false, render: (v) => METRIC_LABELS[v] || v },
    { key: 'pre', label: 'Pre', align: 'right', render: (v, row) => renderVal(row.metric)(v) },
    { key: 'post', label: 'Post', align: 'right', render: (v, row) => renderVal(row.metric)(v) },
    { key: 'prevspost', label: 'Pre vs Post', align: 'right', delta: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'lyPrevspost', label: 'LY Pre vs Post', align: 'right', delta: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'growthPct', label: 'Growth%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ] : [
    { key: 'metric', label: 'Metric', sortable: false, render: (v) => METRIC_LABELS[v] || v },
    { key: 'postLY', label: 'LY Post', align: 'right', render: (v, row) => renderVal(row.metric)(v) },
    { key: 'post', label: 'Post', align: 'right', render: (v, row) => renderVal(row.metric)(v) },
    { key: 'yoy', label: 'YoY', align: 'right', delta: true, render: (v, row) => renderVal(row.metric)(v) },
    { key: 'yoyPct', label: 'YoY%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ];

  return (
    <div>
      <h3 className="text-sm font-semibold text-[var(--text)] mb-2">{title}</h3>
      <DataTable columns={columns} data={data} sortable={false} />
    </div>
  );
}

export default function CompareScreen() {
  const { summaryTables } = useDataStore();
  const sections = PLATFORM_SECTIONS
    .map(section => ({ ...section, summary: summaryTables?.[section.key] || [] }))
    .filter(section => section.summary.length);

  return (
    <div className="space-y-6">
      {sections.map(section => (
        <div key={section.key} className="space-y-4">
          <div className="flex items-center gap-2">
            {section.key === 'dd' && <span className="platform-dot dd" />}
            {section.key === 'ue' && <span className="platform-dot ue" />}
            <h2 className="text-base font-semibold text-[var(--text)]">{section.label}</h2>
          </div>
          <SummaryTable title={`${section.label} — Pre vs Post`} data={section.summary} type="prepost" />
          <SummaryTable title={`${section.label} — Year over Year`} data={section.summary} type="yoy" />
        </div>
      ))}
    </div>
  );
}
