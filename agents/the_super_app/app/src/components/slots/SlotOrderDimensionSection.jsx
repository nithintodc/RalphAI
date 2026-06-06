import DataTable from '../ui/DataTable';
import { formatByKind } from '../../lib/utils/formatters';
import { buildSlotTimeColumn } from '../../lib/slots/slotTableColumns';

function renderCell(kind, v) {
  return formatByKind(kind, v);
}

const CUSTOMER_ITEM_COLS = [
  { key: 'orders', label: 'Orders', kind: 'int' },
  { key: 'newCount', label: 'New', kind: 'int' },
  { key: 'newPct', label: 'New %', kind: 'pct' },
  { key: 'repeatCount', label: 'Repeat', kind: 'int' },
  { key: 'repeatPct', label: 'Repeat %', kind: 'pct' },
  { key: 'unknownCount', label: 'Unknown', kind: 'int' },
  { key: 'unknownPct', label: 'Unknown %', kind: 'pct' },
  { key: 'totalItems', label: 'Total items', kind: 'int' },
  { key: 'avgItemsPerOrder', label: 'Avg items / order', kind: 'num2' },
];

const DASHPASS_COLS = [
  { key: 'orders', label: 'Orders', kind: 'int' },
  { key: 'dashPassCount', label: 'DashPass', kind: 'int' },
  { key: 'dashPassPct', label: 'DashPass %', kind: 'pct' },
  { key: 'nonDashPassCount', label: 'Non-DashPass', kind: 'int' },
  { key: 'nonDashPassPct', label: 'Non-DashPass %', kind: 'pct' },
];

const ORDER_VOLUME_COLS = [
  { key: 'orders', label: 'Orders', kind: 'int' },
];

function buildColumns(rowKey, rowLabel, metricCols, { showSlotTime = false, slotTimeKey = 'slot' } = {}) {
  const cols = [
    {
      key: rowKey,
      label: rowLabel,
      sortable: true,
      labelCol: true,
      wrap: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
  ];
  if (showSlotTime) cols.push(buildSlotTimeColumn(slotTimeKey));
  return [
    ...cols,
    ...metricCols.map((c) => ({
      key: c.key,
      label: c.label,
      align: 'right',
      sortable: true,
      wrap: true,
      render: (v) => renderCell(c.kind, v),
    })),
  ];
}

function PeriodTable({ title, data, rowKey, rowLabel, metricCols, showSlotTime, slotTimeKey }) {
  if (!data?.length) {
    return (
      <div className="space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</h4>
        <p className="text-xs text-[var(--text-subtle)]">No orders in this period for the selected window.</p>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</h4>
      <DataTable
        columns={buildColumns(rowKey, rowLabel, metricCols, { showSlotTime, slotTimeKey })}
        data={data}
        allowHorizontalScroll
        dense
      />
    </div>
  );
}

function BreakdownBlock({ title, analysis, rowKey, rowLabel, dataKey, metricCols, showSlotTime, slotTimeKey }) {
  return (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-[var(--text)]">{title}</h4>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <PeriodTable title="Pre" data={analysis.pre?.[dataKey]} rowKey={rowKey} rowLabel={rowLabel} metricCols={metricCols} showSlotTime={showSlotTime} slotTimeKey={slotTimeKey} />
        <PeriodTable title="Post" data={analysis.post?.[dataKey]} rowKey={rowKey} rowLabel={rowLabel} metricCols={metricCols} showSlotTime={showSlotTime} slotTimeKey={slotTimeKey} />
      </div>
    </div>
  );
}

/**
 * @param {'slot'|'day'|'daySlot'} dimension
 */
export default function SlotOrderDimensionSection({
  analysis,
  platformLabel,
  dimension,
  timeFieldLabel = 'Order received local time',
}) {
  if (!analysis) return null;

  const showCustomerItems = analysis.hasCustomerType || analysis.hasItemCount;
  const breakdownCols = showCustomerItems ? CUSTOMER_ITEM_COLS : ORDER_VOLUME_COLS;

  const dimConfig = {
    slot: { title: 'By slot', rowKey: 'slot', rowLabel: 'Slot', dataKey: 'slot' },
    day: { title: 'By day', rowKey: 'day', rowLabel: 'Day', dataKey: 'day' },
    daySlot: { title: 'By day × slot', rowKey: 'label', rowLabel: 'Day · Slot', dataKey: 'daySlot' },
  }[dimension];

  if (!dimConfig) return null;

  const showSlotTime = dimension === 'slot' || dimension === 'daySlot';
  const slotTimeKey = dimension === 'daySlot' ? 'slot' : dimConfig.rowKey;

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-sm font-semibold text-[var(--text)] mb-1">
          {showCustomerItems ? 'Customer mix & items' : 'Order volume'} — {platformLabel}
        </h3>
        <p className="text-[11px] text-[var(--text-subtle)] leading-relaxed max-w-3xl">
          Dayparts from <strong>{timeFieldLabel}</strong>.
          {showCustomerItems && (
            <> Customer type, item counts, and DashPass mix from SALES_BY_ORDER when those columns are present.</>
          )}
        </p>
      </div>

      <BreakdownBlock
        title={dimConfig.title}
        analysis={analysis}
        rowKey={dimConfig.rowKey}
        rowLabel={dimConfig.rowLabel}
        dataKey={dimConfig.dataKey}
        metricCols={breakdownCols}
        showSlotTime={showSlotTime}
        slotTimeKey={slotTimeKey}
      />

      {analysis.hasDashPass && (
        <BreakdownBlock
          title={`DashPass mix — ${dimConfig.title}`}
          analysis={analysis}
          rowKey={dimConfig.rowKey}
          rowLabel={dimConfig.rowLabel}
          dataKey={dimConfig.dataKey}
          metricCols={DASHPASS_COLS}
          showSlotTime={showSlotTime}
          slotTimeKey={slotTimeKey}
        />
      )}
    </div>
  );
}
