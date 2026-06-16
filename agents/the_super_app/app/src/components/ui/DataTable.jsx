import { useState, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { deltaCellClass, isDeltaColumn } from '../../lib/utils/deltaTone';

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

  const sampleRow = sorted[0] || data?.[0];

  const handleSort = (key) => {
    if (sortCol === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(key);
      setSortDir('desc');
    }
  };

  const tableClass = (() => {
    const size = dense ? 'text-xs' : 'text-sm';
    if (allowHorizontalScroll) {
      return `${size} table-auto w-max max-w-none border-collapse mx-auto`;
    }
    if (layout === 'full') {
      return `${size} w-full table-fixed border-collapse`;
    }
    return `${size} table-auto w-max max-w-full border-collapse mx-auto`;
  })();

  const headPad = allowHorizontalScroll
    ? (dense ? 'px-1 py-1' : 'px-1.5 py-1.5')
    : (dense ? 'px-2 py-1' : 'px-3 py-2');
  const cellPad = allowHorizontalScroll
    ? (dense ? 'px-1 py-0.5' : 'px-1.5 py-0.5')
    : (dense ? 'px-2 py-0.5' : 'px-3 py-2');

  const colClass = (col, isHeader, colIndex) => {
    const isLabelCol = col.labelCol ?? (colIndex === 0 && col.align !== 'right');
    const parts = [
      isHeader ? headPad : cellPad,
      'border-b border-[var(--border)]',
      isLabelCol && layout === 'full' ? 'text-left' : col.align === 'right' ? 'text-right' : 'text-center',
    ];

    if (allowHorizontalScroll) {
      parts.push('w-[1%]');
      if (isLabelCol) {
        parts.push('min-w-[4rem] max-w-[6.5rem]');
      } else {
        parts.push('min-w-[3rem] max-w-[5.5rem]');
      }
      parts.push('align-middle whitespace-normal break-words [overflow-wrap:anywhere]');
    } else if (layout === 'full') {
      parts.push('min-w-0 overflow-hidden');
      if (isHeader) {
        parts.push('align-middle whitespace-normal');
        if (isLabelCol) parts.push('w-[32%]');
        else if (col.shrink || col.align === 'right') parts.push('w-[11%]');
      } else if (col.wrap || isLabelCol) {
        parts.push('align-middle whitespace-normal break-words [overflow-wrap:anywhere]');
        if (isLabelCol) parts.push('w-[32%]');
      } else if (col.shrink || col.align === 'right') {
        parts.push('whitespace-nowrap text-ellipsis');
      } else {
        parts.push('align-middle whitespace-normal break-words [overflow-wrap:anywhere]');
      }
    } else {
      parts.push('whitespace-normal');
      if (isHeader) {
        parts.push('align-middle');
      } else {
        parts.push('align-middle break-words [overflow-wrap:anywhere]');
      }
      if (!col.wrap && !isLabelCol) parts.push('whitespace-nowrap');
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

  const scrollX = allowHorizontalScroll || layout !== 'full' ? 'overflow-x-auto' : 'overflow-x-hidden';

  return (
    <div className={`${shell} ${allowHorizontalScroll ? 'data-table--scrollable' : ''}`}>
      <div
        className={`w-full max-w-full ${scrollX} ${
          allowHorizontalScroll || layout === 'full' ? '' : 'flex justify-center'
        } ${maxHeight ? 'overflow-y-auto' : ''}`}
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
                  <span className="table-heading-content">
                    <span className="table-heading-label">
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
                {columns.map((col, colIndex) => {
                  const showDelta = isDeltaColumn(col, sampleRow);
                  const deltaCls = showDelta ? deltaCellClass(row[col.key]) : '';
                  return (
                    <td
                      key={col.key}
                      className={`${colClass(col, false, colIndex)} ${deltaCls}`}
                      title={
                        typeof row[col.key] === 'string' || typeof row[col.key] === 'number'
                          ? String(row[col.key])
                          : undefined
                      }
                    >
                      {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '-')}
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
}
