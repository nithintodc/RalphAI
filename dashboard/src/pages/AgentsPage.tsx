import { Link } from "react-router-dom";
import {
  Play,
  Cpu,
  Bot,
  ShoppingBag,
  Megaphone,
  BarChart3,
  Calendar,
} from "lucide-react";

const agents = [
  {
    id: "data-run",
    name: "Data Run",
    desc: "Sequential report downloader by selected operators (fresh browser session per operator).",
    icon: Bot,
    status: "ready",
    color: "from-sky-500 to-cyan-700",
    inputs: [
      "Operators (multi-select) from account directory CSV",
      "Always pulls both financial and marketing reports",
      "DoorDash credentials auto-loaded from Account Information CSV",
    ],
    outputs: [
      "Downloaded report files under data/runs/data_run/",
      "Per-operator status: success | no_files | failed",
      "Run summary with selected file count per operator",
    ],
  },
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
    desc: "Two tracks: Offers (promotion mappings to keep) and Ads",
    icon: Megaphone,
    status: "idle",
    color: "from-ink-700 to-black",
    inputs: [
      "Manual / Auto: FINANCIAL_DETAILED (.zip or .csv) or DoorDash credentials",
      "DeepDive mode: deepdive_report JSON, operator_profile, budget_cap (optional)",
    ],
    outputs: [
      "Offers: campaign_mappings — store, min subtotal, slot tags, campaign name, status",
      "Ads: ads_plan — day × daypart tiers, budgets as allocation %, bid hints, campaign names",
      "marketing_plan.json — recommended_campaigns[]; approval workflow",
    ],
  },
  {
    id: "ralphai-offers",
    name: "RalphAI — Offers",
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
    id: "ralphai-ads",
    name: "RalphAI — Ads",
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
      "active_campaigns (RalphAI setup output)",
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
];

export function AgentsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
          Agents
        </h2>
        <p className="mt-1 text-ink-600 dark:text-white/65">
          Agent cards show the runnable workflows available in RalphAI.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => (
          <article
            key={a.id}
            className="brand-card group flex h-full min-h-[220px] flex-col rounded-[24px] p-5 transition hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-soft"
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

            <div className="mt-auto pt-4 flex gap-2">
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
              ) : a.id === "marketingreco" ? (
                <Link
                  to="/agents/marketingreco"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </Link>
              ) : a.id === "ralphai-offers" ? (
                <Link
                  to="/agents/offers"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </Link>
              ) : a.id === "ralphai-ads" ? (
                <Link
                  to="/agents/ads"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </Link>
              ) : a.id === "review" ? (
                <Link
                  to="/agents/campaign-review"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                >
                  <Play className="h-4 w-4" />
                  Run
                </Link>
              ) : a.id === "data-run" ? (
                <Link
                  to="/agents/data-run"
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
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
