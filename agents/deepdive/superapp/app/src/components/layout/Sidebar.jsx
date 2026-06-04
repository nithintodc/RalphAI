import { LayoutDashboard, GitCompareArrows, Activity, Store, Clock, Layers, Megaphone, Shield, Package, ChevronDown, Moon, Sun, CalendarRange, LayoutGrid, MapPin } from 'lucide-react';
import { useUiStore } from '../../stores/uiStore';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', Icon: LayoutDashboard },
  { id: 'compare', label: 'Pre vs Post', Icon: GitCompareArrows, badge: 'Hero' },
  { id: 'diagnostics', label: 'Diagnostics', Icon: Activity },
  { id: 'stores', label: 'Stores', Icon: Store },
  { id: 'map', label: 'Store Map', Icon: MapPin, badge: 'Live' },
  { id: 'abComparison', label: 'A/B Comparison', Icon: GitCompareArrows },
  { id: 'slots', label: 'Slots & Heatmap', Icon: Clock },
  { id: 'buckets', label: 'Order Buckets', Icon: Layers },
  { id: 'marketing', label: 'Marketing', Icon: Megaphone },
  { id: 'operations', label: 'Operations', Icon: Shield },
  { id: 'productMix', label: 'Product Mix', Icon: Package },
  { id: 'app2DateWise', label: 'Date × day-part', Icon: CalendarRange },
  { id: 'app2Bucketing', label: 'AITF bucketing', Icon: LayoutGrid },
];

export default function Sidebar({ active, setActive, operatorName = 'Operator' }) {
  const { theme, toggleTheme } = useUiStore();

  return (
    <aside className="fixed top-0 left-0 h-screen flex flex-col border-r border-[var(--border)] bg-[var(--surface)] z-30" style={{ width: 'var(--sidebar-w)' }}>
      <div className="flex items-center gap-2.5 px-4 h-14 border-b border-[var(--border)]">
        <div className="w-8 h-8 rounded-lg bg-[var(--accent)] text-white flex items-center justify-center font-bold text-sm">R</div>
        <div className="leading-tight">
          <span className="font-semibold text-[var(--text)] text-sm">Ralph</span>
          <span className="text-[var(--text-muted)] text-sm ml-1">Analyse</span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {NAV_ITEMS.map(item => {
          const isActive = active === item.id || (active === 'storeDetail' && item.id === 'stores');
          return (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors cursor-pointer
                ${isActive
                  ? 'bg-[var(--accent-soft)] text-[var(--accent-text)] font-medium border-l-2 border-[var(--accent)]'
                  : 'text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]'
                }`}
            >
              <item.Icon size={16} />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && <span className="badge">{item.badge}</span>}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-[var(--border)] p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-subtle)]">Operator</span>
          <button onClick={toggleTheme} className="p-1 rounded hover:bg-[var(--surface-2)] text-[var(--text-muted)] cursor-pointer">
            {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        </div>
        <div className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-[var(--surface-2)] cursor-pointer">
          <div className="w-7 h-7 rounded-full bg-[var(--accent)] text-white flex items-center justify-center text-xs font-semibold">
            {operatorName.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-[var(--text)] truncate">{operatorName}</div>
          </div>
          <ChevronDown size={14} className="text-[var(--text-subtle)]" />
        </div>
      </div>
    </aside>
  );
}
