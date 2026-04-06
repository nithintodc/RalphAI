import { useLocation } from "react-router-dom";
import { Bell, Search, ChevronDown } from "lucide-react";

const titles: Record<string, string> = {
  "/": "Dashboard",
  "/agents": "Agents",
  "/agents/monthly-reporter": "Monthly Reporter",
  "/runs": "Runs",
  "/settings": "Settings",
  "/logs": "Logs",
};

export function Header() {
  const { pathname } = useLocation();
  const title = titles[pathname] ?? "Dashboard";

  return (
    <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-brand-100 bg-white px-5 py-4 sm:px-6 lg:px-8">
      <div className="flex items-start gap-3">
        <img
          src="/todc-emblem.png"
          alt=""
          className="h-11 w-11 rounded-2xl bg-white p-1 shadow-soft lg:hidden"
        />
        <div>
          <div className="mb-1 inline-flex items-center rounded-full bg-brand-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-900">
            TODC
          </div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-ink-900 dark:text-white">
            {title}
          </h1>
          <p className="text-sm text-ink-500 dark:text-white/60">
            Digital marketing operations for restaurant growth
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
          <input
            type="search"
            placeholder="Search operators, runs, campaigns..."
            className="h-11 w-72 rounded-2xl border border-brand-100 bg-brand-50/70 pl-10 pr-4 text-sm text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/10 dark:bg-white/5 dark:text-slate-100"
          />
        </div>
        <button
          type="button"
          className="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-brand-100 bg-white text-ink-600 transition hover:bg-brand-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10"
          aria-label="Notifications"
        >
          <Bell className="h-[18px] w-[18px]" />
          <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-brand-500 ring-2 ring-white dark:ring-ink-900" />
        </button>
        <button
          type="button"
          className="flex items-center gap-2 rounded-2xl border border-brand-100 bg-white py-1.5 pl-2 pr-3 text-left dark:border-white/10 dark:bg-white/5"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 text-xs font-semibold text-ink-900">
            TD
          </div>
          <span className="hidden text-sm font-medium text-ink-700 dark:text-slate-200 sm:block">
            TODC Ops
          </span>
          <ChevronDown className="h-4 w-4 text-ink-400" />
        </button>
      </div>
    </header>
  );
}
