const logs = [
  { ts: "14:32:01.042", level: "INFO", msg: "flow-manager pipeline.deepdive.start operator_id=op_north_01" },
  { ts: "14:32:01.108", level: "INFO", msg: "ingestion-agent ingestion.done keys=[orders, revenue, ads, menu]" },
  { ts: "14:32:01.112", level: "INFO", msg: "deepdive-agent deepdive.done n_insights=1" },
  { ts: "14:28:55.301", level: "WARN", msg: "campaign_setup retry scheduled idempotency_key=plan_abc" },
  { ts: "14:15:22.000", level: "ERROR", msg: "campaign_review missing post_campaign_data — using stub metrics" },
];

const levelStyle: Record<string, string> = {
  INFO: "bg-sky-100 text-sky-900",
  WARN: "bg-amber-200 text-amber-950",
  ERROR: "bg-red-200 text-red-950",
};

export function LogsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
          Logs
        </h2>
        <p className="mt-1 text-ink-600 dark:text-white/65">
          Structured pipeline output — sample data; stream from your backend later.
        </p>
      </div>

      <div className="overflow-hidden rounded-[28px] border border-brand-200 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-brand-100 bg-brand-50/90 px-4 py-3">
          <span className="text-xs font-semibold uppercase tracking-[0.22em] text-ink-600">
            Live tail (mock)
          </span>
          <button
            type="button"
            className="rounded-xl border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-ink-700 shadow-sm hover:bg-brand-50"
          >
            Clear
          </button>
        </div>
        <pre className="max-h-[min(70vh,560px)] overflow-auto bg-white p-4 font-mono text-[14px] leading-relaxed text-ink-900">
          {logs.map((line, i) => (
            <div
              key={i}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-brand-100 py-2.5 last:border-0 sm:flex-nowrap"
            >
              <span className="shrink-0 tabular-nums text-ink-500">{line.ts}</span>
              <span
                className={`shrink-0 rounded px-2 py-0.5 text-[11px] font-bold uppercase ${levelStyle[line.level] ?? ""}`}
              >
                {line.level}
              </span>
              <span className="min-w-0 flex-1 break-all text-ink-900">{line.msg}</span>
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
