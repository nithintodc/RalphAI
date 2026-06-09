import { useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import { useConfigStore } from '../../stores/configStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { fmt } from '../../lib/utils/formatters';
import { PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';
import { isSinglePeriodMode } from '../../lib/utils/periodMode';
import RankedBarChart from '../../components/charts/RankedBarChart';
import { SERIES } from '../../components/charts/chartTheme';

/** Ranked store charts above the tables. */
function StoresCharts({ stores, isSingleMode }) {
  if (!stores.length) return null;
  if (isSingleMode) {
    const sales = stores.map((s) => ({ label: s.storeId, value: s.post_sales || 0 }));
    return (
      <RankedBarChart
        title="Sales by store — selected period"
        data={sales}
        topN={25}
        color={SERIES.post}
        valueFormatter={fmt.usdK}
      />
    );
  }
  const growth = stores
    .filter((s) => s.sales_growth_pct != null)
    .map((s) => ({ label: s.storeId, value: s.sales_growth_pct }));
  const salesPost = stores.map((s) => ({ label: s.storeId, value: s.post_sales || 0 }));
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <RankedBarChart
        title="Sales growth by store (Pre → Post)"
        subtitle="% change in sales. Green = growing stores, red = declining."
        data={growth}
        topN={25}
        valueFormatter={fmt.delta}
      />
      <RankedBarChart
        title="Sales by store — Post period"
        subtitle="Where the volume sits today."
        data={salesPost}
        topN={25}
        color={SERIES.post}
        valueFormatter={fmt.usdK}
      />
    </div>
  );
}

const METRIC_SPECS = [
  { id: 'sales', label: 'Sales', preKey: 'pre_sales', postKey: 'post_sales', postLyKey: 'postLY_sales', deltaKey: 'sales_prevspost', lyDeltaKey: 'sales_ly_prevspost', yoyDeltaKey: 'sales_yoy', deltaPctKey: 'sales_growth_pct', lyDeltaPctKey: 'sales_ly_growth_pct', yoyPctKey: 'sales_yoy_pct', render: (v) => fmt.usd(v || 0) },
  { id: 'payouts', label: 'Payouts', preKey: 'pre_payouts', postKey: 'post_payouts', postLyKey: 'postLY_payouts', deltaKey: 'payouts_prevspost', lyDeltaKey: 'payouts_ly_prevspost', yoyDeltaKey: 'payouts_yoy', deltaPctKey: 'payouts_growth_pct', lyDeltaPctKey: 'payouts_ly_growth_pct', yoyPctKey: 'payouts_yoy_pct', render: (v) => fmt.usd(v || 0) },
  { id: 'orders', label: 'Orders', preKey: 'pre_orders', postKey: 'post_orders', postLyKey: 'postLY_orders', deltaKey: 'orders_prevspost', lyDeltaKey: 'orders_ly_prevspost', yoyDeltaKey: 'orders_yoy', deltaPctKey: 'orders_growth_pct', lyDeltaPctKey: 'orders_ly_growth_pct', yoyPctKey: 'orders_yoy_pct', render: (v) => fmt.int(v || 0) },
  { id: 'aov', label: 'AOV', preKey: 'pre_aov', postKey: 'post_aov', postLyKey: 'postLY_aov', deltaKey: 'aov_prevspost', lyDeltaKey: 'aov_ly_prevspost', yoyDeltaKey: 'aov_yoy', deltaPctKey: 'aov_growth_pct', lyDeltaPctKey: 'aov_ly_growth_pct', yoyPctKey: 'aov_yoy_pct', render: (v) => fmt.usd2(v || 0) },
  { id: 'mktSpend', label: 'Marketing Spend', platforms: ['dd'], preKey: 'pre_mktSpend', postKey: 'post_mktSpend', postLyKey: 'postLY_mktSpend', deltaKey: 'mktSpend_prevspost', lyDeltaKey: 'mktSpend_ly_prevspost', yoyDeltaKey: 'mktSpend_yoy', deltaPctKey: 'mktSpend_growth_pct', lyDeltaPctKey: 'mktSpend_ly_growth_pct', yoyPctKey: 'mktSpend_yoy_pct', render: (v) => fmt.usd(v || 0) },
  { id: 'profitability', label: 'Profitability %', preKey: 'pre_profitability', postKey: 'post_profitability', postLyKey: 'postLY_profitability', deltaKey: 'prof_prevspost', lyDeltaKey: 'prof_ly_prevspost', yoyDeltaKey: 'prof_yoy', deltaPctKey: 'prof_growth_pct', lyDeltaPctKey: 'prof_ly_growth_pct', yoyPctKey: 'prof_yoy_pct', render: (v) => fmt.pct(v || 0) },
];

/** Marketing spend is DoorDash-only (Uber Eats has no marketing data; Combined would just double a single platform). */
function specsForPlatform(platformKey) {
  return METRIC_SPECS.filter((spec) => !spec.platforms || spec.platforms.includes(platformKey));
}

const STORE_ID_COL = { key: 'storeId', label: 'Store ID', sortable: true, labelCol: true, render: (v) => <span className="font-medium">{v}</span> };

function buildPvpColumns(spec) {
  return [
    STORE_ID_COL,
    { key: spec.preKey, label: 'Pre', align: 'right', sortable: true, render: spec.render },
    { key: spec.postKey, label: 'Post', align: 'right', sortable: true, render: spec.render },
    { key: spec.deltaKey, label: 'Pre vs Post Δ', align: 'right', sortable: true, delta: true, render: spec.render },
    { key: spec.lyDeltaKey, label: 'LY Pre vs Post Δ', align: 'right', sortable: true, delta: true, render: spec.render },
    { key: spec.deltaPctKey, label: 'Pre vs Post %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
    { key: spec.lyDeltaPctKey, label: 'LY Growth%', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
  ];
}

function buildYoyColumns(spec) {
  return [
    STORE_ID_COL,
    { key: spec.postLyKey, label: 'LY Post', align: 'right', sortable: true, render: spec.render },
    { key: spec.postKey, label: 'Post', align: 'right', sortable: true, render: spec.render },
    { key: spec.yoyDeltaKey, label: 'YoY Δ', align: 'right', sortable: true, delta: true, render: spec.render },
    { key: spec.yoyPctKey, label: 'YoY %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
  ];
}

function buildPostColumns(spec) {
  return [
    STORE_ID_COL,
    { key: spec.postKey, label: 'Selected period', align: 'right', sortable: true, render: spec.render },
  ];
}

export default function StoresScreen() {
  const { storeTables } = useDataStore();
  const { setActiveTab, setSelectedStore } = useUiStore();
  const dateAnalysisMode = useConfigStore((s) => s.dateAnalysisMode);
  const isSingleMode = isSinglePeriodMode(dateAnalysisMode);

  const sections = useMemo(() => PLATFORM_SECTIONS
    .map((section) => ({
      ...section,
      stores: storeTables?.[section.key] || [],
    }))
    .filter((section) => section.stores.length), [storeTables]);

  const handleClick = (row) => {
    setSelectedStore(row.storeId, row._platform);
    setActiveTab('storeDetail');
  };

  return (
    <div className="space-y-10 max-w-full min-w-0 overflow-x-hidden">
      {sections.map((section) => (
        <div key={section.key} className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {section.key === 'dd' && <PlatformLogo platform="dd" size={18} />}
              {section.key === 'ue' && <PlatformLogo platform="ue" size={18} />}
              <h2 className="text-base font-semibold text-[var(--text)]">{section.label}</h2>
            </div>
            <p className="text-sm text-[var(--text-muted)]">{section.stores.length} stores</p>
          </div>

          <StoresCharts stores={section.stores} isSingleMode={isSingleMode} />

          {isSingleMode ? (
            <div className="space-y-4">
              {specsForPlatform(section.key).map((spec) => (
                <div key={`${section.key}-${spec.id}-post`} className="space-y-2">
                  <h3 className="text-sm font-semibold text-[var(--text)]">{spec.label}</h3>
                  <SplitDataTable
                    columns={buildPostColumns(spec)}
                    data={section.stores.map((row) => ({ ...row, _platform: section.key }))}
                    onRowClick={handleClick}
                    maxHeight="320px"
                    dense
                  />
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text)] border-b border-[var(--border)] pb-2">Pre vs Post</h3>
                {specsForPlatform(section.key).map((spec) => (
                  <div key={`${section.key}-${spec.id}-pvp`} className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{spec.label}</h4>
                    <SplitDataTable
                      columns={buildPvpColumns(spec)}
                      data={section.stores.map((row) => ({ ...row, _platform: section.key }))}
                      onRowClick={handleClick}
                      maxHeight="320px"
                      dense
                    />
                  </div>
                ))}
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text)] border-b border-[var(--border)] pb-2">Year over Year</h3>
                {specsForPlatform(section.key).map((spec) => (
                  <div key={`${section.key}-${spec.id}-yoy`} className="space-y-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{spec.label}</h4>
                    <SplitDataTable
                      columns={buildYoyColumns(spec)}
                      data={section.stores.map((row) => ({ ...row, _platform: section.key }))}
                      onRowClick={handleClick}
                      maxHeight="320px"
                      dense
                    />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
