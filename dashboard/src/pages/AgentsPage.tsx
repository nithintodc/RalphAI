import { Link } from "react-router-dom";
import {
  Play,
  Cpu,
  Bot,
  ShoppingBag,
  Megaphone,
  BarChart3,
  Skull,
  Activity,
  Globe,
} from "lucide-react";
import { agentRunRoute } from "../config/agentRoutes";
import { REPORTING_BROWSER_USE_FORKS } from "../config/reportingBrowserUseForks";

const agents = [
  {
    id: "data-run",
    name: "Data Run",
    desc: "DoorDash report zip downloader — pick operators, report types, and date range.",
    icon: Bot,
    status: "ready",
    color: "from-sky-500 to-cyan-700",
    inputs: [
      "Operators (multi-select) from Airtable account directory",
      "Report types: Financial, Marketing, Operations, Sales, Product mix, Refund",
      "From / to dates (same range for all selected reports)",
      "DoorDash credentials from Airtable Account Information",
    ],
    outputs: [
      "Zip files under data/DataRun_{timestamp}_{operator}/",
      "One fresh browser session per operator",
      "Per-operator status: success | partial | no_files | failed",
    ],
  },
  {
    id: "the_super_app",
    name: "The Super App",
    desc: "Primary React analytics UI — Pre/Post, diagnostics, marketing, register, and Breakdown financial summary.",
    icon: BarChart3,
    status: "ready",
    color: "from-brand-500 to-brand-700",
    inputs: ["Financial and Marketing exports"],
    outputs: ["React Interactive UI", "Breakdown — Financial Summary table"],
  },
  {
    id: "strategist",
    name: "Strategist",
    desc: "Logs into each operator's DoorDash portal, downloads 90-day reports, and generates ads + promo marketing plans.",
    icon: Bot,
    status: "ready",
    color: "from-violet-500 to-purple-700",
    inputs: [
      "Operators (multi-select) from Airtable account directory",
      "DoorDash credentials auto-loaded from Airtable Account Information",
      "Downloads 90-day financial + marketing reports per operator",
    ],
    outputs: [
      "90days/<operator_email>/ads.csv — ads campaign plan",
      "90days/<operator_email>/promo.csv — promo campaign plan",
      "Per-operator status: success | failed | skipped",
    ],
  },
  {
    id: "health-check",
    name: "Health Check",
    desc: "One combined DoorDash export per operator for the last two Mon–Sun weeks; splits into weekly CSVs and WoW (prior vs latest completed week).",
    icon: Activity,
    status: "ready",
    color: "from-emerald-500 to-teal-700",
    inputs: [
      "Operators (multi-select) from Airtable account directory",
      "DoorDash credentials from Airtable Account Information",
      "Runs full pipeline per operator in sequence (login → download → analytics)",
    ],
    outputs: [
      "data/healthcheck/run-<timestamp>/<operator>/rawdata, operatorlevel, WoW",
      "WoW/register_wow_report.html and .pdf (one HTML per operator)",
      "Slack: PDF link on Google Drive",
    ],
  },
  {
    id: "campaign-killer",
    name: "Campaign Killer",
    desc: "Ends active DoorDash campaigns named TODC-*: login → Campaigns → Active + Apply → row menu → End campaign → confirm → Technical issue reason → End campaign.",
    icon: Skull,
    status: "ready",
    color: "from-red-500 to-red-800",
    inputs: [
      "Operators (multi-select) from Airtable account directory",
      "DoorDash credentials auto-loaded from Airtable Account Information",
      "Typing TODC in campaigns search (optional; on by default) then Active filter; bot still only ends names starting with TODC-",
    ],
    outputs: [
      "Per-operator: campaigns ended count + names",
      "Status: success | login_failed | partial | error",
      "JSON report under data/runs/campaign_killer/",
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
    id: "app2_0",
    name: "App2.0 (Legacy)",
    desc: "Legacy Streamlit P&L — use The Super App → Breakdown for the financial summary table.",
    icon: BarChart3,
    status: "ready",
    color: "from-emerald-600 to-emerald-800",
    inputs: ["Financial and Marketing exports"],
    outputs: ["Redirected to Super App Breakdown"],
  },
  {
    id: "app3_0",
    name: "App3.0 (Legacy)",
    desc: "Cloud-ready Streamlit app with comparison engine.",
    icon: BarChart3,
    status: "ready",
    color: "from-teal-600 to-teal-800",
    inputs: ["Financial and Marketing exports"],
    outputs: ["Streamlit Interactive UI"],
  },
  {
    id: "markup_app",
    name: "Markup App",
    desc: "Static markup viewing HTTP server.",
    icon: Cpu,
    status: "ready",
    color: "from-slate-600 to-slate-800",
    inputs: ["Static HTML/Assets"],
    outputs: ["HTTP Server UI"],
  },
  ...REPORTING_BROWSER_USE_FORKS.map((fork) => ({
    id: fork.id,
    name: `RBU — ${fork.shortLabel}`,
    desc: fork.desc,
    icon: Globe,
    status: "stub" in fork && fork.stub ? "legacy" : "ready",
    color: fork.color,
    inputs: [
      "DoorDash email/password (form or .env)",
      fork.id === "reporting_browser_use_browser"
        ? "BROWSER_USE_API_KEY (.env)"
        : "GEMINI_API_KEY (.env)",
      "Optional: Multilogin, CDP, FORCE_FULL_RUN (.env)",
    ],
    outputs: [
      "Full main.py pipeline for this fork directory",
      "Downloads + combined analysis + campaign execution",
    ],
  })),
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

            <div className="mt-auto flex gap-2 pt-4">
              {agentRunRoute(a.id) ? (
                <Link
                  to={agentRunRoute(a.id)!}
                  className={[
                    "inline-flex flex-1 items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold text-white transition",
                    a.id === "campaign-killer"
                      ? "bg-red-600 hover:bg-red-700"
                      : "bg-ink-900 hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400",
                  ].join(" ")}
                >
                  {a.id === "campaign-killer" ? (
                    <Skull className="h-4 w-4" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Run
                </Link>
              ) : (
                <span className="inline-flex flex-1 items-center justify-center rounded-2xl bg-brand-50 px-4 py-2.5 text-sm font-medium text-ink-500">
                  Coming soon
                </span>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
