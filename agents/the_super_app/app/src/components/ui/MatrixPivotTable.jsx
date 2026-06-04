import { splitColKeys } from '../../lib/utils/splitTableColumns';

const DEFAULT_MAX_COLS = 8;

/** Wide pivot matrix split into multiple tables so the page never scrolls horizontally. */
export default function MatrixPivotTable({
  rowHeaderLabel = 'Store',
  rowKeys,
  colKeys,
  colTitles,
  rowTitles,
  matrix,
  formatCell,
  maxHeight = 'min(70vh, 560px)',
  maxColsPerTable = DEFAULT_MAX_COLS,
}) {
  const fmt = formatCell ?? ((v) => (v == null || v === 0 ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })));

  if (!rowKeys?.length || !colKeys?.length || !matrix?.length) {
    return (
      <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
        Not enough structure in this file to build a pivot (need store + dimension + numeric column).
      </div>
    );
  }

  const colChunks = splitColKeys(colKeys, maxColsPerTable);

  const renderChunk = (chunkKeys, chunkIndex) => {
    const colStart = chunkIndex * maxColsPerTable;
    return (
      <div key={chunkIndex} className="card p-0 overflow-hidden max-w-full">
        {colChunks.length > 1 && (
          <p className="text-[10px] text-[var(--text-subtle)] px-3 pt-2">
            Columns {colStart + 1}–{colStart + chunkKeys.length}
            {colTitles?.[colStart] ? ` · ${colTitles[colStart]}` : ''}
            {chunkKeys.length > 1 && colTitles?.[colStart + chunkKeys.length - 1]
              ? ` → ${colTitles[colStart + chunkKeys.length - 1]}`
              : ''}
          </p>
        )}
        <div className="overflow-y-auto overflow-x-hidden max-w-full" style={{ maxHeight }}>
          <table className="w-full table-fixed border-collapse text-xs">
            <thead className="sticky top-0 z-10">
              <tr className="bg-[var(--surface-2)] border-b border-[var(--border)]">
                <th
                  className="sticky left-0 z-20 w-[22%] px-1.5 py-1 text-left text-[11px] font-semibold text-[var(--text-muted)] border-r border-[var(--border)] bg-[var(--surface-2)] shadow-[2px_0_4px_-2px_rgba(0,0,0,0.08)] whitespace-normal break-words [overflow-wrap:anywhere] align-bottom"
                  title={String(rowHeaderLabel)}
                >
                  <span className="table-heading-label">{rowHeaderLabel}</span>
                </th>
                {chunkKeys.map((c, j) => (
                  <th
                    key={String(c)}
                    className="px-1 py-1 text-right text-[10px] font-semibold text-[var(--text-muted)] border-b border-[var(--border)] whitespace-normal break-words [overflow-wrap:anywhere] align-bottom"
                    title={String(colTitles?.[colStart + j] ?? c)}
                  >
                    <span className="table-heading-label">{String(c)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowKeys.map((rk, i) => (
                <tr key={String(rk)} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)]/60">
                  <td
                    className="sticky left-0 z-[1] w-[22%] px-1.5 py-0.5 text-[11px] font-medium text-[var(--text)] border-r border-[var(--border)] bg-[var(--surface)] whitespace-normal break-words [overflow-wrap:anywhere] align-top"
                    title={String(rowTitles?.[i] ?? rk)}
                  >
                    {String(rk)}
                  </td>
                  {chunkKeys.map((c, j) => {
                    const v = matrix[i]?.[colStart + j];
                    return (
                      <td key={String(c)} className="px-1 py-0.5 text-right tnum text-[11px] text-[var(--text)] tabular-nums whitespace-nowrap overflow-hidden text-ellipsis">
                        {fmt(v, c, rk)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-3 max-w-full min-w-0 overflow-x-hidden">
      {colChunks.map((chunkKeys, i) => renderChunk(chunkKeys, i))}
    </div>
  );
}
