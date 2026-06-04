import { useMemo, useState } from 'react';
import SplitDataTable from '../../components/ui/SplitDataTable';
import SummaryKpiStrip from '../../components/ui/SummaryKpiStrip';
import { useApp2Pack } from '../../hooks/useApp2Pack';
import { columnsFromObjects, APP2_MERCHANT_STORE_COL } from '../../lib/engine/app2Bucketing';

export default function App2DateWiseScreen() {
  const { pack, combinedSummary } = useApp2Pack();
  const [storeFilter, setStoreFilter] = useState('');

  const detailRows = useMemo(() => {
    const rows = pack?.aggTables?.Post || [];
    if (!storeFilter) return rows;
    return rows.filter((r) => String(r[APP2_MERCHANT_STORE_COL]) === storeFilter);
  }, [pack, storeFilter]);

  const storeOptions = useMemo(() => {
    const rows = pack?.aggTables?.Post || [];
    return [...new Set(rows.map((r) => String(r[APP2_MERCHANT_STORE_COL])))].filter(Boolean).sort((a, b) =>
      a.localeCompare(b, undefined, { numeric: true }),
    );
  }, [pack]);

  return (
    <div className="space-y-6">
      {combinedSummary.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-[var(--text)]">Combined summary metrics</h2>
          <SummaryKpiStrip summary={combinedSummary} />
        </section>
      )}

      {pack?.empty ? (
        <div className="card">
          <p className="text-sm text-[var(--text-muted)] leading-relaxed">
            Load DoorDash financial data and set Pre/Post periods in the top bar. App 2.0 rollups use the same hour
            bands and GC buckets as the legacy Python export.
          </p>
        </div>
      ) : (
        <section className="space-y-3">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">Date × day-part detail</h2>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5 leading-relaxed">
              Store × month × week × calendar date × day-part (Early morning … Late night),{' '}
              <strong>Post</strong> period only. Matches the &quot;Detail — Post period&quot; block in the workbook export.
            </p>
          </div>

          <label className="flex flex-col gap-1 text-xs text-[var(--text-muted)] max-w-xs">
            <span>Filter by store</span>
            <select
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-2 py-2 text-xs text-[var(--text)]"
            >
              <option value="">All stores</option>
              {storeOptions.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>

          <SplitDataTable
            columns={columnsFromObjects(detailRows)}
            data={detailRows}
            maxHeight="calc(100vh - 320px)"
            dense
          />
        </section>
      )}
    </div>
  );
}
