/** Full company store map — every account's stores across the enterprise (no operator scope). */
const MAP_SRC = "/internal-apps/the-super-app/map.html?locationsApi=/api/super-app/locations";

export function StoreMapPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-4">
      <div>
        <h2 className="font-display text-xl font-semibold text-ink-900">Store Map</h2>
        <p className="text-sm text-ink-600">
          Every account and store across the company. Filter by brand, business name, market, and status.
        </p>
      </div>

      <div className="brand-card min-h-0 flex-1 overflow-hidden rounded-[28px] bg-white">
        <iframe src={MAP_SRC} className="h-full w-full border-0" title="Company Store Map" />
      </div>
    </div>
  );
}
