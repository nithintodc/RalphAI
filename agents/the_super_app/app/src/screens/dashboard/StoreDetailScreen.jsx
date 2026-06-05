import { ArrowLeft } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import KpiCard from '../../components/ui/KpiCard';
import { fmt } from '../../lib/utils/formatters';

export default function StoreDetailScreen() {
  const { storeTables } = useDataStore();
  const { selectedStore, selectedStorePlatform, setActiveTab } = useUiStore();

  const platformKey = selectedStorePlatform || 'combined';
  const platformLabel = platformKey === 'dd' ? 'DoorDash' : platformKey === 'ue' ? 'UberEats' : 'Combined';
  const stores = storeTables?.[platformKey] || [];
  const store = stores.find(s => s.storeId === selectedStore);

  if (!store) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Store not found</p>
        <button onClick={() => setActiveTab('stores')} className="mt-3 text-[var(--accent)] text-sm cursor-pointer">Back to stores</button>
      </div>
    );
  }

  const kpis = [
    { label: 'Sales', value: store.post_sales, format: 'usd', delta: store.sales_growth_pct, yoy: store.sales_yoy_pct },
    { label: 'Payouts', value: store.post_payouts, format: 'usd', delta: store.payouts_growth_pct, yoy: store.payouts_yoy_pct },
    { label: 'Orders', value: store.post_orders, format: 'int', delta: store.orders_growth_pct, yoy: store.orders_yoy_pct },
    { label: 'AOV', value: store.post_aov, format: 'usd2', delta: store.aov_growth_pct, yoy: store.aov_yoy_pct },
    { label: 'Profitability', value: store.post_profitability, format: 'pct', delta: store.prof_growth_pct, yoy: store.prof_yoy_pct },
  ];

  const periods = [
    { label: 'Pre', metrics: ['pre_sales', 'pre_payouts', 'pre_orders', 'pre_aov', 'pre_profitability'] },
    { label: 'Post', metrics: ['post_sales', 'post_payouts', 'post_orders', 'post_aov', 'post_profitability'] },
    { label: 'Pre LY', metrics: ['preLY_sales', 'preLY_payouts', 'preLY_orders', 'preLY_aov', 'preLY_profitability'] },
    { label: 'Post LY', metrics: ['postLY_sales', 'postLY_payouts', 'postLY_orders', 'postLY_aov', 'postLY_profitability'] },
  ];

  const metricLabels = ['Sales', 'Payouts', 'Orders', 'AOV', 'Profitability'];
  const metricFormats = ['usd', 'usd', 'int', 'usd2', 'pct'];

  return (
    <div className="space-y-6">
      <button onClick={() => setActiveTab('stores')} className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--text)] cursor-pointer">
        <ArrowLeft size={16} />
        Back to Stores
      </button>

      <h2 className="text-lg font-bold text-[var(--text)]">{platformLabel} Store: {store.storeId}</h2>

      <div className="grid grid-cols-5 gap-4">
        {kpis.map(k => <KpiCard key={k.label} {...k} compact />)}
      </div>

      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--text)] mb-3">Period Comparison</h3>
        <div className="overflow-x-auto flex justify-center">
        <table className="table-auto w-max max-w-full text-sm mx-auto">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="text-center py-2 px-3 text-xs text-[var(--text-muted)]">Metric</th>
              {periods.map(p => <th key={p.label} className="text-center py-2 px-3 text-xs text-[var(--text-muted)]">{p.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {metricLabels.map((label, i) => (
              <tr key={label} className="border-b border-[var(--border)] last:border-0">
                <td className="py-2 px-3 text-center font-medium text-[var(--text)]">{label}</td>
                {periods.map(p => (
                  <td key={p.label} className="py-2 px-3 text-center tnum">
                    {fmt[metricFormats[i] === 'usd' ? 'usd' : metricFormats[i] === 'int' ? 'int' : metricFormats[i] === 'usd2' ? 'usd2' : 'pct'](store[p.metrics[i]] || 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
