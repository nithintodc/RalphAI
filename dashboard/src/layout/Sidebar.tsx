import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Grid2x2,
  History,
  ScrollText,
  Calendar,
  Settings,
  Skull,
  Activity,
  Briefcase,
  Map,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

const STORAGE_KEY = "ralph-sidebar-collapsed";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Grid2x2 },
  { to: "/store-map", label: "Store Map", icon: Map },
  { to: "/agents/health-check", label: "Health Check", icon: Activity },
  { to: "/agents/campaign-killer", label: "Campaign Killer", icon: Skull },
  { to: "/agents/the-super-app?tab=breakdown", label: "Breakdown", icon: Calendar },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/runs", label: "Runs", icon: History },
  { to: "/logs", label: "Logs", icon: ScrollText },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed));
    } catch {
      // ignore storage errors
    }
  }, [collapsed]);

  return (
    <aside
      className={[
        "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-brand-100 bg-white text-ink-900 transition-[width] duration-300 ease-in-out lg:flex",
        collapsed ? "w-[76px]" : "w-[290px]",
      ].join(" ")}
    >
      <div
        className={[
          "border-b border-brand-100 transition-all duration-300",
          collapsed ? "px-3 py-4" : "px-6 py-5",
        ].join(" ")}
      >
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          className={[
            "mb-4 flex w-full items-center rounded-2xl text-sm font-medium text-ink-600 transition hover:bg-brand-50 hover:text-ink-900",
            collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2.5",
          ].join(" ")}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[18px] w-[18px] shrink-0" />
          ) : (
            <>
              <PanelLeftClose className="h-[18px] w-[18px] shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>

        {collapsed ? (
          <img
            src="/logos/TODC.webp"
            alt="TODC"
            className="mx-auto h-10 w-10 rounded-xl bg-white p-1 object-contain shadow-soft"
          />
        ) : (
          <>
            <img src="/logos/TODC.webp" alt="TODC" className="h-auto w-[132px] object-contain" />
            <p className="mt-4 text-[11px] font-medium uppercase tracking-[0.26em] text-ink-500">
              Agent Control
            </p>
          </>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
        {!collapsed && (
          <p className="px-3 pb-2 pt-2 text-[10px] font-semibold uppercase tracking-[0.24em] text-ink-400">
            Workspace
          </p>
        )}
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/" || to === "/agents"}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              [
                "group flex items-center rounded-2xl text-sm font-medium transition-all duration-200",
                collapsed ? "justify-center px-0 py-3" : "gap-3 px-4 py-3",
                isActive
                  ? "bg-brand-500 text-ink-900 shadow-soft"
                  : "text-ink-600 hover:bg-brand-50 hover:text-ink-900",
              ].join(" ")
            }
          >
            <Icon className="h-[18px] w-[18px] shrink-0 opacity-90 group-hover:opacity-100" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
