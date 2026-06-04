import { useState, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

export default function DataTable({
  columns,
  data,
  onRowClick,
  sortable = true,
  maxHeight,
  layout = 'full',
  dense = false,
  bare = false,
  /** Register only: allow horizontal scroll inside the table shell. */
  allowHorizontalScroll = false,
}) {
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

  const tableClass = (() => {
    if (allowHorizontalScroll) {
      return `${dense ? 'text-xs' : 'text-sm'} table-auto w-max max-w-none border-collapse`;
    }
    if (layout === 'auto') return `${dense ? 'text-xs' : 'text-sm'} table-auto w-full max-w-full`;
    if (layout === 'tight' || layout === 'full') {
      return `${dense ? 'text-xs' : 'text-sm'} w-full table-fixed`;
    }
    return `${dense ? 'text-xs' : 'text-sm'} w-full table-fixed`;
  })();

  const headPad = allowHorizontalScroll
    ? (dense ? 'px-1 py-1' : 'px-1.5 py-1.5')
    : (dense ? 'px-2 py-1' : 'px-3 py-2');
  const cellPad = allowHorizontalScroll
    ? (dense ? 'px-1 py-0.5' : 'px-1.5 py-0.5')
    : (dense ? 'px-2 py-0.5' : 'px-3 py-2');

  const colClass = (col, isHeader, colIndex) => {
    const parts = [
      isHeader ? headPad : cellPad,
      'border-b border-[var(--border)]',
      col.align === 'right' ? 'text-right' : 'text-left',
    ];
    const isLabelCol = col.labelCol ?? (colIndex === 0 && col.align !== 'right');

    if (allowHorizontalScroll) {
      parts.push('w-[1%]');
      if (isLabelCol) {
        parts.push('min-w-[3.75rem] max-w-[5.25rem]');
      } else {
        parts.push('min-w-[2.75rem] max-w-[4.25rem]');
      }
      if (isHeader) {
        parts.push('align-bottom whitespace-normal');
      } else if (col.wrap || isLabelCol) {
        parts.push('align-top whitespace-normal break-words [overflow-wrap:anywhere]');
      } else {
        parts.push('align-top whitespace-nowrap');
      }
    } else {
      parts.push('min-w-0 overflow-hidden');
      if (isHeader) {
        parts.push('align-bottom whitespace-normal');
        if (isLabelCol) parts.push('w-[22%]');
        else if (col.shrink || col.align === 'right') parts.push('w-[12%]');
      } else if (col.wrap || isLabelCol) {
        parts.push('align-top whitespace-normal break-words [overflow-wrap:anywhere]');
        if (isLabelCol) parts.push('w-[22%]');
      } else if (col.shrink || col.align === 'right') {
        parts.push('whitespace-nowrap text-ellipsis');
      } else {
        parts.push('align-top whitespace-normal break-words [overflow-wrap:anywhere]');
      }
    }

    if (col.className) parts.push(col.className);
    if (isHeader) {
      parts.push('text-xs font-semibold text-[var(--text-muted)] leading-snug');
      if (sortable && col.sortable !== false) parts.push('cursor-pointer hover:text-[var(--text)] select-none');
    } else {
      parts.push('tnum');
    }
    return parts.join(' ');
  };

  const shell = bare
    ? `max-w-full ${allowHorizontalScroll ? '' : 'overflow-hidden'}`
    : `card p-0 max-w-full ${allowHorizontalScroll ? '' : 'overflow-hidden'}`;

  const scrollX = allowHorizontalScroll ? 'overflow-x-auto' : 'overflow-x-hidden';

  return (
    <div className={`${shell} ${allowHorizontalScroll ? 'data-table--scrollable' : ''}`}>
      <div
        className={`max-w-full ${scrollX} ${maxHeight ? 'overflow-y-auto' : ''}`}
        style={maxHeight ? { maxHeight } : {}}
      >
        <table className={tableClass}>
          <thead className="sticky top-0 z-10">
            <tr className="bg-[var(--surface-2)]">
              {columns.map((col, colIndex) => (
                <th
                  key={col.key}
                  onClick={() => sortable && col.sortable !== false && handleSort(col.key)}
                  className={colClass(col, true, colIndex)}
                  title={typeof col.label === 'string' ? col.label : undefined}
                >
                  <span
                    className={
                      allowHorizontalScroll
                        ? 'table-heading-content table-heading-content--compact'
                        : 'table-heading-content'
                    }
                  >
                    <span
                      className={
                        allowHorizontalScroll
                          ? 'table-heading-label table-heading-label--compact'
                          : 'table-heading-label'
                      }
                    >
                      {col.label}
                    </span>
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
                {columns.map((col, colIndex) => (
                  <td
                    key={col.key}
                    className={`${colClass(col, false, colIndex)}
                      ${col.delta && row[col.key] > 0 ? 'text-[var(--positive)]' : ''}
                      ${col.delta && row[col.key] < 0 ? 'text-[var(--negative)]' : ''}`}
                    title={
                      typeof row[col.key] === 'string' || typeof row[col.key] === 'number'
                        ? String(row[col.key])
                        : undefined
                    }
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
