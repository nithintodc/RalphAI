import { useEffect, useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
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
import { formatByKind } from '../../lib/utils/formatters';

function formatMetricCell(kind, v) {
  return formatByKind(kind, v);
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
        <span className="block max-w-[min(48vw,22rem)] truncate font-medium" title={String(v ?? '')}>
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
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      {blocks.map((b) => (
        <Section key={`${label}-${b.title}`} title={`${label} — ${b.title}`} subtitle={b.subtitle}>
          <SplitDataTable
            columns={campaignColumns}
            data={b.rows}
            maxHeight="min(42vh, 360px)"
            dense
            split={false}
          />
        </Section>
      ))}
    </div>
  );
}

export default function MarketingScreen() {
  const { ddMarketing, marketingTables, setMarketingTables } = useDataStore();
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
    setMarketingTables({ _spendMappingVersion: 2, bySource, campaigns });
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
        DoorDash marketing only. Check after Promo = (Sales ÷ Orders) − (Spend ÷ Orders). Campaign tables use the post period.
      </p>

      {postCorpRows.length > 0 && (
        <Section title="Corp vs TODC — Post period" subtitle="Promotions + Sponsored Listings combined">
          <SplitDataTable columns={impactColumns} data={postCorpRows} sortable={false} dense split={false} />
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
          <SplitDataTable columns={impactColumns} data={preCorpRows} sortable={false} dense split={false} />
        </Section>
      )}

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
          />
        </Section>
      )}

      <CampaignHighlights label="Promo" campaigns={promoCampaigns} />

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
          />
        </Section>
      )}

      <CampaignHighlights label="Ads" campaigns={adsCampaigns} />
    </div>
  );
}
