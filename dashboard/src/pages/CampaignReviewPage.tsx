import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import { OperatorAccountPicker } from "../components/OperatorAccountPicker";

type ReviewMode = "manual" | "auto";

export function CampaignReviewPage() {
  const [operatorId, setOperatorId] = useState("");
  const [mode, setMode] = useState<ReviewMode>("manual");
  const [marketingFiles, setMarketingFiles] = useState<File[]>([]);
  const [dataDir, setDataDir] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!operatorId.trim()) {
      setError("Enter an Operator ID.");
      return;
    }
    if (mode === "manual" && marketingFiles.length === 0) {
      setError("Upload at least one marketing file (.zip/.csv) in Manual mode.");
      return;
    }

    const formData = new FormData();
    formData.append("operator_id", operatorId.trim());
    formData.append("mode", mode);
    if (mode === "manual") {
      marketingFiles.forEach((file) => formData.append("marketing_files", file));
    } else if (dataDir.trim()) {
      formData.append("data_dir", dataDir.trim());
    }

    setLoading(true);
    try {
      const res = await fetch("/api/runs/campaign-review", { method: "POST", body: formData });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setResult(await res.json());
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
        <h2 className="font-display text-2xl font-semibold text-ink-900">Campaign Review</h2>
        <p className="mt-1 max-w-2xl text-ink-600">
          Review campaign performance with pre/post metrics and recommendations.
        </p>
      </div>

      <form onSubmit={onSubmit} className="brand-card grid gap-4 rounded-[28px] p-6 sm:grid-cols-2">
        <OperatorAccountPicker
          operatorId={operatorId}
          onOperatorIdChange={setOperatorId}
          email=""
          onEmailChange={() => {}}
          password=""
          onPasswordChange={() => {}}
          showDoorDashCredentials={false}
        />

        <label className="flex flex-col gap-1 sm:col-span-2 max-w-md">
          <span className="text-sm font-medium text-ink-700">Mode</span>
          <select
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            value={mode}
            onChange={(e) => setMode(e.target.value as ReviewMode)}
          >
            <option value="manual">Manual upload</option>
            <option value="auto">Auto mode</option>
          </select>
        </label>

        {mode === "manual" ? (
          <label className="flex flex-col gap-1 sm:col-span-2">
            <span className="text-sm font-medium text-ink-700">Marketing files (.zip or .csv)</span>
            <input
              type="file"
              accept=".zip,.csv"
              multiple
              className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              onChange={(e) => setMarketingFiles(Array.from(e.target.files ?? []))}
            />
          </label>
        ) : (
          <label className="flex flex-col gap-1 sm:col-span-2">
            <span className="text-sm font-medium text-ink-700">Data directory (optional)</span>
            <input
              type="text"
              className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={dataDir}
              onChange={(e) => setDataDir(e.target.value)}
              placeholder="e.g. /path/to/TriArch/folder"
            />
          </label>
        )}

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
            {loading ? "Running Campaign Review..." : "Run Campaign Review"}
          </button>
        </div>
      </form>

      {result ? (
        <div className="brand-card rounded-[24px] p-5">
          <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
          <p className="mt-2 text-sm text-ink-700">Status: success</p>
          <p className="mt-1 text-sm text-ink-600">Mode: {String(result.mode ?? mode)}</p>
          <p className="mt-1 text-sm text-ink-600">
            Campaign reviews: {Array.isArray(result.campaign_reviews) ? result.campaign_reviews.length : 0}
          </p>
        </div>
      ) : null}
    </div>
  );
}
