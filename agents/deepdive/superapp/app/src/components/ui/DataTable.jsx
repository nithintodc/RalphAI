import { useState, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

export default function DataTable({ columns, data, onRowClick, sortable = true, maxHeight }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('desc');

  const sorted = useMemo(() => {
    if (!sortCol || !sortable) return data;
    return [...data].sort((a, b) => {
      const av = a[sortCol] ?? 0;
      const bv = b[sortCol] ?? 0;
      if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [data, sortCol, sortDir, sortable]);

  const handleSort = (key) => {
    if (sortCol === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(key);
      setSortDir('desc');
    }
  };

  return (
    <div className="card p-0 overflow-hidden">
      <div className={maxHeight ? 'overflow-auto' : ''} style={maxHeight ? { maxHeight } : {}}>
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="bg-[var(--surface-2)]">
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => sortable && col.sortable !== false && handleSort(col.key)}
                  className={`px-4 py-2.5 text-left text-xs font-semibold text-[var(--text-muted)] border-b border-[var(--border)]
                    ${sortable && col.sortable !== false ? 'cursor-pointer hover:text-[var(--text)] select-none' : ''}
                    ${col.align === 'right' ? 'text-right' : ''}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {sortable && sortCol === col.key && (
                      sortDir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
                    )}
                    {sortable && sortCol !== col.key && col.sortable !== false && (
                      <ArrowUpDown size={11} className="opacity-30" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr
                key={row.id || row.storeId || i}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-[var(--border)] last:border-0 transition-colors
                  ${onRowClick ? 'cursor-pointer hover:bg-[var(--surface-2)]' : ''}`}
              >
                {columns.map(col => (
                  <td
                    key={col.key}
                    className={`px-4 py-2.5 tnum ${col.align === 'right' ? 'text-right' : ''}
                      ${col.delta && row[col.key] > 0 ? 'text-[var(--positive)]' : ''}
                      ${col.delta && row[col.key] < 0 ? 'text-[var(--negative)]' : ''}`}
                  >
                    {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '-')}
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
