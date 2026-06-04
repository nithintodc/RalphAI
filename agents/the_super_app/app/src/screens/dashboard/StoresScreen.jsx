import { useMemo, useState } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import { fmt } from '../../lib/utils/formatters';
import { PLATFORM_SECTIONS } from '../../lib/platforms';

const METRIC_SPECS = [
  { id: 'sales', label: 'Sales', preKey: 'pre_sales', postKey: 'post_sales', postLyKey: 'postLY_sales', deltaKey: 'sales_prevspost', yoyDeltaKey: 'sales_yoy', deltaPctKey: 'sales_growth_pct', yoyPctKey: 'sales_yoy_pct', render: (v) => fmt.usd(v || 0) },
  { id: 'payouts', label: 'Payouts', preKey: 'pre_payouts', postKey: 'post_payouts', postLyKey: 'postLY_payouts', deltaKey: 'payouts_prevspost', yoyDeltaKey: 'payouts_yoy', deltaPctKey: 'payouts_growth_pct', yoyPctKey: 'payouts_yoy_pct', render: (v) => fmt.usd(v || 0) },
  { id: 'orders', label: 'Orders', preKey: 'pre_orders', postKey: 'post_orders', postLyKey: 'postLY_orders', deltaKey: 'orders_prevspost', yoyDeltaKey: 'orders_yoy', deltaPctKey: 'orders_growth_pct', yoyPctKey: 'orders_yoy_pct', render: (v) => fmt.int(v || 0) },
  { id: 'aov', label: 'AOV', preKey: 'pre_aov', postKey: 'post_aov', postLyKey: 'postLY_aov', deltaKey: 'aov_prevspost', yoyDeltaKey: 'aov_yoy', deltaPctKey: 'aov_growth_pct', yoyPctKey: 'aov_yoy_pct', render: (v) => fmt.usd2(v || 0) },
  { id: 'mktSpend', label: 'Marketing Spend', preKey: 'pre_mktSpend', postKey: 'post_mktSpend', postLyKey: 'postLY_mktSpend', deltaKey: 'mktSpend_prevspost', yoyDeltaKey: 'mktSpend_yoy', deltaPctKey: 'mktSpend_growth_pct', yoyPctKey: 'mktSpend_yoy_pct', render: (v) => fmt.usd(v || 0) },
  { id: 'avg_payout', label: 'Avg Payout / Order', preKey: 'pre_avg_payout', postKey: 'post_avg_payout', postLyKey: 'postLY_avg_payout', deltaKey: 'avg_payout_prevspost', yoyDeltaKey: 'avg_payout_yoy', deltaPctKey: 'avg_payout_growth_pct', yoyPctKey: 'avg_payout_yoy_pct', render: (v) => fmt.usd2(v || 0) },
  { id: 'profitability', label: 'Profitability %', preKey: 'pre_profitability', postKey: 'post_profitability', postLyKey: 'postLY_profitability', deltaKey: 'prof_prevspost', yoyDeltaKey: 'prof_yoy', deltaPctKey: 'prof_growth_pct', yoyPctKey: 'prof_yoy_pct', render: (v) => fmt.pct(v || 0) },
];

export default function StoresScreen() {
  const { storeTables } = useDataStore();
  const { setActiveTab, setSelectedStore } = useUiStore();
  const dateAnalysisMode = useConfigStore((s) => s.dateAnalysisMode);
  const [compareView, setCompareView] = useState('pvp');

  const sections = useMemo(() => PLATFORM_SECTIONS
    .map(section => ({
      ...section,
      stores: storeTables?.[section.key] || [],
    }))
    .filter(section => section.stores.length), [storeTables]);

  const isSingleMode = dateAnalysisMode === 'singleRange'
    || dateAnalysisMode === 'singleWeek'
    || dateAnalysisMode === 'singleMonth'
    || dateAnalysisMode === 'singleQuarter'
    || dateAnalysisMode === 'singleYear';
  const tableMode = isSingleMode ? 'post' : compareView;

  const buildColumns = (spec) => {
    const base = [{ key: 'storeId', label: 'Store ID', sortable: true, render: (v) => <span className="font-medium">{v}</span> }];
    if (tableMode === 'post') {
      return [
        ...base,
        { key: spec.postKey, label: 'Selected period', align: 'right', sortable: true, render: spec.render },
      ];
    }
    if (tableMode === 'yoy') {
      return [
        ...base,
        { key: spec.postLyKey, label: 'LY Post', align: 'right', sortable: true, render: spec.render },
        { key: spec.postKey, label: 'Post', align: 'right', sortable: true, render: spec.render },
        { key: spec.yoyDeltaKey, label: 'YoY Δ', align: 'right', sortable: true, delta: true, render: spec.render },
        { key: spec.yoyPctKey, label: 'YoY %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
      ];
    }
    return [
      ...base,
      { key: spec.preKey, label: 'Pre', align: 'right', sortable: true, render: spec.render },
      { key: spec.postKey, label: 'Post', align: 'right', sortable: true, render: spec.render },
      { key: spec.deltaKey, label: 'Pre vs Post Δ', align: 'right', sortable: true, delta: true, render: spec.render },
      { key: spec.deltaPctKey, label: 'Pre vs Post %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
    ];
  };

  const handleClick = (row) => {
    setSelectedStore(row.storeId, row._platform);
    setActiveTab('storeDetail');
  };

  return (
    <div className="space-y-8">
      {!isSingleMode && (
        <div className="inline-flex rounded-lg border border-[var(--border)] p-0.5 bg-[var(--surface-2)]">
          <button
            type="button"
            onClick={() => setCompareView('pvp')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer ${compareView === 'pvp' ? 'bg-[var(--surface)] text-[var(--text)]' : 'text-[var(--text-muted)]'}`}
          >
            Pre vs Post
          </button>
          <button
            type="button"
            onClick={() => setCompareView('yoy')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer ${compareView === 'yoy' ? 'bg-[var(--surface)] text-[var(--text)]' : 'text-[var(--text-muted)]'}`}
          >
            YoY
          </button>
        </div>
      )}
      {sections.map(section => (
        <div key={section.key} className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {section.key === 'dd' && <span className="platform-dot dd" />}
              {section.key === 'ue' && <span className="platform-dot ue" />}
              <h2 className="text-base font-semibold text-[var(--text)]">{section.label}</h2>
            </div>
            <p className="text-sm text-[var(--text-muted)]">{section.stores.length} stores</p>
          </div>
          <div className="space-y-4">
            {METRIC_SPECS.map((spec) => (
              <div key={`${section.key}-${spec.id}`} className="space-y-2">
                <h3 className="text-sm font-semibold text-[var(--text)]">{spec.label}</h3>
                <DataTable
                  columns={buildColumns(spec)}
                  data={section.stores.map(row => ({ ...row, _platform: section.key }))}
                  onRowClick={handleClick}
                  maxHeight="320px"
                />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
