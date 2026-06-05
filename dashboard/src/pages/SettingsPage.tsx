import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Moon, Sun, Link2, ChevronRight } from "lucide-react";

export function SettingsPage() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    if (dark) document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  }, [dark]);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8">
      <div>
        <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
          Settings
        </h2>
        <p className="mt-1 text-ink-600 dark:text-white/65">
          Appearance and API connection. Values persist in localStorage when wired.
        </p>
      </div>

      <section className="brand-card rounded-[28px] p-6">
        <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
          Appearance
        </h3>
        <div className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-brand-100 bg-brand-50/70 p-4 dark:border-white/10 dark:bg-white/5">
          <div>
            <p className="font-medium text-ink-900 dark:text-white">Dark mode</p>
            <p className="text-sm text-ink-500 dark:text-white/55">
              Reduce glare for long monitoring sessions.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setDark(!dark)}
            className="flex h-11 w-11 items-center justify-center rounded-2xl border border-brand-100 bg-white text-ink-700 transition hover:bg-brand-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
            aria-label="Toggle dark mode"
          >
            {dark ? (
              <Sun className="h-5 w-5 text-amber-500" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </button>
        </div>
      </section>

      <section className="brand-card rounded-[28px] p-6">
        <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
          API
        </h3>
        <p className="mt-1 text-sm text-ink-500 dark:text-white/55">
          Point the dashboard at your FastAPI or orchestrator host. Dev proxy
          maps <code className="rounded bg-brand-100 px-1 dark:bg-white/10">/api</code>{" "}
          → <code className="rounded bg-brand-100 px-1 dark:bg-white/10">127.0.0.1:8000</code>.
        </p>
        <label className="mt-4 block">
          <span className="text-sm font-medium text-ink-700 dark:text-slate-300">
            Base URL
          </span>
          <input
            type="url"
            defaultValue="http://127.0.0.1:8000"
            className="mt-2 w-full rounded-2xl border border-brand-100 bg-white px-4 py-3 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/10 dark:bg-white/5 dark:text-slate-100"
          />
        </label>
      </section>

      <section className="brand-card rounded-[28px] p-6">
        <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
          Browser automation
        </h3>
        <p className="mt-1 text-sm text-ink-500 dark:text-white/55">
          Map Airtable operators to Multilogin browser profiles. Used by Health Check, Data Run,
          Strategist, and all browser-use agents.
        </p>
        <Link
          to="/settings/operator-mapping"
          className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-brand-100 bg-brand-50/70 p-4 transition hover:border-brand-300 hover:bg-brand-50 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-500/40"
        >
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
              <Link2 className="h-5 w-5" />
            </span>
            <div>
              <p className="font-medium text-ink-900 dark:text-white">
                Operator ↔ Multilogin mapping
              </p>
              <p className="mt-0.5 text-sm text-ink-500 dark:text-white/55">
                Venn view, edit assignments, save JSON + CSV
              </p>
            </div>
          </div>
          <ChevronRight className="h-5 w-5 shrink-0 text-ink-400" />
        </Link>
      </section>

      <section className="brand-card rounded-[28px] p-6">
        <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
          Data directory
        </h3>
        <p className="mt-1 text-sm text-ink-500 dark:text-white/55">
          TODC agents write under <code className="font-mono text-xs">data/operators/</code>.
          Set <code className="font-mono text-xs">TODC_DATA_DIR</code> on the server.
        </p>
      </section>
    </div>
  );
}
