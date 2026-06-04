import { useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import DataTable from '../../components/ui/DataTable';
import MatrixPivotTable from '../../components/ui/MatrixPivotTable';
import { fmt } from '../../lib/utils/formatters';
import {
  pivotDowntimeByStore,
  pivotDowntimeByDimension,
  pivotCountByStore,
  pivotStoreByDatePeriod,
  pickCategoryColumn,
  pickStoreColumn,
  inferCategoricalColumns,
  discoverDowntimePivotCatalog,
  discoverCountPivotCatalog,
} from '../../lib/utils/opsProductPivot';

function cols(rows) {
  return rows?.[0] ? Object.keys(rows[0]) : [];
}

const dhmCols = [
  { key: 'label', label: 'Bucket', sortable: true, render: (v) => <span className="font-medium">{v}</span> },
  { key: 'days', label: 'Days', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
  { key: 'hours', label: 'Hours', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
  { key: 'minutes', label: 'Minutes', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
  { key: 'totalMinutes', label: 'Total (min)', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
  { key: 'lineCount', label: 'Rows', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
];

export default function OperationsScreen() {
  const { ddOps } = useDataStore();

  const hasData = ddOps.byOrder || ddOps.byStore || ddOps.byTime;

  const downtimeRows = ddOps.byStore?.downtime?.data;
  const downtimeColumns = useMemo(() => cols(downtimeRows), [downtimeRows]);
  const downtimePivot = useMemo(
    () => pivotDowntimeByStore(downtimeRows || [], downtimeColumns),
    [downtimeRows, downtimeColumns],
  );

  const storeColEarly = useMemo(() => pickStoreColumn(downtimeColumns), [downtimeColumns]);
  const categoryCol = useMemo(() => {
    const picked = pickCategoryColumn(downtimeColumns, [storeColEarly].filter(Boolean));
    if (picked) return picked;
    const inferred = inferCategoricalColumns(downtimeRows || [], downtimeColumns, {
      exclude: [storeColEarly].filter(Boolean),
      maxUniq: 90,
    });
    return inferred[0]?.col ?? null;
  }, [downtimeColumns, downtimeRows, storeColEarly]);

  const downtimeCatalog = useMemo(
    () => discoverDowntimePivotCatalog(downtimeRows || [], downtimeColumns, { maxMatrixCols: 20, maxMatrices: 14 }),
    [downtimeRows, downtimeColumns],
  );

  const downtimeByCategory = useMemo(() => {
    if (!downtimeRows?.length || !categoryCol) return null;
    return pivotDowntimeByDimension(downtimeRows, downtimeColumns, categoryCol);
  }, [downtimeRows, downtimeColumns, categoryCol]);

  const cancelRows = ddOps.byStore?.cancellations?.data;
  const cancelCols = useMemo(() => cols(cancelRows), [cancelRows]);
  const cancelPivot = useMemo(() => pivotCountByStore(cancelRows || [], cancelCols), [cancelRows, cancelCols]);
  const cancelPivotCatalog = useMemo(
    () => discoverCountPivotCatalog(cancelRows || [], cancelCols, { maxMatrices: 6, maxMatrixCols: 16 }),
    [cancelRows, cancelCols],
  );

  const missRows = ddOps.byStore?.missingIncorrect?.data;
  const missCols = useMemo(() => cols(missRows), [missRows]);
  const missPivot = useMemo(() => pivotCountByStore(missRows || [], missCols), [missRows, missCols]);
  const missPivotCatalog = useMemo(
    () => discoverCountPivotCatalog(missRows || [], missCols, { maxMatrices: 6, maxMatrixCols: 16 }),
    [missRows, missCols],
  );

  const timeAggRows = ddOps.byTime?.aggregate?.data;
  const timeAggCols = useMemo(() => cols(timeAggRows), [timeAggRows]);
  const timePivot = useMemo(
    () => pivotStoreByDatePeriod(timeAggRows || [], timeAggCols, { maxCols: 36 }),
    [timeAggRows, timeAggCols],
  );

  const timeByStoreRows = ddOps.byTime?.byStore?.data;
  const timeByStoreCols = useMemo(() => cols(timeByStoreRows), [timeByStoreRows]);
  const timeByStorePivot = useMemo(
    () => pivotStoreByDatePeriod(timeByStoreRows || [], timeByStoreCols, { maxCols: 28 }),
    [timeByStoreRows, timeByStoreCols],
  );

  const orderSheets = useMemo(() => {
    const bo = ddOps.byOrder;
    if (!bo || typeof bo !== 'object') return [];
    return [
      ['Avoidable wait', bo.avoidableWait],
      ['Cancelled orders', bo.cancelled],
      ['Missing / incorrect', bo.missingIncorrect],
    ]
      .filter(([, s]) => s?.data?.length)
      .map(([label, s]) => ({
        label,
        rows: s.data,
        pivot: pivotCountByStore(s.data, cols(s.data)),
        countCatalog: discoverCountPivotCatalog(s.data, cols(s.data), { maxMatrices: 5, maxMatrixCols: 14 }),
      }));
  }, [ddOps.byOrder]);

  const extraOneWay = useMemo(
    () =>
      downtimeCatalog.oneWay.filter(
        (o) => o.dimCol !== downtimePivot.storeCol && o.dimCol !== categoryCol,
      ),
    [downtimeCatalog.oneWay, downtimePivot.storeCol, categoryCol],
  );

  if (!hasData) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Operations data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">Upload DoorDash Operations Quality ZIP files to see quality metrics.</p>
      </div>
    );
  }

  const downtimeTableCols = [
    { key: 'store', label: 'Store', sortable: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'days', label: 'Days', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
    { key: 'hours', label: 'Hours', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
    { key: 'minutes', label: 'Minutes', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
    { key: 'totalMinutes', label: 'Total (min)', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
    { key: 'lineCount', label: 'Rows', align: 'right', sortable: true, render: (v) => fmt.int(v ?? 0) },
  ];

  const countCols = [
    { key: 'store', label: 'Store', sortable: true, render: (v) => <span className="font-medium">{v}</span> },
    { key: 'rowCount', label: 'Count', align: 'right', sortable: true, render: (v) => fmt.int(Number(v) || 0) },
  ];

  const metricFormat = (valueCol) => {
    const name = String(valueCol || '').toLowerCase();
    const money = /sales|revenue|payout|amount|fee|cost|price|usd|\$/.test(name);
    const pct = /percent|ratio|rate|%/.test(name);
    return (v) => {
      if (v == null || v === 0) return '—';
      if (pct) return `${Number(v).toFixed(1)}%`;
      if (money) return fmt.usd2(v);
      if (Math.abs(v) >= 1000) return fmt.int(v);
      return Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 });
    };
  };

  const minuteFmt = (v) => (v == null || v === 0 ? '—' : fmt.int(Math.round(v)));

  return (
    <div className="space-y-8">
      {downtimePivot.rows.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Downtime by store</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Durations converted to total minutes, then split into{' '}
              <span className="font-medium text-[var(--text-muted)]">days · hours · minutes</span>
              {downtimePivot.downtimeCols?.length ? (
                <>
                  {' '}
                  · summed columns: {downtimePivot.downtimeCols.join(', ')}
                </>
              ) : null}
              {downtimePivot.storeCol ? (
                <>
                  {' '}
                  · store field: <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{downtimePivot.storeCol}</code>
                </>
              ) : null}
            </p>
          </div>
          <DataTable columns={downtimeTableCols} data={downtimePivot.rows} maxHeight="min(480px, 55vh)" />
        </section>
      )}

      {downtimeByCategory?.rows?.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Downtime by category</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Grouped by <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{downtimeByCategory.dimCol}</code>
              {downtimeByCategory.downtimeCols?.length ? (
                <> · same duration fields as store view: {downtimeByCategory.downtimeCols.join(', ')}</>
              ) : null}
            </p>
          </div>
          <DataTable columns={dhmCols} data={downtimeByCategory.rows} maxHeight="min(440px, 50vh)" />
        </section>
      )}

      {downtimeCatalog.catalogLines.length > 0 && (
        <details className="card p-4" open>
          <summary className="text-sm font-semibold text-[var(--text)] cursor-pointer">
            All discovered downtime pivots
          </summary>
          <p className="text-[11px] text-[var(--text-subtle)] mt-2 mb-3">
            Built from your CSV headers: dimensions include store, matched category/type/reason-style fields, dates, and other
            medium-cardinality columns. Matrices sum the same downtime minutes as the tables above.
          </p>
          <ul className="text-xs text-[var(--text-muted)] space-y-1 mb-4 list-disc pl-4">
            {downtimeCatalog.catalogLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>

          {extraOneWay.map((block) => (
            <div key={block.dimCol} className="mb-6 last:mb-0">
              <h4 className="text-xs font-semibold text-[var(--text)] mb-2">{block.title}</h4>
              <DataTable columns={dhmCols} data={block.rows} maxHeight="min(360px, 42vh)" />
            </div>
          ))}

          {downtimeCatalog.matrices
            .filter((m) => !/store.*×.*store|store\s*name.*×.*store/i.test(m.title))
            .map((m) => (
            <div key={`${m.rowDim}|${m.colDim}`} className="mb-6 last:mb-0">
              <h4 className="text-xs font-semibold text-[var(--text)] mb-2">{m.title}</h4>
              <p className="text-[10px] text-[var(--text-subtle)] mb-1">
                Rows: {m.rowDim} · Cols: {m.colDim}
                {m.colMode === 'chrono' ? ' · columns in time order' : ' · top columns + Other'}
              </p>
              <MatrixPivotTable
                rowHeaderLabel={m.rowDim}
                rowKeys={m.rowKeys}
                colKeys={m.colKeys}
                matrix={m.matrix}
                formatCell={minuteFmt}
                maxHeight="min(56vh, 520px)"
              />
            </div>
          ))}
        </details>
      )}

      {cancelPivot.rows.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Cancellations by store</h3>
            {cancelPivot.sumCol ? (
              <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                Totals sum <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{cancelPivot.sumCol}</code> per store
                (aggregated export). Store column:{' '}
                <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{cancelPivot.storeCol}</code>.
              </p>
            ) : (
              <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                One row = one cancellation event · store:{' '}
                <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{cancelPivot.storeCol}</code>
              </p>
            )}
          </div>
          <DataTable columns={countCols} data={cancelPivot.rows} maxHeight="400px" />
        </section>
      )}

      {(cancelPivotCatalog.matrices.length > 0 || cancelPivotCatalog.catalogLines.length > 0) && (
        <details className="card p-4">
          <summary className="text-sm font-semibold text-[var(--text)] cursor-pointer">
            Cancellations — extra count pivots
          </summary>
          <ul className="text-xs text-[var(--text-muted)] space-y-1 mt-2 mb-3 list-disc pl-4">
            {cancelPivotCatalog.catalogLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          {cancelPivotCatalog.matrices.map((m) => (
            <div key={`can-${m.rowDim}|${m.colDim}`} className="mb-6 last:mb-0">
              <h4 className="text-xs font-semibold text-[var(--text)] mb-2">{m.title}</h4>
              <MatrixPivotTable
                rowHeaderLabel={m.rowDim}
                rowKeys={m.rowKeys}
                colKeys={m.colKeys}
                matrix={m.matrix}
                formatCell={(v) => (v == null || v === 0 ? '—' : fmt.int(v))}
                maxHeight="min(48vh, 440px)"
              />
            </div>
          ))}
        </details>
      )}

      {missPivot.rows.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Missing / incorrect by store</h3>
            {missPivot.sumCol ? (
              <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                Totals sum <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{missPivot.sumCol}</code> per store
                (aggregated export). Store column:{' '}
                <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{missPivot.storeCol}</code>.
              </p>
            ) : (
              <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                One row = one issue · store:{' '}
                <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{missPivot.storeCol}</code>
              </p>
            )}
          </div>
          <DataTable columns={countCols} data={missPivot.rows} maxHeight="400px" />
        </section>
      )}

      {(missPivotCatalog.matrices.length > 0 || missPivotCatalog.catalogLines.length > 0) && (
        <details className="card p-4">
          <summary className="text-sm font-semibold text-[var(--text)] cursor-pointer">
            Missing / incorrect — extra count pivots
          </summary>
          <ul className="text-xs text-[var(--text-muted)] space-y-1 mt-2 mb-3 list-disc pl-4">
            {missPivotCatalog.catalogLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          {missPivotCatalog.matrices.map((m) => (
            <div key={`miss-${m.rowDim}|${m.colDim}`} className="mb-6 last:mb-0">
              <h4 className="text-xs font-semibold text-[var(--text)] mb-2">{m.title}</h4>
              <MatrixPivotTable
                rowHeaderLabel={m.rowDim}
                rowKeys={m.rowKeys}
                colKeys={m.colKeys}
                matrix={m.matrix}
                formatCell={(v) => (v == null || v === 0 ? '—' : fmt.int(v))}
                maxHeight="min(48vh, 440px)"
              />
            </div>
          ))}
        </details>
      )}

      {timePivot.rowStores?.length > 0 && timePivot.colProducts?.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Operations quality over time (pivot)</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Rows: <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{timePivot.storeCol}</code>
              {' · '}
              Period: <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{timePivot.dateCol}</code>
              {' · '}
              Values: <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{timePivot.valueCol}</code>
              {' '}
              (most recent {timePivot.colProducts.length} periods)
            </p>
          </div>
          <MatrixPivotTable
            rowHeaderLabel="Store"
            rowKeys={timePivot.rowStores}
            colKeys={timePivot.colProducts}
            matrix={timePivot.matrix}
            formatCell={metricFormat(timePivot.valueCol)}
            maxHeight="min(70vh, 560px)"
          />
        </section>
      )}

      {timeByStorePivot.rowStores?.length > 0 && timeByStorePivot.colProducts?.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">By store (time export) — pivot</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              {timeByStorePivot.storeCol} × {timeByStorePivot.dateCol} · {timeByStorePivot.valueCol}
            </p>
          </div>
          <MatrixPivotTable
            rowHeaderLabel="Store"
            rowKeys={timeByStorePivot.rowStores}
            colKeys={timeByStorePivot.colProducts}
            matrix={timeByStorePivot.matrix}
            formatCell={metricFormat(timeByStorePivot.valueCol)}
            maxHeight="min(60vh, 480px)"
          />
        </section>
      )}

      {orderSheets.map(({ label, rows, pivot, countCatalog }) => (
        <section key={label} className="space-y-3">
          <h3 className="text-sm font-semibold text-[var(--text)]">{label} — by store</h3>
          {pivot.rows?.length ? (
            <DataTable columns={countCols} data={pivot.rows} maxHeight="360px" />
          ) : (
            <p className="text-xs text-[var(--text-muted)]">{rows.length} rows — could not detect a store column for pivot.</p>
          )}
          {(countCatalog.matrices.length > 0 || countCatalog.catalogLines.length > 0) && (
            <details className="card p-4">
              <summary className="text-xs font-semibold text-[var(--text)] cursor-pointer">
                {label} — discovered count pivots
              </summary>
              <ul className="text-[11px] text-[var(--text-muted)] space-y-1 mt-2 mb-2 list-disc pl-4">
                {countCatalog.catalogLines.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
              {countCatalog.matrices.map((m) => (
                <div key={`${label}-${m.rowDim}|${m.colDim}`} className="mb-4 last:mb-0">
                  <h4 className="text-[11px] font-semibold text-[var(--text)] mb-1">{m.title}</h4>
                  <MatrixPivotTable
                    rowHeaderLabel={m.rowDim}
                    rowKeys={m.rowKeys}
                    colKeys={m.colKeys}
                    matrix={m.matrix}
                    formatCell={(v) => (v == null || v === 0 ? '—' : fmt.int(v))}
                    maxHeight="min(40vh, 380px)"
                  />
                </div>
              ))}
            </details>
          )}
        </section>
      ))}
    </div>
  );
}
