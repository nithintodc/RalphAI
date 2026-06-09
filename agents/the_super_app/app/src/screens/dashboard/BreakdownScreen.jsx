import { useMemo } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import PlatformLogo from '../../components/ui/PlatformLogo';
import { fmt } from '../../lib/utils/formatters';
import { buildPlatformFinancialBreakdowns } from '../../lib/engine/financialBreakdown';
import { deltaCellClass } from '../../lib/utils/deltaTone';
import GroupedBarChart from '../../components/charts/GroupedBarChart';
import RankedBarChart from '../../components/charts/RankedBarChart';
import { SERIES } from '../../components/charts/chartTheme';

function formatAmount(row, value) {
  if (value == null || Number.isNaN(value)) return '—';
  if (row.isProfitability) return fmt.pct(value);
  return fmt.usd2(value);
}

const METRIC_COL = {
  key: 'metric',
  label: 'Metric',
  sortable: false,
  labelCol: true,
  wrap: true,
  render: (v) => <span className="font-medium">{v}</span>,
};

const PERIOD_COLUMNS = [
  METRIC_COL,
  {
    key: 'value',
    label: 'Amount',
    sortable: false,
    wrap: true,
    render: (v, row) => formatAmount(row, v),
  },
  {
    key: 'sharePct',
    label: '% of sales',
    sortable: false,
    wrap: true,
    render: (v, row) => {
      if (row.isProfitability) return '—';
      if (v == null) return '—';
      return fmt.pct(v);
    },
  },
];

function TransitionCell({ before, after, growthPct, row }) {
  const growthLabel = growthPct == null
    ? '—'
    : row.isProfitability
      ? `${growthPct >= 0 ? '+' : ''}${growthPct.toFixed(1)} pp`
      : fmt.delta(growthPct);
  const deltaCls = growthPct == null ? '' : deltaCellClass(growthPct);

  return (
    <span className="inline-flex flex-wrap items-center justify-center gap-1.5">
      <span className="tnum">{formatAmount(row, before)}</span>
      <span className="text-[var(--text-subtle)]">→</span>
      <span className="tnum">{formatAmount(row, after)}</span>
      <span className={`tnum font-medium ${deltaCls}`}>{growthLabel}</span>
    </span>
  );
}

const PVP_COLUMNS = [
  METRIC_COL,
  {
    key: 'transition',
    label: 'Pre → Post',
    sortable: false,
    wrap: true,
    render: (_, row) => (
      <TransitionCell before={row.pre} after={row.post} growthPct={row.growthPct} row={row} />
    ),
  },
];

const YOY_COLUMNS = [
  METRIC_COL,
  {
    key: 'transition',
    label: 'LY Post → Post',
    sortable: false,
    wrap: true,
    render: (_, row) => (
      <TransitionCell before={row.lyPost} after={row.post} growthPct={row.yoyPct} row={row} />
    ),
  },
];

function BreakdownTable({ title, columns, data }) {
  if (!data?.length) return null;
  return (
    <div className="space-y-2">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{title}</h4>
      <DataTable columns={columns} data={data} sortable={false} dense />
    </div>
  );
}

/** Composition shift (% of sales, Pre vs Post) + per-line growth, above the tables. */
function BreakdownCharts({ section }) {
  const shareRows = (section.post || [])
    .filter((r) => !r.isProfitability && r.sharePct != null)
    .map((r) => {
      const preR = (section.pre || []).find((p) => p.metric === r.metric);
      return { metric: r.metric, preShare: preR?.sharePct ?? 0, postShare: r.sharePct };
    });
  const growthRows = (section.pvp || [])
    .filter((r) => !r.isProfitability && r.growthPct != null)
    .map((r) => ({ label: r.metric, value: r.growthPct }));

  if (!shareRows.length && !growthRows.length) return null;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      {shareRows.length > 0 && (
        <GroupedBarChart
          title="Lines as % of sales — Pre vs Post"
          subtitle="How each cost/credit line's share of sales shifted."
          data={shareRows}
          xKey="metric"
          height={320}
          angle={-35}
          smallTicks
          valueFormatter={fmt.pct}
          series={[
            { key: 'preShare', name: 'Pre', color: SERIES.pre },
            { key: 'postShare', name: 'Post', color: SERIES.post },
          ]}
        />
      )}
      {growthRows.length > 0 && (
        <RankedBarChart
          title="Pre → Post change by line"
          subtitle="% change in each line from Pre to Post. Green = up, red = down."
          data={growthRows}
          valueFormatter={fmt.delta}
        />
      )}
    </div>
  );
}

function PlatformBreakdownSection({ section }) {
  const label = section.platform === 'dd' ? 'DoorDash' : 'Uber Eats';

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2">
        <PlatformLogo platform={section.platform} size={18} />
        <h3 className="text-base font-semibold text-[var(--text)]">{label}</h3>
      </div>

      <BreakdownCharts section={section} />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <BreakdownTable title="Pre" columns={PERIOD_COLUMNS} data={section.pre} />
        <BreakdownTable title="Post" columns={PERIOD_COLUMNS} data={section.post} />
        <BreakdownTable title="Last year — Pre" columns={PERIOD_COLUMNS} data={section.lyPre} />
        <BreakdownTable title="Last year — Post" columns={PERIOD_COLUMNS} data={section.lyPost} />
      </div>

      <div className="grid grid-cols-1 gap-6 pt-2 border-t border-[var(--border)]">
        <BreakdownTable title="Pre vs Post" columns={PVP_COLUMNS} data={section.pvp} />
        <BreakdownTable title="Year over year (Post vs LY Post)" columns={YOY_COLUMNS} data={section.yoy} />
      </div>
    </div>
  );
}

export default function BreakdownScreen() {
  const { ddFinancial, ueFinancial } = useDataStore();
  const config = useConfigStore();

  const sections = useMemo(
    () => buildPlatformFinancialBreakdowns(ddFinancial, ueFinancial, config),
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

  if (!sections.length) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        No rows in the selected date windows after exclusions.
      </p>
    );
  }

  return (
    <div className="space-y-10 max-w-full min-w-0">
      <div>
        <h2 className="text-lg font-semibold text-[var(--text)]">Financial Summary</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)] max-w-3xl">
          DoorDash and Uber Eats shown separately. Period tables include each line as a share of platform sales.
          Pre vs Post and YoY show value transitions with growth %.
        </p>
      </div>

      {sections.map((section) => (
        <PlatformBreakdownSection key={section.platform} section={section} />
      ))}
    </div>
  );
}
