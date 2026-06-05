import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
} from "lucide-react";
type RunRecord = {
  id: string;
  agent: string;
  operator?: string;
  status?: string;
  started?: string;
  duration?: string;
};

function parseDurationToSeconds(duration?: string): number | null {
  if (!duration) return null;
  const minMatch = duration.match(/(\d+)\s*m/);
  const secMatch = duration.match(/(\d+)\s*s/);
  const mins = minMatch ? Number(minMatch[1]) : 0;
  const secs = secMatch ? Number(secMatch[1]) : 0;
  const total = mins * 60 + secs;
  if (!Number.isFinite(total) || total <= 0) return null;
  return total;
}

function formatSeconds(total: number | null): string {
  if (total == null || !Number.isFinite(total) || total <= 0) return "—";
  const mins = Math.floor(total / 60);
  const secs = Math.round(total % 60);
  return `${mins}m ${String(secs).padStart(2, "0")}s`;
}

function parseRunStart(raw?: string): Date | null {
  if (!raw) return null;
  // Index timestamps are UTC without a timezone marker ("YYYY-MM-DD HH:MM:SS") —
  // append "Z" so they aren't misread as local time.
  const normalized = raw.includes("T") ? raw : `${raw.replace(" ", "T")}Z`;
  const dt = new Date(normalized);
  if (Number.isNaN(dt.getTime())) return null;
  return dt;
}

function timeAgo(raw?: string): string {
  const dt = parseRunStart(raw);
  if (!dt) return "just now";
  const deltaSec = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 1000));
  if (deltaSec < 60) return "just now";
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)} min ago`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)} hr ago`;
  return `${Math.floor(deltaSec / 86400)} day ago`;
}

