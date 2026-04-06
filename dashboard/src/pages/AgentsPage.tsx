import { Link } from "react-router-dom";
import {
  Play,
  Cpu,
  ShoppingBag,
  Megaphone,
  BarChart3,
  ArrowDownCircle,
  ArrowUpCircle,
  Calendar,
} from "lucide-react";

const agents = [
  {
    id: "deepdive",
    name: "DeepDive",
    desc: "Ingest and analyze 90-day DoorDash data; output structured report.",
    icon: BarChart3,
    status: "idle",
    color: "from-brand-500 to-brand-700",
    inputs: [
      "operator_id (TODC registry)",
      "DoorDash exports: financial, sponsored listings, promotions",
      "Optional: date_range (defaults to last 90 days)",
    ],
    outputs: [
      "deepdive.json — order_breakdown, revenue_metrics",
      "top_items, promo_performance, ads_performance",
      "anomalies[], recommendations_seed for downstream LLM",
    ],
  },
  {
    id: "marketingreco",
    name: "MarketingReco",
    desc: "Generate campaign plans from insights; approval workflow.",
    icon: Megaphone,
    status: "idle",
    color: "from-ink-700 to-black",
    inputs: [
      "deepdive_report (JSON from DeepDive)",
      "operator_profile — stores, region, tier",
      "budget_cap, campaign_history (optional)",
    ],
    outputs: [
      "marketing_plan.json — recommended_campaigns[]",
      "Per campaign: type, budget, day-parts, discount_pct, rationale",
      "approval_status: pending | approved | rejected | modified",
    ],
  },
  {
    id: "clawbot-offers",
    name: "Clawbot — Offers",
    desc: "Browser automation for promo campaigns in Merchant Portal.",
    icon: ShoppingBag,
    status: "ready",
    color: "from-brand-400 to-emerald-700",
    inputs: [
      "Approved marketing_plan (promo / combo rows)",
      "campaign_type: offers",
      "store_ids, Merchant Portal credentials (secrets)",
    ],
    outputs: [
      "setup.json — campaigns_created[] with portal campaign_id",
      "status: active | scheduled | failed per campaign",
      "review_scheduled_at (e.g. +7 days)",
    ],
  },
  {
    id: "clawbot-ads",
    name: "Clawbot — Ads",
    desc: "Sponsored listing setup and scheduling.",
    icon: Cpu,
    status: "ready",
    color: "from-brand-500 to-ink-800",
    inputs: [
      "Approved marketing_plan (sponsored_listing rows)",
      "campaign_type: ads",
      "store_ids, Merchant Portal credentials (secrets)",
    ],
    outputs: [
      "setup.json — campaigns_created[] (sponsored listings)",
      "scheduled_start / scheduled_end per campaign",
      "review_scheduled_at for /marketingperf",
    ],
  },
  {
    id: "review",
    name: "Campaign Review",
    desc: "Post-campaign metrics and /update /delete /keep /new.",
    icon: BarChart3,
    status: "idle",
    color: "from-amber-500 to-orange-600",
    inputs: [
      "active_campaigns (Clawbot setup output)",
      "post_campaign_data — 7-day DoorDash export",
      "pre_campaign_baseline (DeepDive or prior metrics)",
    ],
    outputs: [
      "campaign_review.json — per-campaign pre/post metrics",
      "recommendation: /update | /delete | /new | /keep",
      "next_review_date, optional update_params",
    ],
  },
  {
    id: "monthly-reporter",
    name: "Monthly Reporter",
    desc: "Consolidated monthly KPI rollup and narrative for operators and stakeholders.",
    icon: Calendar,
    status: "idle",
    color: "from-violet-500 to-indigo-700",
    inputs: [
      "Pre/Post date ranges (MM/DD/YYYY-MM/DD/YYYY), operator ID & name",
      "dd-data.csv, ue-data.csv; optional MARKETING_*.csv (multi-upload, Streamlit-style)",
      "Optional: exclude dates, DD/UE store ID filters",
    ],
    outputs: [
      "Full Excel export + optional date-wise Excel (in-app download)",
      "Preview tables in dashboard; artifacts under data/runs/monthly_reporter/",
      "Google Drive upload when service-account JSON is configured",
    ],
  },
  {
    id: "ingestion",
    name: "Ingestion (legacy)",
    desc: "Contract-based micro-agent for raw pulls.",
    icon: Cpu,
    status: "legacy",
    color: "from-slate-500 to-slate-700",
    inputs: [
      "operator_id, source (e.g. doordash), days (e.g. 90)",
      "JSON stdin per contracts/ingestion.json",
    ],
    outputs: [
      "Normalized buckets: orders[], revenue[], ads[], menu[]",
      "Passes to legacy DeepDive / orchestrator chain",
    ],
  },
];

