import { useEffect, useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import MarketingBreakdownSection from '../../components/marketing/MarketingBreakdownSection';
import { buildCorpVsTodcBySource, buildCampaignTable, MARKETING_SUMMARY_METRICS } from '../../lib/engine/marketing';
import { fmt } from '../../lib/utils/formatters';
import { growthPct, round } from '../../lib/utils/safeMath';

function formatMetricCell(kind, v) {
  if (v == null || Number.isNaN(v)) return '—';
  switch (kind) {
    case 'int':
      return fmt.int(v);
    case 'usd':
      return fmt.usd(v);
    case 'usd2':
      return fmt.usd2(v);
    case 'roas':
      return fmt.x(v);
    default:
      return String(v);
  }
}

function formatMetricDelta(kind, v) {
  if (v == null || Number.isNaN(v)) return '—';
  if (kind === 'roas') {
    const s = v >= 0 ? '+' : '';
    return `${s}${Number(v).toFixed(2)}×`;
  }
  return formatMetricCell(kind, v);
}

function buildPvpRows(data, metric) {
  if (!data?.corp) return [];
  const k = metric.key;
  return [data.corp, data.todc, data.total].map((r) => ({
    group: r.label,
    pre: r[`${k}Pre`],
    post: r[`${k}Post`],
    pvp: r[`${k}Pvp`],
    lyPrevspost: round((r[`${k}LyPost`] ?? 0) - (r[`${k}LyPre`] ?? 0), metricDecimals(metric.key)),
    pvpPct: r[`${k}PvpPct`],
    lyGrowthPct: round(growthPct(r[`${k}LyPre`], r[`${k}LyPost`]), 1),
    _total: r.label === 'Total',
  }));
}

function buildYoyRows(data, metric) {
  if (!data?.corp) return [];
  const k = metric.key;
  return [data.corp, data.todc, data.total].map((r) => ({
    group: r.label,
    lyPost: r[`${k}LyPost`],
    post: r[`${k}Post`],
    yoy: r[`${k}Yoy`],
    yoyPct: r[`${k}YoyPct`],
    _total: r.label === 'Total',
  }));
}

function metricDecimals(metricKey) {
  if (metricKey === 'orders') return 0;
  if (['promoAov', 'cpo', 'checkAfterPromo', 'roas'].includes(metricKey)) return 2;
  return 0;
}

function buildPvpColumns(metric) {
  const kind = metric.kind;
  const render = (v) => formatMetricCell(kind, v);
  const renderDelta = (v) => formatMetricDelta(kind, v);
  return [
    {
      key: 'group',
      label: 'Group',
      labelCol: true,
      render: (v, row) => (
        <span className={row._total ? 'font-semibold' : 'font-medium'}>{v}</span>
      ),
    },
    { key: 'pre', label: 'Pre', align: 'right', render },
    { key: 'post', label: 'Post', align: 'right', render },
    { key: 'pvp', label: 'Pre vs Post Δ', align: 'right', delta: true, render: renderDelta },
    { key: 'lyPrevspost', label: 'LY Pre vs Post Δ', align: 'right', delta: true, render: renderDelta },
    { key: 'pvpPct', label: 'Pre vs Post %', align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'lyGrowthPct', label: 'LY Growth%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ];
}

function buildYoyColumns(metric) {
  const kind = metric.kind;
  const render = (v) => formatMetricCell(kind, v);
  const renderDelta = (v) => formatMetricDelta(kind, v);
  return [
    {
      key: 'group',
      label: 'Group',
      labelCol: true,
      render: (v, row) => (
        <span className={row._total ? 'font-semibold' : 'font-medium'}>{v}</span>
      ),
    },
    { key: 'lyPost', label: 'LY Post', align: 'right', render },
    { key: 'post', label: 'Post', align: 'right', render },
    { key: 'yoy', label: 'YoY Δ', align: 'right', delta: true, render: renderDelta },
    { key: 'yoyPct', label: 'YoY %', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ];
}

function buildPostImpactRows(data) {
  if (!data?.corp) return [];
  return [data.corp, data.todc, data.total].map((r) => ({
    group: r.label,
    sales: r.salesPost,
    spend: r.spendPost,
    promoAov: r.promoAovPost,
    cpo: r.cpoPost,
    checkAfterPromo: r.checkAfterPromoPost,
    _total: r.label === 'Total',
  }));
}

const postImpactColumns = [
  {
    key: 'group',
    label: 'Group',
    sortable: false,
    labelCol: true,
    render: (v, row) => <span className={row._total ? 'font-semibold' : 'font-medium'}>{v}</span>,
  },
  { key: 'sales', label: 'Sales', align: 'right', sortable: false, render: (v) => fmt.usd(v || 0) },
  { key: 'spend', label: 'Spend', align: 'right', sortable: false, render: (v) => fmt.usd(v || 0) },
  { key: 'promoAov', label: 'Promo AOV', align: 'right', sortable: false, render: (v) => fmt.usd2(v || 0) },
  { key: 'cpo', label: 'Cost / Order', align: 'right', sortable: false, render: (v) => fmt.usd2(v || 0) },
  { key: 'checkAfterPromo', label: 'Check After Promo', align: 'right', sortable: false, render: (v) => fmt.usd2(v || 0) },
];

function MarketingSourceSection({ title, data }) {
  if (!data?.corp) return null;
  const hasPre = data.meta?.hasPre;
  const postImpact = buildPostImpactRows(data);

  return (
    <section className="space-y-5">
      <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>

      <div className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)] border-b border-[var(--border)] pb-2">
          Post-period impact
        </h4>
        <p className="text-[10px] text-[var(--text-subtle)]">
          Check After Promo = Promo AOV − Cost / Order · Promo AOV = Sales / Orders (marketing data).
        </p>
        <SplitDataTable columns={postImpactColumns} data={postImpact} sortable={false} dense />
      </div>

      {!hasPre && (
        <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Pre period is not set — Pre and Δ PvP columns default to zero. Set Pre dates in the top bar for a real Pre vs Post comparison.
        </p>
      )}

      <div className="space-y-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)] border-b border-[var(--border)] pb-2">
          Pre vs Post
        </h4>
        {MARKETING_SUMMARY_METRICS.map((metric) => (
          <div key={`pvp-${metric.key}`} className="space-y-2">
            <h5 className="text-xs font-semibold text-[var(--text)]">{metric.label}</h5>
            <SplitDataTable
              columns={buildPvpColumns(metric)}
              data={buildPvpRows(data, metric)}
              sortable={false}
              dense
            />
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)] border-b border-[var(--border)] pb-2">
          Year over Year
        </h4>
        {MARKETING_SUMMARY_METRICS.map((metric) => (
          <div key={`yoy-${metric.key}`} className="space-y-2">
            <h5 className="text-xs font-semibold text-[var(--text)]">{metric.label}</h5>
            <SplitDataTable
              columns={buildYoyColumns(metric)}
              data={buildYoyRows(data, metric)}
              sortable={false}
              dense
            />
          </div>
        ))}
      </div>
    </section>
  );
}

export default function MarketingScreen() {
  const {
    ddFinancial,
    ddMarketing,
    ddMarketingRaw,
    ddSales,
    marketingTables,
    setMarketingTables,
  } = useDataStore();
  const config = useConfigStore();

  useEffect(() => {
    const promo = ddMarketing?.promotion;
    const sponsored = ddMarketing?.sponsored;
    if (!promo && !sponsored) return;

    const postStart = config.ddPostStart;
    const postEnd = config.ddPostEnd;
    if (!postStart || !postEnd) return;

    const bySource = buildCorpVsTodcBySource(promo, sponsored, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart,
      postEnd,
      excludedDates: config.ddExcludedDates || [],
    });
    const campaigns = buildCampaignTable(promo, sponsored, postStart, postEnd);
    setMarketingTables({ bySource, campaigns });
  }, [
    ddMarketing,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
    setMarketingTables,
  ]);

  const mt = marketingTables;

  const campaignCols = useMemo(() => [
    { key: 'campaignName', label: 'Campaign', labelCol: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'source', label: 'Source', render: (v) => <span className="text-xs capitalize">{v}</span> },
    {
      key: 'isSelfServe',
      label: 'Type',
      render: (v) => (
        <span className={`text-xs px-1.5 py-0.5 rounded ${v ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]' : 'bg-purple-50 text-purple-700'}`}>
          {v ? 'TODC' : 'Corp'}
        </span>
      ),
    },
    { key: 'orders', label: 'Orders', align: 'right', render: (v) => fmt.int(v) },
    { key: 'sales', label: 'Sales', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'spend', label: 'Spend', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'promoAov', label: 'Promo AOV', align: 'right', render: (v) => fmt.usd2(v) },
    { key: 'roas', label: 'ROAS', align: 'right', render: (v) => fmt.x(v) },
    { key: 'cpo', label: 'Cost/Order', align: 'right', render: (v) => fmt.usd2(v) },
    { key: 'checkAfterPromo', label: 'Check After Promo', align: 'right', render: (v) => fmt.usd2(v) },
  ], []);

  const hasCorpTodc = !!(ddMarketing?.promotion || ddMarketing?.sponsored);
  const hasBreakdownInputs = !!(
    ddFinancial?.length
    || ddMarketingRaw?.promotion
    || ddSales?.byTime?.data?.length
  );

  if (!hasCorpTodc && !hasBreakdownInputs) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Marketing data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">
          Upload DoorDash Financial, Marketing, and Sales (by time) ZIPs for full analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10 max-w-full min-w-0 overflow-x-hidden">
      {hasBreakdownInputs ? (
        <MarketingBreakdownSection
          ddFinancial={ddFinancial}
          marketingPromotionRaw={ddMarketingRaw?.promotion}
          salesByTimeRaw={ddSales?.byTime}
        />
      ) : null}

      {hasCorpTodc ? (
        <>
          <p className="text-xs text-[var(--text-subtle)] leading-relaxed max-w-3xl">
            Corp vs TODC by metric — same Pre / Post / YoY windows as the rest of the app.
            Promotions and Sponsored Listings are reported individually (DoorDash only — Uber Eats has no marketing data).
            Campaign performance below remains Post period only.
          </p>

          <MarketingSourceSection
        title="Promotions"
        data={mt?.bySource?.promotion}
      />

      <MarketingSourceSection
        title="Sponsored Listings"
        data={mt?.bySource?.sponsored}
      />

          {mt?.campaigns?.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Campaign Performance (Post period)</h3>
              <SplitDataTable
                columns={campaignCols}
                data={mt.campaigns}
                maxHeight="400px"
                dense
                chunkTitles={['Campaign details', 'Performance metrics']}
              />
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
