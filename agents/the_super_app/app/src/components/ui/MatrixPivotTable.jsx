import { useMemo } from 'react';
import { splitColKeys } from '../../lib/utils/splitTableColumns';
import { heatBackground, matrixValueRange } from '../../lib/utils/heatmap';

const DEFAULT_MAX_COLS = 8;

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
  /** When false, one scrollable table (no column splitting). */
  splitColumns = true,
  heatmap = false,
  heatmapHigherIsWorse = true,
}) {
  const fmt = formatCell ?? ((v) => (v == null || v === 0 ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })));

  const heatRange = useMemo(
    () => (heatmap ? matrixValueRange(matrix) : { min: 0, max: 0 }),
    [heatmap, matrix],
  );

  if (!rowKeys?.length || !colKeys?.length || !matrix?.length) {
    return (
      <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
        Not enough structure in this file to build a pivot (need store + dimension + numeric column).
      </div>
    );
  }

  const colChunks = splitColumns ? splitColKeys(colKeys, maxColsPerTable) : [colKeys];

  const renderChunk = (chunkKeys, chunkIndex) => {
    const colStart = splitColumns ? chunkIndex * maxColsPerTable : 0;
    return (
      <div key={chunkIndex} className="card p-0 overflow-hidden max-w-full">
        {splitColumns && colChunks.length > 1 && (
          <p className="text-[10px] text-[var(--text-subtle)] px-3 pt-2">
            Columns {colStart + 1}–{colStart + chunkKeys.length}
            {colTitles?.[colStart] ? ` · ${colTitles[colStart]}` : ''}
            {chunkKeys.length > 1 && colTitles?.[colStart + chunkKeys.length - 1]
              ? ` → ${colTitles[colStart + chunkKeys.length - 1]}`
              : ''}
          </p>
        )}
        <div
          className={`max-w-full flex justify-center ${splitColumns ? 'overflow-x-hidden' : 'overflow-x-auto'} overflow-y-auto`}
          style={{ maxHeight }}
        >
          <table className={`${splitColumns ? 'w-full table-fixed' : 'table-auto w-max min-w-full mx-auto'} border-collapse text-xs`}>
            <thead className="sticky top-0 z-10">
              <tr className="bg-[var(--surface-2)] border-b border-[var(--border)]">
                <th
                  className={`sticky left-0 z-20 px-1.5 py-1 text-center text-[10px] font-semibold text-[var(--text-muted)] border-r border-[var(--border)] bg-[var(--surface-2)] shadow-[2px_0_4px_-2px_rgba(0,0,0,0.08)] whitespace-normal break-words [overflow-wrap:anywhere] align-middle ${splitColumns ? 'w-[22%]' : 'min-w-[4.5rem] max-w-[7rem]'}`}
                  title={String(rowHeaderLabel)}
                >
                  <span className="table-heading-label">{rowHeaderLabel}</span>
                </th>
                {chunkKeys.map((c, j) => (
                  <th
                    key={String(c)}
                    className={`px-1 py-1 text-center text-[10px] font-semibold text-[var(--text-muted)] border-b border-[var(--border)] whitespace-normal break-words [overflow-wrap:anywhere] align-middle leading-tight ${splitColumns ? '' : 'min-w-[3.25rem] max-w-[5.5rem]'}`}
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
                    className="sticky left-0 z-[1] px-1.5 py-0.5 text-center text-[11px] font-medium text-[var(--text)] border-r border-[var(--border)] bg-[var(--surface)] whitespace-normal break-words [overflow-wrap:anywhere] align-middle"
                    title={String(rowTitles?.[i] ?? rk)}
                  >
                    {String(rk)}
                  </td>
                  {chunkKeys.map((c, j) => {
                    const v = matrix[i]?.[colStart + j];
                    const bg = heatmap
                      ? heatBackground(v, heatRange.min, heatRange.max, { higherIsWorse: heatmapHigherIsWorse })
                      : undefined;
                    return (
                      <td
                        key={String(c)}
                        className="px-1 py-0.5 text-center tnum text-[11px] text-[var(--text)] tabular-nums whitespace-normal break-words [overflow-wrap:anywhere] align-middle"
                        style={bg ? { backgroundColor: bg } : undefined}
                      >
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
    <div className={`space-y-3 max-w-full min-w-0 ${splitColumns ? 'overflow-x-hidden' : ''}`}>
      {colChunks.map((chunkKeys, i) => renderChunk(chunkKeys, i))}
    </div>
  );
}
