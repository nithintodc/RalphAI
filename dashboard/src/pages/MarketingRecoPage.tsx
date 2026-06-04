import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Play, Loader2 } from "lucide-react";
import { OperatorAccountPicker } from "../components/OperatorAccountPicker";

type RecoMode = "manual" | "auto";
type ResultTab = "slots" | "offers" | "ads";
type AdsSubTab = "upload" | "slots";

/** Matches Excel "Ads" sheet / API `ads_upload_rows`. */
type AdsUploadRow = {
  store_id?: string | number;
  slots?: string;
  bid_strategy?: number;
  budget?: number;
  campaign_name?: string;
};

export function MarketingRecoPage() {
  const [operatorId, setOperatorId] = useState("");
  const [mode, setMode] = useState<RecoMode>("manual");
  const [registerFile, setRegisterFile] = useState<File | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const [resultTab, setResultTab] = useState<ResultTab>("offers");
  const [adsSubTab, setAdsSubTab] = useState<AdsSubTab>("upload");
  const mappings = useMemo(() => (result?.campaign_mappings as any[]) ?? [], [result]);
  const slotRecommendations = useMemo(
    () => (result?.slot_recommendations as any[]) ?? [],
    [result],
  );
  const adsPlan = result?.ads_plan as
    | {
        store_id?: number;
        store_name?: string | null;
        store_count?: number;
        stores?: Array<{ store_id?: number; store_name?: string }>;
        date_range?: string;
        budget_model?: string;
        total_campaigns?: number;
        tier_summary?: Record<string, number>;
        campaigns?: any[];
        slot_table?: Array<{
          store_id?: number;
          store_name?: string;
          slot?: string;
          orders?: number;
          sales?: number;
          net_total?: number;
          profitability_pct?: number;
          ad_placement?: string;
          budget_estimate?: number;
          weekly_budget?: number;
        }>;
        slot_table_help?: {
          profitability_definition?: string;
          placement_rule?: string;
          budget_rule?: string;
          weekly_budget_rule?: string;
          min_bid_per_order_usd?: number;
        };
      }
    | null
    | undefined;
  const adsSlotRows = useMemo(() => adsPlan?.slot_table ?? [], [adsPlan]);
  const adsUploadRows = useMemo(
    () => (result?.ads_upload_rows as AdsUploadRow[] | undefined) ?? [],
    [result],
  );

  useEffect(() => {
    if (result?.run_id) {
      setAdsSubTab("upload");
      if ((result?.slot_recommendations as unknown[] | undefined)?.length) {
        setResultTab("slots");
      }
    }
  }, [result?.run_id]);

  const adsStoreSummary = useMemo(() => {
    const n = adsPlan?.store_count ?? (adsPlan?.stores?.length ? adsPlan.stores.length : 0);
    if (!adsPlan || n <= 0) return null;
    if (n === 1) {
      const one = adsPlan.stores?.[0];
      const label = one?.store_name
        ? `${one.store_name} (${one.store_id ?? adsPlan.store_id ?? "—"})`
        : adsPlan.store_name
          ? `${adsPlan.store_name} (${adsPlan.store_id ?? one?.store_id ?? "—"})`
          : String(one?.store_id ?? adsPlan.store_id ?? "—");
      return { count: 1, label };
    }
    const ids = (adsPlan.stores ?? []).map((s) => s.store_id).filter((x) => x != null);
    return {
      count: n,
      label: `${n} stores${ids.length ? ` · IDs: ${ids.slice(0, 8).join(", ")}${ids.length > 8 ? "…" : ""}` : ""}`,
    };
  }, [adsPlan]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!operatorId.trim()) {
      setError("Enter an Operator ID.");
      return;
    }
    if (mode === "manual" && !registerFile) {
      setError("Upload a DoorDash register file (.xlsx, .xls, or .csv) for Manual mode.");
      return;
    }
    if (mode === "auto" && (!email.trim() || !password)) {
      setError("Provide DoorDash email and password for Auto mode.");
      return;
    }

    const formData = new FormData();
    formData.append("operator_id", operatorId.trim());
    formData.append("mode", mode);
    if (mode === "manual" && registerFile) {
      formData.append("register_file", registerFile);
    }
    if (mode === "auto") {
      formData.append("doordash_email", email.trim());
      formData.append("doordash_password", password);
    }

    setLoading(true);
    try {
      const res = await fetch("/api/runs/marketingreco", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 h-full">
      <div>
        <Link
          to="/agents"
          className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>
        <h2 className="font-display text-2xl font-semibold text-ink-900">MarketingReco</h2>
        <p className="mt-1 max-w-2xl text-ink-600">
          Upload a DoorDash register Excel (manual) with per-store, per-day, per-slot AOV and profitability. The agent
          suggests Ads when AOV &lt; $20 and profitability &gt; 75%, promos when AOV &gt; $20 (
          <code className="text-xs">TODC-StoreID-$minSubtotal</code>
          ), or no action otherwise. Auto mode still uses the legacy financial download pipeline.
        </p>
      </div>

      <form onSubmit={onSubmit} className="brand-card grid gap-4 rounded-[28px] p-6 sm:grid-cols-2">
        <OperatorAccountPicker
          operatorId={operatorId}
          onOperatorIdChange={setOperatorId}
          email={email}
          onEmailChange={setEmail}
          password={password}
          onPasswordChange={setPassword}
          showDoorDashCredentials={mode === "auto"}
        />

        <label className="flex flex-col gap-1 sm:col-span-2 max-w-md">
          <span className="text-sm font-medium text-ink-700">Mode</span>
          <select
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            value={mode}
            onChange={(e) => setMode(e.target.value as RecoMode)}
          >
            <option value="manual">Manual upload</option>
            <option value="auto">Auto mode</option>
          </select>
        </label>

        {mode === "manual" ? (
          <label className="flex flex-col gap-1 sm:col-span-2">
            <span className="text-sm font-medium text-ink-700">DD register file (.xlsx, .xls, or .csv)</span>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              onChange={(e) => setRegisterFile(e.target.files?.[0] ?? null)}
            />
          </label>
        ) : null}

        {error ? (
          <div className="sm:col-span-2 rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">
            {error}
          </div>
        ) : null}

        <div className="sm:col-span-2 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? "Running MarketingReco..." : "Run MarketingReco"}
          </button>
        </div>
      </form>

      {result ? (
        <>
          <div className="brand-card rounded-[24px] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
              {result?.downloads?.campaigns_excel ? (
                <a
                  href={result.downloads.campaigns_excel}
                  className="inline-flex items-center gap-2 rounded-xl border border-brand-200 px-3 py-2 text-sm font-medium text-ink-800 hover:bg-brand-50"
                >
                  Download Excel (Offers + Ads)
                </a>
              ) : null}
            </div>
            <p className="mt-2 text-sm text-ink-700">
              Slot rows: {slotRecommendations.length} · Promos: {mappings.length} · Ads upload rows:{" "}
              {adsUploadRows.length} ({adsSlotRows.length} qualifying slots)
            </p>
          </div>

          <div className="flex gap-2 border-b border-brand-100 pb-2">
            {(
              [
                { id: "slots" as const, label: "By slot" },
                { id: "offers" as const, label: "Offers" },
                { id: "ads" as const, label: "Ads" },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setResultTab(t.id)}
                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                  resultTab === t.id
                    ? "bg-ink-900 text-white dark:bg-brand-500 dark:text-ink-900"
                    : "text-ink-600 hover:bg-brand-50"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {resultTab === "slots" ? (
            <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
              <h3 className="font-display text-lg font-semibold text-ink-900">Slot recommendations</h3>
              <p className="mt-1 text-sm text-ink-600">
                Per store × day × daypart: AOV &lt; $20 and profitability &gt; 75% → Ads; AOV &lt; $20 and ≤ 75% → none;
                AOV &gt; $20 → promo campaign.
              </p>
              {slotRecommendations.length > 0 ? (
                <table className="mt-3 min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-brand-100 text-left text-ink-600">
                      <th className="py-2 pr-3">Store</th>
                      <th className="py-2 pr-3">Day</th>
                      <th className="py-2 pr-3">Daypart</th>
                      <th className="py-2 pr-3">Orders</th>
                      <th className="py-2 pr-3">AOV</th>
                      <th className="py-2 pr-3">Profit %</th>
                      <th className="py-2 pr-3">Action</th>
                      <th className="py-2 pr-3">Campaign</th>
                      <th className="py-2 pr-3">Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slotRecommendations.map((row, idx) => (
                      <tr key={`${row.store_id}-${row.day}-${row.daypart}-${idx}`} className="border-b border-brand-50">
                        <td className="py-2 pr-3 text-ink-900">{row.store_id ?? "—"}</td>
                        <td className="py-2 pr-3">{row.day ?? "—"}</td>
                        <td className="py-2 pr-3">{row.daypart ?? "—"}</td>
                        <td className="py-2 pr-3">{row.orders ?? "—"}</td>
                        <td className="py-2 pr-3">
                          {row.aov != null ? `$${Number(row.aov).toFixed(2)}` : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {row.profitability_pct != null ? `${Number(row.profitability_pct).toFixed(1)}%` : "—"}
                        </td>
                        <td className="py-2 pr-3 font-medium capitalize">{row.action ?? "—"}</td>
                        <td className="py-2 pr-3">{row.campaign_name || "—"}</td>
                        <td className="py-2 pr-3 max-w-xs text-ink-600 text-xs">{row.rationale ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="mt-4 text-sm text-ink-600">No slot rows in this run.</p>
              )}
            </div>
          ) : resultTab === "offers" ? (
            <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
              <h3 className="font-display text-lg font-semibold text-ink-900">Promotions to keep</h3>
              <p className="mt-1 text-sm text-ink-600">
                Promo campaigns grouped by store and uplifted min subtotal (AOV × 1.2, rounded to $5).
              </p>
              <table className="mt-3 min-w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-100 text-left text-ink-600">
                    <th className="py-2 pr-3">Store ID</th>
                    <th className="py-2 pr-3">DoorDash Store ID</th>
                    <th className="py-2 pr-3">Store Name</th>
                    <th className="py-2 pr-3">Minimum Subtotal</th>
                    <th className="py-2 pr-3">Slot Tags</th>
                    <th className="py-2 pr-3">Campaign Name</th>
                    <th className="py-2 pr-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {mappings.map((m, idx) => (
                    <tr key={`${m.campaign_name}-${idx}`} className="border-b border-brand-50">
                      <td className="py-2 pr-3 text-ink-900">{m.store_id ?? "-"}</td>
                      <td className="py-2 pr-3 text-ink-600">{m.doordash_store_id ?? "—"}</td>
                      <td className="py-2 pr-3">{m.store_name ?? "-"}</td>
                      <td className="py-2 pr-3">{m.min_subtotal ?? 0}</td>
                      <td className="py-2 pr-3">
                        {Array.isArray(m.slot_tags) ? m.slot_tags.join(", ") : (m.slot_tags ?? "-")}
                      </td>
                      <td className="py-2 pr-3">{m.campaign_name ?? "-"}</td>
                      <td className="py-2 pr-3">{m.status ?? "Pending"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
              <h3 className="font-display text-lg font-semibold text-ink-900">Ads</h3>
              <p className="mt-1 text-sm text-ink-600">
                Same columns as the Excel <strong>Ads</strong> sheet (RalphAI — Ads upload):{" "}
                <strong>Merchant store ID</strong>, <strong>Slots</strong> (tags 1–42 where Ad placement is Yes),{" "}
                <strong>Bid strategy</strong> <strong>3</strong>, <strong>Budget</strong> (sum of budget estimates ÷
                12), <strong>Campaign name</strong>. Use <em>By slot</em> for daypart-level metrics (Ads slots sheet).
              </p>

              <div className="mt-4 flex flex-wrap gap-2 border-b border-brand-100 pb-2">
                {(
                  [
                    { id: "upload" as const, label: "Upload sheet" },
                    { id: "slots" as const, label: "By slot (detail)" },
                  ] as const
                ).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setAdsSubTab(t.id)}
                    className={`rounded-xl px-3 py-1.5 text-sm font-semibold transition ${
                      adsSubTab === t.id
                        ? "bg-brand-100 text-ink-900 dark:bg-white/10 dark:text-white"
                        : "text-ink-600 hover:bg-brand-50"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {adsPlan ? (
                <div className="mt-3 grid gap-2 text-sm text-ink-700 sm:grid-cols-2">
                  <div>
                    <span className="text-ink-500">Stores</span> · {adsStoreSummary?.label ?? "—"}
                  </div>
                  <div>
                    <span className="text-ink-500">Window</span> · {adsPlan.date_range ?? "—"}
                  </div>
                  {adsPlan.slot_table_help ? (
                    <div className="sm:col-span-2 rounded-xl bg-brand-50/80 p-3 text-xs text-ink-700 dark:bg-white/5">
                      <p className="font-medium text-ink-800">Rules</p>
                      <ul className="mt-1 list-disc space-y-1 pl-4">
                        <li>{adsPlan.slot_table_help.placement_rule}</li>
                        <li>{adsPlan.slot_table_help.budget_rule}</li>
                        {adsPlan.slot_table_help.weekly_budget_rule ? (
                          <li>{adsPlan.slot_table_help.weekly_budget_rule}</li>
                        ) : null}
                        {adsPlan.slot_table_help.min_bid_per_order_usd != null ? (
                          <li>Minimum bid per order: ${adsPlan.slot_table_help.min_bid_per_order_usd}</li>
                        ) : null}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {adsSubTab === "upload" ? (
                adsUploadRows.length > 0 ? (
                  <table className="mt-4 min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-brand-100 text-left text-ink-600">
                        <th className="py-2 pr-3">Merchant store ID</th>
                        <th className="py-2 pr-3">Slots</th>
                        <th className="py-2 pr-3">Bid strategy</th>
                        <th className="py-2 pr-3">Budget</th>
                        <th className="py-2 pr-3">Campaign name</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adsUploadRows.map((row, idx: number) => (
                        <tr
                          key={`${row.store_id ?? "x"}-${row.campaign_name ?? idx}`}
                          className="border-b border-brand-50"
                        >
                          <td className="py-2 pr-3 text-ink-900">{row.store_id ?? "—"}</td>
                          <td className="py-2 pr-3 font-mono text-xs text-ink-800">{row.slots ?? "—"}</td>
                          <td className="py-2 pr-3">{row.bid_strategy ?? "—"}</td>
                          <td className="py-2 pr-3">
                            {row.budget != null
                              ? `$${Number(row.budget).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                              : "—"}
                          </td>
                          <td className="py-2 pr-3 max-w-[220px] truncate" title={row.campaign_name}>
                            {row.campaign_name ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="mt-4 text-sm text-ink-600">
                    No upload rows yet (no slots with Ad placement Yes), or re-run MarketingReco so the API includes{" "}
                    <code className="text-xs">ads_upload_rows</code>. Check <em>By slot (detail)</em> for raw slot
                    metrics.
                  </p>
                )
              ) : adsPlan && adsSlotRows.length > 0 ? (
                <table className="mt-4 min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-brand-100 text-left text-ink-600">
                      <th className="py-2 pr-3">Merchant store ID</th>
                      <th className="py-2 pr-3">Store</th>
                      <th className="py-2 pr-3">Slot</th>
                      <th className="py-2 pr-3">Orders</th>
                      <th className="py-2 pr-3">Sales</th>
                      <th className="py-2 pr-3">Net total</th>
                      <th className="py-2 pr-3">Profitability</th>
                      <th className="py-2 pr-3">Ad placement</th>
                      <th className="py-2 pr-3">Budget</th>
                      <th className="py-2 pr-3">Weekly budget</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adsSlotRows.map((row, idx: number) => (
                      <tr key={`${row.store_id ?? "x"}-${row.slot}-${idx}`} className="border-b border-brand-50">
                        <td className="py-2 pr-3 text-ink-900">{row.store_id ?? "—"}</td>
                        <td className="py-2 pr-3 max-w-[200px] truncate" title={row.store_name}>
                          {row.store_name ?? "—"}
                        </td>
                        <td className="py-2 pr-3 text-ink-900">{row.slot ?? "—"}</td>
                        <td className="py-2 pr-3">{row.orders ?? "—"}</td>
                        <td className="py-2 pr-3">
                          {row.sales != null
                            ? `$${Number(row.sales).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                            : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {row.net_total != null
                            ? `$${Number(row.net_total).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                            : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {row.profitability_pct != null ? `${Number(row.profitability_pct).toFixed(1)}%` : "—"}
                        </td>
                        <td className="py-2 pr-3 font-medium">
                          {row.ad_placement === "Yes" ? (
                            <span className="text-emerald-700 dark:text-emerald-400">Yes</span>
                          ) : (
                            <span className="text-ink-500">No</span>
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          {row.ad_placement === "Yes" && row.budget_estimate != null && row.budget_estimate > 0
                            ? `$${Number(row.budget_estimate).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                            : row.ad_placement === "Yes"
                              ? "$0.00"
                              : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          {(() => {
                            if (row.ad_placement !== "Yes") return "—";
                            const w =
                              row.weekly_budget != null
                                ? Number(row.weekly_budget)
                                : row.budget_estimate != null
                                  ? Number(row.budget_estimate) / 12
                                  : null;
                            if (w == null || Number.isNaN(w)) return "—";
                            return `$${w.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                          })()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="mt-4 text-sm text-ink-600">
                  No ads slots for this run (no register rows with AOV &lt; $20 and profitability &gt; 75%).
                </p>
              )}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
