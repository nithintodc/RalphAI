import { useMemo } from 'react';
import DataTable from './DataTable';
import { splitTableColumns } from '../../lib/utils/splitTableColumns';

/**
 * Renders one or more tight tables so wide datasets never force horizontal page scroll.
 * Register screen uses DataTable with allowHorizontalScroll instead.
 */
export default function SplitDataTable({
  columns,
  data,
  splitAt = 5,
  split = true,
  chunkTitles,
  layout = 'tight',
  dense = false,
  ...rest
}) {
  const chunks = useMemo(() => {
    if (!split || !columns?.length) return [columns];
    return splitTableColumns(columns, { maxDataCols: splitAt });
  }, [columns, split, splitAt]);

  if (!chunks.length || !chunks[0]?.length) {
    return <DataTable columns={columns || []} data={data} layout={layout} dense={dense} {...rest} />;
  }

  if (chunks.length === 1) {
    return <DataTable columns={chunks[0]} data={data} layout={layout} dense={dense} {...rest} />;
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
          <DataTable columns={chunkCols} data={data} layout={layout} dense={dense} {...rest} />
        </div>
      ))}
    </div>
  );
}
