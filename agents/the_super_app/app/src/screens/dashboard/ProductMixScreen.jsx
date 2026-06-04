import { useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import MatrixPivotTable from '../../components/ui/MatrixPivotTable';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { fmt } from '../../lib/utils/formatters';
import { parseDate, getLastYearDates, isInRange } from '../../lib/utils/dateUtils';
import { growthPct, round, safeDivide } from '../../lib/utils/safeMath';
import {
  pivotProductByStore,
  pivotStoreByProduct,
  pivotOneWaySum,
  pickProductColumn,
  pickColumnByRegexOrder,
  pickErrorChargeColumn,
  pickProductMixDateColumn,
  isCoarseProductMixDates,
  normalizeProductMixStoreRows,
  sortPivotRows,
} from '../../lib/utils/opsProductPivot';
import { buildDdStoreIdToMerchantMap } from '../../lib/utils/storeCatalog';

const QTY_PATTERNS = [/units?\s*sold/i, /quantity/i, /\bqty\b/i, /orders/i, /count/i];
function toNum(v) {
  if (v == null) return 0;
  const n = Number(String(v).replace(/[$,]/g, ''));
  return Number.isFinite(n) ? n : 0;
}

function buildOneWayTable(keys, values) {
  if (!keys?.length) return [];
  return keys
    .map((key, i) => ({ key, value: values[i] }))
    .sort((a, b) => b.value - a.value);
}

/** ceil(n * pct), at least 1. */
function topCount(n, pct = 0.05) {
  if (!n) return 0;
  return Math.max(1, Math.ceil(n * pct));
}

export default function ProductMixScreen() {
  const { ddProductMix, ddFinancial } = useDataStore();
  const config = useConfigStore();

  const columns = useMemo(
    () => (ddProductMix?.[0] ? Object.keys(ddProductMix[0]) : []),
    [ddProductMix],
  );

  const pmixStores = useMemo(() => {
    const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(ddFinancial);
    return normalizeProductMixStoreRows(ddProductMix || [], columns, ddStoreIdToMerchant);
  }, [ddProductMix, columns, ddFinancial]);

  const pmixRows = pmixStores.rows;
  const pmixStoreCol = pmixStores.storeCol;
  const labelByKey = pmixStores.labelByKey;

  const productStorePivot = useMemo(
    () => pivotProductByStore(pmixRows, columns, { maxStoreCols: 26, storeCol: pmixStoreCol }),
    [pmixRows, columns, pmixStoreCol],
  );
  const storeProductPivot = useMemo(
    () => pivotStoreByProduct(pmixRows, columns, { maxProductCols: 26, storeCol: pmixStoreCol }),
    [pmixRows, columns, pmixStoreCol],
  );

  const valueCol = productStorePivot.valueCol || storeProductPivot.valueCol;
  const productCol = productStorePivot.productCol || storeProductPivot.productCol;

  const byProduct = useMemo(
    () => pivotOneWaySum(pmixRows, productCol, valueCol),
    [pmixRows, productCol, valueCol],
  );

  const dateCol = useMemo(
    () => pickProductMixDateColumn(columns, pmixRows),
    [columns, pmixRows],
  );
  const coarseDates = useMemo(
    () => isCoarseProductMixDates(pmixRows, dateCol),
    [pmixRows, dateCol],
  );

  // Per-product Pre / Post / LY when rows have real order-level dates (not report Start/End only).
  const productPeriods = useMemo(() => {
    if (coarseDates || !dateCol || !productCol || !valueCol) return null;
    const { ddPreStart, ddPreEnd, ddPostStart, ddPostEnd } = config;
    if (!ddPostStart || !ddPostEnd) return null;
    const ly = getLastYearDates(ddPostStart, ddPostEnd);
    const lyPre = ddPreStart && ddPreEnd ? getLastYearDates(ddPreStart, ddPreEnd) : null;

    const map = new Map();
    for (const r of pmixRows) {
      const d = parseDate(r[dateCol]);
      if (!d) continue;
      const name = String(r[productCol] ?? '').trim();
      if (!name) continue;
      const sales = toNum(r[valueCol]);
      const cur = map.get(name) || { product: name, pre: 0, post: 0, preLY: 0, postLY: 0 };
      if (ddPreStart && ddPreEnd && isInRange(d, ddPreStart, ddPreEnd)) cur.pre += sales;
      if (isInRange(d, ddPostStart, ddPostEnd)) cur.post += sales;
      if (lyPre && isInRange(d, lyPre.start, lyPre.end)) cur.preLY += sales;
      if (isInRange(d, ly.start, ly.end)) cur.postLY += sales;
      map.set(name, cur);
    }
    return [...map.values()]
      .map((p) => ({
        ...p,
        pre: round(p.pre),
        post: round(p.post),
        postLY: round(p.postLY),
        growthPct: round(growthPct(p.pre, p.post), 1),
      }))
      .sort((a, b) => b.post - a.post);
  }, [pmixRows, coarseDates, dateCol, productCol, valueCol, config]);

  const productStoreMatrix = useMemo(() => {
    if (!productStorePivot.rowProducts?.length || !productStorePivot.colStores?.length) return null;
    return sortPivotRows(
      {
        rowHeaderLabel: 'Product',
        rowKeys: productStorePivot.rowProducts,
        colKeys: productStorePivot.colStores,
        matrix: productStorePivot.matrix,
      },
      { by: 'total', dir: 'desc' },
    );
  }, [productStorePivot]);

  const storeProductMatrix = useMemo(() => {
    if (!storeProductPivot.rowStores?.length || !storeProductPivot.colProducts?.length) return null;
    return sortPivotRows(
      {
        rowHeaderLabel: 'Store',
        rowKeys: storeProductPivot.rowStores,
        colKeys: storeProductPivot.colProducts,
        matrix: storeProductPivot.matrix,
      },
      { by: 'total', dir: 'desc' },
    );
  }, [storeProductPivot]);

  const byProductRows = useMemo(() => buildOneWayTable(byProduct.keys, byProduct.values), [byProduct]);

  // Per-product aggregation for the top-5% highlight tables.
  const productAgg = useMemo(() => {
    const aggProductCol = productCol || pickProductColumn(columns);
    const salesCol = valueCol;
    const qtyCol = pickColumnByRegexOrder(columns, QTY_PATTERNS);
    const errorCol = pickErrorChargeColumn(columns);
    if (!aggProductCol || !salesCol) return [];
    const map = new Map();
    for (const r of pmixRows) {
      const name = String(r[aggProductCol] ?? '').trim();
      if (!name) continue;
      const cur = map.get(name) || { product: name, sales: 0, qty: 0, errorCharges: 0 };
      cur.sales += toNum(r[salesCol]);
      if (qtyCol) cur.qty += toNum(r[qtyCol]);
      if (errorCol) cur.errorCharges += toNum(r[errorCol]);
      map.set(name, cur);
    }
    return [...map.values()].map((p) => ({
      ...p,
      aov: p.qty > 0 ? p.sales / p.qty : null,
      errorChargePct: p.sales > 0 ? round(safeDivide(p.errorCharges, p.sales) * 100, 2) : null,
    }));
  }, [pmixRows, columns, productCol, valueCol]);

  const hasAov = useMemo(() => productAgg.some((p) => p.aov != null), [productAgg]);
  const hasErrorCharge = useMemo(
    () => productAgg.some((p) => (p.errorCharges || 0) > 0),
    [productAgg],
  );

  const topSellingRows = useMemo(() => {
    const sorted = [...productAgg].sort((a, b) => b.sales - a.sales);
    return sorted.slice(0, topCount(sorted.length));
  }, [productAgg]);

  const topAovRows = useMemo(() => {
    const withAov = productAgg.filter((p) => p.aov != null);
    const sorted = withAov.sort((a, b) => b.aov - a.aov);
    return sorted.slice(0, topCount(sorted.length));
  }, [productAgg]);

  const topErrorChargeRows = useMemo(() => {
    const eligible = productAgg.filter((p) => p.sales > 0 && p.errorChargePct != null);
    const sorted = [...eligible].sort((a, b) => b.errorChargePct - a.errorChargePct);
    return sorted.slice(0, topCount(sorted.length));
  }, [productAgg]);

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

  const valueLabel = valueCol ? `Total (${valueCol})` : 'Total';
  const lineCount = ddProductMix.length.toLocaleString();

  const productCell = (v) => (
    <span className="block max-w-[min(52vw,26rem)] truncate font-medium" title={String(v ?? '')}>
      {v}
    </span>
  );

  const productColumnSpec = {
    key: 'product',
    label: 'Product',
    labelCol: true,
    sortable: true,
    render: productCell,
  };
  const productKeyColumnSpec = {
    key: 'key',
    label: 'Product',
    labelCol: true,
    sortable: true,
    render: productCell,
  };

  const tableProps = { dense: true };

  const productCols = [
    productKeyColumnSpec,
    {
      key: 'value',
      label: valueLabel,
      align: 'right',
      sortable: true,
      render: (v) => formatCell(v),
    },
  ];

  const highlightSalesCols = [
    productColumnSpec,
    { key: 'sales', label: 'Gross sales', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    ...(hasAov ? [{ key: 'aov', label: 'AOV', align: 'right', sortable: true, render: (v) => (v == null ? '—' : fmt.usd2(v)) }] : []),
  ];

  const highlightAovCols = [
    productColumnSpec,
    { key: 'aov', label: 'AOV', align: 'right', sortable: true, render: (v) => (v == null ? '—' : fmt.usd2(v)) },
    { key: 'sales', label: 'Gross sales', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
  ];

  const highlightErrorChargeCols = [
    productColumnSpec,
    { key: 'errorChargePct', label: 'Error charge %', align: 'right', sortable: true, render: (v) => (v == null ? '—' : fmt.pct(v)) },
    { key: 'errorCharges', label: 'Error charges', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'sales', label: 'Gross sales', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
  ];

  const productPeriodCols = [
    productColumnSpec,
    { key: 'pre', label: 'Pre', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'post', label: 'Post', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'postLY', label: 'LY Post', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'growthPct', label: 'Growth %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
  ];

  return (
    <div className="space-y-5 max-w-full min-w-0 overflow-x-hidden">
      {(topSellingRows.length > 0 || topAovRows.length > 0 || topErrorChargeRows.length > 0) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {topSellingRows.length > 0 && (
            <section className="space-y-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Top 5% — highest selling</h3>
                <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                  {topSellingRows.length} of {productAgg.length} products by gross sales
                </p>
              </div>
              <SplitDataTable columns={highlightSalesCols} data={topSellingRows} maxHeight="min(45vh, 360px)" {...tableProps} />
            </section>
          )}
          {hasAov && topAovRows.length > 0 && (
            <section className="space-y-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Top 5% — highest AOV</h3>
                <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                  {topAovRows.length} of {productAgg.length} products by average order value
                </p>
              </div>
              <SplitDataTable columns={highlightAovCols} data={topAovRows} maxHeight="min(45vh, 360px)" {...tableProps} />
            </section>
          )}
          {hasErrorCharge && topErrorChargeRows.length > 0 && (
            <section className="space-y-2 xl:col-span-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Top 5% — highest error charge %</h3>
                <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                  {topErrorChargeRows.length} of {productAgg.length} products · error charge % = error charges ÷ gross sales
                </p>
              </div>
              <SplitDataTable columns={highlightErrorChargeCols} data={topErrorChargeRows} maxHeight="min(45vh, 360px)" {...tableProps} />
            </section>
          )}
        </div>
      )}

      {productStoreMatrix && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Product × Store</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              {lineCount} line items · sorted by highest total first
              {valueCol && (
                <>
                  {' · '}
                  Values (Σ): <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{valueCol}</code>
                </>
              )}
            </p>
          </div>
          <MatrixPivotTable
            rowHeaderLabel={productStoreMatrix.rowHeaderLabel}
            rowKeys={productStoreMatrix.rowKeys}
            colKeys={productStoreMatrix.colKeys}
            colTitles={productStoreMatrix.colKeys.map((k) => (k === 'Other' ? 'Other' : (labelByKey.get(k) || k)))}
            matrix={productStoreMatrix.matrix}
            formatCell={formatCell}
            maxHeight="min(55vh, 480px)"
          />
        </section>
      )}

      {storeProductMatrix && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">Store × Product</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Top products per store · sorted by highest total first
            </p>
          </div>
          <MatrixPivotTable
            rowHeaderLabel={storeProductMatrix.rowHeaderLabel}
            rowKeys={storeProductMatrix.rowKeys}
            colKeys={storeProductMatrix.colKeys}
            rowTitles={storeProductMatrix.rowKeys.map((k) => labelByKey.get(k) || k)}
            matrix={storeProductMatrix.matrix}
            formatCell={formatCell}
            maxHeight="min(55vh, 480px)"
          />
        </section>
      )}

      {productPeriods?.length > 0 ? (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">By product — Pre vs Post &amp; YoY</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Gross sales per product across periods · Growth % = Pre → Post
              {' · '}
              dates from <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{dateCol}</code>
            </p>
          </div>
          <SplitDataTable columns={productPeriodCols} data={productPeriods} maxHeight="min(60vh, 520px)" {...tableProps} />
        </section>
      ) : byProductRows.length > 0 && (
        <section className="space-y-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">By product (total)</h3>
            <p className="text-xs text-[var(--text-subtle)] mt-0.5">
              Gross sales summed across all stores per product
              {coarseDates
                ? ' · this export uses report Start/End ranges (not daily dates), so Pre / Post / LY is not shown'
                : !dateCol && ' · no date column found for period split'}
            </p>
          </div>
          <SplitDataTable columns={productCols} data={byProductRows} maxHeight="min(55vh, 480px)" {...tableProps} />
        </section>
      )}

      {!productStoreMatrix && !storeProductMatrix && !byProductRows.length && !productPeriods?.length && (
        <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
          Could not build product mix tables from this export.
        </div>
      )}
    </div>
  );
}
