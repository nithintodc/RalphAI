import { useMemo } from 'react';
import DataTable from './DataTable';
import { splitTableColumns } from '../../lib/utils/splitTableColumns';

/**
 * Wide tables render as one scrollable table with wrapped headers (split opt-in only).
 */
export default function SplitDataTable({
  columns,
  data,
  splitAt = 5,
  split = false,
  chunkTitles,
  layout = 'tight',
  dense = false,
  allowHorizontalScroll = true,
  ...rest
}) {
  const wrappedColumns = useMemo(
    () => (columns || []).map((col) => ({ ...col, wrap: col.wrap ?? true })),
    [columns],
  );

  const chunks = useMemo(() => {
    if (!split || !wrappedColumns.length) return [wrappedColumns];
    return splitTableColumns(wrappedColumns, { maxDataCols: splitAt });
  }, [wrappedColumns, split, splitAt]);

  if (!chunks.length || !chunks[0]?.length) {
    return (
      <DataTable
        columns={wrappedColumns}
        data={data}
        layout={layout}
        dense={dense}
        allowHorizontalScroll={allowHorizontalScroll}
        {...rest}
      />
    );
  }

  if (chunks.length === 1) {
    return (
      <DataTable
        columns={chunks[0]}
        data={data}
        layout={layout}
        dense={dense}
        allowHorizontalScroll={allowHorizontalScroll}
        {...rest}
      />
    );
  }

  return (
    <div className="space-y-4 max-w-full min-w-0">
      {chunks.map((chunkCols, i) => (
        <div key={i} className="max-w-full min-w-0">
          {chunkTitles?.[i] ? (
            <p className="text-[10px] font-medium text-[var(--text-subtle)] mb-1.5">{chunkTitles[i]}</p>
          ) : (
            <p className="text-[10px] text-[var(--text-subtle)] mb-1.5">
              Columns {i + 1} of {chunks.length}
            </p>
          )}
          <DataTable
            columns={chunkCols}
            data={data}
            layout={layout}
            dense={dense}
            allowHorizontalScroll={allowHorizontalScroll}
            {...rest}
          />
        </div>
      ))}
    </div>
  );
}
