import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";

type ReportTypeOption = {
  id: string;
  label: string;
  description: string;
};

function defaultDateRange(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  start.setMonth(start.getMonth() - 3);
  start.setDate(1);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

const FALLBACK_REPORT_TYPES: ReportTypeOption[] = [
  { id: "financial", label: "Financial report", description: "Transactions, payouts." },
  { id: "operations", label: "Operations report", description: "Accuracy, wait time, product mix." },
  { id: "sales", label: "Sales report", description: "Sales, orders, ticket size." },
  { id: "product_mix", label: "Product mix report", description: "Products sold and errors." },
  { id: "marketing", label: "Marketing report", description: "Campaign performance." },
  { id: "refund", label: "Refund report", description: "Refund reasons and values." },
];

export function DataRunPage() {
  const defaults = useMemo(() => defaultDateRange(), []);
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [reportTypes, setReportTypes] = useState<ReportTypeOption[]>(FALLBACK_REPORT_TYPES);
  const [selectedOperatorIds, setSelectedOperatorIds] = useState<string[]>([]);
  const [selectedReportTypeIds, setSelectedReportTypeIds] = useState<string[]>(["financial", "marketing"]);
  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [opRes, typeRes] = await Promise.all([
          fetch("/api/account-directory"),
          fetch("/api/data-run/report-types"),
        ]);
        if (!cancelled && opRes.ok) {
          const data = (await opRes.json()) as { operators?: AccountOperator[] };
          setOperators(Array.isArray(data.operators) ? data.operators : []);
        }
        if (!cancelled && typeRes.ok) {
          const data = (await typeRes.json()) as { report_types?: ReportTypeOption[] };
          if (Array.isArray(data.report_types) && data.report_types.length) {
            setReportTypes(data.report_types);
          }
        }
      } catch {
        if (!cancelled) {
          setError("Could not load operators or report types from API.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedOperatorSet = useMemo(() => new Set(selectedOperatorIds), [selectedOperatorIds]);
  const selectedReportSet = useMemo(() => new Set(selectedReportTypeIds), [selectedReportTypeIds]);

  function toggleOperator(operatorId: string) {
    setSelectedOperatorIds((prev) =>
      prev.includes(operatorId) ? prev.filter((v) => v !== operatorId) : [...prev, operatorId]
    );
  }

  function toggleReportType(id: string) {
    setSelectedReportTypeIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!selectedOperatorIds.length) {
      setError("Select at least one operator.");
      return;
    }
    if (!selectedReportTypeIds.length) {
      setError("Select at least one report type.");
      return;
    }
    if (!startDate || !endDate) {
      setError("Start and end dates are required.");
      return;
    }
    if (endDate < startDate) {
      setError("End date must be on or after start date.");
      return;
    }

    const formData = new FormData();
    formData.append("operator_ids", JSON.stringify(selectedOperatorIds));
    formData.append("report_types", JSON.stringify(selectedReportTypeIds));
    formData.append("start_date", startDate);
    formData.append("end_date", endDate);

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
  const dateRange = (result?.date_range || {}) as Record<string, string>;

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
          DoorDash data download via Multilogin: each operator opens its mapped profile, goes straight to Reports if
          already signed in, otherwise logs in with credentials from operator_multilogin_mapping.json. Zip files are
          saved under{" "}
          <code className="rounded bg-brand-50 px-1.5 py-0.5 text-xs">data/DataRun/&#123;timestamp&#125;/&#123;operator&#125;/</code>{" "}
          (zips only — never extracted).
        </p>
      </div>

      <form onSubmit={onSubmit} className="brand-card grid gap-5 rounded-[28px] p-6">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-ink-700">Operators (multi-select)</div>
            <div className="inline-flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSelectedOperatorIds(operators.map((op) => op.operator_id))}
                className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-brand-50"
              >
                Select all
              </button>
              <button
                type="button"
                onClick={() => setSelectedOperatorIds([])}
                className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-brand-50"
              >
                Clear all
              </button>
            </div>
          </div>
          <div className="max-h-56 overflow-auto rounded-xl border border-brand-200 p-3">
            <div className="grid gap-2 sm:grid-cols-2">
              {operators.map((op) => (
                <label key={op.operator_id} className="inline-flex items-start gap-2 text-sm text-ink-700">
                  <input
                    type="checkbox"
                    checked={selectedOperatorSet.has(op.operator_id)}
                    onChange={() => toggleOperator(op.operator_id)}
                    className="mt-0.5 h-4 w-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
                  />
                  <span>{op.business_name}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-ink-700">Report types (multi-select)</div>
            <div className="inline-flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSelectedReportTypeIds(reportTypes.map((r) => r.id))}
                className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-brand-50"
              >
                Select all
              </button>
              <button
                type="button"
                onClick={() => setSelectedReportTypeIds([])}
                className="rounded-lg border border-brand-200 px-3 py-1.5 text-xs font-medium text-ink-700 hover:bg-brand-50"
              >
                Clear all
              </button>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {reportTypes.map((rt) => (
              <label
                key={rt.id}
                className="flex cursor-pointer gap-3 rounded-xl border border-brand-100 p-3 hover:border-brand-200 hover:bg-brand-50/40"
              >
                <input
                  type="checkbox"
                  checked={selectedReportSet.has(rt.id)}
                  onChange={() => toggleReportType(rt.id)}
                  className="mt-1 h-4 w-4 shrink-0 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
                />
                <span>
                  <span className="block text-sm font-medium text-ink-800">{rt.label}</span>
                  <span className="mt-0.5 block text-xs text-ink-500">{rt.description}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-700">
            From date
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
              className="rounded-xl border border-brand-200 px-3 py-2.5 text-sm font-normal text-ink-900"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-700">
            To date
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
              className="rounded-xl border border-brand-200 px-3 py-2.5 text-sm font-normal text-ink-900"
            />
          </label>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
        ) : null}

        <div className="pt-1">
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
          <p className="mt-2 text-sm text-ink-700">
            Status:{" "}
            <span
              className={
                result.status === "success"
                  ? "font-medium text-emerald-700"
                  : result.status === "partial"
                    ? "font-medium text-amber-700"
                    : "font-medium text-red-700"
              }
            >
              {String(result.status ?? "unknown")}
            </span>
          </p>
          <p className="mt-1 text-sm text-ink-600">
            Date range: {dateRange.start ?? "—"} → {dateRange.end ?? "—"}
          </p>
          <p className="mt-1 text-sm text-ink-600">
            Report types: {Array.isArray(result.report_types) ? (result.report_types as string[]).join(", ") : "—"}
          </p>
          {!!runResults.length ? (
            <div className="mt-4 max-h-80 overflow-auto rounded-xl border border-brand-100">
              <table className="w-full text-left text-sm">
                <thead className="bg-brand-50 text-ink-700">
                  <tr>
                    <th className="px-3 py-2">Operator</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Zips</th>
                    <th className="px-3 py-2">Error</th>
                    <th className="px-3 py-2">Folder</th>
                  </tr>
                </thead>
                <tbody>
                  {runResults.map((row, idx) => (
                    <tr key={`${String(row.operator_id ?? "op")}-${idx}`} className="border-t border-brand-100">
                      <td className="px-3 py-2">{String(row.business_name ?? row.operator_id ?? "")}</td>
                      <td className="px-3 py-2">{String(row.status ?? "")}</td>
                      <td className="px-3 py-2">
                        {Array.isArray(row.zip_files) ? row.zip_files.length : 0}
                      </td>
                      <td className="max-w-sm px-3 py-2 text-xs text-red-700">
                        {[
                          String(row.error ?? ""),
                          Array.isArray(row.warnings) ? (row.warnings as string[]).join("; ") : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      </td>
                      <td className="max-w-xs truncate px-3 py-2 text-xs text-ink-500">
                        {String(row.download_dir ?? "")}
                      </td>
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
