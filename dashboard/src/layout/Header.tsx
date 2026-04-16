import { useLocation } from "react-router-dom";

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
    </header>
  );
}
