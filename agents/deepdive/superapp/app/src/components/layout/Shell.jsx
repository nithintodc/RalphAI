import Sidebar from './Sidebar';
import Topbar from './Topbar';

const SCREEN_META = {
  overview: { title: 'Overview', crumb: 'Dashboard' },
  compare: { title: 'Pre vs Post', crumb: 'All metrics' },
  diagnostics: { title: 'Diagnostics', crumb: 'Sales decomposition' },
  stores: { title: 'Stores', crumb: 'All stores' },
  map: { title: 'Store Map', crumb: 'Account locations · live from Airtable' },
  abComparison: { title: 'A/B Comparison', crumb: 'Tagged store groups' },
  storeDetail: { title: 'Store Detail', crumb: '' },
  slots: { title: 'Slots & Heatmap', crumb: 'Time-of-day analysis' },
  buckets: { title: 'Order Buckets', crumb: 'Ticket size distribution' },
  marketing: { title: 'Marketing', crumb: 'Corp vs TODC · Pre / Post / YoY' },
  operations: { title: 'Operations', crumb: 'Quality metrics' },
  productMix: { title: 'Product Mix', crumb: 'Item performance' },
  app2DateWise: { title: 'Date × day-part', crumb: 'App 2.0 · Post period detail' },
  app2Bucketing: { title: 'AITF bucketing', crumb: 'App 2.0 · Store × period rollups' },
};

export default function Shell({ active, setActive, periodLabel, onExport, isExporting, children }) {
  const meta = SCREEN_META[active] || SCREEN_META.overview;

  return (
    <div className="flex min-h-screen relative">
      <Sidebar active={active} setActive={setActive} />
      <div className="flex-1" style={{ marginLeft: 'var(--sidebar-w)' }}>
        <Topbar
          title={meta.title}
          crumb={meta.crumb}
          periodLabel={periodLabel}
          onExport={onExport}
          isExporting={isExporting}
        />
        <main className="p-6 max-w-[1440px]">
          {children}
        </main>
      </div>
    </div>
  );
}
