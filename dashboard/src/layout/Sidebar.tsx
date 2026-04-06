import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Bot,
  History,
  Settings,
  ScrollText,
  Calendar,
} from "lucide-react";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/agents/monthly-reporter", label: "Monthly Report", icon: Calendar },
  { to: "/runs", label: "Runs", icon: History },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/logs", label: "Logs", icon: ScrollText },
] as const;

export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-[290px] shrink-0 flex-col border-r border-brand-100 bg-white text-ink-900 lg:flex">
      <div className="border-b border-brand-100 px-6 py-6">
        <img src="/todc-logo.png" alt="TODC" className="h-auto w-[132px]" />
        <p className="mt-4 text-[11px] font-medium uppercase tracking-[0.26em] text-ink-500">
          Agent Control
        </p>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-4">
        <p className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.24em] text-ink-400">
          Workspace
        </p>
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/" || to === "/agents" || to === "/agents/monthly-reporter"}
            className={({ isActive }) =>
              [
                "group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-brand-500 text-ink-900 shadow-soft"
                  : "text-ink-600 hover:bg-brand-50 hover:text-ink-900",
              ].join(" ")
            }
          >
            <Icon className="h-[18px] w-[18px] shrink-0 opacity-90 group-hover:opacity-100" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-brand-100 p-4">
        <div className="rounded-2xl border border-brand-100 bg-brand-50/80 p-4">
          <div className="flex items-center gap-3">
            <img
              src="/todc-emblem.png"
              alt=""
              className="h-10 w-10 rounded-xl border border-brand-100 bg-white p-1.5"
            />
            <div>
              <p className="text-xs font-medium text-ink-500">Environment</p>
              <p className="mt-1 text-sm font-semibold text-brand-600">
                development
              </p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
