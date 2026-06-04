import { useMemo } from 'react';
import { useDataStore } from '../stores/dataStore';
import { useConfigStore } from '../stores/configStore';
import { buildApp2BucketingPack } from '../lib/engine/app2Bucketing';

export function useApp2Pack() {
  const ddFinancial = useDataStore((s) => s.ddFinancial);
  const summaryTables = useDataStore((s) => s.summaryTables);
  const config = useConfigStore();

  const pack = useMemo(
    () => buildApp2BucketingPack(ddFinancial, config),
    [
      ddFinancial,
      config.ddPreStart,
      config.ddPreEnd,
      config.ddPostStart,
      config.ddPostEnd,
      config.ddExcludedDates,
    ],
  );

  const combinedSummary = useMemo(() => summaryTables?.combined || [], [summaryTables]);

  return { pack, combinedSummary };
}
