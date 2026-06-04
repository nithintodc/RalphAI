/** Wide pivot matrix: sticky row header + scrollable metric columns. */
export default function MatrixPivotTable({
  rowHeaderLabel = 'Store',
  rowKeys,
  colKeys,
  matrix,
  formatCell,
  maxHeight = 'min(70vh, 560px)',
}) {
  const fmt = formatCell ?? ((v) => (v == null || v === 0 ? '—' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 })));

  if (!rowKeys?.length || !colKeys?.length || !matrix?.length) {
    return (
      <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
        Not enough structure in this file to build a pivot (need store + dimension + numeric column).
      </div>
    );
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="overflow-auto" style={{ maxHeight }}>
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 z-10">
            <tr className="bg-[var(--surface-2)] border-b border-[var(--border)]">
              <th className="sticky left-0 z-20 min-w-[120px] max-w-[200px] px-2 py-2 text-left font-semibold text-[var(--text-muted)] border-r border-[var(--border)] bg-[var(--surface-2)] shadow-[2px_0_4px_-2px_rgba(0,0,0,0.08)]">
                {rowHeaderLabel}
              </th>
              {colKeys.map((c) => (
                <th
                  key={String(c)}
                  className="px-2 py-2 text-right font-semibold text-[var(--text-muted)] whitespace-nowrap border-b border-[var(--border)] min-w-[4.5rem] max-w-[160px] truncate"
                  title={String(c)}
                >
                  {String(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowKeys.map((rk, i) => (
              <tr key={String(rk)} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)]/60">
                <td className="sticky left-0 z-[1] min-w-[120px] max-w-[200px] px-2 py-1.5 font-medium text-[var(--text)] border-r border-[var(--border)] bg-[var(--surface)] truncate" title={String(rk)}>
                  {String(rk)}
                </td>
                {(matrix[i] || []).map((v, j) => (
                  <td key={String(colKeys[j])} className="px-2 py-1.5 text-right tnum text-[var(--text)] tabular-nums">
                    {fmt(v, colKeys[j], rk)}
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
