import { useMemo } from 'react';
import { useDataStore } from '../stores/dataStore';
import { useConfigStore } from '../stores/configStore';
import { buildSlotAnalysis, buildSlotTicketBucketAnalysis } from '../lib/engine/slots';

export function useSlotFinancialAnalyses() {
  const { ddFinancial, ueFinancial } = useDataStore();
  const config = useConfigStore();
  const {
    ddPreStart, ddPreEnd, ddPostStart, ddPostEnd, ddExcludedDates,
    uePreStart, uePreEnd, uePostStart, uePostEnd, ueExcludedDates,
  } = config;

  return useMemo(() => {
    const build = (platform, rawData) => {
      if (!rawData) return null;
      const isUe = platform === 'ue';
      const preStart = isUe ? uePreStart : ddPreStart;
      const preEnd = isUe ? uePreEnd : ddPreEnd;
      const postStart = isUe ? uePostStart : ddPostStart;
      const postEnd = isUe ? uePostEnd : ddPostEnd;
      const excludedDates = isUe ? ueExcludedDates : ddExcludedDates;
      if (!preStart || !preEnd || !postStart || !postEnd) return null;
      const analysis = buildSlotAnalysis(rawData, {
        preStart, preEnd, postStart, postEnd, excludedDates, platform,
      });
      const ticketBuckets = buildSlotTicketBucketAnalysis(rawData, {
        preStart, preEnd, postStart, postEnd, excludedDates, platform,
      });
      return { ...analysis, ticketBuckets };
    };

    return {
      dd: build('dd', ddFinancial),
      ue: build('ue', ueFinancial),
    };
  }, [
    ddFinancial, ueFinancial,
    ddPreStart, ddPreEnd, ddPostStart, ddPostEnd, ddExcludedDates,
    uePreStart, uePreEnd, uePostStart, uePostEnd, ueExcludedDates,
  ]);
}
