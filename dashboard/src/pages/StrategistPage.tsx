import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";
import { AgentRunLogPanel } from "../components/AgentRunLogPanel";
import { appendAgentLogLines, pollAgentRun } from "../lib/agentRunPolling";

type StrategistMode = "auto" | "manual";
type ResultTab = "slots" | "offers" | "ads";

function formatSlotAction(row: Record<string, unknown>): string {
  const action = String(row.action ?? "").trim().toLowerCase();
  if (action === "promo+ads" || (action === "promo" && row.ad_placement === true)) {
    return "Offer + Ads";
  }
  if (action === "promo") return "Offer";
  if (action === "ads") return "Ads";
  if (action === "none") return "None";
  return String(row.action ?? "");
}

interface OperatorResult {
  operator_id: string;
  business_name: string;
  email?: string;
  status: string;
  error?: string;
  combined_analysis?: string | null;
  campaigns_xlsx?: string | null;
  slot_info_csv?: string | null;
  output_dir?: string;
}

export function StrategistPage() {
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [mode, setMode] = useState<StrategistMode>("auto");
  const [selectedOperatorIds, setSelectedOperatorIds] = useState<string[]>([]);
  const [manualOperatorId, setManualOperatorId] = useState("");
  const [financialFile, setFinancialFile] = useState<File | null>(null);
  const [marketingFile, setMarketingFile] = useState<File | null>(null);
  const [registerFile, setRegisterFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [resultTab, setResultTab] = useState<ResultTab>("slots");
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [queuePosition, setQueuePosition] = useState<number | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/account-directory");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { operators?: AccountOperator[] };
        if (cancelled) return;
        setOperators(Array.isArray(data.operators) ? data.operators : []);
      } catch {
        if (!cancelled) {
          setOperators([]);
          setError("Could not load operators from account directory.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedSet = useMemo(() => new Set(selectedOperatorIds), [selectedOperatorIds]);
  const mappings = useMemo(() => (result?.campaign_mappings as unknown[]) ?? [], [result]);
  const slotRecommendations = useMemo(
    () => (result?.slot_recommendations as unknown[]) ?? [],
    [result],
  );
  const adsPlan = result?.ads_plan as
    | { slot_table?: Array<Record<string, unknown>> }
    | null
    | undefined;
  const adsSlotRows = useMemo(() => adsPlan?.slot_table ?? [], [adsPlan]);
  const adsQualifyingSlots = useMemo(
    () =>
      adsSlotRows.filter((row) => {
        const placement = String(row.ad_placement ?? "").trim().toLowerCase();
        return placement === "yes" || placement === "y" || placement === "true" || placement === "1";
      }),
    [adsSlotRows],
  );
  const adsUploadRows = useMemo(
    () => (result?.ads_upload_rows as unknown[]) ?? [],
    [result],
  );

  function toggleOperator(operatorId: string) {
    setSelectedOperatorIds((prev) =>
      prev.includes(operatorId) ? prev.filter((v) => v !== operatorId) : [...prev, operatorId],
    );
  }

  function selectAllOperators() {
    setSelectedOperatorIds(operators.map((op) => op.operator_id));
  }

  function clearAllOperators() {
    setSelectedOperatorIds([]);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setRunId(null);
    setRunStatus(null);
    setQueuePosition(null);
    setLogLines([]);

    const formData = new FormData();
    formData.append("mode", mode);

    if (mode === "manual") {
      if (!manualOperatorId.trim()) {
        setError("Select an operator for manual mode.");
        return;
      }
      if (!financialFile && !registerFile) {
        setError("Upload a DoorDash FINANCIAL zip (.zip), or a legacy register file.");
        return;
      }
      formData.append("operator_id", manualOperatorId.trim());
      if (financialFile) formData.append("financial_file", financialFile);
      if (marketingFile) formData.append("marketing_file", marketingFile);
      if (registerFile && !financialFile) formData.append("register_file", registerFile);
    } else {
      if (!selectedOperatorIds.length) {
        setError("Select at least one operator for auto mode.");
        return;
      }
      formData.append("operator_ids", JSON.stringify(selectedOperatorIds));
    }

    setLoading(true);
    try {
      const res = await fetch("/api/runs/strategist", { method: "POST", body: formData });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const started = (await res.json()) as Record<string, unknown>;
      const id = String(started.run_id || "");
      if (!id) throw new Error("No run_id returned from API.");
      setRunId(id);
      setRunStatus(String(started.status || "queued"));
      if (typeof started.queue_position === "number") {
        setQueuePosition(started.queue_position);
      }

      const data = await pollAgentRun("strategist", id, {
        onStatus: (status, payload) => {
          setRunStatus(status);
          if (typeof payload.queue_position === "number") {
            setQueuePosition(payload.queue_position);
          }
        },
        onLogLines: (lines) => {
          setLogLines((prev) => appendAgentLogLines(prev, lines));
        },
      });
      setResult(data);
      if ((data?.slot_recommendations as unknown[] | undefined)?.length) {
        setResultTab("slots");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const runResults = Array.isArray(result?.results) ? (result?.results as OperatorResult[]) : [];
  const isManualResult = result?.mode === "manual";

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
        <h2 className="font-display text-2xl font-semibold text-ink-900">Strategist</h2>
        <p className="mt-1 max-w-3xl text-ink-600">
          <strong>Auto:</strong> logs into each operator&apos;s DoorDash portal, downloads 90-day reports, and generates
          store-wise Offers + Ads campaigns. <strong>Manual:</strong> upload a DD FINANCIAL zip (same analysis as
          reporting_browser_use) to build combined_analysis, campaign mappings, and slot_info — Ads on the bottom 8
          active slots per store by orders.
        </p>
      </div>

      <form onSubmit={onSubmit} className="brand-card grid gap-4 rounded-[28px] p-6">
        <label className="flex flex-col gap-1 max-w-md">
          <span className="text-sm font-medium text-ink-700">Mode</span>
          <select
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            value={mode}
            onChange={(e) => setMode(e.target.value as StrategistMode)}
          >
            <option value="auto">Auto — portal download + analysis</option>
            <option value="manual">Manual — FINANCIAL zip → combined analysis + campaigns</option>
          </select>
        </label>

        {mode === "manual" ? (
          <>
            <label className="flex flex-col gap-1 max-w-md">
              <span className="text-sm font-medium text-ink-700">Operator</span>
              <select
                className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                value={manualOperatorId}
                onChange={(e) => setManualOperatorId(e.target.value)}
              >
                <option value="">Select operator…</option>
                {operators.map((op) => (
                  <option key={op.operator_id} value={op.operator_id}>
                    {op.business_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-700">DD FINANCIAL zip (.zip)</span>
              <input
                type="file"
                accept=".zip"
                className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900"
                onChange={(e) => setFinancialFile(e.target.files?.[0] ?? null)}
              />
              <span className="text-xs text-ink-500">
                Must include FINANCIAL_DETAILED_TRANSACTIONS. Date range is read from the filename when present.
              </span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-sm font-medium text-ink-700">DD Marketing zip (.zip, optional)</span>
              <input
                type="file"
                accept=".zip"
                className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900"
                onChange={(e) => setMarketingFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <details className="rounded-xl border border-brand-100 bg-brand-50/40 px-3 py-2 text-sm text-ink-600">
              <summary className="cursor-pointer font-medium text-ink-700">Legacy: register upload</summary>
              <label className="mt-2 flex flex-col gap-1">
                <span className="text-xs text-ink-600">DD register file (.xlsx, .xls, or .csv)</span>
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900"
                  onChange={(e) => setRegisterFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </details>
          </>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-ink-700">Operators (multi-select)</div>
              <div className="inline-flex items-center gap-2">
                <button
                  type="button"
                  onClick={selectAllOperators}
                  className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-brand-50"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={clearAllOperators}
                  className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-brand-50"
                >
                  Clear all
                </button>
              </div>
            </div>
            <div className="max-h-72 overflow-auto rounded-xl border border-brand-200 p-3">
              <div className="grid gap-2 sm:grid-cols-2">
                {operators.map((op) => (
                  <label key={op.operator_id} className="inline-flex items-start gap-2 text-sm text-ink-700">
                    <input
                      type="checkbox"
                      checked={selectedSet.has(op.operator_id)}
                      onChange={() => toggleOperator(op.operator_id)}
                      className="mt-0.5 h-4 w-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
                    />
                    <span>{op.business_name}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {error ? (
          <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">{error}</div>
        ) : null}

        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? "Running Strategist..." : "Run Strategist"}
          </button>
        </div>
      </form>

      {runId ? (
        <AgentRunLogPanel
          agent="strategist"
          runId={runId}
          status={runStatus}
          queuePosition={queuePosition}
          lines={logLines}
        />
      ) : null}

      {result ? (
        <>
          <div className="brand-card rounded-[24px] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
              {isManualResult && (result?.downloads as { campaigns_excel?: string; slot_info_csv?: string } | undefined) ? (
                <div className="flex flex-wrap gap-2">
                  {(result.downloads as { campaigns_excel?: string }).campaigns_excel ? (
                    <a
                      href={(result.downloads as { campaigns_excel: string }).campaigns_excel}
                      className="inline-flex items-center gap-2 rounded-xl border border-brand-200 px-3 py-2 text-sm font-medium text-ink-800 hover:bg-brand-50"
                    >
                      Download combined_analysis.xlsx
                    </a>
                  ) : null}
                  {(result.downloads as { slot_info_csv?: string }).slot_info_csv ? (
                    <a
                      href={(result.downloads as { slot_info_csv: string }).slot_info_csv}
                      className="inline-flex items-center gap-2 rounded-xl border border-brand-200 px-3 py-2 text-sm font-medium text-ink-800 hover:bg-brand-50"
                    >
                      Download slot_info.csv
                    </a>
                  ) : null}
                </div>
              ) : null}
            </div>
            {isManualResult ? (
              <p className="mt-2 text-sm text-ink-700">
                Slot rows: {slotRecommendations.length} · Promos: {mappings.length} · Ads upload rows:{" "}
                {adsUploadRows.length} ({adsQualifyingSlots.length} qualifying slots)
              </p>
            ) : (
              <>
                <p className="mt-2 text-sm text-ink-700">Status: {String(result.status ?? "unknown")}</p>
                <p className="mt-1 text-sm text-ink-600">Operators: {String(result.selected_operator_count ?? 0)}</p>
              </>
            )}
          </div>

          {isManualResult ? (
            <>
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

              {resultTab === "slots" && slotRecommendations.length > 0 ? (
                <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-brand-100 text-left text-ink-600">
                        <th className="py-2 pr-3">Store</th>
                        <th className="py-2 pr-3">Day</th>
                        <th className="py-2 pr-3">Daypart</th>
                        <th className="py-2 pr-3">AOV</th>
                        <th className="py-2 pr-3">Profit %</th>
                        <th className="py-2 pr-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(slotRecommendations as Array<Record<string, unknown>>).map((row, idx) => (
                        <tr key={idx} className="border-t border-brand-50">
                          <td className="py-2 pr-3">{String(row.store_id ?? "")}</td>
                          <td className="py-2 pr-3">{String(row.day ?? "")}</td>
                          <td className="py-2 pr-3">{String(row.daypart ?? "")}</td>
                          <td className="py-2 pr-3">{String(row.aov ?? "")}</td>
                          <td className="py-2 pr-3">{String(row.profitability_pct ?? "")}</td>
                          <td className="py-2 pr-3">
                            {formatSlotAction(row)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {resultTab === "offers" && mappings.length > 0 ? (
                <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-brand-100 text-left text-ink-600">
                        <th className="py-2 pr-3">Store</th>
                        <th className="py-2 pr-3">Min subtotal</th>
                        <th className="py-2 pr-3">Slot tags</th>
                        <th className="py-2 pr-3">Campaign</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(mappings as Array<Record<string, unknown>>).map((m, idx) => (
                        <tr key={idx} className="border-t border-brand-50">
                          <td className="py-2 pr-3">{String(m.store_id ?? "")}</td>
                          <td className="py-2 pr-3">{String(m.min_subtotal ?? "")}</td>
                          <td className="py-2 pr-3">
                            {Array.isArray(m.slot_tags) ? (m.slot_tags as unknown[]).join(", ") : String(m.slot_tags ?? "")}
                          </td>
                          <td className="py-2 pr-3">{String(m.campaign_name ?? "")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {resultTab === "ads" && (adsQualifyingSlots.length > 0 || adsUploadRows.length > 0) ? (
                <div className="space-y-4">
                  {adsUploadRows.length > 0 ? (
                    <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
                      <p className="mb-3 text-sm font-semibold text-ink-800">Per store (Ralph Ads upload)</p>
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="border-b border-brand-100 text-left text-ink-600">
                            <th className="py-2 pr-3">Store</th>
                            <th className="py-2 pr-3">Slot tags</th>
                            <th className="py-2 pr-3">Bid</th>
                            <th className="py-2 pr-3">Campaign</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(adsUploadRows as Array<Record<string, unknown>>).map((row, idx) => (
                            <tr key={idx} className="border-t border-brand-50">
                              <td className="py-2 pr-3">{String(row.store_id ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.slots ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.bid_strategy ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.campaign_name ?? "")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                  {adsQualifyingSlots.length > 0 ? (
                    <div className="brand-card rounded-[24px] p-5 overflow-x-auto">
                      <p className="mb-3 text-sm font-semibold text-ink-800">
                        Per slot (matches slot_info.csv Offer + Ads rows)
                      </p>
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="border-b border-brand-100 text-left text-ink-600">
                            <th className="py-2 pr-3">Store</th>
                            <th className="py-2 pr-3">Day</th>
                            <th className="py-2 pr-3">Daypart</th>
                            <th className="py-2 pr-3">Orders</th>
                            <th className="py-2 pr-3">Sales</th>
                          </tr>
                        </thead>
                        <tbody>
                          {adsQualifyingSlots.map((row, idx) => (
                            <tr key={idx} className="border-t border-brand-50">
                              <td className="py-2 pr-3">{String(row.store_id ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.day_of_week ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.daypart ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.orders ?? "")}</td>
                              <td className="py-2 pr-3">{String(row.sales ?? "")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : runResults.length > 0 ? (
            <div className="brand-card rounded-[24px] p-5 max-h-96 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-brand-50 text-ink-700">
                  <tr>
                    <th className="px-3 py-2">Operator</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Combined Analysis</th>
                    <th className="px-3 py-2">Campaigns</th>
                    <th className="px-3 py-2">Slot info</th>
                    <th className="px-3 py-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {runResults.map((row, idx) => (
                    <tr key={`${row.operator_id ?? "op"}-${idx}`} className="border-t border-brand-100 align-top">
                      <td className="px-3 py-2">{row.business_name ?? row.operator_id ?? ""}</td>
                      <td className="px-3 py-2">
                        <span
                          className={
                            row.status === "success"
                              ? "text-green-700"
                              : row.status === "failed"
                                ? "text-red-600"
                                : "text-amber-600"
                          }
                        >
                          {row.status}
                        </span>
                      </td>
                      <td className="px-3 py-2">{row.combined_analysis ? "combined_analysis_*.xlsx" : "-"}</td>
                      <td className="px-3 py-2">{row.campaigns_xlsx ? "Campaign Mappings" : "-"}</td>
                      <td className="px-3 py-2">{row.slot_info_csv ? "slot_info.csv" : "-"}</td>
                      <td className="px-3 py-2">
                        {row.error ? (
                          <span className="block max-w-md whitespace-pre-wrap break-words text-xs text-red-700">
                            {row.error}
                          </span>
                        ) : (
                          <span className="text-ink-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
