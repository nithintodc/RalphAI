import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Activity, ExternalLink, FileText, Square } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";

const HEALTHCHECK_RUNNING_KEY = "healthcheck:running";
const HEALTHCHECK_RUN_ID_KEY = "healthcheck:run_id";

type RunPayload = Record<string, unknown>;
type InFlightHealthCheck = {
  startedAtIso: string;
  runId: string;
  promise: Promise<RunPayload>;
};

function parseApiError(body: string, status: number): string {
  const trimmed = body.trim();
  if (!trimmed) return `Request failed (HTTP ${status})`;
  try {
    const parsed = JSON.parse(trimmed) as {
      detail?: string | Array<{ msg?: string }>;
      error?: string;
    };
    if (typeof parsed.error === "string" && parsed.error.trim()) {
      return parsed.error.trim();
    }
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
  } catch {
    // not JSON
  }
  return trimmed;
}

async function pollHealthCheckRun(
  runId: string,
  onProgress?: (message: string) => void
): Promise<RunPayload> {
  for (;;) {
    const res = await fetch(`/api/runs/health-check/${encodeURIComponent(runId)}`);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(parseApiError(text, res.status));
    }
    const data = (await res.json()) as RunPayload;
    const status = String(data.status || "").toLowerCase();
    const progress = data.progress as { phase?: string; detail?: string } | undefined;
    if (status === "running" && progress?.phase && onProgress) {
      onProgress(
        progress.detail ? `${progress.phase}: ${progress.detail}` : String(progress.phase)
      );
    }
    if (status && status !== "running") {
      if (status === "interrupted" || status === "error") {
        throw new Error(
          String(data.error || data.detail || "Health check did not complete.")
        );
      }
      return data;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
}

type CampaignReviewItem = {
  campaign_name?: string;
  recommendation?: string;
  aov_lift_pct?: number;
  order_volume_lift_pct?: number;
  net_revenue_delta?: number;
  rationale?: string;
};

type CampaignReviewSummary = {
  campaign_reviews?: CampaignReviewItem[];
  mode?: string;
  notes?: string;
  error?: string;
};

type GrowthHealthSummary = {
  status?: string;
  summary?: string;
  threshold_pct?: number;
  unhealthy_metrics?: string[];
  healthy_metrics?: string[];
};

type OperatorReport = {
  operator?: string;
  email?: string;
  status?: string;
  failure_reason?: string;
  download_error?: string;
  browser_report_url?: string;
  pdf_drive_url?: string;
  pdf_local_url?: string;
  pdf_public_url?: string;
  pdf_export_ok?: boolean;
  wow_viz_html?: string;
  campaign_review?: CampaignReviewSummary;
  growth_health?: GrowthHealthSummary;
  growth_drilldown_md?: string;
};

let inFlightHealthCheck: InFlightHealthCheck | null = null;

function browserUrlFor(report: OperatorReport): string | null {
  if (report.browser_report_url) return report.browser_report_url;
  if (report.wow_viz_html) {
    return `/api/healthcheck/wow-viz?path=${encodeURIComponent(report.wow_viz_html)}`;
  }
  return null;
}

function pdfUrlFor(report: OperatorReport): { url: string | null; isDrive: boolean } {
  const drive = (report.pdf_drive_url || "").trim();
  if (drive && drive.includes("drive.google.com")) {
    return { url: drive, isDrive: true };
  }
  const local = (report.pdf_local_url || report.pdf_public_url || "").trim();
  if (local) return { url: local, isDrive: false };
  return { url: null, isDrive: false };
}

export function HealthCheckPage() {
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [selectedOperatorIds, setSelectedOperatorIds] = useState<string[]>([]);
  const [selectedEmails, setSelectedEmails] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [result, setResult] = useState<RunPayload | null>(null);
  const [growthThresholdPct, setGrowthThresholdPct] = useState("2");

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
          setError("Could not load operators from Airtable.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function attach(promise: Promise<RunPayload>) {
      setLoading(true);
      setInfo("Health check is running in background. You can navigate and come back.");
      setError(null);
      try {
        const data = await promise;
        if (cancelled) return;
        setResult(data);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Request failed");
      } finally {
        if (cancelled) return;
        setLoading(false);
        localStorage.removeItem(HEALTHCHECK_RUNNING_KEY);
        inFlightHealthCheck = null;
      }
    }

    if (inFlightHealthCheck?.promise) {
      void attach(inFlightHealthCheck.promise);
      return () => {
        cancelled = true;
      };
    }

    const persistedRunId = localStorage.getItem(HEALTHCHECK_RUN_ID_KEY);
    const persistedStarted = localStorage.getItem(HEALTHCHECK_RUNNING_KEY);
    if (!persistedRunId && !persistedStarted) {
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setInfo("Health check is still running in background.");

    const resume = async () => {
      try {
        if (persistedRunId) {
          const data = await pollHealthCheckRun(persistedRunId, (msg) => setInfo(msg));
          if (cancelled) return;
          setResult(data);
          setInfo(
            String(data.status || "").toLowerCase() === "cancelled"
              ? "Health check was stopped."
              : "Health check finished."
          );
        }
      } catch {
        // Fall back to runs index polling.
      } finally {
        if (!cancelled) {
          setLoading(false);
          localStorage.removeItem(HEALTHCHECK_RUNNING_KEY);
          localStorage.removeItem(HEALTHCHECK_RUN_ID_KEY);
          inFlightHealthCheck = null;
        }
      }
    };

    if (persistedRunId) {
      void resume();
      return () => {
        cancelled = true;
      };
    }

    const poll = async () => {
      try {
        const res = await fetch("/api/runs");
        if (!res.ok) return;
        const runs = (await res.json()) as Array<{
          agent?: string;
          started?: string;
          status?: string;
        }>;
        const startedAt = persistedStarted || "";
        const finished = runs.some(
          (r) =>
            (r.agent || "") === "health_check" &&
            (r.started || "") >= startedAt &&
            (r.status || "").toLowerCase() !== "running"
        );
        if (finished && !cancelled) {
          setLoading(false);
          setInfo("Background health check finished. Re-run or check Slack for the PDF link.");
          localStorage.removeItem(HEALTHCHECK_RUNNING_KEY);
        }
      } catch {
        // Ignore polling failures.
      }
    };

    const id = window.setInterval(() => {
      void poll();
    }, 8000);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const selectedSet = useMemo(() => new Set(selectedOperatorIds), [selectedOperatorIds]);

  function toggleOperator(operatorId: string) {
    setSelectedOperatorIds((prev) =>
      prev.includes(operatorId) ? prev.filter((v) => v !== operatorId) : [...prev, operatorId]
    );
  }

  function selectAllOperators() {
    setSelectedOperatorIds(operators.map((op) => op.operator_id));
  }

  function clearAllOperators() {
    setSelectedOperatorIds([]);
  }

  const reportCards = useMemo(() => {
    if (!result) return [];
    const wantEmails = new Set(selectedEmails.map((e) => e.toLowerCase()));
    const fromApi = Array.isArray(result.operator_reports)
      ? (result.operator_reports as OperatorReport[])
      : [];
    const fallback = Array.isArray(result.operator_results)
      ? (result.operator_results as OperatorReport[])
      : [];
    const rows = fromApi.length ? fromApi : fallback;

    return rows
      .filter((r) => {
        if (!wantEmails.size) return true;
        const em = (r.email || "").trim().toLowerCase();
        return em && wantEmails.has(em);
      })
      .filter((r) => r.status === "success")
      .map((r) => {
        const pdf = pdfUrlFor(r);
        return {
          operator: String(r.operator || r.email || "Operator"),
          browserUrl: browserUrlFor(r),
          pdfUrl: pdf.url,
          pdfIsDrive: pdf.isDrive,
        };
      })
      .filter((r) => r.browserUrl || r.pdfUrl);
  }, [result, selectedEmails]);

  const failedOperators = useMemo(() => {
    if (!result) return [];
    const wantEmails = new Set(selectedEmails.map((e) => e.toLowerCase()));
    const rows = Array.isArray(result.operator_results)
      ? (result.operator_results as OperatorReport[])
      : Array.isArray(result.operator_reports)
        ? (result.operator_reports as OperatorReport[])
        : [];
    return rows.filter((r) => {
      if (r.status === "success") return false;
      if (!wantEmails.size) return true;
      const em = (r.email || "").trim().toLowerCase();
      return em && wantEmails.has(em);
    });
  }, [result, selectedEmails]);

  const wowWeeks = result?.wow_weeks as
    | { previous_completed?: string; current_completed?: string }
    | undefined;

  const growthHealthByOperator = useMemo(() => {
    if (!result) return [];
    const wantEmails = new Set(selectedEmails.map((e) => e.toLowerCase()));
    const rows = Array.isArray(result.operator_results)
      ? (result.operator_results as OperatorReport[])
      : Array.isArray(result.operator_reports)
        ? (result.operator_reports as OperatorReport[])
        : [];
    return rows
      .filter((r) => {
        if (r.status !== "success" || !r.growth_health) return false;
        if (!wantEmails.size) return true;
        const em = (r.email || "").trim().toLowerCase();
        return em && wantEmails.has(em);
      })
      .map((r) => ({
        operator: String(r.operator || r.email || "Operator"),
        growth: r.growth_health as GrowthHealthSummary,
        mdPath: r.growth_drilldown_md,
      }));
  }, [result, selectedEmails]);

  const campaignReviewByOperator = useMemo(() => {
    if (!result) return [];
    const rows = Array.isArray(result.operator_results)
      ? (result.operator_results as OperatorReport[])
      : Array.isArray(result.operator_reports)
        ? (result.operator_reports as OperatorReport[])
        : [];
    return rows
      .filter((r) => r.status === "success" && r.campaign_review)
      .map((r) => ({
        operator: String(r.operator || r.email || "Operator"),
        review: r.campaign_review as CampaignReviewSummary,
      }));
  }, [result]);

  async function stopHealthCheck() {
    setStopping(true);
    setInfo("Stopping health check…");
    try {
      await fetch("/api/runs/health-check/cancel", { method: "POST" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send stop request");
    } finally {
      setStopping(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!selectedOperatorIds.length) {
      setError("Select at least one operator.");
      return;
    }

    const emailSet = new Set<string>();
    for (const id of selectedOperatorIds) {
      const row = operators.find((o) => o.operator_id === id);
      const em = row?.doordash_email?.trim();
      if (em) emailSet.add(em);
    }
    const emails = [...emailSet];
    if (!emails.length) {
      setError("Selected operators have no DoorDash login in Airtable.");
      return;
    }

    setSelectedEmails(emails);

    const formData = new FormData();
    formData.append("operator_emails", JSON.stringify(emails));
    const threshold = Number(growthThresholdPct);
    if (Number.isFinite(threshold) && threshold > 0) {
      formData.append("growth_threshold_pct", String(threshold));
    }

    const startedAtIso = new Date().toISOString().replace("T", " ").slice(0, 19);
    localStorage.setItem(HEALTHCHECK_RUNNING_KEY, startedAtIso);
    setLoading(true);
    setInfo("Health check started. Results will post to Slack as a PDF link when ready.");

    const runPromise: Promise<RunPayload> = (async () => {
      const res = await fetch("/api/runs/health-check", { method: "POST", body: formData });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(parseApiError(text, res.status));
      }
      const started = (await res.json()) as RunPayload;
      const runId = String(started.run_id || "").trim();
      if (!runId) {
        throw new Error("Server did not return run_id");
      }
      localStorage.setItem(HEALTHCHECK_RUN_ID_KEY, runId);
      return pollHealthCheckRun(runId, (msg) => setInfo(msg));
    })();
    inFlightHealthCheck = { startedAtIso, runId: "", promise: runPromise };

    try {
      const data = await runPromise;
      setResult(data);
      const st = String(data.status || "").toLowerCase();
      if (st === "cancelled") {
        setInfo("Health check stopped.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
      localStorage.removeItem(HEALTHCHECK_RUNNING_KEY);
      localStorage.removeItem(HEALTHCHECK_RUN_ID_KEY);
      inFlightHealthCheck = null;
    }
  }

  const succeeded = typeof result?.operators_succeeded === "number" ? result.operators_succeeded : null;
  const failed = typeof result?.operators_failed === "number" ? result.operators_failed : null;

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
        <h2 className="font-display text-2xl font-semibold text-ink-900">Health Check</h2>
        <p className="mt-1 max-w-3xl text-ink-600">
          Pick operators and run weekly WoW analysis. A configurable growth gate checks sales, payouts,
          orders, AOV, and new customers — if any metric is below your WoW threshold, the agent deep-dives
          platform → store → day → slot for that metric only. Campaign review runs automatically when
          marketing data is downloaded. Use <strong>View in browser</strong> for the full styled report.
        </p>
      </div>

      <form onSubmit={onSubmit} className="brand-card grid gap-4 rounded-[28px] p-6">
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
                  <span>
                    {op.business_name}
                    {!op.doordash_email?.trim() ? (
                      <span className="ml-1 text-xs text-amber-700">(no DoorDash login)</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 sm:max-w-xs">
          <label htmlFor="growth-threshold" className="text-sm font-medium text-ink-700">
            WoW growth threshold (%)
          </label>
          <input
            id="growth-threshold"
            type="number"
            min={0}
            step={0.5}
            value={growthThresholdPct}
            onChange={(e) => setGrowthThresholdPct(e.target.value)}
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm text-ink-800"
          />
          <p className="text-xs text-ink-500">
            Each gate metric must grow at least this much week-over-week (default 2). Try 5 or 10 for stricter checks.
          </p>
        </div>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        )}
        {info && !error && (
          <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-ink-700">{info}</div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
            {loading ? "Health check running..." : "Run health check"}
          </button>
          {loading ? (
            <button
              type="button"
              onClick={() => void stopHealthCheck()}
              disabled={stopping}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-red-300 bg-white px-5 py-3 text-sm font-semibold text-red-800 transition hover:bg-red-50 disabled:opacity-60"
            >
              <Square className="h-4 w-4 fill-current" />
              {stopping ? "Stopping…" : "Stop"}
            </button>
          ) : null}
        </div>
      </form>

      {result && (
        <div className="brand-card rounded-[28px] p-6">
          <h3 className="font-display text-lg font-semibold text-ink-900">Reports</h3>
          {wowWeeks?.previous_completed && wowWeeks?.current_completed ? (
            <p className="mt-1 text-sm text-ink-600">
              WoW window: {wowWeeks.previous_completed} → {wowWeeks.current_completed}
              {succeeded != null ? (
                <>
                  {" "}
                  · {succeeded} succeeded
                  {failed ? `, ${failed} failed` : ""}
                </>
              ) : null}
            </p>
          ) : null}

          {reportCards.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-3">
              {reportCards.map((card) => (
                <li key={card.operator} className="flex flex-wrap items-center gap-2">
                  <span className="min-w-[10rem] text-sm font-medium text-ink-800">{card.operator}</span>
                  {card.browserUrl ? (
                    <a
                      href={card.browserUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-semibold text-ink-800 hover:bg-brand-50"
                    >
                      <ExternalLink className="h-4 w-4" />
                      View in browser
                    </a>
                  ) : null}
                  {card.pdfUrl ? (
                    <a
                      href={card.pdfUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 rounded-2xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
                    >
                      <FileText className="h-4 w-4" />
                      {card.pdfIsDrive ? "Open PDF (Drive)" : "Open PDF"}
                    </a>
                  ) : (
                    <span className="text-xs text-amber-800">
                      PDF not ready — run{" "}
                      <code className="rounded bg-amber-50 px-1">python -m playwright install chromium</code>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : failedOperators.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-3">
              {failedOperators.map((row) => (
                <li
                  key={String(row.operator || row.email)}
                  className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
                >
                  <span className="font-medium">{row.operator || row.email}</span>
                  <p className="mt-1 text-red-800">
                    {row.failure_reason ||
                      "Download or processing failed. Check API logs (terminal running ./run.sh)."}
                  </p>
                  {(row.failure_reason || "").includes("multilogin_signin_failed") ? (
                    <p className="mt-2 text-xs text-red-700">
                      This is not a Playwright issue. Update{" "}
                      <code className="rounded bg-red-100/80 px-1">MULTILOGIN_USERNAME</code> /{" "}
                      <code className="rounded bg-red-100/80 px-1">MULTILOGIN_PASSWORD_B64</code> in{" "}
                      <code className="rounded bg-red-100/80 px-1">.env</code>, confirm login at
                      app.multilogin.com, restart <code className="rounded bg-red-100/80 px-1">./run.sh</code>,
                      and keep the Multilogin desktop app open.
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-ink-600">
              No report links yet. If downloads failed, check the terminal logs. PDF export needs Playwright
              Chromium: <code className="rounded bg-brand-50 px-1">python -m playwright install chromium</code>
            </p>
          )}

          {growthHealthByOperator.length > 0 ? (
            <div className="mt-8 border-t border-brand-100 pt-6">
              <h4 className="font-display text-base font-semibold text-ink-900">Growth health gate</h4>
              <p className="mt-1 text-sm text-ink-600">
                Combined WoW check on sales, payouts, orders, AOV, and new customers. Deep dive only when a
                metric misses the threshold.
              </p>
              <ul className="mt-4 flex flex-col gap-4">
                {growthHealthByOperator.map(({ operator, growth }) => {
                  const healthy = growth.status === "healthy";
                  return (
                    <li
                      key={operator}
                      className={`rounded-xl border px-4 py-3 text-sm ${
                        healthy
                          ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                          : "border-amber-200 bg-amber-50 text-amber-950"
                      }`}
                    >
                      <p className="font-medium">{operator}</p>
                      <p className="mt-1">{growth.summary}</p>
                      {!healthy && growth.unhealthy_metrics?.length ? (
                        <p className="mt-1 text-xs opacity-90">
                          Deep dive: {growth.unhealthy_metrics.join(", ")} · threshold {growth.threshold_pct}%
                        </p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}

          {campaignReviewByOperator.length > 0 ? (
            <div className="mt-8 border-t border-brand-100 pt-6">
              <h4 className="font-display text-base font-semibold text-ink-900">Campaign review</h4>
              <p className="mt-1 text-sm text-ink-600">
                Pre/post metrics and recommendations from the marketing download (included in this health check run).
              </p>
              <ul className="mt-4 flex flex-col gap-6">
                {campaignReviewByOperator.map(({ operator, review }) => {
                  const reviews = review.campaign_reviews ?? [];
                  return (
                    <li key={operator}>
                      <p className="text-sm font-medium text-ink-800">{operator}</p>
                      {review.error ? (
                        <p className="mt-1 text-sm text-amber-800">{review.error}</p>
                      ) : reviews.length > 0 ? (
                        <div className="mt-2 overflow-x-auto rounded-xl border border-brand-100">
                          <table className="min-w-full text-left text-sm">
                            <thead className="bg-brand-50 text-ink-700">
                              <tr>
                                <th className="px-3 py-2">Campaign</th>
                                <th className="px-3 py-2">Recommendation</th>
                                <th className="px-3 py-2">AOV lift %</th>
                                <th className="px-3 py-2">Order lift %</th>
                                <th className="px-3 py-2">Net revenue Δ</th>
                              </tr>
                            </thead>
                            <tbody>
                              {reviews.map((item, idx) => (
                                <tr key={`${item.campaign_name ?? "c"}-${idx}`} className="border-t border-brand-50">
                                  <td className="px-3 py-2">{item.campaign_name ?? "—"}</td>
                                  <td className="px-3 py-2 font-medium">{item.recommendation ?? "—"}</td>
                                  <td className="px-3 py-2">{item.aov_lift_pct ?? "—"}</td>
                                  <td className="px-3 py-2">{item.order_volume_lift_pct ?? "—"}</td>
                                  <td className="px-3 py-2">{item.net_revenue_delta ?? "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="mt-1 text-sm text-ink-500">No campaign rows produced.</p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
