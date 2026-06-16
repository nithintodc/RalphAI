import { useMemo, useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import { useUiStore } from '../../stores/uiStore';
import PlatformLogo from '../../components/ui/PlatformLogo';
import WowGroupTable from '../../components/wow/WowGroupTable';
import WowPeriodsTable from '../../components/wow/WowPeriodsTable';
import {
  buildWowWeeklySalesSeries,
  buildWowStoreScopeOptions,
  buildWowGroupSalesTables,
  buildWowAnalysisRangeTable,
} from '../../lib/engine/wowWeeklySales';
import {
  WEEK_DEFINITION_OPTIONS,
  resolveWeekStartsOn,
  getWeekDefinitionById,
} from '../../lib/utils/weekDefinition';
import { WOW_TABLE_METRICS } from '../../lib/engine/wowMetrics';
import { fmt } from '../../lib/utils/formatters';
import { AXIS_TICK, GRID } from '../../components/charts/chartTheme';

const PLATFORM_TABS = [
  { id: 'combined', label: 'Combined', logo: null },
  { id: 'dd', label: 'DoorDash', logo: 'dd' },
  { id: 'ue', label: 'Uber Eats', logo: 'ue' },
];

const YEAR_COLORS = [
  '#f97316',
  '#3b82f6',
  '#22c55e',
  '#a855f7',
  '#ec4899',
  '#14b8a6',
];

function compactAxisTick(v) {
  if (v == null || !Number.isFinite(v)) return '';
  const abs = Math.abs(v);
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${Math.round(v)}`;
}

function WowTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-[var(--text)] mb-1.5">Week {label}</p>
      {payload
        .filter((e) => e.value != null)
        .map((entry) => (
          <p key={String(entry.dataKey)} className="flex justify-between gap-6 tnum">
            <span style={{ color: entry.color }}>{entry.name}</span>
            <span className="font-medium text-[var(--text)]">{fmt.usd(entry.value)}</span>
          </p>
        ))}
    </div>
  );
}

export default function WowScreen() {
  const { ddFinancial, ueFinancial, ddMarketing, storeTables } = useDataStore();
  const config = useConfigStore();
  const weekDefinitionId = useConfigStore((s) => s.weekDefinitionId);
  const setWeekDefinitionId = useConfigStore((s) => s.setWeekDefinitionId);
  const dateAnalysisMode = useConfigStore((s) => s.dateAnalysisMode);
  const setActiveTab = useUiStore((s) => s.setActiveTab);

  const [platform, setPlatform] = useState('combined');
  const [storeScope, setStoreScope] = useState('total');
  const [groupMetric, setGroupMetric] = useState('sales');
  const isWowMode = dateAnalysisMode === 'wow';
  const analysisRangeStart = config.ddPostStart || config.uePostStart;
  const analysisRangeEnd = config.ddPostEnd || config.uePostEnd;

  const weekStartsOn = resolveWeekStartsOn(weekDefinitionId);
  const weekLabel = getWeekDefinitionById(weekDefinitionId).label;

  const scopeOptions = useMemo(
    () => buildWowStoreScopeOptions(storeTables, config),
    [storeTables, config.storeTagMap],
  );

  const groupTables = useMemo(
    () => buildWowGroupSalesTables({
      ddFinancial,
      ueFinancial,
      ddMarketing,
      config,
      storeTables,
      platform,
      weekStartsOn,
      rangeStart: isWowMode ? analysisRangeStart : null,
      rangeEnd: isWowMode ? analysisRangeEnd : null,
      weekCount: 4,
      metricKey: groupMetric,
    }),
    [ddFinancial, ueFinancial, ddMarketing, config, storeTables, platform, weekStartsOn, isWowMode, analysisRangeStart, analysisRangeEnd, groupMetric],
  );

  const rangeTable = useMemo(
    () => (isWowMode && analysisRangeStart && analysisRangeEnd
      ? buildWowAnalysisRangeTable({
        ddFinancial,
        ueFinancial,
        ddMarketing,
        config,
        platform,
        storeScope,
        weekStartsOn,
        rangeStart: analysisRangeStart,
        rangeEnd: analysisRangeEnd,
      })
      : null),
    [isWowMode, analysisRangeStart, analysisRangeEnd, ddFinancial, ueFinancial, ddMarketing, config, platform, storeScope, weekStartsOn],
  );

  const series = useMemo(
    () => buildWowWeeklySalesSeries({
      ddFinancial,
      ueFinancial,
      config,
      platform,
      storeScope,
      weekStartsOn,
    }),
    [ddFinancial, ueFinancial, config, platform, storeScope, weekStartsOn],
  );

  useEffect(() => {
    if (dateAnalysisMode === 'wow') {
      setActiveTab('wow');
    }
  }, [dateAnalysisMode, setActiveTab]);

  const platformLabel = platform === 'combined'
    ? 'Combined DoorDash + Uber Eats sales'
    : platform === 'dd'
      ? 'DoorDash sales'
      : 'Uber Eats sales';

  const scopeLabel = useMemo(() => {
    if (storeScope === 'total') return 'Total';
    if (storeScope === 'A') return 'Group A · TODC';
    if (storeScope === 'B') return 'Group B · Non-TODC';
    const hit = scopeOptions.stores.find((s) => s.id === storeScope);
    return hit?.label || storeScope;
  }, [storeScope, scopeOptions.stores]);

  const hasChartData = series.years.length > 0 && series.chartRows.some((row) =>
    series.years.some((y) => row[`y${y}`] != null),
  );

  return (
    <div className="space-y-4 min-w-0 max-w-full">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-[var(--text)]">Week over week</h2>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            {isWowMode
              ? `All business weeks in your analysis range · ${weekLabel}`
              : `Weekly sales by year · business calendar ${weekLabel}`}
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <label className="flex flex-col gap-1 min-w-[140px]">
            <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)]">
              Your week
            </span>
            <select
              value={weekDefinitionId}
              onChange={(e) => setWeekDefinitionId(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] cursor-pointer focus:outline-none focus:border-[var(--accent)]"
            >
              {WEEK_DEFINITION_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
          </label>

          {isWowMode && (
            <label className="flex flex-col gap-1 min-w-[160px]">
              <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)]">
                Group tables
              </span>
              <select
                value={groupMetric}
                onChange={(e) => setGroupMetric(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] cursor-pointer focus:outline-none focus:border-[var(--accent)]"
              >
                {WOW_TABLE_METRICS.map((m) => (
                  <option key={m.key} value={m.key}>{m.label}</option>
                ))}
              </select>
            </label>
          )}

          {isWowMode && (
            <label className="flex flex-col gap-1 min-w-[180px]">
              <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)]">
                Scope
              </span>
              <select
                value={storeScope}
                onChange={(e) => setStoreScope(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] cursor-pointer focus:outline-none focus:border-[var(--accent)]"
              >
                <option value="total">Total</option>
                {scopeOptions.hasA && <option value="A">Group A · TODC</option>}
                {scopeOptions.hasB && <option value="B">Group B · Non-TODC</option>}
                {scopeOptions.stores.length > 0 && (
                  <optgroup label="Stores">
                    {scopeOptions.stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}{s.tag ? ` (${s.tag})` : ''}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </label>
          )}

          {!isWowMode && (
            <label className="flex flex-col gap-1 min-w-[180px]">
              <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)]">
                Chart scope
              </span>
              <select
                value={storeScope}
                onChange={(e) => setStoreScope(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] cursor-pointer focus:outline-none focus:border-[var(--accent)]"
              >
                <option value="total">Total</option>
                {scopeOptions.hasA && <option value="A">Group A · TODC</option>}
                {scopeOptions.hasB && <option value="B">Group B · Non-TODC</option>}
                {scopeOptions.stores.length > 0 && (
                  <optgroup label="Stores">
                    {scopeOptions.stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}{s.tag ? ` (${s.tag})` : ''}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
            </label>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-1 p-0.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] w-fit max-w-full">
        {PLATFORM_TABS.map((tab) => {
          const disabled = tab.id === 'dd' && !ddFinancial?.length
            || tab.id === 'ue' && !ueFinancial?.length;
          return (
            <button
              key={tab.id}
              type="button"
              disabled={disabled}
              onClick={() => setPlatform(tab.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer
                ${platform === tab.id
                  ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)] border border-transparent'
                }
                ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              {tab.logo && <PlatformLogo platform={tab.logo} size={14} />}
              {tab.label}
            </button>
          );
        })}
      </div>

      {isWowMode && (
        <div className="space-y-4 min-w-0">
          <WowPeriodsTable
            table={rangeTable}
            scopeLabel={scopeLabel}
            platformLabel={platformLabel}
            weekLabel={weekLabel}
          />
          <WowGroupTable group={groupTables.groupA} platformLabel={platformLabel} />
          <div className="h-3 bg-[var(--surface-2)] border-y border-[var(--border)]" aria-hidden />
          <WowGroupTable group={groupTables.groupB} platformLabel={platformLabel} />
        </div>
      )}

      {!isWowMode && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="min-h-[4.5rem] rounded-xl border border-[var(--border)] bg-[var(--surface)]" aria-hidden />
            <div className="min-h-[4.5rem] rounded-xl border border-[var(--border)] bg-[var(--surface)]" aria-hidden />
          </div>

          <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 min-w-0">
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
              <p className="text-xs font-medium text-[var(--text-muted)]">
                Weekly sales · {scopeLabel}
                {platform !== 'combined' && ` · ${platform === 'dd' ? 'DoorDash' : 'Uber Eats'}`}
              </p>
              {!hasChartData && (
                <p className="text-[10px] text-amber-800">No weekly data for this selection.</p>
              )}
            </div>

            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={series.chartRows} margin={{ top: 8, right: 16, left: 4, bottom: 8 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="week"
                  tick={AXIS_TICK}
                  axisLine={false}
                  tickLine={false}
                  label={{ value: 'Week', position: 'insideBottom', offset: -2, fontSize: 11, fill: 'var(--text-subtle)' }}
                />
                <YAxis
                  tick={AXIS_TICK}
                  width={52}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={compactAxisTick}
                  domain={[0, 'auto']}
                />
                <Tooltip content={<WowTooltip />} />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value) => <span className="text-xs text-[var(--text-muted)]">{value}</span>}
                />
                {series.years.map((year, i) => (
                  <Line
                    key={year}
                    type="monotone"
                    dataKey={`y${year}`}
                    name={String(year)}
                    stroke={YEAR_COLORS[i % YEAR_COLORS.length]}
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
