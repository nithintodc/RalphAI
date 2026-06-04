import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { useConfigStore } from '../../stores/configStore';

const SCREEN_META = {
  overview: { title: 'Overview', crumb: 'Dashboard' },
  compare: { title: 'Pre vs Post', crumb: 'All metrics' },
  breakdown: { title: 'Breakdown', crumb: 'Financial summary' },
  diagnostics: { title: 'Diagnostics', crumb: 'Sales decomposition' },
  stores: { title: 'Stores', crumb: 'All stores' },
  map: { title: 'Store Map', crumb: 'Operator stores · live from Airtable' },
  abComparison: { title: 'A/B Comparison', crumb: 'Tagged store groups' },
  storeDetail: { title: 'Store Detail', crumb: '' },
  slots: { title: 'Slots & Heatmap', crumb: 'Time-of-day analysis' },
  buckets: { title: 'Order Buckets', crumb: 'Ticket size distribution' },
  marketing: { title: 'Marketing', crumb: 'Corp vs TODC · Pre / Post / YoY' },
  operations: { title: 'Operations', crumb: 'Quality metrics' },
  productMix: { title: 'Product Mix', crumb: 'Item performance' },
  register: { title: 'Register', crumb: 'Layer 1 · store × day × slot · weekday avg' },
};

export default function Shell({ active, setActive, periodLabel, onExport, isExporting, children }) {
  const meta = SCREEN_META[active] || SCREEN_META.overview;
  const operatorName = useConfigStore((s) => s.operatorName) || 'Operator';
  const isMapView = active === 'map';

  return (
    <div className="superapp-shell flex min-h-screen relative min-w-0 max-w-full w-full overflow-x-hidden">
      <Sidebar active={active} setActive={setActive} operatorName={operatorName} />
      <div
        className="superapp-main flex flex-1 flex-col min-w-0 min-h-0 transition-[margin] duration-300 ease-in-out"
        style={{ marginLeft: 'var(--sidebar-w)' }}
      >
        <Topbar
          title={meta.title}
          crumb={meta.crumb}
          periodLabel={periodLabel}
          onExport={onExport}
          isExporting={isExporting}
        />
        <main
          className={
            isMapView
              ? 'flex flex-1 flex-col min-h-0 w-full min-w-0 p-0 overflow-hidden'
              : 'p-6 w-full min-w-0 overflow-x-hidden'
          }
        >
          {children}
        </main>
      </div>
    </div>
  );
}