function IoList({
  title,
  icon: Icon,
  items,
  variant,
}: {
  title: string;
  icon: typeof ArrowDownCircle;
  items: string[];
  variant: "in" | "out";
}) {
  return (
    <div
      className={
        variant === "in"
          ? "rounded-2xl border border-brand-100 bg-brand-50/80 dark:border-white/10 dark:bg-white/5"
          : "rounded-2xl border border-brand-200/80 bg-brand-100/50 dark:border-brand-500/20 dark:bg-brand-500/10"
      }
    >
      <div className="flex items-center gap-2 border-b border-brand-100/80 px-3 py-2 dark:border-white/10">
        <Icon
          className={`h-3.5 w-3.5 shrink-0 ${variant === "in" ? "text-ink-500" : "text-brand-700 dark:text-brand-400"}`}
        />
        <span className="text-[11px] font-bold uppercase tracking-wider text-ink-500 dark:text-white/55">
          {title}
        </span>
      </div>
      <ul className="space-y-1.5 px-3 py-2.5">
        {items.map((line) => (
          <li
            key={line}
            className="flex gap-2 text-[13px] leading-snug text-ink-600 dark:text-white/72"
          >
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-400 dark:bg-brand-500" />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AgentsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
          Agents
        </h2>
        <p className="mt-1 text-ink-600 dark:text-white/65">
          Each card lists <strong className="font-medium text-ink-700 dark:text-white">Requires</strong> (inputs) and{" "}
          <strong className="font-medium text-ink-700 dark:text-white">Produces</strong> (outputs) for chaining and contracts.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => (
          <article
            key={a.id}
            className="brand-card group flex flex-col rounded-[24px] p-5 transition hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-soft"
          >
            <div className="flex items-start justify-between gap-3">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br ${a.color} text-white shadow-soft`}
              >
                <a.icon className="h-6 w-6" />
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  a.status === "running"
                    ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                    : a.status === "legacy"
                      ? "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                      : "bg-brand-100 text-ink-900 dark:bg-brand-500/20 dark:text-brand-300"
                }`}
              >
                {a.status}
              </span>
            </div>
            <h3 className="mt-4 font-display text-lg font-semibold text-ink-900 dark:text-white">
              {a.name}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-white/65">
              {a.desc}
            </p>

            <div className="mt-4 flex flex-col gap-3">
              <IoList
                title="Requires"
                icon={ArrowDownCircle}
                items={a.inputs}
                variant="in"
              />
              <IoList
                title="Produces"
                icon={ArrowUpCircle}
                items={a.outputs}
                variant="out"
              />
            </div>

            <div className="mt-4 flex gap-2">
              {a.id === "monthly-reporter" ? (
                <Link
                  to="/agents/monthly-reporter"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </Link>
              ) : a.id === "deepdive" ? (
                <Link
                  to="/agents/deepdive"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </Link>
              ) : (
                <button
                  type="button"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </button>
              )}
              <button
                type="button"
                className="rounded-2xl border border-brand-100 px-4 py-2.5 text-sm font-medium text-ink-700 transition hover:bg-brand-50 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5"
              >
                Docs
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
