import { useMemo } from 'react';

// Port of the local export API (same convention as exportWorkbook.js / reportDocument.js).
// The map.html (served from /public) fetches `${base}/locations` for live Airtable data.
const EXPORT_API_PORT = import.meta.env.VITE_LOCAL_EXPORT_API_PORT || '8765';
// In production the export API lives on a deployed host (e.g. Cloud Run), not a
// local port. Prefer an explicit base, else derive it from the Sheets export URL.
const EXPORT_API_BASE =
  import.meta.env.VITE_EXPORT_API_BASE
  || (import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL
    ? import.meta.env.VITE_GOOGLE_SHEETS_EXPORT_URL.replace(/\/export\/?$/, '')
    : '');

/**
 * Store Map — full-bleed Leaflet map (app/public/map.html) of all enterprise
 * restaurant locations, pulling live records from the Airtable "Account
 * Information" table via the export API, with brand/market/status filters.
 */
export default function MapScreen() {
  const src = useMemo(() => (
    EXPORT_API_BASE
      ? `/map.html?api=${encodeURIComponent(EXPORT_API_BASE)}`
      : `/map.html?apiPort=${encodeURIComponent(EXPORT_API_PORT)}`
  ), []);

  return (
    // Break out of the padded <main> so the map fills the viewport.
    <div className="-m-6">
      <div
        className="overflow-hidden border-t border-[var(--border)] bg-[var(--surface)]"
        style={{ height: 'calc(100vh - 3.5rem)' }}
      >
        <iframe
          src={src}
          title="Enterprise Restaurant Map"
          className="w-full h-full block"
          style={{ border: 0 }}
          loading="lazy"
        />
      </div>
    </div>
  );
}
