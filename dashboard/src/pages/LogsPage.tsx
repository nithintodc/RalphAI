import { useEffect, useMemo, useState } from "react";

type LogLine = {
  ts: string;
  level: string;
  msg: string;
};

const levelStyle: Record<string, string> = {
  INFO: "bg-sky-100 text-sky-900",
  WARN: "bg-amber-200 text-amber-950",
  ERROR: "bg-red-200 text-red-950",
};

export function LogsPage() {
  const [logs, setLogs] = useState<LogLine[]>([]);

  useEffect(() => {
    let active = true;
    async function loadLogs() {
      try {
        const res = await fetch("/api/logs/live?limit=120");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as LogLine[];
        if (active) setLogs(Array.isArray(data) ? data : []);
      } catch {
        if (active) setLogs([]);
      }
    }
    loadLogs();
    const timer = window.setInterval(loadLogs, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const visibleLogs = useMemo(() => logs, [logs]);

  function formatTs(ts: string): string {
    if (!ts) return "—";
    // Backend timestamps are UTC without a marker — append "Z" so they render in local time.
    const normalized = ts.includes("T") ? ts : `${ts.replace(" ", "T")}Z`;
    const dt = new Date(normalized);
    if (Number.isNaN(dt.getTime())) return ts;
    return dt.toLocaleTimeString([], { hour12: false });
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
          Logs
        </h2>
        <p className="mt-1 text-ink-600 dark:text-white/65">
          Live pipeline activity from your backend run history.
        </p>
      </div>

      <div className="overflow-hidden rounded-[28px] border border-brand-200 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-brand-100 bg-brand-50/90 px-4 py-3">
          <span className="text-xs font-semibold uppercase tracking-[0.22em] text-ink-600">
            Live tail
          </span>
          <button
            type="button"
            onClick={() => setLogs([])}
            className="rounded-xl border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 shadow-sm hover:bg-brand-50"
          >
            Clear
          </button>
        </div>
        <pre className="max-h-[min(70vh,560px)] overflow-auto bg-white p-4 font-mono text-[14px] leading-relaxed text-ink-900">
          {visibleLogs.length > 0 ? (
            visibleLogs.map((line, i) => (
              <div
                key={`${line.ts}-${i}`}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-brand-100 py-2.5 last:border-0 sm:flex-nowrap"
              >
                <span className="shrink-0 tabular-nums text-ink-500">{formatTs(line.ts)}</span>
                <span
                  className={`shrink-0 rounded px-2 py-0.5 text-[11px] font-bold uppercase ${levelStyle[line.level] ?? ""}`}
                >
                  {line.level}
                </span>
                <span className="min-w-0 flex-1 break-all text-ink-900">{line.msg}</span>
              </div>
            ))
          ) : (
            <div className="py-3 text-sm text-ink-500">No live log lines yet. Trigger an agent run to stream entries.</div>
          )}
        </pre>
      </div>
    </div>
  );
}
