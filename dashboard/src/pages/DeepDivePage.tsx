import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Play, Loader2 } from "lucide-react";

export function DeepDivePage() {
  const [operatorId, setOperatorId] = useState("TriArch");
  const [zipFiles, setZipFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setReportUrl(null);
    
    if (!operatorId.trim()) {
      setError("Enter an Operator ID.");
      return;
    }

    if (zipFiles.length === 0) {
      setError("Upload at least one DoorDash zip export before running DeepDive.");
      return;
    }
    
    const formData = new FormData();
    formData.append("operator_id", operatorId.trim());
    zipFiles.forEach((file) => formData.append("zip_files", file));

    setLoading(true);
    try {
      const res = await fetch("/api/runs/deepdive", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.report_url) {
        setReportUrl(data.report_url);
      } else {
        throw new Error("No report URL returned");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <Link
            to="/agents"
            className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to agents
          </Link>
          <h2 className="font-display text-2xl font-semibold text-ink-900">DeepDive</h2>
          <p className="mt-1 max-w-2xl text-ink-600">
            Upload the same DoorDash zip exports here, let DeepDive open and analyze them, and generate a structured HTML report.
          </p>
        </div>
      </div>

      <form
        onSubmit={onSubmit}
        className="brand-card grid gap-4 rounded-[28px] p-6 sm:grid-cols-2 flex-shrink-0"
      >
        <div className="sm:col-span-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">Configuration</h3>
        </div>
        
        <label className="flex flex-col gap-1 sm:col-span-2 max-w-md">
          <span className="text-sm font-medium text-ink-700">Operator ID</span>
          <input
            type="text"
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            placeholder="e.g. TriArch"
            required
          />
        </label>

        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-sm font-medium text-ink-700">DoorDash zip exports</span>
          <input
            type="file"
            accept=".zip"
            multiple
            className="rounded-xl border border-brand-200 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            onChange={(e) => setZipFiles(Array.from(e.target.files ?? []))}
          />
          <span className="text-xs text-ink-500">
            CLI default reads zips from <code className="text-ink-800">data/data/TriArch</code>. Here, upload one or more
            DoorDash export zips; DeepDive will extract them and build the report.
          </span>
          {zipFiles.length > 0 ? (
            <span className="text-xs text-ink-600">
              Selected: {zipFiles.map((file) => file.name).join(", ")}
            </span>
          ) : null}
        </label>

        {error && (
          <div className="sm:col-span-2 rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">
            {error}
          </div>
        )}

        <div className="sm:col-span-2 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? "Uploading and analyzing..." : "Upload and run DeepDive"}
          </button>
        </div>
      </form>

      {reportUrl && (
        <div className="flex-1 min-h-[600px] brand-card rounded-[28px] overflow-hidden flex flex-col">
          <div className="bg-brand-50/50 px-4 py-3 border-b border-brand-100 flex justify-between items-center">
            <h3 className="font-display font-semibold text-ink-900">Analysis Report</h3>
            <a 
              href={reportUrl} 
              target="_blank" 
              rel="noreferrer"
              className="text-sm text-brand-700 hover:text-brand-800 font-medium"
            >
              Open in new tab
            </a>
          </div>
          <iframe 
            src={reportUrl} 
            className="w-full flex-1 border-0 bg-white"
            title="DeepDive Report"
          />
        </div>
      )}
    </div>
  );
}
