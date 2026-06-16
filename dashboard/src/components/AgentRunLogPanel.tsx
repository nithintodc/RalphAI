import { useEffect, useMemo, useRef } from "react";
import { AGENT_LOG_VISIBLE_LINES, type AgentRunAgent } from "../lib/agentRunPolling";

const levelStyle: Record<string, string> = {
  INFO: "bg-sky-100 text-sky-900",
  WARNING: "bg-amber-200 text-amber-950",
  WARN: "bg-amber-200 text-amber-950",
  ERROR: "bg-red-200 text-red-950",
  DEBUG: "bg-slate-100 text-slate-800",
};

type Props = {
  agent: AgentRunAgent;
  runId: string | null;
  status?: string | null;
  queuePosition?: number | null;
  lines: string[];
  className?: string;
};

function parseLogLine(raw: string): { ts: string; level: string; msg: string } {
  const parts = raw.split(" | ");
  if (parts.length >= 4) {
    return {
      ts: parts[0],
      level: parts[1].trim(),
      msg: parts.slice(3).join(" | "),
    };
  }
  return { ts: "", level: "INFO", msg: raw };
}

export function AgentRunLogPanel({
  agent,
  runId,
  status,
  queuePosition,
  lines,
  className = "",
}: Props) {
  const tailRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const el = tailRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  const parsed = useMemo(
    () => lines.slice(-AGENT_LOG_VISIBLE_LINES).map(parseLogLine),
    [lines],
  );
  const statusLabel = (status || "—").toLowerCase();

  return (
    <div className={`overflow-hidden rounded-[24px] border border-brand-200 bg-white shadow-card ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-brand-100 bg-brand-50/90 px-4 py-3">
        <span className="text-xs font-semibold uppercase tracking-[0.22em] text-ink-600">
          Run log — {agent}
        </span>
        <div className="flex flex-wrap items-center gap-2 text-xs text-ink-600">
          {runId ? <span className="font-mono">{runId.slice(0, 8)}…</span> : null}
          {statusLabel === "queued" && queuePosition != null && queuePosition > 0 ? (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-900">
              Queue position {queuePosition}
            </span>
          ) : null}
          {status ? (
            <span className="rounded-full bg-white px-2 py-0.5 font-medium capitalize ring-1 ring-brand-200">
              {statusLabel}
            </span>
          ) : null}
        </div>
      </div>
      <pre
        ref={tailRef}
        className="overflow-hidden bg-white p-4 font-mono text-[13px] leading-relaxed text-ink-900"
      >
        {parsed.length > 0 ? (
          parsed.map((line, i) => (
            <div
              key={`${line.ts}-${i}`}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-brand-100 py-2 last:border-0 sm:flex-nowrap"
            >
              {line.ts ? <span className="shrink-0 tabular-nums text-ink-500">{line.ts}</span> : null}
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${levelStyle[line.level] ?? "bg-slate-100 text-slate-800"}`}
              >
                {line.level}
              </span>
              <span className="min-w-0 flex-1 break-all text-ink-900">{line.msg}</span>
            </div>
          ))
        ) : (
          <div className="text-sm text-ink-500">
            {statusLabel === "queued"
              ? "Waiting in browser queue (Offers → Ads → Strategist)…"
              : "Log lines will appear here as the run progresses."}
          </div>
        )}
      </pre>
    </div>
  );
}
