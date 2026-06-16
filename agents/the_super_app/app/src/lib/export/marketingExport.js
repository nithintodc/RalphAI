import { buildAnalysisScope } from '../utils/abStoreFilter';
import { buildMarketingStoreResolver } from '../utils/marketingStoreMatch';
import {
  buildCorpVsTodcBySource,
  buildCampaignTable,
  buildCorpTodcImpactRows,
  buildCampaignHighlights,
  filterCampaignsBySource,
  MARKETING_IMPACT_METRICS,
} from '../engine/marketing';
import { exportByKind } from '../utils/formatters';

export { MARKETING_IMPACT_METRICS };

export const MARKETING_IMPACT_HEADERS = ['Group', ...MARKETING_IMPACT_METRICS.map((m) => m.label)];
export const CAMPAIGN_IMPACT_HEADERS = ['Campaign', ...MARKETING_IMPACT_METRICS.map((m) => m.label)];

function marketingTablesNeedRebuild(tables) {
  const c = tables?.bySource?.combined?.corp;
  if (!c || c.ordersPre === undefined) return true;
  return tables?._spendMappingVersion !== 5;
}

function marketingScopeFromConfig(data, config) {
  const scope = buildAnalysisScope(config);
  const resolveMarketingStoreId = buildMarketingStoreResolver(data?.ddFinancial);
  return { scope, resolveMarketingStoreId };
}

/** Build or reuse marketing tables (matches Marketing screen + Excel export). */
export function resolveMarketingTables(data, config) {
  if (
    (data.marketingTables?.bySource || data.marketingTables?.campaigns)
    && !marketingTablesNeedRebuild(data.marketingTables)
  ) {
    return data.marketingTables;
  }

  const promotion = data.ddMarketing?.promotion;
  const sponsored = data.ddMarketing?.sponsored;
  if ((!promotion && !sponsored) || !config.ddPostStart || !config.ddPostEnd) {
    return null;
  }

  const { scope, resolveMarketingStoreId } = marketingScopeFromConfig(data, config);

  return {
    _spendMappingVersion: 5,
    bySource: buildCorpVsTodcBySource(
      promotion,
      sponsored,
      {
        preStart: config.ddPreStart,
        preEnd: config.ddPreEnd,
        postStart: config.ddPostStart,
        postEnd: config.ddPostEnd,
        excludedDates: config.ddExcludedDates || [],
      },
      scope,
      resolveMarketingStoreId,
    ),
    campaigns: buildCampaignTable(
      promotion,
      sponsored,
      config.ddPostStart,
      config.ddPostEnd,
      scope,
      resolveMarketingStoreId,
    ),
  };
}

export function marketingImpactExportRows(table, period) {
  return buildCorpTodcImpactRows(table, period).map((r) => [
    r.group,
    ...MARKETING_IMPACT_METRICS.map((m) => exportByKind(m.kind, r[m.key])),
  ]);
}

export function campaignImpactExportRows(campaigns) {
  return (campaigns || []).map((row) => [
    row.campaignName,
    ...MARKETING_IMPACT_METRICS.map((m) => exportByKind(m.kind, row[m.key])),
  ]);
}

export function marketingCampaignSlices(marketingTables) {
  const allCampaigns = marketingTables?.campaigns || [];
  return {
    promoCampaigns: filterCampaignsBySource(allCampaigns, 'promotion'),
    adsCampaigns: filterCampaignsBySource(allCampaigns, 'sponsored'),
  };
}

export { buildCampaignHighlights };
