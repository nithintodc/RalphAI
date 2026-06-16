import { fmt, formatByKind } from '../utils/formatters';
import { getSlotTimeRange, SLOT_TIME_COLUMN_LABEL } from '../engine/slots';

export const SLOT_TIME_COLUMN_KEY = 'slotTime';

export function renderSlotValue(valueKind, v) {
  return formatByKind(valueKind, v);
}

export function buildSlotTimeColumn(fromKey = 'slot') {
  return {
    key: SLOT_TIME_COLUMN_KEY,
    label: SLOT_TIME_COLUMN_LABEL,
    sortable: false,
    labelCol: true,
    wrap: true,
    render: (_, row) => {
      const range = getSlotTimeRange(row?.[fromKey] ?? row?.slot);
      return range ? <span className="text-[var(--text-muted)] text-[11px]">{range}</span> : '—';
    },
  };
}

export function buildSlotPvpColumns(spec) {
  const preLabel = spec.dailyAvg ? 'Pre (avg/day)' : 'Pre';
  const postLabel = spec.dailyAvg ? 'Post (avg/day)' : 'Post';
  return [
    {
      key: 'slot',
      label: 'Slot',
      sortable: false,
      labelCol: true,
      wrap: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    buildSlotTimeColumn('slot'),
    { key: 'pre', label: preLabel, align: 'right', wrap: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'post', label: postLabel, align: 'right', wrap: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'prevspost', label: 'PvP Δ', align: 'right', delta: true, wrap: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'growthPct', label: 'PvP %', align: 'right', delta: true, wrap: true, render: (v) => (v == null ? '—' : fmt.delta(v)) },
    { key: 'lyPrevspost', label: 'LY Pre vs Post Δ', align: 'right', delta: true, wrap: true, render: (v) => (v == null ? '—' : renderSlotValue(spec.valueKind, v)) },
    { key: 'lyGrowthPct', label: 'LY Growth%', align: 'right', delta: true, wrap: true, render: (v) => (v == null ? '—' : fmt.delta(v)) },
  ];
}

export function buildSlotYoyColumns(spec) {
  const lyLabel = spec.dailyAvg ? 'LY Post (avg/day)' : 'LY Post';
  const postLabel = spec.dailyAvg ? 'Post (avg/day)' : 'Post';
  return [
    {
      key: 'slot',
      label: 'Slot',
      sortable: false,
      labelCol: true,
      wrap: true,
      render: (v) => <span className="font-medium">{v}</span>,
    },
    buildSlotTimeColumn('slot'),
    { key: 'postLY', label: lyLabel, align: 'right', wrap: true, render: (v) => (v == null ? '—' : renderSlotValue(spec.valueKind, v)) },
    { key: 'post', label: postLabel, align: 'right', wrap: true, render: (v) => renderSlotValue(spec.valueKind, v) },
    { key: 'yoy', label: 'YoY Δ', align: 'right', delta: true, wrap: true, render: (v) => (v == null ? '—' : renderSlotValue(spec.valueKind, v)) },
    { key: 'yoyPct', label: 'YoY %', align: 'right', delta: true, wrap: true, render: (v) => (v == null ? '—' : fmt.delta(v)) },
  ];
}
