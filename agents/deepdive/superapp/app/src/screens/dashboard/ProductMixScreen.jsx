import { useMemo, useState } from 'react';
import { useDataStore } from '../../stores/dataStore';
import MatrixPivotTable from '../../components/ui/MatrixPivotTable';
import DataTable from '../../components/ui/DataTable';
import { fmt } from '../../lib/utils/formatters';
import {
  pivotProductByStore,
  pivotStoreByProduct,
  pivotOneWaySum,
  sortPivotRows,
} from '../../lib/utils/opsProductPivot';

const PIVOT_VIEWS = [
  { id: 'productStore', label: 'Product × Store' },
  { id: 'storeProduct', label: 'Store × Product' },
  { id: 'byStore', label: 'By store (total)' },
  { id: 'byProduct', label: 'By product (total)' },
];

const SORT_OPTIONS = [
  { id: 'total-desc', by: 'total', dir: 'desc', label: 'Highest total first' },
  { id: 'total-asc', by: 'total', dir: 'asc', label: 'Lowest total first' },
  { id: 'name-asc', by: 'name', dir: 'asc', label: 'Name A → Z' },
  { id: 'name-desc', by: 'name', dir: 'desc', label: 'Name Z → A' },
];

export default function ProductMixScreen() {
  const { ddProductMix } = useDataStore();
  const [view, setView] = useState('productStore');
  const [sortId, setSortId] = useState('total-desc');
  const [storeFilter, setStoreFilter] = useState('');
  const [productFilter, setProductFilter] = useState('');

  const columns = useMemo(
    () => (ddProductMix?.[0] ? Object.keys(ddProductMix[0]) : []),
    [ddProductMix],
  );

  const filteredRows = useMemo(() => {
    let rows = ddProductMix || [];
    if (storeFilter) {
      const storeCol = columns.find((c) => /store\s*id|merchant\s*store/i.test(String(c)));
      if (storeCol) rows = rows.filter((r) => String(r[storeCol]) === storeFilter);
    }
    if (productFilter) {
      const productCol = columns.find((c) => /item\s*name|menu\s*item|product/i.test(String(c)));
      if (productCol) {
        const q = productFilter.toLowerCase();
        rows = rows.filter((r) => String(r[productCol] || '').toLowerCase().includes(q));
      }
    }
    return rows;
  }, [ddProductMix, columns, storeFilter, productFilter]);

  const productStorePivot = useMemo(
    () => pivotProductByStore(filteredRows, columns, { maxStoreCols: 26 }),
    [filteredRows, columns],
  );
  const storeProductPivot = useMemo(
    () => pivotStoreByProduct(filteredRows, columns, { maxProductCols: 26 }),
    [filteredRows, columns],
  );

  const valueCol = productStorePivot.valueCol || storeProductPivot.valueCol;
  const byStore = useMemo(
    () => pivotOneWaySum(filteredRows, productStorePivot.storeCol, valueCol),
    [filteredRows, productStorePivot.storeCol, valueCol],
  );
  const byProduct = useMemo(
    () => pivotOneWaySum(filteredRows, productStorePivot.productCol, valueCol),
    [filteredRows, productStorePivot.productCol, valueCol],
  );

  const storeOptions = useMemo(() => {
    if (!productStorePivot.storeCol) return [];
    return [...new Set((ddProductMix || []).map((r) => String(r[productStorePivot.storeCol])))].filter(Boolean).sort((a, b) =>
      a.localeCompare(b, undefined, { numeric: true }),
    );
  }, [ddProductMix, productStorePivot.storeCol]);

  const sortOpt = SORT_OPTIONS.find((s) => s.id === sortId) || SORT_OPTIONS[0];

  const activeMatrix = useMemo(() => {
    if (view === 'productStore') {
      return {
        rowHeaderLabel: 'Product',
        rowKeys: productStorePivot.rowProducts,
        colKeys: productStorePivot.colStores,
        matrix: productStorePivot.matrix,
      };
    }
    if (view === 'storeProduct') {
      return {
        rowHeaderLabel: 'Store',
        rowKeys: storeProductPivot.rowStores,
        colKeys: storeProductPivot.colProducts,
        matrix: storeProductPivot.matrix,
      };
    }
    return null;
  }, [view, productStorePivot, storeProductPivot]);

  const sortedMatrix = useMemo(() => {
    if (!activeMatrix?.rowKeys?.length) return activeMatrix;
    return sortPivotRows(activeMatrix, { by: sortOpt.by, dir: sortOpt.dir });
  }, [activeMatrix, sortOpt]);

  const oneWayTable = useMemo(() => {
    const src = view === 'byStore' ? byStore : view === 'byProduct' ? byProduct : null;
    if (!src?.keys?.length) return [];
    const rows = src.keys.map((key, i) => ({ key, value: src.values[i] }));
    if (sortOpt.by === 'name') {
      rows.sort((a, b) => (sortOpt.dir === 'asc' ? a.key.localeCompare(b.key) : b.key.localeCompare(a.key)));
    } else {
      rows.sort((a, b) => (sortOpt.dir === 'asc' ? a.value - b.value : b.value - a.value));
    }
    return rows;
  }, [view, byStore, byProduct, sortOpt]);

  if (!ddProductMix || !ddProductMix.length) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Product Mix data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">Upload the DoorDash Product Mix ZIP to see item-level performance.</p>
      </div>
    );
  }

  const name = String(valueCol || '').toLowerCase();
  const money = /sales|revenue|payout|amount|fee|cost|price|usd|\$/.test(name);
  const formatCell = (v) => {
    if (v == null || v === 0) return '—';
    if (money) return fmt.usd2(v);
    if (Math.abs(v) >= 1000) return fmt.int(v);
    return Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 });
  };

  const oneWayCols = [
    {
      key: 'key',
      label: view === 'byStore' ? 'Store' : 'Product',
      sortable: false,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    {
      key: 'value',
      label: valueCol ? `Total (${valueCol})` : 'Total',
      align: 'right',
      sortable: false,
      render: (v) => formatCell(v),
    },
  ];

  const hasMatrix = sortedMatrix?.rowKeys?.length > 0 && sortedMatrix?.colKeys?.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex flex-wrap gap-1 p-0.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)]">
          {PIVOT_VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setView(v.id)}
              className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-colors cursor-pointer
                ${view === v.id
                  ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)]'
                }`}
            >
              {v.label}
            </button>
          ))}
        </div>

        <label className="flex flex-col gap-0.5 text-[10px] text-[var(--text-muted)]">
          Sort
          <select
            value={sortId}
            onChange={(e) => setSortId(e.target.value)}
            className="px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] min-w-[10rem]"
          >
            {SORT_OPTIONS.map((s) => (
              <option key={s.id} value={s.id}>{s.label}</option>
            ))}
          </select>
        </label>

        {storeOptions.length > 0 && (
          <label className="flex flex-col gap-0.5 text-[10px] text-[var(--text-muted)]">
            Store filter
            <select
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value)}
              className="px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] min-w-[8rem]"
            >
              <option value="">All stores</option>
              {storeOptions.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </label>
        )}

        <label className="flex flex-col gap-0.5 text-[10px] text-[var(--text-muted)]">
          Product search
          <input
            type="text"
            value={productFilter}
            onChange={(e) => setProductFilter(e.target.value)}
            placeholder="Filter by name…"
            className="px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] min-w-[10rem]"
          />
        </label>
      </div>

      <section className="space-y-2">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text)]">
            {PIVOT_VIEWS.find((v) => v.id === view)?.label}
          </h3>
          <p className="text-xs text-[var(--text-subtle)] mt-0.5">
            {filteredRows.length.toLocaleString()} line items
            {valueCol && (
              <>
                {' · '}
                Values (Σ): <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{valueCol}</code>
              </>
            )}
          </p>
        </div>

        {(view === 'productStore' || view === 'storeProduct') && hasMatrix && (
          <MatrixPivotTable
            rowHeaderLabel={sortedMatrix.rowHeaderLabel}
            rowKeys={sortedMatrix.rowKeys}
            colKeys={sortedMatrix.colKeys}
            matrix={sortedMatrix.matrix}
            formatCell={formatCell}
            maxHeight="min(75vh, 640px)"
          />
        )}

        {(view === 'byStore' || view === 'byProduct') && oneWayTable.length > 0 && (
          <DataTable columns={oneWayCols} data={oneWayTable} maxHeight="min(75vh, 640px)" />
        )}

        {((view === 'productStore' || view === 'storeProduct') && !hasMatrix) && (
          <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
            Could not build this pivot from the current filters.
          </div>
        )}
      </section>
    </div>
  );
}
