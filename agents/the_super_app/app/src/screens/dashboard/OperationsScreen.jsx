import { useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import MatrixPivotTable from '../../components/ui/MatrixPivotTable';
import { fmt } from '../../lib/utils/formatters';
import { heatBackground, minMaxNumeric } from '../../lib/utils/heatmap';
import {
  pivotDowntimeByStore,
  pivotDowntimeByDimension,
  pivotCountByStore,
  pickCategoryColumn,
  pickStoreColumn,
  inferCategoricalColumns,
  formatDurationDHM,
  pivotStoreReasonMatrix,
  pivotTopDatesPerStore,
} from '../../lib/utils/opsProductPivot';
import { PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';
import RankedBarChart from '../../components/charts/RankedBarChart';
import ChartCard from '../../components/charts/ChartCard';
import { TOOLTIP_STYLE, CATEGORICAL, WARN } from '../../components/charts/chartTheme';

/** Downtime ranked-by-store + by-category donut, above the ops tables. */
function DowntimeCharts({ storeRows, categoryRows, categoryCol }) {
  const hasStore = storeRows.some((r) => (r.totalMinutes || 0) > 0);
  const sortedCats = [...(categoryRows || [])].sort((a, b) => (b.totalMinutes || 0) - (a.totalMinutes || 0));
  const top = sortedCats.slice(0, 7);
  const restTotal = sortedCats.slice(7).reduce((s, r) => s + (r.totalMinutes || 0), 0);
  const pieData = top.map((r) => ({ name: r.label, value: Math.round(r.totalMinutes || 0) }));
  if (restTotal > 0) pieData.push({ name: 'Other', value: Math.round(restTotal) });
  const hasCat = pieData.some((d) => d.value > 0);
  if (!hasStore && !hasCat) return null;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {hasStore && (
        <RankedBarChart
          title="Downtime by store"
          subtitle="Total store offline time. Longer bars = more lost availability."
          data={storeRows.map((r) => ({ label: r.label, value: r.totalMinutes || 0 }))}
          topN={15}
          color={WARN}
          valueFormatter={formatDurationDHM}
        />
      )}
      {hasCat && (
        <ChartCard title="Downtime by category" subtitle={`Share of total downtime by ${categoryCol || 'category'}.`} height={300}>
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={95} paddingAngle={2}>
              {pieData.map((_, i) => <Cell key={i} fill={CATEGORICAL[i % CATEGORICAL.length]} />)}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => formatDurationDHM(v)} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
          </PieChart>
        </ChartCard>
      )}
    </div>
  );
}

function cols(rows) {
  return rows?.[0] ? Object.keys(rows[0]) : [];
}

function mapDurationRows(rows, labelKey = 'store') {
  return (rows || []).map((r) => ({
    ...r,
    duration: formatDurationDHM(r.totalMinutes),
    label: r[labelKey] ?? r.label,
  }));
}

