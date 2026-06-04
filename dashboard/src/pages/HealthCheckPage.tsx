import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Activity, ExternalLink, FileText } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";

const HEALTHCHECK_RUNNING_KEY = "healthcheck:running";

type RunPayload = Record<string, unknown>;
type InFlightHealthCheck = {
  startedAtIso: string;
  promise: Promise<RunPayload>;
};

type OperatorReport = {
  operator?: string;
  email?: string;
  status?: string;
  browser_report_url?: string;
  pdf_drive_url?: string;
  pdf_local_url?: string;
  pdf_public_url?: string;
  pdf_export_ok?: boolean;
  wow_viz_html?: string;
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
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [result, setResult] = useState<RunPayload | null>(null);

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

    const persisted = localStorage.getItem(HEALTHCHECK_RUNNING_KEY);
    if (!persisted) {
      return () => {
        cancelled = true;
      };
    }

    setLoading(true);
    setInfo("Health check is still running in background.");

    const poll = async () => {
      try {
        const res = await fetch("/api/runs");
        if (!res.ok) return;
        const runs = (await res.json()) as Array<{
          agent?: string;
          started?: string;
          status?: string;
        }>;
        const startedAt = persisted;
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

  const wowWeeks = result?.wow_weeks as
    | { previous_completed?: string; current_completed?: string }
    | undefined;

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

    const startedAtIso = new Date().toISOString().replace("T", " ").slice(0, 19);
    localStorage.setItem(HEALTHCHECK_RUNNING_KEY, startedAtIso);
    setLoading(true);
    setInfo("Health check started. Results will post to Slack as a PDF link when ready.");

    const runPromise: Promise<RunPayload> = (async () => {
      const res = await fetch("/api/runs/health-check", { method: "POST", body: formData });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      return (await res.json()) as RunPayload;
    })();
    inFlightHealthCheck = { startedAtIso, promise: runPromise };

    try {
      setResult(await runPromise);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
      localStorage.removeItem(HEALTHCHECK_RUNNING_KEY);
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
          Pick operators and run. Use <strong>View in browser</strong> for the full styled report (tables and
          colours). Open PDF (Drive) is the same report as a PDF in Google Drive — also what Slack links to.
          HTML is never uploaded to Drive (Drive only shows raw HTML source).
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

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        )}
        {info && !error && (
          <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-ink-700">{info}</div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
          {loading ? "Health check running..." : "Run health check"}
        </button>
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
          ) : (
            <p className="mt-3 text-sm text-ink-600">
              No report link for the selected operators yet. Re-run the health check after Playwright Chromium
              is installed.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
