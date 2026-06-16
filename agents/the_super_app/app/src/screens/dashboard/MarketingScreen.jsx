import { useEffect, useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import { buildAnalysisScope } from '../../lib/utils/abStoreFilter';
import { buildMarketingStoreResolver } from '../../lib/utils/marketingStoreMatch';
import SplitDataTable from '../../components/ui/SplitDataTable';
import {
  buildCorpVsTodcBySource,
  buildCampaignTable,
  buildCorpTodcImpactRows,
  buildCampaignHighlights,
  filterCampaignsBySource,
  MARKETING_IMPACT_METRICS,
  sliceMarketingPct,
} from '../../lib/engine/marketing';
import { formatByKind, fmt } from '../../lib/utils/formatters';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip,
} from 'recharts';
import ChartCard from '../../components/charts/ChartCard';
import RankedBarChart from '../../components/charts/RankedBarChart';
import { TOOLTIP_STYLE, AXIS_TICK, GRID } from '../../components/charts/chartTheme';

function formatMetricCell(kind, v) {
  return formatByKind(kind, v);
}

function ScatterTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md max-w-[16rem]">
      <p className="font-semibold text-[var(--text)] mb-1 truncate">{d.name}</p>
      <p className="tnum text-[var(--text-muted)]">Spend: {fmt.usd(d.x)}</p>
      <p className="tnum text-[var(--text-muted)]">ROAS: {fmt.x(d.y)}</p>
      <p className="tnum text-[var(--text-muted)]">Sales: {fmt.usd(d.z)}</p>
    </div>
  );
}

/** Spend vs ROAS scatter + top-spend ranking for a campaign source. */
function MarketingCharts({ label, campaigns }) {
  const eligible = (campaigns || []).filter((c) => (c.spend || 0) > 0);
  if (eligible.length < 2) return null;
  const scatterData = eligible.map((c) => ({
    x: Math.abs(c.spend || 0), y: c.roas || 0, z: Math.abs(c.sales || 0), name: c.campaignName,
  }));
  const topSpend = eligible.map((c) => ({ label: c.campaignName, value: Math.abs(c.spend || 0) }));
  return (
    <div className="flex flex-col gap-4 w-full">
      <ChartCard
        title={`${label} — Spend vs ROAS`}
        subtitle="Each bubble is a campaign; size = sales. Higher & left-er = more efficient spend."
        height={300}
      >
        <ScatterChart margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis type="number" dataKey="x" name="Spend" tick={AXIS_TICK} axisLine={false} tickLine={false} tickFormatter={fmt.usdK} />
          <YAxis type="number" dataKey="y" name="ROAS" tick={AXIS_TICK} axisLine={false} tickLine={false} tickFormatter={(v) => fmt.x(v)} width={48} />
          <ZAxis type="number" dataKey="z" range={[40, 420]} />
          <Tooltip content={<ScatterTip />} cursor={{ strokeDasharray: '3 3' }} contentStyle={TOOLTIP_STYLE} />
          <Scatter data={scatterData} fill="var(--accent)" fillOpacity={0.55} />
        </ScatterChart>
      </ChartCard>
      <RankedBarChart
        title={`${label} — Top campaigns by spend`}
        subtitle="Where the marketing budget is going (post period)."
        data={topSpend}
        topN={12}
        color="var(--accent)"
        valueFormatter={fmt.usdK}
      />
    </div>
  );
}

function buildImpactColumns(includeCampaign = false) {
  const cols = [];
  if (includeCampaign) {
    cols.push({
      key: 'campaignName',
      label: 'Campaign',
      labelCol: true,
      sortable: true,
      render: (v) => (
        <span className="block font-medium break-words text-left" title={String(v ?? '')}>
          {v}
        </span>
      ),
    });
  } else {
    cols.push({
      key: 'group',
      label: 'Group',
      labelCol: true,
      sortable: false,
      render: (v, row) => (
        <span className={row._total ? 'font-semibold' : 'font-medium'}>{v}</span>
      ),
    });
  }
  for (const m of MARKETING_IMPACT_METRICS) {
    cols.push({
      key: m.key,
      label: m.label,
      align: 'right',
      sortable: includeCampaign,
      render: (v) => formatMetricCell(m.kind, v),
    });
  }
  return cols;
}

const impactColumns = buildImpactColumns(false);
const campaignColumns = buildImpactColumns(true);

