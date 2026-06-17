import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import { OperatorAccountPicker } from "../components/OperatorAccountPicker";
import { AgentRunLogPanel } from "../components/AgentRunLogPanel";
import { appendAgentLogLines, pollAgentRun } from "../lib/agentRunPolling";

type AdsMode = "manual" | "auto";

export function AdsPage() {
  const [operatorId, setOperatorId] = useState("");
  const [mode, setMode] = useState<AdsMode>("auto");
  const [adsSheetFile, setAdsSheetFile] = useState<File | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [queuePosition, setQueuePosition] = useState<number | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setRunId(null);
    setRunStatus(null);
    setQueuePosition(null);
    setLogLines([]);

    if (!operatorId.trim()) {
      setError("Enter an Operator ID.");
      return;
    }
    if (!email.trim() || !password) {
      setError("DoorDash email and password are required for browser login.");
      return;
    }
    if (mode === "manual" && !adsSheetFile) {
      setError("Upload an ads plan sheet (.csv or .xlsx) in Manual mode.");
      return;
    }

    const formData = new FormData();
    formData.append("operator_id", operatorId.trim());
    formData.append("mode", mode);
    formData.append("doordash_email", email.trim());
    formData.append("doordash_password", password);
    if (mode === "manual" && adsSheetFile) {
      formData.append("ads_sheet_file", adsSheetFile);
    }

    setLoading(true);
    try {
      const res = await fetch("/api/runs/ads", { method: "POST", body: formData });
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

      const final = await pollAgentRun("ads", id, {
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
      setResult(final);
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
        <h2 className="font-display text-2xl font-semibold text-ink-900">RalphAI — Ads</h2>
        <p className="mt-1 max-w-2xl text-ink-600">
          <strong>Auto</strong> (default): loads the latest Strategist <strong>Ads Campaign Mappings</strong> sheet from{" "}
          <code>data/Strategist/</code>, then runs sponsored listing browser automation with Slack updates.
        </p>
        <p className="mt-2 max-w-2xl text-sm text-ink-600">
          <strong>Manual</strong>: upload CSV/Excel (sheet <strong>Ads</strong>). Columns: Merchant store ID, Slots
          (tags 1–42), Bid strategy, Campaign name. Portal flow: Marketing → Run a campaign →{" "}
          <strong>Advertise to all customers</strong>, audience <strong>Existing customers</strong>, custom schedule.
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
          showDoorDashCredentials
        />

        <label className="flex flex-col gap-1 sm:col-span-2 max-w-md">
          <span className="text-sm font-medium text-ink-700">Mode</span>
          <select
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            value={mode}
            onChange={(e) => setMode(e.target.value as AdsMode)}
          >
            <option value="auto">Auto (latest Strategist Ads sheet)</option>
            <option value="manual">Manual (upload Ads sheet)</option>
          </select>
        </label>

        {mode === "manual" ? (
          <label className="flex flex-col gap-1 sm:col-span-2">
            <span className="text-sm font-medium text-ink-700">CSV/Excel (Excel uses sheet named "Ads")</span>
            <input
              type="file"
              accept=".csv,.xlsx,.xls,.xlsm,.xltx,.xltm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
              className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              onChange={(e) => setAdsSheetFile(e.target.files?.[0] ?? null)}
            />
          </label>
        ) : null}

        {error ? (
          <div className="sm:col-span-2 rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">{error}</div>
        ) : null}

        <div className="sm:col-span-2 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading
              ? mode === "manual"
                ? "Running Ads setup..."
                : "Creating Ads campaigns..."
              : "Run RalphAI — Ads"}
          </button>
        </div>
      </form>

      {runId ? (
        <AgentRunLogPanel
          agent="ads"
          runId={runId}
          status={runStatus}
          queuePosition={queuePosition}
          lines={logLines}
        />
      ) : null}

      {result ? (
        <div className="brand-card rounded-[24px] p-5">
          <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
          <p className="mt-2 text-sm text-ink-700">Status: {String(result.status ?? "unknown")}</p>
          {result.mode != null ? <p className="mt-1 text-sm text-ink-600">Mode: {String(result.mode)}</p> : null}
          {result.run_id ? (
            <p className="mt-1 text-sm text-ink-600">Run ID: {String(result.run_id)}</p>
          ) : null}
          {result.rows_file ? (
            <p className="mt-1 text-sm text-ink-600">Sheet: {String(result.rows_file)}</p>
          ) : null}
          {result.campaigns_source ? (
            <p className="mt-1 text-sm text-ink-600">Sheet: {String(result.campaigns_source)}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
