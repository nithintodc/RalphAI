import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Skull } from "lucide-react";
import type { AccountOperator } from "../components/OperatorAccountPicker";
interface OperatorResult {
  operator_id: string;
  email: string;
  status: string;
  campaigns_ended: string[];
  campaigns_ended_count: number;
  errors: string[];
}

export function CampaignKillerPage() {
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [selectedOperatorIds, setSelectedOperatorIds] = useState<string[]>([]);
  const [headless, setHeadless] = useState(false);
  const [searchTodcInTable, setSearchTodcInTable] = useState(true);
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
    formData.append("headless", headless ? "true" : "false");
    formData.append("search_todc", searchTodcInTable ? "true" : "false");

    setLoading(true);
    try {
      const res = await fetch("/api/runs/campaign-killer", { method: "POST", body: formData });
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

  const runResults = Array.isArray(result?.results) ? (result.results as OperatorResult[]) : [];
  const totalEnded = typeof result?.total_campaigns_ended === "number" ? result.total_campaigns_ended : 0;

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
        <h2 className="font-display text-2xl font-semibold text-ink-900">Campaign Killer</h2>
        <p className="mt-1 max-w-3xl text-ink-600">
          Run from here with the button below — no terminal needed. Ends active DoorDash campaigns whose names
          start with <strong className="font-medium">TODC-</strong>.
          Logs in, opens Campaigns, sets <strong className="font-medium">All statuses</strong> to{" "}
          <strong className="font-medium">Active</strong> and Apply, then ends each matching row via the row
          menu, confirms <strong className="font-medium">Yes, end</strong>, selects{" "}
          <strong className="font-medium">Technical issue — I have trouble with the campaign settings</strong>,
          and clicks <strong className="font-medium">End campaign</strong>. Like other merchant automations, a
          visible browser window opens so you can complete MFA or captcha if prompted.
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

        <div className="flex flex-col gap-3 rounded-xl border border-brand-100 bg-brand-50/40 p-4">
          <div className="text-xs font-medium uppercase tracking-wide text-ink-500">Run options</div>
          <label className="inline-flex cursor-pointer items-start gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={headless}
              onChange={(e) => setHeadless(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
            />
            <span>
              <span className="font-medium">Headless browser</span>
              <span className="block text-ink-500">
                No window (fails if login needs MFA/captcha). Leave off for interactive login.
              </span>
            </span>
          </label>
          <label className="inline-flex cursor-pointer items-start gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={searchTodcInTable}
              onChange={(e) => setSearchTodcInTable(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500"
            />
            <span>
              <span className="font-medium">Search table for TODC</span>
              <span className="block text-ink-500">
                Narrows the list to campaigns whose names contain <strong>TODC</strong> (e.g.{" "}
                <strong>TODC-26081-$10</strong>) before Active filter. Recommended on; turn off only if search
                fails on a UI change.
              </span>
            </span>
          </label>
        </div>

        {error ? <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">{error}</div> : null}

        <div className="pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-red-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Skull className="h-4 w-4" />}
            {loading ? "Running…" : "Run Campaign Killer"}
          </button>
        </div>
      </form>

      {result ? (
        <div className="brand-card rounded-[24px] p-5">
          <h3 className="font-display text-lg font-semibold text-ink-900">Kill Results</h3>
          <div className="mt-2 flex gap-6 text-sm">
            <p className="text-ink-700">Status: <span className="font-medium">{String(result.status ?? "unknown")}</span></p>
            <p className="text-ink-700">Operators: <span className="font-medium">{String(result.total_operators ?? 0)}</span></p>
            <p className="text-red-600 font-semibold">Campaigns ended: {totalEnded}</p>
          </div>

          {runResults.length > 0 && (
            <div className="mt-4 max-h-[420px] overflow-auto rounded-xl border border-brand-100">
              <table className="w-full text-left text-sm">
                <thead className="bg-brand-50 text-ink-700 sticky top-0">
                  <tr>
                    <th className="px-3 py-2">Operator</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Ended</th>
                    <th className="px-3 py-2">Campaigns</th>
                    <th className="px-3 py-2">Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {runResults.map((row, idx) => (
                    <tr key={`${row.operator_id}-${idx}`} className="border-t border-brand-100">
                      <td className="px-3 py-2">{row.operator_id}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                            row.status === "success"
                              ? "bg-green-100 text-green-700"
                              : row.status === "skipped_2fa"
                                ? "bg-orange-100 text-orange-700"
                                : row.status === "login_failed"
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-red-100 text-red-700"
                          }`}
                        >
                          {row.status === "skipped_2fa" ? "2FA — skipped" : row.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-semibold">{row.campaigns_ended_count}</td>
                      <td className="px-3 py-2 text-xs text-ink-500">
                        {row.campaigns_ended.length > 0
                          ? row.campaigns_ended.join(", ")
                          : "—"}
                      </td>
                      <td className="px-3 py-2 text-xs text-red-500">
                        {row.errors.length > 0 ? row.errors.join("; ") : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
