import { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  GitCompareArrows,
  Activity,
  Store,
  Clock,
  Layers,
  Megaphone,
  Shield,
  Package,
  ChevronDown,
  Moon,
  Sun,
  MapPin,
  Database,
  Table2,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useUiStore } from '../../stores/uiStore';
import { logoAssetUrl } from '../../lib/brand/brandLogos';

const STORAGE_KEY = 'superapp-sidebar-collapsed';
const SIDEBAR_EXPANDED = '232px';
const SIDEBAR_COLLAPSED = '76px';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', Icon: LayoutDashboard },
  { id: 'compare', label: 'Pre vs Post', Icon: GitCompareArrows, badge: 'Hero' },
  { id: 'breakdown', label: 'Breakdown', Icon: Table2 },
  { id: 'diagnostics', label: 'Diagnostics', Icon: Activity },
  { id: 'stores', label: 'Stores', Icon: Store },
  { id: 'map', label: 'Store Map', Icon: MapPin, badge: 'Live' },
  { id: 'abComparison', label: 'A/B Comparison', Icon: GitCompareArrows },
  { id: 'slots', label: 'Slots & Heatmap', Icon: Clock },
  { id: 'buckets', label: 'Order Buckets', Icon: Layers },
  { id: 'marketing', label: 'Marketing', Icon: Megaphone },
  { id: 'operations', label: 'Operations', Icon: Shield },
  { id: 'productMix', label: 'Product Mix', Icon: Package },
  { id: 'register', label: 'Register', Icon: Database },
];

function setSidebarWidth(collapsed) {
  document.documentElement.style.setProperty(
    '--sidebar-w',
    collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED,
  );
}

export default function Sidebar({ active, setActive, operatorName = 'Operator' }) {
  const { theme, toggleTheme } = useUiStore();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const isCollapsed = localStorage.getItem(STORAGE_KEY) === 'true';
      setSidebarWidth(isCollapsed);
      return isCollapsed;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    setSidebarWidth(collapsed);
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed));
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <aside
      className="fixed top-0 left-0 z-30 flex h-screen flex-col overflow-hidden border-r border-[var(--border)] bg-[var(--surface)] transition-[width] duration-300 ease-in-out"
      style={{ width: 'var(--sidebar-w)' }}
    >
      <div
        className={`shrink-0 overflow-hidden border-b border-[var(--border)] ${
          collapsed ? 'px-2 py-3' : 'px-3 py-3'
        }`}
      >
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          className={`mb-3 flex w-full items-center rounded-md text-xs font-medium text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text)] cursor-pointer ${
            collapsed ? 'justify-center px-0 py-2' : 'gap-2 px-2 py-2'
          }`}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} />
          ) : (
            <>
              <PanelLeftClose size={18} className="shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>

        {collapsed ? (
          <img
            src={logoAssetUrl('todc')}
            alt="TODC"
            className="mx-auto h-8 w-8 rounded-md object-contain"
          />
        ) : (
          <>
            <img
              src={logoAssetUrl('todc')}
              alt="TODC"
              className="mb-2 h-8 w-auto max-w-full object-contain object-left"
            />
            <p className="truncate text-sm font-semibold text-[var(--text)]">Ralph Analyse</p>
            <p
              className="mt-0.5 truncate text-[10px] leading-snug text-[var(--text-subtle)]"
              title="DoorDash & Uber Eats — Pre vs Post partnership analytics"
            >
              {'DD & UE · Pre vs Post'}
            </p>
          </>
        )}
      </div>

      <nav className={`flex-1 overflow-y-auto py-1 space-y-0.5 ${collapsed ? 'px-1.5' : 'px-2'}`}>
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.id || (active === 'storeDetail' && item.id === 'stores');
          return (
            <button
              key={item.id}
              type="button"
              title={collapsed ? item.label : undefined}
              onClick={() => setActive(item.id)}
              className={`relative w-full flex items-center rounded-md text-sm transition-colors cursor-pointer
                ${collapsed ? 'justify-center px-0 py-2' : 'gap-2.5 px-3 py-1.5'}
                ${isActive
                  ? collapsed
                    ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]'
                    : 'bg-[var(--accent-soft)] text-[var(--accent-text)] font-medium border-l-2 border-[var(--accent)]'
                  : 'text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]'
                }`}
            >
              <item.Icon size={16} className="shrink-0" />
              {!collapsed && (
                <>
                  <span className="flex-1 text-left truncate">{item.label}</span>
                  {item.badge && <span className="badge shrink-0">{item.badge}</span>}
                </>
              )}
              {collapsed && item.badge && (
                <span
                  className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-[var(--accent)]"
                  aria-hidden
                />
              )}
            </button>
          );
        })}
      </nav>

      <div className={`border-t border-[var(--border)] ${collapsed ? 'p-2' : 'p-3'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center mb-2' : 'justify-between mb-2'}`}>
          {!collapsed && (
            <span className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-subtle)]">
              Operator
            </span>
          )}
          <button
            type="button"
            onClick={toggleTheme}
            title={theme === 'light' ? 'Dark mode' : 'Light mode'}
            className="p-1 rounded hover:bg-[var(--surface-2)] text-[var(--text-muted)] cursor-pointer"
          >
            {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
          </button>
        </div>
        <div
          className={`flex items-center rounded-md hover:bg-[var(--surface-2)] cursor-pointer ${
            collapsed ? 'justify-center p-1.5' : 'gap-2 px-2 py-1.5'
          }`}
          title={collapsed ? operatorName : undefined}
        >
          <div className="w-7 h-7 shrink-0 rounded-full bg-[var(--accent)] text-white flex items-center justify-center text-xs font-semibold">
            {operatorName.charAt(0).toUpperCase()}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[var(--text)] truncate">{operatorName}</div>
              </div>
              <ChevronDown size={14} className="text-[var(--text-subtle)] shrink-0" />
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