function Section({ title, subtitle, children }) {
  return (
    <section className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>
        {subtitle ? <p className="text-xs text-[var(--text-subtle)] mt-0.5">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function CampaignHighlights({ label, campaigns }) {
  const eligible = campaigns.filter((c) => (c.spend || 0) > 0);
  const n = sliceMarketingPct(eligible.length);
  const topRoas = useMemo(() => buildCampaignHighlights(campaigns, 'topRoas'), [campaigns]);
  const topSpend = useMemo(() => buildCampaignHighlights(campaigns, 'topSpend'), [campaigns]);
  const poorRoas = useMemo(() => buildCampaignHighlights(campaigns, 'poorRoas'), [campaigns]);

  if (!eligible.length) return null;

  const blocks = [
    { title: `Top ${n} by ROAS`, rows: topRoas, subtitle: `${topRoas.length} of ${eligible.length} campaigns with spend` },
    { title: `Top ${n} by spend`, rows: topSpend, subtitle: 'Highest marketing spend in post period' },
    { title: `Bottom ${n} by ROAS`, rows: poorRoas, subtitle: 'Lowest return on ad/promo spend' },
  ];

  return (
    <div className="flex flex-col gap-6 w-full">
      {blocks.map((b) => (
        <Section key={`${label}-${b.title}`} title={`${label} — ${b.title}`} subtitle={b.subtitle}>
          <SplitDataTable
            columns={campaignColumns}
            data={b.rows}
            maxHeight="min(42vh, 360px)"
            dense
            split={false}
            layout="full"
          />
        </Section>
      ))}
    </div>
  );
}

export default function MarketingScreen() {
  const { ddFinancial, ddMarketing, marketingTables, setMarketingTables } = useDataStore();
  const config = useConfigStore();

  useEffect(() => {
    const promo = ddMarketing?.promotion;
    const sponsored = ddMarketing?.sponsored;
    if (!promo && !sponsored) return;

    const postStart = config.ddPostStart;
    const postEnd = config.ddPostEnd;
    if (!postStart || !postEnd) return;

    const scope = buildAnalysisScope(config);
    const resolveMarketingStoreId = buildMarketingStoreResolver(ddFinancial);

    const bySource = buildCorpVsTodcBySource(promo, sponsored, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart,
      postEnd,
      excludedDates: config.ddExcludedDates || [],
    }, scope, resolveMarketingStoreId);
    const campaigns = buildCampaignTable(
      promo,
      sponsored,
      postStart,
      postEnd,
      scope,
      resolveMarketingStoreId,
    );
    setMarketingTables({ _spendMappingVersion: 5, bySource, campaigns });
  }, [
    ddFinancial,
    ddMarketing,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
    config.storeTagMap,
    config.includedStoreIds,
    config.ddToUeStoreMap,
    setMarketingTables,
  ]);

  const mt = marketingTables;
  const combined = mt?.bySource?.combined;
  const hasPre = combined?.meta?.hasPre;

  const postCorpRows = useMemo(
    () => buildCorpTodcImpactRows(combined, 'post'),
    [combined],
  );
  const preCorpRows = useMemo(
    () => buildCorpTodcImpactRows(combined, 'pre'),
    [combined],
  );

  const allCampaigns = mt?.campaigns || [];
  const promoCampaigns = useMemo(
    () => filterCampaignsBySource(allCampaigns, 'promotion'),
    [allCampaigns],
  );
  const adsCampaigns = useMemo(
    () => filterCampaignsBySource(allCampaigns, 'sponsored'),
    [allCampaigns],
  );

  const hasCorpTodc = !!(ddMarketing?.promotion || ddMarketing?.sponsored);

  if (!hasCorpTodc) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Marketing data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">
          Upload DoorDash Marketing ZIP (promotions and sponsored listings) to see Corp vs TODC and campaign tables.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-full min-w-0 overflow-x-hidden">
      <p className="text-xs text-[var(--text-subtle)] leading-relaxed max-w-3xl">
        DoorDash marketing only. Corporate vs TODC uses the DD <strong>Is self serve campaign</strong> column:
        false = Corporate, true = TODC. Store map only limits which stores are included.
        Total = Corporate + TODC.
      </p>

      {postCorpRows.length > 0 && (
        <Section title="Corp vs TODC — Post period" subtitle="Promotions + Sponsored Listings combined">
          <SplitDataTable columns={impactColumns} data={postCorpRows} sortable={false} dense split={false} layout="full" />
        </Section>
      )}

      {preCorpRows.length > 0 && (
        <Section
          title="Corp vs TODC — Pre period"
          subtitle={hasPre ? 'Promotions + Sponsored Listings combined' : 'Set Pre dates in the top bar to populate this table'}
        >
          {!hasPre && (
            <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-2">
              Pre period is not configured — values below are zero. Set Pre dates for a real comparison.
            </p>
          )}
          <SplitDataTable columns={impactColumns} data={preCorpRows} sortable={false} dense split={false} layout="full" />
        </Section>
      )}

      <MarketingCharts label="Promo" campaigns={promoCampaigns} />

      {promoCampaigns.length > 0 && (
        <Section
          title="Promo campaigns"
          subtitle={`${promoCampaigns.length} campaigns · post period · promotion source`}
        >
          <SplitDataTable
            columns={campaignColumns}
            data={promoCampaigns}
            maxHeight="min(50vh, 440px)"
            dense
            split={false}
            layout="full"
          />
        </Section>
      )}

      <CampaignHighlights label="Promo" campaigns={promoCampaigns} />

      <MarketingCharts label="Ads" campaigns={adsCampaigns} />

      {adsCampaigns.length > 0 && (
        <Section
          title="Ads campaigns"
          subtitle={`${adsCampaigns.length} campaigns · post period · sponsored listings`}
        >
          <SplitDataTable
            columns={campaignColumns}
            data={adsCampaigns}
            maxHeight="min(50vh, 440px)"
            dense
            split={false}
            layout="full"
          />
        </Section>
      )}

      <CampaignHighlights label="Ads" campaigns={adsCampaigns} />
    </div>
  );
}
