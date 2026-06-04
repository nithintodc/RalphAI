import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  CalendarRange,
  Download,
  FileSpreadsheet,
  Loader2,
  Table2,
  Upload,
} from "lucide-react";

type TablePreview = { columns: string[]; rows: Record<string, unknown>[] };

type MonthlyReporterResult = {
  run_id: string;
  summary_text?: string;
  preview?: { tables?: Record<string, TablePreview>; summary_text?: string };
  downloads?: { full: string; date: string | null; bucketing: string | null; deepdive?: string | null };
};

function PreviewTable({ title, data }: { title: string; data: TablePreview | undefined }) {
  if (!data || !data.columns?.length) {
    return (
      <div className="rounded-[24px] border border-brand-100 bg-brand-50/50 p-4 text-sm text-ink-500">
        No data for {title}
      </div>
    );
  }

  const cols = data.columns.slice(0, 24);
  return (
    <div className="overflow-hidden rounded-[24px] border border-brand-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-brand-100 bg-brand-50/80 px-4 py-3">
        <Table2 className="h-4 w-4 text-brand-600" />
        <span className="text-sm font-semibold text-ink-800">{title}</span>
        <span className="text-xs text-ink-500">({data.rows.length} rows)</span>
      </div>
      <div className="max-h-[min(420px,50vh)] overflow-auto">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead className="sticky top-0 bg-white shadow-sm">
            <tr className="border-b border-brand-100">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-2 font-semibold text-ink-700">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-100">
            {data.rows.map((row, ri) => (
              <tr key={ri} className="hover:bg-brand-50/60">
                {cols.map((c) => (
                  <td key={c} className="max-w-[240px] truncate px-3 py-2 text-ink-700">
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

function PreviewSection({
  title,
  description,
  items,
}: {
  title: string;
  description: string;
  items: Array<{ title: string; data: TablePreview | undefined }>;
}) {
  const visible = items.filter((item) => item.data?.columns?.length);
  if (!visible.length) return null;

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h3 className="font-display text-lg font-semibold text-ink-900">{title}</h3>
        <p className="mt-1 text-sm text-ink-500">{description}</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {visible.map((item) => (
          <PreviewTable key={item.title} title={item.title} data={item.data} />
        ))}
      </div>
    </section>
  );
}

function StatusPill({ label, active }: { label: string; active: boolean }) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium",
        active ? "bg-emerald-100 text-emerald-800" : "bg-brand-100 text-ink-600",
      ].join(" ")}
    >
      {label}
    </span>
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
  const [marketingFiles, setMarketingFiles] = useState<File[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MonthlyReporterResult | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!preRange.trim() || !postRange.trim()) {
      setError("Enter both Pre and Post date ranges in MM/DD/YYYY-MM/DD/YYYY format.");
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
      const json = (await res.json()) as MonthlyReporterResult;
      setResult(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const tables = result?.preview?.tables;

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
          <h2 className="font-display text-3xl font-semibold text-ink-900">Monthly Reporter</h2>
          <p className="mt-2 max-w-3xl text-sm text-ink-600">
            App2.0 parity for TODC monthly analysis. This run path now mirrors the updated cloud app:
            Pre/Post setup, optional DD and UE financial files, uploaded marketing folders, combined and
            platform summaries, financial summary, slot analysis, and export bundles.
          </p>
        </div>
      </div>

      <section className="rounded-[28px] border border-brand-200 bg-gradient-to-br from-[#f8f6f3] via-white to-[#fff7f2] p-6">
        <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="flex flex-col gap-3">
            <div className="inline-flex w-fit items-center gap-2 rounded-full bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-brand-700 shadow-sm">
              <FileSpreadsheet className="h-4 w-4" />
              TODC Analytics
            </div>
            <h3 className="font-display text-2xl font-semibold text-ink-900">How It Works</h3>
            <div className="space-y-2 text-sm text-ink-600">
              <p>1. Set the Pre and Post periods. Last-year comparisons are derived from those ranges.</p>
              <p>2. Upload DD, UE, and any `MARKETING_*.csv` files you have. Missing uploads are allowed.</p>
              <p>3. Run analysis to generate the same App2.0-style summaries, slot tables, and exports.</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
            <div className="rounded-[24px] border border-brand-200 bg-white p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink-800">
                <CalendarRange className="h-4 w-4 text-brand-600" />
                Required
              </div>
              <p className="mt-2 text-sm text-ink-600">Pre and Post periods.</p>
            </div>
            <div className="rounded-[24px] border border-brand-200 bg-white p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink-800">
                <Upload className="h-4 w-4 text-brand-600" />
                Optional
              </div>
              <p className="mt-2 text-sm text-ink-600">DD, UE, and marketing CSV uploads.</p>
            </div>
            <div className="rounded-[24px] border border-brand-200 bg-white p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink-800">
                <Download className="h-4 w-4 text-brand-600" />
                Exports
              </div>
              <p className="mt-2 text-sm text-ink-600">Full report, date export, and bucketing export.</p>
            </div>
          </div>
        </div>
      </section>

      <form onSubmit={onSubmit} className="brand-card grid gap-5 rounded-[28px] p-6 lg:grid-cols-2">
        <div className="lg:col-span-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">1. Configure Date Ranges</h3>
          <p className="mt-1 text-sm text-ink-500">Use App2.0 format: MM/DD/YYYY-MM/DD/YYYY.</p>
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
          <span className="text-sm font-medium text-ink-700">Operator ID</span>
          <input
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="op_north_01"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">Operator name</span>
          <input
            value={operatorName}
            onChange={(e) => setOperatorName(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="alpha"
          />
        </label>

        <label className="flex flex-col gap-1 lg:col-span-2">
          <span className="text-sm font-medium text-ink-700">Excluded dates</span>
          <input
            value={excludedDates}
            onChange={(e) => setExcludedDates(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="11/28/2025, 11/29/2025"
          />
        </label>

        <div className="lg:col-span-2 mt-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">2. Upload Data Files</h3>
          <p className="mt-1 text-sm text-ink-500">
            Same App2.0 upload pattern: optional financial files plus any marketing exports.
          </p>
        </div>

        <label className="flex flex-col gap-2 rounded-[24px] border border-brand-200 bg-brand-50/40 p-4">
          <span className="text-sm font-medium text-ink-700">DoorDash financial CSV</span>
          <input type="file" accept=".csv,text/csv" onChange={(e) => setDdFile(e.target.files?.[0] ?? null)} className="text-sm" />
          <StatusPill label={ddFile ? ddFile.name : "No file selected"} active={Boolean(ddFile)} />
        </label>

        <label className="flex flex-col gap-2 rounded-[24px] border border-brand-200 bg-brand-50/40 p-4">
          <span className="text-sm font-medium text-ink-700">UberEats financial CSV</span>
          <input type="file" accept=".csv,text/csv" onChange={(e) => setUeFile(e.target.files?.[0] ?? null)} className="text-sm" />
          <StatusPill label={ueFile ? ueFile.name : "No file selected"} active={Boolean(ueFile)} />
        </label>

        <label className="flex flex-col gap-2 rounded-[24px] border border-brand-200 bg-brand-50/40 p-4 lg:col-span-2">
          <span className="text-sm font-medium text-ink-700">Marketing CSVs</span>
          <p className="text-xs text-ink-500">
            Upload all `MARKETING_PROMOTION*.csv` and `MARKETING_SPONSORED_LISTING*.csv` files together.
          </p>
          <input
            type="file"
            multiple
            accept=".csv,text/csv"
            onChange={(e) => setMarketingFiles(Array.from(e.target.files ?? []))}
            className="text-sm"
          />
          <StatusPill
            label={
              marketingFiles.length
                ? `${marketingFiles.length} file(s): ${marketingFiles.map((f) => f.name).join(", ")}`
                : "No marketing files selected"
            }
            active={marketingFiles.length > 0}
          />
        </label>

        <div className="lg:col-span-2 mt-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">3. Optional Store Filters</h3>
          <p className="mt-1 text-sm text-ink-500">Comma-separated IDs, same as App2.0 store selection narrowing.</p>
        </div>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">DoorDash store IDs</span>
          <input
            value={ddStores}
            onChange={(e) => setDdStores(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="101, 102"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-ink-700">UberEats store IDs</span>
          <input
            value={ueStores}
            onChange={(e) => setUeStores(e.target.value)}
            className="rounded-2xl border border-brand-200 px-3 py-2 text-sm"
            placeholder="201, 202"
          />
        </label>

        <div className="lg:col-span-2 flex flex-wrap items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loading ? "Running…" : "Run Analysis"}
          </button>
          <p className="text-xs text-ink-500">
            API path: <code className="rounded bg-brand-50 px-1">/api/runs/monthly-reporter</code>
          </p>
        </div>

        {error ? (
          <div className="lg:col-span-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            {error}
          </div>
        ) : null}
      </form>

      {result ? (
        <div className="flex flex-col gap-6">
          <section className="brand-card rounded-[28px] p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 className="font-display text-lg font-semibold text-ink-900">Run Summary</h3>
                <p className="mt-2 text-sm text-ink-700">{result.summary_text}</p>
                <p className="mt-3 text-xs text-ink-500">
                  Run ID: <code className="rounded bg-brand-50 px-1">{result.run_id}</code>
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <a
                  href={result.downloads?.full}
                  className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 shadow-sm hover:bg-brand-50"
                >
                  <Download className="h-4 w-4" />
                  Full Excel
                </a>
                {result.downloads?.date ? (
                  <a
                    href={result.downloads.date}
                    className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 shadow-sm hover:bg-brand-50"
                  >
                    <Download className="h-4 w-4" />
                    Date Export
                  </a>
                ) : null}
                {result.downloads?.bucketing ? (
                  <a
                    href={result.downloads.bucketing}
                    className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 shadow-sm hover:bg-brand-50"
                  >
                    <Download className="h-4 w-4" />
                    Bucketing Export
                  </a>
                ) : null}
                {result.downloads?.deepdive ? (
                  <a
                    href={result.downloads.deepdive}
                    className="inline-flex items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-sm font-medium text-ink-800 shadow-sm hover:bg-brand-50"
                  >
                    <Download className="h-4 w-4" />
                    DeepDive JSON
                  </a>
                ) : null}
              </div>
            </div>
          </section>

          <PreviewSection
            title="Financial Summary"
            description="Top-level financial summary from the updated App2.0 export path."
            items={[{ title: "Financial Summary", data: tables?.financial_summary }]}
          />

          <PreviewSection
            title="Combined Views"
            description="Combined current-year and year-over-year views across both platforms."
            items={[
              { title: "Combined — Pre vs Post", data: tables?.combined_summary_pre_post },
              { title: "Combined — YoY", data: tables?.combined_summary_yoy },
              { title: "Combined stores — Pre vs Post", data: tables?.combined_store_pre_post },
              { title: "Combined stores — YoY", data: tables?.combined_store_yoy },
            ]}
          />

          <PreviewSection
            title="DoorDash"
            description="DoorDash summary, store, and slot analysis tables."
            items={[
              { title: "DD summary — Pre vs Post", data: tables?.dd_summary_pre_post },
              { title: "DD summary — YoY", data: tables?.dd_summary_yoy },
              { title: "DD stores — Pre vs Post", data: tables?.dd_store_pre_post },
              { title: "DD stores — YoY", data: tables?.dd_store_yoy },
              { title: "DD slot sales — Pre vs Post", data: tables?.dd_slot_sales_pre_post },
              { title: "DD slot sales — YoY", data: tables?.dd_slot_sales_yoy },
              { title: "DD slot payouts — Pre vs Post", data: tables?.dd_slot_payouts_pre_post },
              { title: "DD slot payouts — YoY", data: tables?.dd_slot_payouts_yoy },
            ]}
          />

          <PreviewSection
            title="UberEats"
            description="UberEats summary, store, and slot analysis tables."
            items={[
              { title: "UE summary — Pre vs Post", data: tables?.ue_summary_pre_post },
              { title: "UE summary — YoY", data: tables?.ue_summary_yoy },
              { title: "UE stores — Pre vs Post", data: tables?.ue_store_pre_post },
              { title: "UE stores — YoY", data: tables?.ue_store_yoy },
              { title: "UE slot sales — Pre vs Post", data: tables?.ue_slot_sales_pre_post },
              { title: "UE slot sales — YoY", data: tables?.ue_slot_sales_yoy },
              { title: "UE slot payouts — Pre vs Post", data: tables?.ue_slot_payouts_pre_post },
              { title: "UE slot payouts — YoY", data: tables?.ue_slot_payouts_yoy },
            ]}
          />

          <PreviewSection
            title="Marketing"
            description="Corporate vs TODC combined and source-specific tables from uploaded marketing exports."
            items={[
              { title: "Corporate vs TODC — Combined", data: tables?.corporate_vs_todc },
              { title: "Corporate vs TODC — Promotion", data: tables?.promotion_corporate_vs_todc },
              { title: "Corporate vs TODC — Sponsored", data: tables?.sponsored_corporate_vs_todc },
            ]}
          />
        </div>
      ) : null}
    </div>
  );
}
