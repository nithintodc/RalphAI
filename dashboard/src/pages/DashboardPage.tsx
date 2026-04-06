import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
  Zap,
} from "lucide-react";

const stats = [
  {
    label: "Active agents",
    value: "6",
    sub: "All healthy",
    icon: Bot,
    color: "from-brand-400 to-brand-600",
  },
  {
    label: "Runs today",
    value: "24",
    sub: "+12% vs yesterday",
    icon: Activity,
    color: "from-ink-700 to-ink-900",
  },
  {
    label: "Success rate",
    value: "98.2%",
    sub: "Last 7 days",
    icon: CheckCircle2,
    color: "from-brand-500 to-emerald-700",
  },
  {
    label: "Avg. duration",
    value: "2m 14s",
    sub: "Per pipeline step",
    icon: Clock,
    color: "from-ink-500 to-ink-700",
  },
];

const recent = [
  {
    id: "run_8f2a",
    agent: "DeepDive",
    op: "op_north_01",
    status: "success",
    time: "2 min ago",
  },
  {
    id: "run_8f29",
    agent: "MarketingReco",
    op: "op_north_01",
    status: "success",
    time: "8 min ago",
  },
  {
    id: "run_8f28",
    agent: "Campaign Setup",
    op: "op_west_04",
    status: "running",
    time: "12 min ago",
  },
];

export function DashboardPage() {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col gap-8">
      <section className="brand-card overflow-hidden rounded-[28px] border border-white/70 p-6 sm:p-7">
        <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
          <div>
            <div className="inline-flex items-center rounded-full bg-brand-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-ink-900">
              TODC Overview
            </div>
            <h2 className="mt-4 max-w-2xl font-display text-3xl font-semibold tracking-tight text-ink-900 dark:text-white sm:text-4xl">
              Operate campaigns with the same tone as the TODC brand.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-ink-600 dark:text-white/70 sm:text-base">
              Monitor agents, launch growth workflows, and keep restaurant performance
              visible from one branded control surface.
            </p>
          </div>
          <div className="brand-grid rounded-[24px] border border-brand-200/70 bg-brand-50/70 p-5 dark:border-brand-500/20 dark:bg-white/5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-ink-500 dark:text-white/50">
              Live Priority
            </p>
            <p className="mt-3 font-display text-2xl font-semibold text-ink-900 dark:text-white">
              Merchant Portal Campaign Launch
            </p>
            <p className="mt-2 text-sm leading-6 text-ink-600 dark:text-white/65">
              DeepDive and MarketingReco are aligned for the next promotion cycle.
            </p>
            <Link
              to="/agents"
              className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-ink-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
            >
              <Zap className="h-4 w-4" />
              Run agent
            </Link>
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
            {recent.map((r) => (
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
                        : "bg-amber-50 text-amber-800 dark:bg-amber-950/50 dark:text-amber-400"
                    }`}
                  >
                    {r.status}
                  </span>
                  <p className="mt-1 text-xs text-ink-400 dark:text-white/40">{r.time}</p>
                </div>
              </li>
            ))}
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
                label: "DeepDive — 90 day analysis",
                onClick: () => {
                  navigate("/agents/deepdive");
                },
              },
              { label: "MarketingReco — plan generation" },
              { label: "Review — 7-day performance" },
              { label: "Monthly Reporter — KPI rollup" },
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
