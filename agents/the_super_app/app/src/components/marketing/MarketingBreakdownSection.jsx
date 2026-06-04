import { useEffect, useMemo, useState } from 'react';
import SplitDataTable from '../ui/SplitDataTable';
import { fmt } from '../../lib/utils/formatters';
import {
  buildCombinedRows,
  buildFinancialDatasetFromDdFinancial,
  buildMarketingDataset,
  buildMarketingBreakdownAnalysis,
  buildSalesDataset,
  COMBINED_COLUMNS,
  computeFinancialScope,
  computeMarketingScope,
  computeSalesScope,
  fetchDefaultBreakdownDatasets,
} from '../../lib/engine/marketingBreakdown';

function SummaryGrid({ items }) {
  if (!items?.length) return null;
  return (
    <div className="flex flex-wrap gap-2 max-w-full">
      {items.map((item) => (
        <div
          key={item.label}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 min-w-[7.5rem] max-w-[11rem] flex-1"
        >
          <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)] leading-tight">{item.label}</p>
          <p className="text-sm font-semibold tnum text-[var(--text)] mt-0.5 whitespace-nowrap">
            {item.kind === 'usd' ? fmt.usd(item.value) : item.kind === 'int' ? fmt.int(item.value) : item.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options, allLabel, disabled }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-[var(--text-muted)]">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm text-[var(--text)] disabled:opacity-50"
      >
        <option value="ALL">{allLabel}</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </label>
  );
}

function nullableUsd(v) {
  return v == null || Number.isNaN(v) ? '—' : fmt.usd(v);
}

function nullableInt(v) {
  return v == null || Number.isNaN(v) ? '—' : fmt.int(v);
}

function nullableUsd2(v) {
  return v == null || Number.isNaN(v) ? '—' : fmt.usd2(v);
}

const combinedTableColumns = COMBINED_COLUMNS.map((col) => {
  const base = { key: col.key, label: col.label, align: 'right', sortable: true };
  if (col.key === 'label') {
    return { ...base, align: 'left', labelCol: true, render: (v) => <span className="font-medium">{v}</span> };
  }
  if (col.key === 'finOrders' || col.key === 'mktOrders' || col.key === 'salesOrders') {
    return { ...base, render: (v) => nullableInt(v) };
  }
  if (col.key === 'salesAov') {
    return { ...base, render: (v) => nullableUsd2(v) };
  }
  return { ...base, render: (v) => nullableUsd(v) };
});

function ScopeCard({ title, meta, filters, summary, children }) {
  return (
    <div className="card space-y-3 min-w-0 max-w-full">
      <div>
        <h4 className="text-sm font-semibold text-[var(--text)]">{title}</h4>
        {meta ? <p className="text-[10px] text-[var(--text-subtle)] mt-0.5">Source: {meta}</p> : null}
      </div>
      {filters}
      <SummaryGrid items={summary} />
      {children}
    </div>
  );
}

export default function MarketingBreakdownSection({
  ddFinancial,
  marketingPromotionRaw,
  salesByTimeRaw,
}) {
  const [analysis, setAnalysis] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(false);

  const [storeFilter, setStoreFilter] = useState('ALL');
  const [campaignFilter, setCampaignFilter] = useState('ALL');
  const [marketingStoreFilter, setMarketingStoreFilter] = useState('ALL');
  const [selfServeFilter, setSelfServeFilter] = useState('ALL');
  const [salesStoreFilter, setSalesStoreFilter] = useState('ALL');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        let financial = null;
        let marketing = null;
        let sales = null;

        if (ddFinancial?.length) {
          financial = buildFinancialDatasetFromDdFinancial(ddFinancial);
        }
        if (marketingPromotionRaw?.data?.length) {
          marketing = buildMarketingDataset(
            marketingPromotionRaw.data,
            marketingPromotionRaw.fileLabel || 'Marketing promotion',
            'upload',
          );
        }
        if (salesByTimeRaw?.data?.length) {
          sales = buildSalesDataset(
            salesByTimeRaw.data,
            salesByTimeRaw.fileLabel || 'Sales by time',
            'upload',
          );
        }

        if (!financial || !marketing || !sales) {
          const defaults = await fetchDefaultBreakdownDatasets();
          if (!financial && defaults.financial) financial = defaults.financial;
          if (!marketing && defaults.marketing) marketing = defaults.marketing;
          if (!sales && defaults.sales) sales = defaults.sales;
        }

        if (!financial && !marketing && !sales) {
          throw new Error(
            'Upload Financial, Marketing (promotion), and Sales (by time) exports to run the breakdown pivots.',
          );
        }

        if (!cancelled) {
          setAnalysis(buildMarketingBreakdownAnalysis({ financial, marketing, sales }));
          setStoreFilter('ALL');
          setCampaignFilter('ALL');
          setMarketingStoreFilter('ALL');
          setSelfServeFilter('ALL');
          setSalesStoreFilter('ALL');
        }
      } catch (err) {
        if (!cancelled) {
          setAnalysis(null);
          setLoadError(err.message || String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [ddFinancial, marketingPromotionRaw, salesByTimeRaw]);

  const financialScope = useMemo(() => {
    if (!analysis?.financial) return null;
    return computeFinancialScope(analysis.financial, storeFilter);
  }, [analysis, storeFilter]);

  const marketingScope = useMemo(() => {
    if (!analysis?.marketing) return null;
    return computeMarketingScope(analysis.marketing, {
      campaignId: campaignFilter,
      storeId: marketingStoreFilter,
      selfServe: selfServeFilter,
    });
  }, [analysis, campaignFilter, marketingStoreFilter, selfServeFilter]);

  const salesScope = useMemo(() => {
    if (!analysis?.sales) return null;
    return computeSalesScope(analysis.sales, salesStoreFilter);
  }, [analysis, salesStoreFilter]);

  const combinedRows = useMemo(() => {
    if (!financialScope && !marketingScope && !salesScope) return [];
    return buildCombinedRows(
      financialScope?.pivot || [],
      marketingScope?.pivot || [],
      salesScope?.pivot || [],
    );
  }, [financialScope, marketingScope, salesScope]);

  const missing = [];
  if (analysis && !analysis.financial) missing.push('Financial detailed');
  if (analysis && !analysis.marketing) missing.push('Marketing promotion');
  if (analysis && !analysis.sales) missing.push('Sales by time');

  if (loading) {
    return (
      <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
        Loading marketing breakdown pivots…
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="card border-amber-200 bg-amber-50 py-6 px-4 text-sm text-amber-900">
        {loadError}
      </div>
    );
  }

  if (!analysis) return null;

  return (
    <section className="space-y-6 min-w-0 max-w-full">
      <div>
        <h3 className="text-sm font-semibold text-[var(--text)]">DoorDash export breakdown</h3>
        <p className="text-xs text-[var(--text-muted)] mt-1 max-w-3xl leading-relaxed">
          Financial, marketing promotion, and sales-by-time pivots merged on date / granularity.
        </p>
        <p className="text-[10px] text-[var(--text-subtle)] mt-2">{analysis.statusMessage}</p>
        {missing.length > 0 ? (
          <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            Missing: {missing.join(', ')}. Upload the matching DoorDash ZIPs or rely on server root-scan fallback.
          </p>
        ) : null}
      </div>

      {analysis.financial ? (
        <ScopeCard
          title="Financial detailed pivot"
          meta={financialScope?.fileLabel}
          summary={financialScope?.summary}
          filters={(
            <FilterSelect
              label="Merchant store ID"
              value={storeFilter}
              onChange={setStoreFilter}
              options={analysis.financial.storeIds}
              allLabel="All stores"
            />
          )}
        />
      ) : null}

      {analysis.marketing ? (
        <ScopeCard
          title="Marketing promotion pivot"
          meta={marketingScope?.fileLabel}
          summary={marketingScope?.summary}
          filters={(
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <FilterSelect
                label="Campaign ID"
                value={campaignFilter}
                onChange={setCampaignFilter}
                options={analysis.marketing.campaignIds}
                allLabel="All campaigns"
              />
              <FilterSelect
                label="Store ID"
                value={marketingStoreFilter}
                onChange={setMarketingStoreFilter}
                options={analysis.marketing.storeIds}
                allLabel="All stores"
              />
              <FilterSelect
                label="Is self serve campaign"
                value={selfServeFilter}
                onChange={setSelfServeFilter}
                options={analysis.marketing.selfServeValues}
                allLabel="All"
              />
            </div>
          )}
        />
      ) : null}

      {analysis.sales ? (
        <ScopeCard
          title="Sales by time · product performance"
          meta={salesScope?.fileLabel}
          summary={salesScope?.summary}
          filters={(
            <FilterSelect
              label="Store name"
              value={salesStoreFilter}
              onChange={setSalesStoreFilter}
              options={analysis.sales.storeNames}
              allLabel="All stores"
            />
          )}
        />
      ) : null}

      <div className="card space-y-3 min-w-0 max-w-full">
        <div>
          <h4 className="text-sm font-semibold text-[var(--text)]">Combined pivot</h4>
          <p className="text-[10px] text-[var(--text-subtle)] mt-1">
            Rows merge by date. Sales granularity values align to the same timeline where possible.
          </p>
        </div>
        <SplitDataTable
          columns={combinedTableColumns}
          data={combinedRows}
          sortable
          splitAt={4}
          dense
          bare
          maxHeight="480px"
          chunkTitles={['Financial metrics', 'Marketing metrics', 'Sales metrics', 'Promotion & ad fees']}
        />
      </div>
    </section>
  );
}
