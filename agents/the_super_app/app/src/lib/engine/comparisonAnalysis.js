import { buildDdPlatformData, buildUePlatformData } from './periodEngine';
import { addDerivedMetrics, buildSummaryTables } from './metrics';
import { alignCrossPlatformStoreTables } from './crossPlatformStoreAlign';
import { applyStoreTableScope } from '../utils/abStoreFilter';
import {
  buildStorePeriodAlignmentFromRows,
  filterStoreRowsByIds,
} from '../utils/storePeriodAlignment';

/**
 * Build store tables, aligned summaries, and period comparison metadata.
 */
export function runComparisonAnalysis({
  ddFinancial,
  ueFinancial,
  ddConfig,
  ueConfig,
  hasDd,
  hasUe,
  ddReady,
  ueReady,
  scope,
  storeMap,
  isSinglePeriod,
}) {
  let ddStoreFull = [];
  let ueStoreFull = [];

  if (hasDd && ddReady) {
    ddStoreFull = buildDdPlatformData(ddFinancial, ddConfig);
    ddStoreFull = addDerivedMetrics(ddStoreFull);
  }

  if (hasUe && ueReady) {
    ueStoreFull = buildUePlatformData(ueFinancial, ueConfig);
    ueStoreFull = addDerivedMetrics(ueStoreFull);
  }

  const ddAlignment = isSinglePeriod ? null : buildStorePeriodAlignmentFromRows(ddStoreFull);
  const ueAlignment = isSinglePeriod ? null : buildStorePeriodAlignmentFromRows(ueStoreFull);

  const ddStore = isSinglePeriod
    ? ddStoreFull
    : filterStoreRowsByIds(ddStoreFull, ddAlignment?.pvp?.commonIds);
  const ueStore = isSinglePeriod
    ? ueStoreFull
    : filterStoreRowsByIds(ueStoreFull, ueAlignment?.pvp?.commonIds);

  const aligned = alignCrossPlatformStoreTables(ddStore, ueStore, storeMap);

  let storeTables = {
    dd: aligned.dd,
    ue: aligned.ue,
    combined: aligned.combined,
  };
  storeTables = applyStoreTableScope(storeTables, scope);

  const summaries = buildSummaryTables(storeTables.dd, storeTables.ue, {
    dd: ddAlignment,
    ue: ueAlignment,
  });

  return {
    storeTables,
    summaries,
    storePeriodAlignment: { dd: ddAlignment, ue: ueAlignment },
    crossPlatformAlignment: aligned.crossPlatform,
  };
}
