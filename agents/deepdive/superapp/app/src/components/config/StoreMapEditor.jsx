import { useMemo } from 'react';
import { Plus, RotateCw } from 'lucide-react';
import {
  buildDdStoreCatalog,
  buildUeStoreCatalog,
  buildSuggestedMapRows,
  applyUeSelection,
  formatUeOptionLabel,
} from '../../lib/utils/storeCatalog';

export default function StoreMapEditor({
  ddFinancial,
  ueFinancial,
  rows,
  setRows,
}) {
  const ddCatalog = useMemo(() => buildDdStoreCatalog(ddFinancial), [ddFinancial]);
  const ueCatalog = useMemo(() => buildUeStoreCatalog(ueFinancial), [ueFinancial]);
  const ddById = useMemo(() => new Map(ddCatalog.map((d) => [d.id, d])), [ddCatalog]);

  const unmatchedUe = useMemo(() => {
    const mapped = new Set(rows.map((r) => r.ueId).filter(Boolean));
    return ueCatalog.filter((s) => !mapped.has(s.id));
  }, [ueCatalog, rows]);

  const resetSuggested = () => {
    setRows(buildSuggestedMapRows(ddCatalog, ueCatalog, {}));
  };

  const onUeChange = (index, ueId) => {
    setRows((prev) => prev.map((r, i) => (i === index ? applyUeSelection(r, ueId, ueCatalog) : r)));
  };
  const onTagChange = (index, tag) => {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, tag: String(tag ?? '').trim() } : r)));
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
        <span className="text-[10px] text-[var(--text-subtle)] self-center">
          {ddCatalog.length} DoorDash · {ueCatalog.length} Uber Eats stores detected
        </span>
      </div>

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
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
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
                      value={row.tag || ''}
                      onChange={(e) => onTagChange(i, e.target.value)}
                      className={`${ueSelectClass} max-w-[8rem]`}
                      title="Optional group tag for A/B comparison"
                    >
                      <option value="">—</option>
                      <option value="A">A</option>
                      <option value="B">B</option>
                    </select>
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
