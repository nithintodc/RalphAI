import { useMemo } from 'react';
import { useDataStore } from '../stores/dataStore';
import { useConfigStore } from '../stores/configStore';
import { buildSlotAnalysis, buildSlotTicketBucketAnalysis, hasDdFinancialForSlots } from '../lib/engine/slots';
import { getUniqueStores as getDdStores } from '../lib/parsers/ddFinancial';
import { getUniqueStores as getUeStores } from '../lib/parsers/ueFinancial';
import { buildPeriodExcludedStores, mergeExcludedStores } from '../lib/utils/storePeriodAlignment';
import { isSinglePeriodMode } from '../lib/utils/periodMode';

export function useSlotFinancialAnalyses() {
  const { ddFinancial, ueFinancial, storePeriodAlignment } = useDataStore();
  const config = useConfigStore();
  const {
    ddPreStart, ddPreEnd, ddPostStart, ddPostEnd, ddExcludedDates, ddExcludedStores,
    uePreStart, uePreEnd, uePostStart, uePostEnd, ueExcludedDates, ueExcludedStores,
    dateAnalysisMode,
  } = config;
  const isSinglePeriod = isSinglePeriodMode(dateAnalysisMode);

  return useMemo(() => {
    const build = (platform, rawData) => {
      const isUe = platform === 'ue';
      const preStart = isUe ? uePreStart : ddPreStart;
      const preEnd = isUe ? uePreEnd : ddPreEnd;
      const postStart = isUe ? uePostStart : ddPostStart;
      const postEnd = isUe ? uePostEnd : ddPostEnd;
      const excludedDates = isUe ? ueExcludedDates : ddExcludedDates;
      const manualExcluded = isUe ? ueExcludedStores : ddExcludedStores;
      if (!preStart || !preEnd || !postStart || !postEnd) return null;
      if (!rawData?.length) return null;
      if (!isUe && !hasDdFinancialForSlots(rawData)) return null;

      const allStores = isUe ? getUeStores(rawData) : getDdStores(rawData);
      const alignment = isSinglePeriod ? null : storePeriodAlignment?.[platform];
      const periodExcluded = buildPeriodExcludedStores(allStores, alignment);
      const excludedStores = mergeExcludedStores(manualExcluded, periodExcluded);

      const slotConfig = {
        preStart, preEnd, postStart, postEnd, excludedDates, excludedStores, platform,
      };
      const analysis = buildSlotAnalysis(rawData, slotConfig);
      if (!analysis) return null;
      const ticketBuckets = buildSlotTicketBucketAnalysis(rawData, slotConfig);
      return { ...analysis, ticketBuckets };
    };

    return {
      dd: build('dd', ddFinancial),
      ue: build('ue', ueFinancial),
    };
  }, [
    ddFinancial, ueFinancial, storePeriodAlignment, isSinglePeriod,
    ddPreStart, ddPreEnd, ddPostStart, ddPostEnd, ddExcludedDates, ddExcludedStores,
    uePreStart, uePreEnd, uePostStart, uePostEnd, ueExcludedDates, ueExcludedStores,
  ]);
}
