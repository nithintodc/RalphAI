import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Activity } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";

const HEALTHCHECK_RUNNING_KEY = "healthcheck:running";

type RunPayload = Record<string, unknown>;
type InFlightHealthCheck = {
  startedAtIso: string;
  promise: Promise<RunPayload>;
};

let inFlightHealthCheck: InFlightHealthCheck | null = null;

export function HealthCheckPage() {
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [selectedOperatorIds, setSelectedOperatorIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

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
    if (!persisted) return () => {
      cancelled = true;
    };

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
          setInfo("Background health check finished. Open Runs for latest status details.");
          localStorage.removeItem(HEALTHCHECK_RUNNING_KEY);
        }
      } catch {
        // Ignore polling failures, keep state until user refreshes.
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
      setError("Selected operators have no DoorDash login in the account file.");
      return;
    }

    const formData = new FormData();
    formData.append("operator_emails", JSON.stringify(emails));

    const startedAtIso = new Date().toISOString().replace("T", " ").slice(0, 19);
    localStorage.setItem(HEALTHCHECK_RUNNING_KEY, startedAtIso);
    setLoading(true);
    setInfo("Health check started. Status will remain even if you navigate away.");

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

  const masterSheets = Array.isArray(result?.master_sheets)
    ? (result.master_sheets as string[])
    : [];
  const outputDir = typeof result?.output_dir === "object" && result.output_dir !== null
    ? JSON.stringify(result.output_dir)
    : typeof result?.output_dir === "string"
      ? result.output_dir
      : "";

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
          Pick operators and run. The agent logs into each DoorDash account in order, pulls <strong>one</strong>{" "}
          combined export for the last two completed Mon–Sun weeks (financial + marketing), splits them into weekly
          CSVs, then builds WoW analysis (previous completed week vs the most recent completed week). No dates or
          week counts to configure — the window is always “today” relative to the server clock.
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
        <div className="brand-card rounded-[28px] p-6 text-sm text-ink-700">
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-brand-50/80 p-4 font-mono text-xs">
            {JSON.stringify(result, null, 2)}
          </pre>
          {outputDir && (
            <p className="mt-3 text-ink-600">
              Output directory: <code className="rounded bg-white px-1">{outputDir}</code>
            </p>
          )}
          {masterSheets.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-ink-600">
              {masterSheets.map((p) => (
                <li key={p}>
                  <code className="text-xs">{p}</code>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
