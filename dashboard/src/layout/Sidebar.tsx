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
} from "lucide-react";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Grid2x2 },
  { to: "/agents/health-check", label: "Health Check", icon: Activity },
  { to: "/agents/campaign-killer", label: "Campaign Killer", icon: Skull },
  { to: "/agents/monthly-reporter", label: "Monthly Report", icon: Calendar },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/runs", label: "Runs", icon: History },
  { to: "/logs", label: "Logs", icon: ScrollText },
  { to: "/settings", label: "Settings", icon: Settings },
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
            end={to === "/" || to === "/agents"}
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
    </aside>
  );
}
