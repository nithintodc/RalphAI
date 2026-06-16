/**
 * Capture the operator store map as a PNG data URI for PDF / report export.
 * Loads map.html in a hidden iframe and waits for Leaflet + tiles before screenshot.
 */
import { buildStoreMetricsLookup } from '../utils/storeIdMatch';

export const MAP_METRICS_STORAGE_KEY = 'superapp_store_metrics';

/**
 * @param {object} config useConfigStore state (operatorName)
 * @param {object} storeTables from useDataStore
 * @returns {Promise<string|null>} PNG data URI or null when capture fails / no operator
 */
export async function captureOperatorMapScreenshot(config, storeTables) {
  const operator = (config?.operatorName || '').trim();
  if (!operator || typeof document === 'undefined') return null;

  try {
    const metrics = buildStoreMetricsLookup(storeTables || {});
    sessionStorage.setItem(MAP_METRICS_STORAGE_KEY, JSON.stringify(metrics));
  } catch {
    /* quota / private mode — map still renders without KPI tooltips */
  }

  return new Promise((resolve) => {
    const iframe = document.createElement('iframe');
    iframe.setAttribute('aria-hidden', 'true');
    iframe.tabIndex = -1;
    iframe.style.cssText = 'position:fixed;left:-10000px;top:0;width:960px;height:540px;border:0;opacity:0;pointer-events:none;';

    const params = new URLSearchParams({
      locationsApi: '/api/super-app/locations',
      metricsKey: MAP_METRICS_STORAGE_KEY,
      embed: '1',
      capture: '1',
      operator,
    });
    const base = import.meta.env.BASE_URL || '/';
    const mapPath = `${base.endsWith('/') ? base : `${base}/`}map.html`;
    iframe.src = `${mapPath}?${params.toString()}`;

    let settled = false;
    const finish = (dataUrl) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      window.removeEventListener('message', onMessage);
      iframe.remove();
      resolve(dataUrl || null);
    };

    const timer = setTimeout(() => finish(null), 28000);

    function onMessage(event) {
      if (event.source !== iframe.contentWindow) return;
      const data = event.data;
      if (!data || data.type !== 'superapp-map-capture-result') return;
      finish(typeof data.dataUrl === 'string' ? data.dataUrl : null);
    }

    window.addEventListener('message', onMessage);
    document.body.appendChild(iframe);

    iframe.addEventListener('load', () => {
      iframe.contentWindow?.postMessage({ type: 'superapp-map-capture' }, '*');
    }, { once: true });
  });
}
