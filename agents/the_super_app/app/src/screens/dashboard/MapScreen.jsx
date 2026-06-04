import { useMemo, useEffect } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import { buildStoreMetricsLookup } from '../../lib/utils/storeIdMatch';

const METRICS_STORAGE_KEY = 'superapp_store_metrics';

/**
 * Store Map — operator-scoped Leaflet map (public/map.html) with Airtable pins
 * and Post-period Sales / Payouts / AOV / Profitability in popups.
 */
export default function MapScreen() {
  const { storeTables } = useDataStore();
  const operatorName = useConfigStore((s) => s.operatorName);

  useEffect(() => {
    const metrics = buildStoreMetricsLookup(storeTables);
    try {
      sessionStorage.setItem(METRICS_STORAGE_KEY, JSON.stringify(metrics));
    } catch {
      /* ignore quota errors */
    }
  }, [storeTables]);

  const src = useMemo(() => {
    const params = new URLSearchParams();
    params.set('locationsApi', '/api/super-app/locations');
    params.set('metricsKey', METRICS_STORAGE_KEY);
    params.set('embed', '1');
    if (operatorName?.trim()) {
      params.set('operator', operatorName.trim());
    }
    const base = import.meta.env.BASE_URL || '/';
    const mapPath = `${base.endsWith('/') ? base : `${base}/`}map.html`;
    return `${mapPath}?${params.toString()}`;
  }, [operatorName]);

  if (!operatorName?.trim()) {
    return (
      <div className="card py-12 text-center">
        <p className="text-sm text-[var(--text-muted)]">
          Select an operator during configuration to view their store map.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 w-full min-w-0">
      <iframe
        key={src}
        src={src}
        title="Operator Store Map"
        className="block w-full min-w-0 flex-1 border-0 bg-[var(--surface)]"
        loading="lazy"
      />
    </div>
  );
}
