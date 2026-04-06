import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Download, Loader2, Table2 } from "lucide-react";

type TablePreview = { columns: string[]; rows: Record<string, unknown>[] };

function PreviewTable({ title, data }: { title: string; data: TablePreview | undefined }) {
  if (!data || !data.columns?.length) {
    return (
      <div className="rounded-2xl border border-brand-100 bg-brand-50/50 p-4 text-sm text-ink-500">
        No data for {title}
      </div>
    );
  }
  const cols = data.columns.slice(0, 24);
  return (
    <div className="overflow-hidden rounded-2xl border border-brand-200 bg-white">
      <div className="flex items-center gap-2 border-b border-brand-100 bg-brand-50/80 px-3 py-2">
        <Table2 className="h-4 w-4 text-brand-600" />
        <span className="text-sm font-semibold text-ink-800">{title}</span>
        <span className="text-xs text-ink-500">({data.rows.length} rows)</span>
      </div>
      <div className="max-h-[min(420px,50vh)] overflow-auto">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead className="sticky top-0 bg-white shadow-sm">
            <tr className="border-b border-brand-100">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-2 font-semibold text-ink-700">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-100">
            {data.rows.map((row, ri) => (
              <tr key={ri} className="hover:bg-brand-50/60">
                {cols.map((c) => (
                  <td key={c} className="max-w-[220px] truncate px-2 py-1.5 text-ink-700">
                    {row[c] === null || row[c] === undefined ? "—" : String(row[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function MonthlyReporterPage() {
  const [preRange, setPreRange] = useState("11/1/2025-11/30/2025");
  const [postRange, setPostRange] = useState("12/1/2025-12/31/2025");
  const [operatorId, setOperatorId] = useState("");
  const [operatorName, setOperatorName] = useState("");
  const [excludedDates, setExcludedDates] = useState("");
  const [ddStores, setDdStores] = useState("");
  const [ueStores, setUeStores] = useState("");
  const [ddFile, setDdFile] = useState<File | null>(null);
  const [ueFile, setUeFile] = useState<File | null>(null);
  /** Promotion & sponsored marketing CSVs — matches Streamlit multi file uploader. */
  const [marketingFiles, setMarketingFiles] = useState<File[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    run_id: string;
    summary_text?: string;
    preview?: { tables?: Record<string, TablePreview>; summary_text?: string };
    downloads?: { full: string; date: string | null };
  } | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!preRange.trim() || !postRange.trim()) {
      setError("Enter both Pre and Post date ranges (required). Same as Streamlit before Run Analysis.");
      return;
    }
    const fd = new FormData();
    fd.append("pre_range", preRange.trim());
    fd.append("post_range", postRange.trim());
    fd.append("operator_id", operatorId.trim());
    fd.append("operator_name", operatorName.trim());
    fd.append("excluded_dates", excludedDates.trim());
    fd.append("dd_store_ids", ddStores.trim());
    fd.append("ue_store_ids", ueStores.trim());
    if (ddFile) fd.append("dd_file", ddFile);
    if (ueFile) fd.append("ue_file", ueFile);
    marketingFiles.forEach((f) => fd.append("marketing_files", f));

    setLoading(true);
    try {
      const res = await fetch("/api/runs/monthly-reporter", {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const json = await res.json();
      setResult(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const tables = result?.preview?.tables;

  const allStreamlitSlotsFilled =
    Boolean(ddFile && ueFile && marketingFiles.length > 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <Link
            to="/agents"
            className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to agents
          </Link>
          <h2 className="font-display text-2xl font-semibold text-ink-900">Monthly Reporter</h2>
          <p className="mt-1 max-w-2xl text-ink-600">
            Matches App2.0 Streamlit: <strong className="font-medium text-ink-800">Pre and Post date ranges are required</strong>;
            DoorDash, UberEats, and marketing files are all optional — analysis runs with whatever you upload. Runs appear on{" "}
            <Link to="/runs" className="font-medium text-brand-700 underline">
              Runs
            </Link>
            .
          </p>
        </div>
      </div>

      <form
        onSubmit={onSubmit}
        className="brand-card grid gap-4 rounded-[28px] p-6 sm:grid-cols-2"
      >
        <div className="sm:col-span-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">Periods</h3>
          <p className="text-sm text-ink-500">Format: MM/DD/YYYY-MM/DD/YYYY for each range.</p>
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">Pre period</span>
          <input
            required
            value={preRange}
            onChange={(e) => setPreRange(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="11/1/2025-11/30/2025"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">Post period</span>
          <input
            required
            value={postRange}
            onChange={(e) => setPostRange(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="12/1/2025-12/31/2025"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">Operator ID (for Runs)</span>
          <input
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="op_north_01"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">Operator name (Excel filename tag)</span>
          <input
            value={operatorName}
            onChange={(e) => setOperatorName(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="alpha"
          />
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-sm font-medium text-ink-700">Exclude dates (optional)</span>
          <input
            value={excludedDates}
            onChange={(e) => setExcludedDates(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="11/28/2025, 11/29/2025"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">DoorDash store IDs filter (optional)</span>
          <input
            value={ddStores}
            onChange={(e) => setDdStores(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="101, 102"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">UberEats store IDs filter (optional)</span>
          <input
            value={ueStores}
            onChange={(e) => setUeStores(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="201, 202"
          />
        </label>

        <div className="sm:col-span-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">Upload data files</h3>
          <p className="text-sm text-ink-500">
            Step 2 in the Streamlit UI — DoorDash, UberEats, and marketing are each optional.
          </p>
          {!allStreamlitSlotsFilled ? (
            <p className="mt-2 text-xs text-ink-600">
              Some files are missing — analysis will proceed with available data only.
            </p>
          ) : null}
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">DoorDash financial (optional)</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setDdFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">UberEats financial (optional)</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setUeFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-sm font-medium text-ink-700">Marketing data (optional)</span>
          <p className="text-xs text-ink-500">
            Upload all <code className="rounded bg-brand-50 px-1">MARKETING_*.csv</code> files at once (Promotion &amp;
            Sponsored) — same as Streamlit &quot;Upload Marketing CSVs&quot;. They are organized under{" "}
            <code className="rounded bg-brand-50 px-1">marketing_data/marketing_*</code> automatically.
          </p>
          <input
            type="file"
            multiple
            accept=".csv,text/csv"
            onChange={(e) => setMarketingFiles(Array.from(e.target.files ?? []))}
            className="text-sm"
          />
          {marketingFiles.length > 0 ? (
            <p className="text-xs text-ink-600">
              {marketingFiles.length} file(s) selected: {marketingFiles.map((f) => f.name).join(", ")}
            </p>
          ) : null}
        </label>

        <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loading ? "Running…" : "Run Analysis"}
          </button>
          <p className="text-xs text-ink-500">
            Requires API: <code className="rounded bg-brand-50 px-1">PYTHONPATH=. uvicorn api.main:app --port 8000</code>
          </p>
        </div>
        {error ? (
          <div className="sm:col-span-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            {error}
          </div>
        ) : null}
      </form>

      {result ? (
        <div className="flex flex-col gap-4">
          <div className="brand-card rounded-[28px] p-6">
            <h3 className="font-display text-lg font-semibold text-ink-900">Summary</h3>
            <p className="mt-2 text-sm text-ink-700">{result.summary_text}</p>
            <p className="mt-3 text-xs text-ink-500">
              Run ID: <code className="rounded bg-brand-50 px-1">{result.run_id}</code>
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a
                href={result.downloads?.full}
                className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 shadow-sm hover:bg-brand-50"
              >
                <Download className="h-4 w-4" />
                Download full Excel
              </a>
              {result.downloads?.date ? (
                <a
                  href={result.downloads.date}
                  className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 shadow-sm hover:bg-brand-50"
                >
                  <Download className="h-4 w-4" />
                  Download date export
                </a>
              ) : null}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <PreviewTable title="Combined — Pre vs Post" data={tables?.combined_summary_pre_post} />
            <PreviewTable title="Combined — YoY" data={tables?.combined_summary_yoy} />
            <PreviewTable title="Combined stores — Pre vs Post" data={tables?.combined_store_pre_post} />
            <PreviewTable title="Combined stores — YoY" data={tables?.combined_store_yoy} />
            <PreviewTable title="Corporate vs TODC" data={tables?.corporate_vs_todc} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
