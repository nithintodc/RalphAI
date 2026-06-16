import { useMemo, useRef, useState } from 'react';
import { Download, Plus, RotateCw, Upload, X } from 'lucide-react';
import {
  buildDdStoreCatalog,
  buildUeStoreCatalog,
  buildSuggestedMapRows,
  applyUeSelection,
  formatUeOptionLabel,
} from '../../lib/utils/storeCatalog';
import { downloadStoreMapCsv, parseStoreMapCsv } from '../../lib/utils/storeMapCsv';
import { STORE_TAG_LABELS } from '../../lib/export/exportSheetSummaries';

const TAG_OPTIONS = [
  { value: '', label: '— none —' },
  { value: 'A', label: `A (${STORE_TAG_LABELS.A})` },
  { value: 'B', label: `B (${STORE_TAG_LABELS.B})` },
];

export default function StoreMapEditor({
  ddFinancial,
  ueFinancial,
  rows,
  setRows,
  operatorName = '',
}) {
  const fileInputRef = useRef(null);
  const [importPreview, setImportPreview] = useState(null);
  const ddCatalog = useMemo(() => buildDdStoreCatalog(ddFinancial), [ddFinancial]);
  const ueCatalog = useMemo(() => buildUeStoreCatalog(ueFinancial), [ueFinancial]);
  const ddById = useMemo(() => new Map(ddCatalog.map((d) => [d.id, d])), [ddCatalog]);
  const safeRows = rows ?? [];

  const unmatchedUe = useMemo(() => {
    const mapped = new Set(safeRows.map((r) => r.ueId).filter(Boolean));
    return ueCatalog.filter((s) => !mapped.has(s.id));
  }, [ueCatalog, safeRows]);

  const clearAllTags = () => {
    setRows((prev) => prev.map((r) => ({ ...r, tag: '' })));
  };

  const setAllTags = (tag) => {
    setRows((prev) => prev.map((r) => ({ ...r, tag })));
  };

  const resetSuggested = () => {
    setImportPreview(null);
    setRows(buildSuggestedMapRows(ddCatalog, ueCatalog, {}));
  };

  const onUeChange = (index, ueId) => {
    setRows((prev) => prev.map((r, i) => (i === index ? applyUeSelection(r, ueId, ueCatalog) : r)));
  };
  const onTagChange = (index, tag) => {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, tag: String(tag ?? '').trim() } : r)));
  };

  const removeRow = (index) => {
    setImportPreview(null);
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const downloadMapping = () => {
    const safeName = String(operatorName || 'operator').replace(/[^\w.-]+/g, '_').slice(0, 40);
    const date = new Date().toISOString().slice(0, 10);
    downloadStoreMapCsv(safeRows, `store-mapping_${safeName}_${date}.csv`);
  };

  const onUploadClick = () => {
    fileInputRef.current?.click();
  };

  const onFileSelected = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    try {
      const text = await file.text();
      const result = parseStoreMapCsv(text, ddCatalog, ueCatalog);
      if (result.errors?.length) {
        setImportPreview({
          kind: 'error',
          fileName: file.name,
          messages: result.errors,
        });
        return;
      }
      setRows(result.rows);
      setImportPreview({
        kind: 'success',
        fileName: file.name,
        messages: result.warnings,
        stats: result.stats,
      });
    } catch (err) {
      setImportPreview({
        kind: 'error',
        fileName: file.name,
        messages: [err?.message || 'Could not read CSV file.'],
      });
    }
  };

  const onDdChange = (index, ddId) => {
    const nextId = String(ddId ?? '').trim();
    const dd = ddById.get(nextId);
    setRows((prev) => prev.map((r, i) => (
      i === index
        ? {
            ...r,
            ddId: nextId,
            merchantStoreId: dd?.merchantStoreId ?? '—',
            ddStoreId: dd?.ddStoreId ?? '—',
            ddName: dd?.name ?? '—',
          }
        : r
    )));
  };

  const addManualRow = (initialUeId = '') => {
    setRows((prev) => {
      const firstUnusedDd = ddCatalog.find((d) => !prev.some((r) => r.ddId === d.id));
      const base = {
        ddId: firstUnusedDd?.id ?? '',
        merchantStoreId: firstUnusedDd?.merchantStoreId ?? '—',
        ddStoreId: firstUnusedDd?.ddStoreId ?? '—',
        ddName: firstUnusedDd?.name ?? '—',
        ueId: '',
        ueName: '',
        isManual: true,
        tag: '',
      };
      return [...prev, applyUeSelection(base, initialUeId, ueCatalog)];
    });
  };

  const ueSelectClass =
    'w-full px-1.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] text-[11px] focus:outline-none focus:border-[var(--accent)] cursor-pointer';

  if (!ddCatalog.length) {
    return (
      <p className="text-xs text-[var(--text-muted)]">No DoorDash store IDs found in the uploaded financial file.</p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--text-muted)] leading-relaxed">
        Map each DoorDash location to Uber Eats using <strong>Merchant Store ID</strong> as the key for the{' '}
        <strong>Combined</strong> table. Pick the matching <strong>UE Store ID</strong> or{' '}
        <strong>UE Store Name</strong> when IDs differ.
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={downloadMapping}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
        >
          <Download size={12} />
          Download mapping (CSV)
        </button>
        <button
          type="button"
          onClick={onUploadClick}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
        >
          <Upload size={12} />
          Upload mapping (CSV)
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={onFileSelected}
        />
        <button
          type="button"
          onClick={resetSuggested}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
        >
          <RotateCw size={12} />
          Reset to suggested mapping
        </button>
        <button
          type="button"
          onClick={() => addManualRow('')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
        >
          <Plus size={12} />
          Add manual mapping row
        </button>
        <button
          type="button"
          onClick={clearAllTags}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
        >
          Clear all tags
        </button>
        <button
          type="button"
          onClick={() => setAllTags('A')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
          title={`Tag every row as A (${STORE_TAG_LABELS.A})`}
        >
          Select all as A
        </button>
        <button
          type="button"
          onClick={() => setAllTags('B')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
          title={`Tag every row as B (${STORE_TAG_LABELS.B})`}
        >
          Select all as B
        </button>
        <span className="text-[10px] text-[var(--text-subtle)] self-center">
          {safeRows.length} row{safeRows.length === 1 ? '' : 's'} in analysis · {ddCatalog.length} DoorDash · {ueCatalog.length} Uber Eats detected
        </span>
      </div>

      {importPreview && (
        <div
          className={`rounded-lg border px-3 py-2 text-xs leading-relaxed ${
            importPreview.kind === 'error'
              ? 'border-red-200 bg-red-50 text-red-950'
              : 'border-amber-200 bg-amber-50 text-amber-950'
          }`}
        >
          <div className="font-medium mb-1">
            {importPreview.kind === 'error' ? 'CSV import failed' : 'CSV import preview'} — {importPreview.fileName}
          </div>
          {importPreview.stats && (
            <p className="mb-1">
              Loaded {importPreview.stats.importedRows} row{importPreview.stats.importedRows === 1 ? '' : 's'}
              ({importPreview.stats.mappedPairs} mapped, {importPreview.stats.ddOnly} DD-only, {importPreview.stats.ueOnly} UE-only).
              {importPreview.stats.duplicateRowsMerged > 0 && (
                <> {importPreview.stats.duplicateRowsMerged} duplicate row{importPreview.stats.duplicateRowsMerged === 1 ? '' : 's'} merged.</>
              )}
              {' '}Review the table below, edit if needed, then Analyze.
            </p>
          )}
          {importPreview.messages?.length > 0 && (
            <ul className="list-disc pl-4 space-y-0.5">
              {importPreview.messages.map((msg) => (
                <li key={msg}>{msg}</li>
              ))}
            </ul>
          )}
          {importPreview.kind === 'success' && (
            <button
              type="button"
              onClick={() => setImportPreview(null)}
              className="mt-2 text-[10px] underline cursor-pointer"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      <p className="text-[10px] text-[var(--text-subtle)] leading-relaxed">
        Removing a row (×) excludes that store from all analysis — same as omitting it from an uploaded CSV.
        Use <strong>Exclude Stores</strong> above for temporary exclusions without changing the map.
      </p>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)] max-h-[min(58vh,520px)] overflow-y-auto">
        <table className="w-full min-w-[1200px] text-xs">
          <thead className="sticky top-0 z-10 bg-[var(--surface-2)]">
            <tr className="border-b border-[var(--border)]">
              <th className="py-2 px-2 text-left font-semibold text-[var(--text-muted)]">DD Store ID</th>
              <th className="py-2 px-2 text-left font-semibold text-[var(--text-muted)]">Merchant Store ID</th>
              <th className="py-2 px-2 text-left font-semibold text-[var(--text-muted)] min-w-[120px]">Store Name (DD)</th>
              <th className="py-2 px-2 text-left font-semibold text-[var(--text-muted)] w-28">UE Store ID</th>
              <th className="py-2 px-2 text-left font-semibold text-[var(--text-muted)] min-w-[160px]">UE Store Name</th>
              <th className="py-2 px-2 text-left font-semibold text-[var(--text-muted)] w-24">Tag</th>
              <th className="py-2 px-2 text-center font-semibold text-[var(--text-muted)] w-10" aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {safeRows.map((row, i) => (
                <tr key={`${row.ddId}-${i}`} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)]/60">
                  <td className="py-1.5 px-2 font-mono text-[var(--text-muted)]" title={row.ddStoreId}>
                    {row.ddStoreId || '—'}
                  </td>
                  <td className="py-1.5 px-2 font-mono text-[var(--text)]">
                    {row.isManual ? (
                      <select
                        value={row.ddId}
                        onChange={(e) => onDdChange(i, e.target.value)}
                        className={`${ueSelectClass} max-w-[11rem] font-mono`}
                      >
                        <option value="">— select DD —</option>
                        {ddCatalog.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.id}
                          </option>
                        ))}
                      </select>
                    ) : (
                      row.merchantStoreId
                    )}
                  </td>
                  <td className="py-1.5 px-2 text-[var(--text-muted)] whitespace-nowrap" title={row.ddName}>
                    {row.ddName}
                  </td>
                  <td className="py-1.5 px-2">
                    <select
                      value={row.ueId}
                      onChange={(e) => onUeChange(i, e.target.value)}
                      className={`${ueSelectClass} max-w-[11rem] font-mono`}
                    >
                      <option value="">— none —</option>
                      {ueCatalog.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-1.5 px-2">
                    <select
                      value={row.ueId}
                      onChange={(e) => onUeChange(i, e.target.value)}
                      className={`${ueSelectClass} min-w-[20rem]`}
                      title={row.ueName || 'Select Uber Eats store by name'}
                    >
                      <option value="">— none —</option>
                      {ueCatalog.map((s) => (
                        <option key={s.id} value={s.id}>
                          {formatUeOptionLabel(s)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-1.5 px-2">
                    <select
                      value={row.tag ?? ''}
                      onChange={(e) => onTagChange(i, e.target.value)}
                      className={`${ueSelectClass} max-w-[9rem]`}
                      title="Group tag for A/B comparison (A = TODC, B = Non-TODC)"
                    >
                      {TAG_OPTIONS.map((opt) => (
                        <option key={opt.value || 'none'} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-1.5 px-2 text-center">
                    <button
                      type="button"
                      onClick={() => removeRow(i)}
                      className="inline-flex items-center justify-center p-1 rounded hover:bg-red-50 text-[var(--text-subtle)] hover:text-[var(--negative)] cursor-pointer"
                      title="Remove from analysis (excludes this store from all calculations)"
                    >
                      <X size={14} />
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {unmatchedUe.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] text-[var(--text-subtle)] leading-relaxed">
            Uber Eats stores not selected on any row ({unmatchedUe.length}). Add them with a manual row:
          </p>
          <div className="flex flex-wrap gap-1.5">
            {unmatchedUe.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => addManualRow(s.id)}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[10px] text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
                title={`Add ${formatUeOptionLabel(s)} as manual mapping row`}
              >
                <Plus size={10} />
                {formatUeOptionLabel(s)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