function durationCols(label = 'Store', labelKey = 'store') {
  return [
    {
      key: labelKey,
      label,
      sortable: true,
      labelCol: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    {
      key: 'duration',
      label: 'Downtime',
      align: 'right',
      sortable: true,
      heatKey: 'totalMinutes',
      render: (v) => v || '—',
    },
  ];
}

function bucketDurationCols(heatMin, heatMax) {
  return [
    {
      key: 'label',
      label: 'Category',
      sortable: true,
      labelCol: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    {
      key: 'duration',
      label: 'Downtime',
      align: 'right',
      sortable: true,
      render: (v, row) => (
        <span
          className="block -mx-2 px-2 py-0.5 rounded-sm"
          style={{ backgroundColor: heatBackground(row.totalMinutes, heatMin, heatMax) }}
        >
          {v || '—'}
        </span>
      ),
    },
  ];
}

function topDateCols({ valueKind, heatMin, heatMax, metricFormat }) {
  const valueLabel = valueKind === 'duration' ? 'Downtime' : 'Count';
  return [
    {
      key: 'store',
      label: 'Store',
      sortable: true,
      labelCol: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    { key: 'date', label: 'Date', sortable: true, wrap: true },
    {
      key: 'display',
      label: valueLabel,
      align: 'right',
      sortable: true,
      render: (v, row) => {
        const bg = heatBackground(row.total, heatMin, heatMax);
        const text = valueKind === 'duration' ? v : (metricFormat ? metricFormat(v) : fmt.int(v));
        return (
          <span className="block -mx-2 px-2 py-0.5 rounded-sm" style={{ backgroundColor: bg }}>
            {text}
          </span>
        );
      },
    },
  ];
}

function countStoreCols(heatMin, heatMax) {
  return [
    {
      key: 'store',
      label: 'Store',
      sortable: true,
      labelCol: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    {
      key: 'rowCount',
      label: 'Count',
      align: 'right',
      sortable: true,
      render: (v) => {
        const n = Number(v) || 0;
        return (
          <span
            className="block -mx-2 px-2 py-0.5 rounded-sm"
            style={{ backgroundColor: heatBackground(n, heatMin, heatMax) }}
          >
            {fmt.int(n)}
          </span>
        );
      },
    },
  ];
}

function OpsSection({ title, subtitle, children }) {
  return (
    <section className="space-y-2">
      <div>
        <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>
        {subtitle ? <p className="text-xs text-[var(--text-subtle)] mt-0.5">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}

function ReasonMatrix({ matrix, title, subtitle, formatCell }) {
  if (!matrix?.rowKeys?.length || !matrix?.colKeys?.length) return null;
  return (
    <OpsSection title={title} subtitle={subtitle}>
      <MatrixPivotTable
        rowHeaderLabel="Store"
        rowKeys={matrix.rowKeys}
        colKeys={matrix.colKeys}
        matrix={matrix.matrix}
        formatCell={formatCell}
        splitColumns={false}
        heatmap
        maxHeight="min(52vh, 460px)"
      />
    </OpsSection>
  );
}

function TopDatesTable({ pivot, title, subtitle, valueKind, metricFormat }) {
  if (!pivot?.rows?.length) return null;
  const totals = pivot.rows.map((r) => r.total);
  const { min, max } = minMaxNumeric(totals);
  return (
    <OpsSection title={title} subtitle={subtitle}>
      <SplitDataTable
        columns={topDateCols({ valueKind, heatMin: min, heatMax: max, metricFormat })}
        data={pivot.rows}
        maxHeight="min(440px, 48vh)"
        layout="tight"
        dense
        split={false}
        allowHorizontalScroll
      />
    </OpsSection>
  );
}

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

  const downtimeByCategory = useMemo(() => {
    if (!downtimeRows?.length || !categoryCol) return null;
    return pivotDowntimeByDimension(downtimeRows, downtimeColumns, categoryCol);
  }, [downtimeRows, downtimeColumns, categoryCol]);

  const downtimeStoreReason = useMemo(
    () => pivotStoreReasonMatrix(downtimeRows || [], downtimeColumns, { valueKind: 'duration', maxReasonCols: 10 }),
    [downtimeRows, downtimeColumns],
  );

  const downtimeTopDates = useMemo(
    () => pivotTopDatesPerStore(downtimeRows || [], downtimeColumns, { topPerStore: 5, valueKind: 'duration' }),
    [downtimeRows, downtimeColumns],
  );

  const cancelRows = ddOps.byStore?.cancellations?.data;
  const cancelCols = useMemo(() => cols(cancelRows), [cancelRows]);
  const cancelPivot = useMemo(() => pivotCountByStore(cancelRows || [], cancelCols), [cancelRows, cancelCols]);
  const cancelStoreReason = useMemo(
    () => pivotStoreReasonMatrix(cancelRows || [], cancelCols, { valueKind: 'count', maxReasonCols: 10 }),
    [cancelRows, cancelCols],
  );
  const cancelTopDates = useMemo(
    () => pivotTopDatesPerStore(cancelRows || [], cancelCols, { topPerStore: 5, valueKind: 'count' }),
    [cancelRows, cancelCols],
  );

  const missRows = ddOps.byStore?.missingIncorrect?.data;
  const missCols = useMemo(() => cols(missRows), [missRows]);
  const missPivot = useMemo(() => pivotCountByStore(missRows || [], missCols), [missRows, missCols]);
  const missStoreReason = useMemo(
    () => pivotStoreReasonMatrix(missRows || [], missCols, { valueKind: 'count', maxReasonCols: 10 }),
    [missRows, missCols],
  );
  const missTopDates = useMemo(
    () => pivotTopDatesPerStore(missRows || [], missCols, { topPerStore: 5, valueKind: 'count' }),
    [missRows, missCols],
  );

  const timeAggRows = ddOps.byTime?.aggregate?.data;
  const timeAggCols = useMemo(() => cols(timeAggRows), [timeAggRows]);
  const timeTopDates = useMemo(
    () => pivotTopDatesPerStore(timeAggRows || [], timeAggCols, { topPerStore: 5, valueKind: 'metric' }),
    [timeAggRows, timeAggCols],
  );

  const timeByStoreRows = ddOps.byTime?.byStore?.data;
  const timeByStoreCols = useMemo(() => cols(timeByStoreRows), [timeByStoreRows]);
  const timeByStoreTopDates = useMemo(
    () => pivotTopDatesPerStore(timeByStoreRows || [], timeByStoreCols, { topPerStore: 5, valueKind: 'metric' }),
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
      .map(([label, s]) => {
        const c = cols(s.data);
        return {
          label,
          rows: s.data,
          pivot: pivotCountByStore(s.data, c),
          storeReason: pivotStoreReasonMatrix(s.data, c, { valueKind: 'count', maxReasonCols: 10 }),
          topDates: pivotTopDatesPerStore(s.data, c, { topPerStore: 5, valueKind: 'count' }),
        };
      });
  }, [ddOps.byOrder]);

  const downtimeStoreRows = useMemo(() => mapDurationRows(downtimePivot.rows), [downtimePivot.rows]);
  const downtimeCategoryRows = useMemo(() => {
    const rows = mapDurationRows(downtimeByCategory?.rows || [], 'label');
    return rows;
  }, [downtimeByCategory]);

  const downtimeStoreHeat = useMemo(
    () => minMaxNumeric(downtimeStoreRows.map((r) => r.totalMinutes)),
    [downtimeStoreRows],
  );
  const downtimeCategoryHeat = useMemo(
    () => minMaxNumeric(downtimeCategoryRows.map((r) => r.totalMinutes)),
    [downtimeCategoryRows],
  );
  const cancelHeat = useMemo(
    () => minMaxNumeric((cancelPivot.rows || []).map((r) => Number(r.rowCount) || 0)),
    [cancelPivot.rows],
  );
  const missHeat = useMemo(
    () => minMaxNumeric((missPivot.rows || []).map((r) => Number(r.rowCount) || 0)),
    [missPivot.rows],
  );

  if (!hasData) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Operations data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">Upload DoorDash Operations Quality ZIP files to see quality metrics.</p>
      </div>
    );
  }

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

  const downtimeStoreTableCols = durationCols('Store', 'store').map((col) => {
    if (col.key !== 'duration') return col;
    return {
      ...col,
      render: (v, row) => (
        <span
          className="block -mx-2 px-2 py-0.5 rounded-sm"
          style={{ backgroundColor: heatBackground(row.totalMinutes, downtimeStoreHeat.min, downtimeStoreHeat.max) }}
        >
          {v || '—'}
        </span>
      ),
    };
  });

  const durationMatrixFmt = (v) => (v == null || v === 0 ? '—' : formatDurationDHM(v));
  const countMatrixFmt = (v) => (v == null || v === 0 ? '—' : fmt.int(v));

  return (
    <div className="space-y-8 max-w-full min-w-0 overflow-x-hidden">
      <DowntimeCharts
        storeRows={downtimeStoreRows}
        categoryRows={downtimeCategoryRows}
        categoryCol={categoryCol}
      />

      {downtimeStoreRows.length > 0 && (
        <OpsSection
          title="Downtime by store"
          subtitle={
            <>
              Total downtime per store
              {downtimePivot.downtimeCols?.length ? ` · summed: ${downtimePivot.downtimeCols.join(', ')}` : ''}
            </>
          }
        >
          <SplitDataTable
            columns={downtimeStoreTableCols}
            data={downtimeStoreRows}
            maxHeight="min(480px, 55vh)"
            layout="tight"
            dense
            split={false}
          />
        </OpsSection>
      )}

      {downtimeCategoryRows.length > 0 && (
        <OpsSection
          title="Downtime by category"
          subtitle={<>Grouped by {categoryCol}</>}
        >
          <SplitDataTable
            columns={bucketDurationCols(downtimeCategoryHeat.min, downtimeCategoryHeat.max)}
            data={downtimeCategoryRows}
            maxHeight="min(440px, 50vh)"
            layout="tight"
            dense
            split={false}
          />
        </OpsSection>
      )}

      <ReasonMatrix
        matrix={downtimeStoreReason}
        title="Downtime by store × reason"
        subtitle={
          downtimeStoreReason
            ? `Stores in rows · reasons in columns (${downtimeStoreReason.reasonCol}) · darker = more downtime`
            : null
        }
        formatCell={durationMatrixFmt}
      />

      <TopDatesTable
        pivot={downtimeTopDates}
        title="Top downtime dates by store"
        subtitle="Up to 5 highest-downtime dates per store (not a full date matrix)"
        valueKind="duration"
      />

      {cancelPivot.rows.length > 0 && (
        <OpsSection
          title="Cancellations by store"
          subtitle={
            cancelPivot.sumCol
              ? `Totals sum ${cancelPivot.sumCol} per store`
              : 'One row = one cancellation event'
          }
        >
          <SplitDataTable
            columns={countStoreCols(cancelHeat.min, cancelHeat.max)}
            data={cancelPivot.rows}
            maxHeight="400px"
            layout="tight"
            dense
            split={false}
          />
        </OpsSection>
      )}

      <ReasonMatrix
        matrix={cancelStoreReason}
        title="Cancellations by store × reason"
        subtitle={cancelStoreReason ? `Reason field: ${cancelStoreReason.reasonCol}` : null}
        formatCell={countMatrixFmt}
      />

      <TopDatesTable
        pivot={cancelTopDates}
        title="Top cancellation dates by store"
        subtitle="Up to 5 highest-count dates per store"
        valueKind="count"
      />

      {missPivot.rows.length > 0 && (
        <OpsSection title="Missing / incorrect by store" subtitle="Event counts per store">
          <SplitDataTable
            columns={countStoreCols(missHeat.min, missHeat.max)}
            data={missPivot.rows}
            maxHeight="400px"
            layout="tight"
            dense
            split={false}
          />
        </OpsSection>
      )}

      <ReasonMatrix
        matrix={missStoreReason}
        title="Missing / incorrect by store × reason"
        subtitle={missStoreReason ? `Reason field: ${missStoreReason.reasonCol}` : null}
        formatCell={countMatrixFmt}
      />

      <TopDatesTable
        pivot={missTopDates}
        title="Top missing / incorrect dates by store"
        subtitle="Up to 5 highest-count dates per store"
        valueKind="count"
      />

      <TopDatesTable
        pivot={timeTopDates}
        title="Operations quality — top dates (aggregate)"
        subtitle={
          timeTopDates.valueCol
            ? `Highest ${timeTopDates.valueCol} dates per store`
            : 'Top dates per store from time aggregate export'
        }
        valueKind="metric"
        metricFormat={metricFormat(timeTopDates.valueCol)}
      />

      <TopDatesTable
        pivot={timeByStoreTopDates}
        title="Operations quality — top dates (by store export)"
        subtitle={
          timeByStoreTopDates.valueCol
            ? `Highest ${timeByStoreTopDates.valueCol} dates per store`
            : 'Top dates per store from by-store time export'
        }
        valueKind="metric"
        metricFormat={metricFormat(timeByStoreTopDates.valueCol)}
      />

      {orderSheets.map(({ label, pivot, storeReason, topDates }) => {
        const heat = minMaxNumeric((pivot.rows || []).map((r) => Number(r.rowCount) || 0));
        return (
          <div key={label} className="space-y-6">
            {pivot.rows?.length > 0 && (
              <OpsSection title={`${label} — by store`}>
                <SplitDataTable
                  columns={countStoreCols(heat.min, heat.max)}
                  data={pivot.rows}
                  maxHeight="360px"
                  layout="tight"
                  dense
                  split={false}
                />
              </OpsSection>
            )}
            <ReasonMatrix
              matrix={storeReason}
              title={`${label} — store × reason`}
              subtitle={storeReason ? `Reason field: ${storeReason.reasonCol}` : null}
              formatCell={countMatrixFmt}
            />
            <TopDatesTable
              pivot={topDates}
              title={`${label} — top dates by store`}
              subtitle="Up to 5 highest-count dates per store"
              valueKind="count"
            />
          </div>
        );
      })}
    </div>
  );
}
