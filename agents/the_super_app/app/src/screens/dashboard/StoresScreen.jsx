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
import { storeSpecsForPlatform } from '../../lib/engine/storeTableSpecs';
import StoreComparisonNotice from '../../components/ui/StoreComparisonNotice';
import CrossPlatformStoreNotice from '../../components/ui/CrossPlatformStoreNotice';
import {
  buildDdStoreIdToMerchantMapFromFinancial,
  displayStoreId,
  storeIdColumnLabel,
} from '../../lib/utils/storeDisplay';

/** Ranked store charts above the tables. */
function StoresCharts({ stores, isSingleMode, platformKey, ddStoreIdToMerchant }) {
  const labelFor = (s) => displayStoreId(s, platformKey, ddStoreIdToMerchant);
  if (!stores.length) return null;
  if (isSingleMode) {
    const sales = stores.map((s) => ({ label: labelFor(s), value: s.post_sales || 0 }));
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
    .map((s) => ({ label: labelFor(s), value: s.sales_growth_pct }));
  const salesPost = stores.map((s) => ({ label: labelFor(s), value: s.post_sales || 0 }));
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

const RENDER_BY_SPEC = {
  sales: (v) => fmt.usd(v || 0),
  payouts: (v) => fmt.usd(v || 0),
  orders: (v) => fmt.int(v || 0),
  aov: (v) => fmt.usd2(v || 0),
  mktSpend: (v) => fmt.usd(v || 0),
  adsSpend: (v) => fmt.usd(v || 0),
  promoSpend: (v) => fmt.usd(v || 0),
  profitability: (v) => fmt.pct(v || 0),
};

function specsForPlatform(platformKey) {
  return storeSpecsForPlatform(platformKey).map((spec) => ({
    ...spec,
    render: RENDER_BY_SPEC[spec.id] || ((v) => fmt.usd(v || 0)),
  }));
}

const STORE_ID_COL = (platformKey, ddStoreIdToMerchant) => ({
  key: 'storeId',
  label: storeIdColumnLabel(platformKey),
  sortable: true,
  labelCol: true,
  render: (_, row) => (
    <span className="font-medium">{displayStoreId(row, platformKey, ddStoreIdToMerchant)}</span>
  ),
});

function buildPvpColumns(spec, platformKey, ddStoreIdToMerchant) {
  return [
    STORE_ID_COL(platformKey, ddStoreIdToMerchant),
    { key: spec.preKey, label: 'Pre', align: 'right', sortable: true, render: spec.render },
    { key: spec.postKey, label: 'Post', align: 'right', sortable: true, render: spec.render },
    { key: spec.deltaKey, label: 'Pre vs Post Δ', align: 'right', sortable: true, delta: true, render: spec.render },
    { key: spec.lyDeltaKey, label: 'LY Pre vs Post Δ', align: 'right', sortable: true, delta: true, render: spec.render },
    { key: spec.deltaPctKey, label: 'Pre vs Post %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
    { key: spec.lyDeltaPctKey, label: 'LY Growth%', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
  ];
}

function buildYoyColumns(spec, platformKey, ddStoreIdToMerchant) {
  return [
    STORE_ID_COL(platformKey, ddStoreIdToMerchant),
    { key: spec.postLyKey, label: 'LY Post', align: 'right', sortable: true, render: spec.render },
    { key: spec.postKey, label: 'Post', align: 'right', sortable: true, render: spec.render },
    { key: spec.yoyDeltaKey, label: 'YoY Δ', align: 'right', sortable: true, delta: true, render: spec.render },
    { key: spec.yoyPctKey, label: 'YoY %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
  ];
}

function buildPostColumns(spec, platformKey, ddStoreIdToMerchant) {
  return [
    STORE_ID_COL(platformKey, ddStoreIdToMerchant),
    { key: spec.postKey, label: 'Selected period', align: 'right', sortable: true, render: spec.render },
  ];
}

export default function StoresScreen() {
  const { storeTables, storePeriodAlignment, crossPlatformAlignment, ddFinancial } = useDataStore();
  const { setActiveTab, setSelectedStore } = useUiStore();
  const dateAnalysisMode = useConfigStore((s) => s.dateAnalysisMode);
  const isSingleMode = isSinglePeriodMode(dateAnalysisMode);
  const ddStoreIdToMerchant = useMemo(
    () => buildDdStoreIdToMerchantMapFromFinancial(ddFinancial),
    [ddFinancial],
  );

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
      {!isSingleMode && crossPlatformAlignment && (
        <CrossPlatformStoreNotice crossPlatform={crossPlatformAlignment} />
      )}

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

          {!isSingleMode && section.key !== 'combined' && storePeriodAlignment?.[section.key] && (
            <StoreComparisonNotice platform={section.key} alignment={storePeriodAlignment[section.key]} />
          )}

          <StoresCharts
            stores={section.stores}
            isSingleMode={isSingleMode}
            platformKey={section.key}
            ddStoreIdToMerchant={ddStoreIdToMerchant}
          />

          {isSingleMode ? (
            <div className="space-y-4">
              {specsForPlatform(section.key).map((spec) => (
                <div key={`${section.key}-${spec.id}-post`} className="space-y-2">
                  <h3 className="text-sm font-semibold text-[var(--text)]">{spec.label}</h3>
                  <SplitDataTable
                    columns={buildPostColumns(spec, section.key, ddStoreIdToMerchant)}
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
                      columns={buildPvpColumns(spec, section.key, ddStoreIdToMerchant)}
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
                      columns={buildYoyColumns(spec, section.key, ddStoreIdToMerchant)}
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
