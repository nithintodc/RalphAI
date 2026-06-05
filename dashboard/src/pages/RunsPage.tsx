import { useEffect, useState } from "react";
import { Filter, Loader2 } from "lucide-react";
type RunRow = {
  id: string;
  agent: string;
  operator: string;
  status: string;
  started: string;
  duration: string;
};

const statusStyle: Record<string, string> = {
  success: "bg-brand-100 text-ink-900 dark:bg-brand-500/20 dark:text-brand-300",
  running:
    "bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400",
  failed: "bg-red-50 text-red-800 dark:bg-red-950/50 dark:text-red-400",
};

function formatStarted(raw: string): string {
  if (!raw) return "—";
  // Backend timestamps are UTC without a marker — append "Z" so they render in local time.
  const normalized = raw.includes("T") ? raw : `${raw.replace(" ", "T")}Z`;
  const dt = new Date(normalized);
  if (Number.isNaN(dt.getTime())) return raw;
  return dt.toLocaleString([], { hour12: false });
}

export function RunsPage() {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiNote, setApiNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/runs");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as Array<{
          id: string;
          agent: string;
          operator: string;
          status: string;
          started: string;
          duration: string;
        }>;
        if (cancelled) return;
        setRuns(Array.isArray(data) ? data : []);
        setApiNote(Array.isArray(data) && data.length > 0 ? null : "No API runs yet.");
      } catch {
        if (!cancelled) {
          setRuns([]);
          setApiNote("API unavailable. Start the API to record and view runs.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
            Runs
          </h2>
          <p className="mt-1 text-ink-600 dark:text-white/65">
            History of pipeline executions across TODC workflows. Monthly Reporter rows come from the local API when
            enabled.
          </p>
          {loading ? (
            <p className="mt-2 inline-flex items-center gap-2 text-xs text-ink-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading run history…
            </p>
          ) : null}
          {apiNote ? (
            <p className="mt-2 rounded-2xl border border-brand-100 bg-brand-50/80 px-3 py-2 text-xs text-ink-600">
              {apiNote}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl border border-brand-100 bg-white px-4 py-2.5 text-sm font-medium text-ink-700 shadow-sm dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
        >
          <Filter className="h-4 w-4" />
          Filters
        </button>
      </div>

      <div className="brand-card overflow-hidden rounded-[28px]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-brand-100 bg-brand-50/80 dark:border-white/10 dark:bg-white/5">
                <th className="px-5 py-3 font-semibold text-ink-700 dark:text-slate-300">
                  Run ID
                </th>
                <th className="px-5 py-3 font-semibold text-ink-700 dark:text-slate-300">
                  Agent
                </th>
                <th className="px-5 py-3 font-semibold text-ink-700 dark:text-slate-300">
                  Operator
                </th>
                <th className="px-5 py-3 font-semibold text-ink-700 dark:text-slate-300">
                  Status
                </th>
                <th className="px-5 py-3 font-semibold text-ink-700 dark:text-slate-300">
                  Started
                </th>
                <th className="px-5 py-3 font-semibold text-ink-700 dark:text-slate-300">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-100/80 dark:divide-white/10">
              {runs.length > 0 ? (
                runs.map((r) => (
                  <tr
                    key={`${r.id}-${r.started}`}
                    className="transition hover:bg-brand-50/70 dark:hover:bg-white/5"
                  >
                    <td className="px-5 py-3 font-mono text-xs text-ink-600 dark:text-slate-400">
                      {r.id}
                    </td>
                    <td className="px-5 py-3 font-medium text-ink-900 dark:text-white">
                      {r.agent}
                    </td>
                    <td className="px-5 py-3 text-ink-600 dark:text-white/60">
                      {r.operator}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${statusStyle[r.status] ?? ""}`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-ink-600 dark:text-white/60">
                      {formatStarted(r.started)}
                    </td>
                    <td className="px-5 py-3 text-ink-600 dark:text-white/60">
                      {r.duration}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-sm text-ink-500 dark:text-white/60">
                    No runs recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
