import { useMemo } from 'react';
import { Table2 } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import { fmt } from '../../lib/utils/formatters';
import {
  buildFinancialSummaryTable,
  isProfitabilityMetric,
} from '../../lib/engine/financialBreakdown';

function formatCell(metric, value) {
  if (value == null || Number.isNaN(value)) return '—';
  if (isProfitabilityMetric(metric)) return fmt.pct(value);
  if (String(metric).includes('%')) return fmt.delta(value);
  return Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const COLUMNS = [
  { key: 'Metric', label: 'Metric', sortable: false },
  { key: 'Pre', label: 'Pre', align: 'right', sortable: false, render: (v, row) => formatCell(row.Metric, v) },
  { key: 'Post', label: 'Post', align: 'right', sortable: false, render: (v, row) => formatCell(row.Metric, v) },
  {
    key: 'Pre vs Post',
    label: 'Pre vs Post',
    align: 'right',
    sortable: false,
    delta: true,
    render: (v, row) => formatCell(row.Metric, v),
  },
  {
    key: 'Linear Growth%',
    label: 'Linear Growth%',
    align: 'right',
    sortable: false,
    delta: true,
    render: (v) => (v == null ? '—' : fmt.delta(v)),
  },
  {
    key: 'Last Year Pre',
    label: 'Last Year Pre',
    align: 'right',
    sortable: false,
    render: (v, row) => formatCell(row.Metric, v),
  },
  {
    key: 'Last Year Post',
    label: 'Last Year Post',
    align: 'right',
    sortable: false,
    render: (v, row) => formatCell(row.Metric, v),
  },
  {
    key: 'LY Pre vs Post',
    label: 'LY Pre vs Post',
    align: 'right',
    sortable: false,
    delta: true,
    render: (v, row) => formatCell(row.Metric, v),
  },
  {
    key: 'LY Linear %',
    label: 'LY Linear %',
    align: 'right',
    sortable: false,
    delta: true,
    render: (v) => (v == null ? '—' : fmt.delta(v)),
  },
  { key: 'YoY', label: 'YoY', align: 'right', sortable: false, delta: true, render: (v, row) => formatCell(row.Metric, v) },
  { key: 'YoY%', label: 'YoY%', align: 'right', sortable: false, delta: true, render: (v) => (v == null ? '—' : fmt.delta(v)) },
];

export default function BreakdownScreen() {
  const { ddFinancial, ueFinancial } = useDataStore();
  const config = useConfigStore();

  const rows = useMemo(
    () => buildFinancialSummaryTable(ddFinancial, ueFinancial, config),
    [ddFinancial, ueFinancial, config],
  );

  const hasData = (ddFinancial?.length || 0) > 0 || (ueFinancial?.length || 0) > 0;
  const hasDates = config.ddPreStart && config.ddPreEnd && config.ddPostStart && config.ddPostEnd;

  if (!hasData) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        Upload DoorDash and/or Uber Eats financial exports to see the financial summary.
      </p>
    );
  }

  if (!hasDates) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        Set Pre and Post analysis periods in Config to build the financial summary.
      </p>
    );
  }

  if (!rows.length) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        No rows in the selected date windows after exclusions.
      </p>
    );
  }

  return (
    <div className="space-y-4 max-w-full min-w-0">
      <div>
        <h2 className="text-lg font-semibold text-[var(--text)]">Financial Summary</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Top-level financial summary (App2.0 / Monthly Reporter parity) from your loaded exports and
          Pre / Post / last-year windows.
        </p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
        <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3">
          <Table2 className="h-4 w-4 text-[var(--accent)]" />
          <span className="text-sm font-semibold text-[var(--text)]">
            Financial Summary
          </span>
          <span className="text-xs text-[var(--text-muted)]">({rows.length} rows)</span>
        </div>
        <div className="max-h-[min(520px,70vh)] overflow-auto">
          <DataTable
            columns={COLUMNS}
            data={rows}
            sortable={false}
            dense
            allowHorizontalScroll
            bare
          />
        </div>
      </div>
    </div>
  );
}
