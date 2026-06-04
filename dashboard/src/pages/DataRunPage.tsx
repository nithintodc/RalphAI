import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";

export function DataRunPage() {
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [selectedOperatorIds, setSelectedOperatorIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

    const formData = new FormData();
    formData.append("operator_ids", JSON.stringify(selectedOperatorIds));

    setLoading(true);
    try {
      const res = await fetch("/api/runs/data-run", { method: "POST", body: formData });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setResult((await res.json()) as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const runResults = Array.isArray(result?.results) ? (result?.results as Record<string, unknown>[]) : [];

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
        <h2 className="font-display text-2xl font-semibold text-ink-900">Data Run</h2>
        <p className="mt-1 max-w-3xl text-ink-600">
          Runs browser-use reporting one operator at a time using DoorDash credentials from Airtable: login, download
          financial and marketing reports, close browser session, start a new session, and repeat.
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
                  <span>{op.business_name}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {error ? <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">{error}</div> : null}

        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? "Running Data Run..." : "Run Data Run"}
          </button>
        </div>
      </form>

      {result ? (
        <div className="brand-card rounded-[24px] p-5">
          <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
          <p className="mt-2 text-sm text-ink-700">Status: {String(result.status ?? "unknown")}</p>
          <p className="mt-1 text-sm text-ink-600">Operators: {String(result.selected_operator_count ?? 0)}</p>
          <p className="mt-1 text-sm text-ink-600">File type: both (financial + marketing)</p>
          {!!runResults.length ? (
            <div className="mt-4 max-h-72 overflow-auto rounded-xl border border-brand-100">
              <table className="w-full text-left text-sm">
                <thead className="bg-brand-50 text-ink-700">
                  <tr>
                    <th className="px-3 py-2">Operator</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Files</th>
                  </tr>
                </thead>
                <tbody>
                  {runResults.map((row, idx) => (
                    <tr key={`${String(row.operator_id ?? "op")}-${idx}`} className="border-t border-brand-100">
                      <td className="px-3 py-2">{String(row.business_name ?? row.operator_id ?? "")}</td>
                      <td className="px-3 py-2">{String(row.status ?? "")}</td>
                      <td className="px-3 py-2">{Array.isArray(row.selected_files) ? row.selected_files.length : 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

