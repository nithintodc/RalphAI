import { useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { fmt } from '../../lib/utils/formatters';
import { parseDate, getLastYearDates, isInRange } from '../../lib/utils/dateUtils';
import { growthPct, round, safeDivide } from '../../lib/utils/safeMath';
import {
  pivotOneWaySum,
  pickProductColumn,
  pickMetricColumn,
  pickErrorChargeColumn,
  pickProductMixDateColumn,
  pickProductMixQtyColumn,
  isCoarseProductMixDates,
} from '../../lib/utils/opsProductPivot';
import RankedBarChart from '../../components/charts/RankedBarChart';
import ChartCard from '../../components/charts/ChartCard';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts';
import { AXIS_TICK, GRID, POS } from '../../components/charts/chartTheme';

function ProductScatterTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md max-w-[16rem]">
      <p className="font-semibold text-[var(--text)] mb-1 truncate">{d.name}</p>
      <p className="tnum text-[var(--text-muted)]">Post sales: {fmt.usd(d.x)}</p>
      <p className="tnum text-[var(--text-muted)]">Growth: {fmt.delta(d.y)}</p>
    </div>
  );
}

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
function slicePct(n, pct = 0.05) {
  if (!n) return 0;
  return Math.max(1, Math.ceil(n * pct));
}

function topGrowthRows(rows, pct = 0.10) {
  const eligible = rows.filter((p) => p.pre > 0);
  const n = slicePct(eligible.length, pct);
  return [...eligible].sort((a, b) => b.growthPct - a.growthPct).slice(0, n);
}

function decliningGrowthRows(rows, pct = 0.10) {
  const eligible = rows.filter((p) => p.pre > 0);
  const n = slicePct(eligible.length, pct);
  return [...eligible].sort((a, b) => a.growthPct - b.growthPct).slice(0, n);
}

export default function ProductMixScreen() {
  const { ddProductMix } = useDataStore();
  const config = useConfigStore();

  const columns = useMemo(
    () => (ddProductMix?.[0] ? Object.keys(ddProductMix[0]) : []),
    [ddProductMix],
  );

  const pmixRows = ddProductMix || [];

  const productCol = useMemo(() => pickProductColumn(columns), [columns]);
  const valueCol = useMemo(
    () => pickMetricColumn(pmixRows, columns, [productCol].filter(Boolean)),
    [pmixRows, columns, productCol],
  );

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

  const byProductRows = useMemo(() => buildOneWayTable(byProduct.keys, byProduct.values), [byProduct]);

  const topGrowthProductRows = useMemo(
    () => (productPeriods ? topGrowthRows(productPeriods) : []),
    [productPeriods],
  );
  const decliningProductRows = useMemo(
    () => (productPeriods ? decliningGrowthRows(productPeriods) : []),
    [productPeriods],
  );

  // Per-product aggregation for the top-5% highlight tables.
  const productAgg = useMemo(() => {
    const aggProductCol = productCol || pickProductColumn(columns);
    const salesCol = valueCol;
    const qtyCol = pickProductMixQtyColumn(columns);
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
      aov: p.qty > 0 ? round(safeDivide(p.sales, p.qty), 2) : null,
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
    return sorted.slice(0, slicePct(sorted.length));
  }, [productAgg]);

  const topAovRows = useMemo(() => {
    const withAov = productAgg.filter((p) => p.aov != null);
    const sorted = withAov.sort((a, b) => b.aov - a.aov);
    return sorted.slice(0, slicePct(sorted.length));
  }, [productAgg]);

  const topErrorChargeRows = useMemo(() => {
    const eligible = productAgg.filter((p) => p.sales > 0 && p.errorChargePct != null);
    const sorted = [...eligible].sort((a, b) => b.errorChargePct - a.errorChargePct);
    return sorted.slice(0, slicePct(sorted.length));
  }, [productAgg]);

  if (!ddProductMix || !ddProductMix.length) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Product Mix data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">Upload the DoorDash Product Mix ZIP to see item-level performance.</p>
      </div>
    );
  }

  const valueLabel = valueCol ? `Total (${valueCol})` : 'Total';

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
      render: (v) => fmt.usd(v || 0),
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

  const growthMoverCols = [
    productColumnSpec,
    { key: 'pre', label: 'Pre', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'post', label: 'Post', align: 'right', sortable: true, render: (v) => fmt.usd(v || 0) },
    { key: 'growthPct', label: 'Growth %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v || 0) },
  ];

  const topSalesBar = [...productAgg].sort((a, b) => b.sales - a.sales).slice(0, 12)
    .map((p) => ({ label: p.product, value: p.sales }));
  const scatterRows = (productPeriods || [])
    .filter((p) => p.post > 0 && p.growthPct != null)
    .map((p) => ({ x: p.post, y: p.growthPct, name: p.product }));

  return (
    <div className="space-y-5 max-w-full min-w-0 overflow-x-hidden">
      {(topSalesBar.length > 0 || scatterRows.length > 1) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {topSalesBar.length > 0 && (
            <RankedBarChart
              title="Top products by gross sales"
              subtitle="The biggest revenue drivers across all stores."
              data={topSalesBar}
              topN={12}
              color="var(--accent)"
              valueFormatter={fmt.usdK}
            />
          )}
          {scatterRows.length > 1 && (
            <ChartCard
              title="Sales vs growth — by product"
              subtitle="Post sales (x) vs Pre→Post growth % (y). Top-right = big & growing; bottom-right = big but declining."
              height={300}
            >
              <ScatterChart margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis type="number" dataKey="x" name="Post sales" tick={AXIS_TICK} axisLine={false} tickLine={false} tickFormatter={fmt.usdK} />
                <YAxis type="number" dataKey="y" name="Growth %" tick={AXIS_TICK} axisLine={false} tickLine={false} width={48} tickFormatter={(v) => `${Math.round(v)}%`} />
                <ZAxis type="number" range={[50, 50]} />
                <ReferenceLine y={0} stroke="var(--border-strong)" />
                <Tooltip content={<ProductScatterTip />} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter data={scatterRows} fill={POS} fillOpacity={0.55} />
              </ScatterChart>
            </ChartCard>
          )}
        </div>
      )}

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

      {(topGrowthProductRows.length > 0 || decliningProductRows.length > 0) && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {topGrowthProductRows.length > 0 && (
            <section className="space-y-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Top 10% — highest growth</h3>
                <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                  {topGrowthProductRows.length} of {productPeriods.length} products · gross sales Pre → Post
                  {' · '}
                  dates from <code className="text-[10px] bg-[var(--surface-2)] px-1 rounded">{dateCol}</code>
                </p>
              </div>
              <SplitDataTable columns={growthMoverCols} data={topGrowthProductRows} maxHeight="min(50vh, 420px)" {...tableProps} />
            </section>
          )}
          {decliningProductRows.length > 0 && (
            <section className="space-y-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--text)]">Declining 10% — largest drops</h3>
                <p className="text-xs text-[var(--text-subtle)] mt-0.5">
                  {decliningProductRows.length} of {productPeriods.length} products · sorted by lowest growth %
                </p>
              </div>
              <SplitDataTable columns={growthMoverCols} data={decliningProductRows} maxHeight="min(50vh, 420px)" {...tableProps} />
            </section>
          )}
        </div>
      )}

      {productPeriods?.length > 0 ? null : byProductRows.length > 0 && (
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

      {!topSellingRows.length && !topGrowthProductRows.length && !byProductRows.length && (
        <div className="card py-8 text-center text-sm text-[var(--text-muted)]">
          Could not build product mix tables from this export.
        </div>
      )}
    </div>
  );
}