function displayAgentName(agent: string): string {
  const map: Record<string, string> = {
    deepdive: "DeepDive (Legacy)",
    marketingreco: "MarketingReco",
    monthly_reporter: "Monthly Reporter (legacy)",
    campaign_review: "Campaign Review",
    data_run: "Data Run",
    strategist: "Strategist",
    health_check: "Health Check",
    campaign_killer: "Campaign Killer",
    offers: "RalphAI Offers",
    ads: "RalphAI Ads",
  };
  return map[agent] ?? agent;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunRecord[]>([]);

  useEffect(() => {
    let active = true;
    async function loadRuns() {
      try {
        const res = await fetch("/api/runs");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as RunRecord[];
        if (active) setRuns(Array.isArray(data) ? data : []);
      } catch {
        if (active) setRuns([]);
      }
    }
    loadRuns();
    const timer = window.setInterval(loadRuns, 15000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const stats = useMemo(() => {
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
      now.getDate(),
    ).padStart(2, "0")}`;
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    const runsToday = runs.filter((r) => {
      const dt = parseRunStart(r.started);
      if (!dt) return false;
      const local = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(
        dt.getDate(),
      ).padStart(2, "0")}`;
      return local === today;
    }).length;
    const lastDayRuns = runs.filter((r) => {
      const dt = parseRunStart(r.started);
      return dt ? dt >= oneDayAgo : false;
    });
    const activeAgents = new Set(lastDayRuns.map((r) => r.agent).filter(Boolean)).size;

    const weekRuns = runs.filter((r) => {
      const dt = parseRunStart(r.started);
      return dt ? dt >= sevenDaysAgo : false;
    });
    const successCount = weekRuns.filter((r) => (r.status ?? "").toLowerCase() === "success").length;
    const successRate = weekRuns.length ? `${((successCount / weekRuns.length) * 100).toFixed(1)}%` : "—";

    const durationSec = runs
      .map((r) => parseDurationToSeconds(r.duration))
      .filter((x): x is number => x != null);
    const avgDuration =
      durationSec.length > 0
        ? formatSeconds(durationSec.reduce((sum, curr) => sum + curr, 0) / durationSec.length)
        : "—";

    return [
      {
        label: "Active agents",
        value: String(activeAgents),
        sub: "In the last 24 hours",
        icon: Bot,
        color: "from-brand-400 to-brand-600",
      },
      {
        label: "Runs today",
        value: String(runsToday),
        sub: "Live from run history",
        icon: Activity,
        color: "from-ink-700 to-ink-900",
      },
      {
        label: "Success rate",
        value: successRate,
        sub: "Last 7 days",
        icon: CheckCircle2,
        color: "from-brand-500 to-emerald-700",
      },
      {
        label: "Avg. duration",
        value: avgDuration,
        sub: "Across recent runs",
        icon: Clock,
        color: "from-ink-500 to-ink-700",
      },
    ];
  }, [runs]);

  const recent = useMemo(
    () =>
      runs.slice(0, 5).map((r) => ({
        id: r.id,
        agent: displayAgentName(r.agent),
        op: r.operator ?? "—",
        status: r.status ?? "unknown",
        time: timeAgo(r.started),
      })),
    [runs],
  );

  return (
    <div className="flex flex-col gap-8">
      <section className="brand-card overflow-hidden rounded-[28px] border border-white/70 p-6 sm:p-7">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <div className="inline-flex items-center rounded-full bg-brand-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-ink-900">
              TODC Overview
            </div>
            <h2 className="mt-4 max-w-2xl font-display text-3xl font-semibold tracking-tight text-ink-900 dark:text-white sm:text-4xl">
              TODC — drive your delivery business, smartly
            </h2>
          </div>
          <div className="flex shrink-0 flex-col items-end justify-end gap-1.5 sm:pb-0.5">
            <img
              src="/logos/TODC.webp"
              alt="TODC"
              className="h-11 w-auto max-w-[min(220px,42vw)] object-contain sm:h-14"
            />
            <p className="text-[9px] font-medium uppercase tracking-[0.16em] text-ink-500 dark:text-white/50">
              The On Demand Company
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ label, value, sub, icon: Icon, color }) => (
          <div
            key={label}
            className="brand-card relative overflow-hidden rounded-[24px] p-5"
          >
            <div
              className={`absolute -right-7 -top-7 h-28 w-28 rounded-full bg-gradient-to-br ${color} opacity-[0.16] blur-2xl`}
            />
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-ink-500 dark:text-white/55">
                  {label}
                </p>
                <p className="mt-1 font-display text-3xl font-semibold text-ink-900 dark:text-white">
                  {value}
                </p>
                <p className="mt-1 text-xs text-ink-500 dark:text-white/50">{sub}</p>
              </div>
              <div
                className={`flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br ${color} text-white shadow-soft`}
              >
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="brand-card rounded-[28px] p-6 lg:col-span-3">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
              Recent activity
            </h3>
            <Link
              to="/runs"
              className="flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800 dark:text-brand-400"
            >
              View all
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <ul className="mt-4 divide-y divide-brand-100/80 dark:divide-white/10">
            {recent.length > 0 ? (
              recent.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between gap-4 py-4 first:pt-0 last:pb-0"
                >
                  <div>
                    <p className="font-medium text-ink-900 dark:text-white">
                      {r.agent}
                    </p>
                    <p className="text-sm text-ink-500 dark:text-white/55">
                      {r.op} · {r.id}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        r.status === "success"
                          ? "bg-brand-100 text-ink-900 dark:bg-brand-500/20 dark:text-brand-300"
                          : r.status === "failed"
                            ? "bg-red-100 text-red-800 dark:bg-red-950/40 dark:text-red-400"
                            : "bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400"
                      }`}
                    >
                      {r.status}
                    </span>
                    <p className="mt-1 text-xs text-ink-400 dark:text-white/40">{r.time}</p>
                  </div>
                </li>
              ))
            ) : (
              <li className="py-4 text-sm text-ink-500">No runs yet. Start an agent to see live activity.</li>
            )}
          </ul>
        </div>

        <div className="overflow-hidden rounded-[28px] bg-gradient-to-br from-ink-900 via-ink-800 to-black p-6 text-white shadow-xl lg:col-span-2">
          <div className="inline-flex rounded-full bg-brand-500 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-ink-900">
            Quick actions
          </div>
          <p className="mt-4 text-sm text-white/72">
            Trigger common flows without touching the CLI.
          </p>
          <ul className="mt-4 space-y-2">
            {[
              {
                label: "Health Check — WoW analysis",
                onClick: () => {
                  navigate("/agents/health-check");
                },
              },
              {
                label: "MarketingReco — plan generation",
                onClick: () => {
                  navigate("/agents/marketingreco");
                },
              },
              {
                label: "Review — 7-day performance",
                onClick: () => {
                  navigate("/agents/campaign-review");
                },
              },
              {
                label: "Breakdown — financial summary",
                onClick: () => {
                  navigate("/agents/the-super-app?tab=breakdown");
                },
              },
            ].map((t) => (
              <li key={typeof t === "string" ? t : t.label}>
                <button
                  type="button"
                  onClick={typeof t === "object" ? t.onClick : undefined}
                  className="flex w-full items-center justify-between rounded-2xl border border-white/10 bg-white/6 px-4 py-3 text-left text-sm font-medium backdrop-blur transition hover:bg-white/10"
                >
                  {typeof t === "string" ? t : t.label}
                  <ArrowRight className="h-4 w-4 opacity-70" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
