import { useMemo, useState, useEffect } from 'react';
import { formatCompactDateRange } from '../../lib/utils/dateUtils';
import { isPresetRangeMode } from '../../lib/utils/periodMode';
import {
  findMatchingComparePreset,
  findMatchingSinglePreset,
} from '../../lib/utils/analysisPeriodSelectors';

const RANGE_COMPARE_GROUPS = [
  { id: 'wow', label: 'WoW', title: 'Week over week in your date range' },
  { id: 'mom', label: 'MoM', title: 'Month over month in your date range' },
  { id: 'qoq', label: 'QoQ', title: 'Quarter over quarter in your date range' },
];

const CUSTOM_COMPARE_GROUPS = [
  { id: 'yoy', label: 'YoY', title: 'Same month or quarter vs last year' },
  { id: 'custom', label: 'Custom', title: 'Manual Pre vs Post dates' },
];

const SINGLE_GROUPS = [
  { id: 'week', label: 'Week', title: 'Mon–Sun weeks in your data' },
  { id: 'month', label: 'Month', title: 'Calendar months in your data' },
  { id: 'quarter', label: 'Quarter', title: 'Calendar quarters in your data' },
  { id: 'year', label: 'Year', title: 'Calendar years in your data' },
];

function PresetButton({ active, label, detail, onClick, disabled = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`w-full text-left rounded-lg border px-2.5 py-2 transition-colors
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${active
          ? 'border-[var(--accent-border)] bg-[var(--accent-soft)] text-[var(--accent-text)]'
          : 'border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-2)]'
        }`}
    >
      <div className="text-xs font-medium leading-snug">{label}</div>
      {detail && (
        <div className={`text-[10px] mt-0.5 leading-snug ${active ? 'text-[var(--accent-text)]/80' : 'text-[var(--text-subtle)]'}`}>
          {detail}
        </div>
      )}
    </button>
  );
}

function PeriodPreviewRow({ label, detail }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-2">
      <div className="text-xs font-medium leading-snug text-[var(--text)]">{label}</div>
      {detail && (
        <div className="text-[10px] mt-0.5 leading-snug text-[var(--text-subtle)]">{detail}</div>
      )}
    </div>
  );
}

export default function PeriodPresetPanel({
  isSinglePeriod,
  dateAnalysisMode,
  compareGroups,
  singleGroups,
  periodsInRange = [],
  rangeStart,
  rangeEnd,
  preStart,
  preEnd,
  postStart,
  postEnd,
  singleStart,
  singleEnd,
  onSelectCompareMode,
  onSelectComparePreset,
  onSelectSinglePreset,
}) {
  const yoyPresets = compareGroups?.yoy || [];

  const singleGroupDefs = useMemo(
    () => SINGLE_GROUPS.filter((g) => (singleGroups?.[g.id] || []).length > 0),
    [singleGroups],
  );

  const activeCompare = useMemo(
    () => findMatchingComparePreset(compareGroups, preStart, preEnd, postStart, postEnd),
    [compareGroups, preStart, preEnd, postStart, postEnd],
  );
  const activeSingle = useMemo(
    () => findMatchingSinglePreset(singleGroups, singleStart, singleEnd),
    [singleGroups, singleStart, singleEnd],
  );

  const isRangeMode = isPresetRangeMode(dateAnalysisMode);
  const isCustomMode = !isSinglePeriod && !isRangeMode;

  const defaultTab = isSinglePeriod
    ? (singleGroupDefs[0]?.id || 'month')
    : isRangeMode
      ? dateAnalysisMode
      : (activeCompare?.groupKey === 'yoy' ? 'yoy' : 'custom');

  const [activeTab, setActiveTab] = useState(defaultTab);

  useEffect(() => {
    if (isSinglePeriod) {
      if (activeSingle?.groupKey) setActiveTab(activeSingle.groupKey);
      return;
    }
    if (isPresetRangeMode(dateAnalysisMode)) {
      setActiveTab(dateAnalysisMode);
      return;
    }
    if (activeCompare?.groupKey === 'yoy') {
      setActiveTab('yoy');
      return;
    }
    setActiveTab('custom');
  }, [isSinglePeriod, dateAnalysisMode, activeCompare?.groupKey, activeSingle?.groupKey]);

  const visibleTab = isSinglePeriod
    ? (singleGroupDefs.some((g) => g.id === activeTab) ? activeTab : singleGroupDefs[0]?.id)
    : isRangeMode
      ? dateAnalysisMode
      : (activeTab === 'yoy' || activeTab === 'custom' ? activeTab : 'custom');

  if (isSinglePeriod) {
    const groupDefs = singleGroupDefs;
    if (!groupDefs.length) {
      return (
        <aside className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 min-w-0 lg:sticky lg:top-4">
          <h4 className="text-xs font-semibold text-[var(--text)] mb-1">Presets</h4>
          <p className="text-[10px] text-[var(--text-subtle)] leading-snug">
            Upload data to see week, month, quarter, and year options.
          </p>
        </aside>
      );
    }

    const presets = singleGroups?.[visibleTab] || [];
    const activePresetId = activeSingle?.preset?.id;

    return (
      <aside className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 min-w-0 flex flex-col gap-2.5 lg:sticky lg:top-4 lg:max-h-[calc(100vh-8rem)]">
        <div>
          <h4 className="text-xs font-semibold text-[var(--text)]">Presets</h4>
          <p className="text-[10px] text-[var(--text-subtle)] mt-0.5 leading-snug">Week, month, quarter, or year</p>
        </div>
        <div className="flex flex-wrap gap-1">
          {groupDefs.map((g) => (
            <button
              key={g.id}
              type="button"
              title={g.title}
              onClick={() => setActiveTab(g.id)}
              className={`px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer border transition-colors
                ${visibleTab === g.id
                  ? 'bg-[var(--surface)] text-[var(--text)] border-[var(--border)] shadow-sm'
                  : 'bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
                }`}
            >
              {g.label}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-1 max-h-[min(320px,42vh)] overflow-y-auto pr-0.5 flex-1 min-h-0">
          {presets.map((preset) => (
            <PresetButton
              key={preset.id}
              active={preset.id === activePresetId}
              label={preset.label}
              detail={formatCompactDateRange(preset.start, preset.end)}
              onClick={() => onSelectSinglePreset(preset)}
            />
          ))}
        </div>
      </aside>
    );
  }

  const rangeGroupLabel = RANGE_COMPARE_GROUPS.find((g) => g.id === visibleTab)?.label || 'Periods';
  const hasRange = rangeStart && rangeEnd;

  return (
    <aside className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 min-w-0 flex flex-col gap-2.5 lg:sticky lg:top-4 lg:max-h-[calc(100vh-8rem)]">
      <div>
        <h4 className="text-xs font-semibold text-[var(--text)]">Analysis type</h4>
        <p className="text-[10px] text-[var(--text-subtle)] mt-0.5 leading-snug">
          WoW · MoM · QoQ use one date range · Custom uses Pre vs Post
        </p>
      </div>

      <div className="flex flex-wrap gap-1">
        {RANGE_COMPARE_GROUPS.map((g) => (
          <button
            key={g.id}
            type="button"
            title={g.title}
            onClick={() => {
              setActiveTab(g.id);
              onSelectCompareMode?.(g.id);
            }}
            className={`px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer border transition-colors
              ${visibleTab === g.id && isRangeMode
                ? 'bg-[var(--surface)] text-[var(--text)] border-[var(--border)] shadow-sm'
                : 'bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
              }`}
          >
            {g.label}
          </button>
        ))}
        {CUSTOM_COMPARE_GROUPS.map((g) => (
          <button
            key={g.id}
            type="button"
            title={g.title}
            onClick={() => {
              setActiveTab(g.id);
              onSelectCompareMode?.(g.id === 'yoy' ? 'yoy' : 'pvp');
            }}
            className={`px-2 py-1 rounded-md text-[11px] font-medium cursor-pointer border transition-colors
              ${visibleTab === g.id && isCustomMode
                ? 'bg-[var(--surface)] text-[var(--text)] border-[var(--border)] shadow-sm'
                : 'bg-transparent text-[var(--text-muted)] border-transparent hover:text-[var(--text)]'
              }`}
          >
            {g.label}
          </button>
        ))}
      </div>

      {isRangeMode && (
        <div className="flex flex-col gap-1 max-h-[min(320px,42vh)] overflow-y-auto pr-0.5 flex-1 min-h-0">
          {!hasRange && (
            <p className="text-[10px] text-[var(--text-subtle)] leading-snug">
              Set a start and end date to preview {rangeGroupLabel} periods in your range.
            </p>
          )}
          {hasRange && periodsInRange.length === 0 && (
            <p className="text-[10px] text-amber-800 leading-snug">
              No {rangeGroupLabel} periods fall in this range with your uploaded data.
            </p>
          )}
          {hasRange && periodsInRange.length > 0 && (
            <>
              <p className="text-[10px] text-[var(--text-subtle)] leading-snug mb-1">
                {periodsInRange.length} {rangeGroupLabel} period{periodsInRange.length === 1 ? '' : 's'} in{' '}
                {formatCompactDateRange(rangeStart, rangeEnd)}
              </p>
              {periodsInRange.map((period, i) => (
                <PeriodPreviewRow
                  key={period.id}
                  label={period.label || `${rangeGroupLabel} ${i + 1}`}
                  detail={formatCompactDateRange(period.start, period.end)}
                />
              ))}
            </>
          )}
        </div>
      )}

      {visibleTab === 'yoy' && isCustomMode && (
        <div className="flex flex-col gap-1 max-h-[min(320px,42vh)] overflow-y-auto pr-0.5 flex-1 min-h-0">
          {yoyPresets.length === 0 && (
            <p className="text-[10px] text-[var(--text-subtle)] leading-snug">No YoY presets in uploaded data.</p>
          )}
          {yoyPresets.map((preset) => {
            const active = preset.id === activeCompare?.preset?.id;
            return (
              <PresetButton
                key={preset.id}
                active={active}
                label={preset.label}
                detail={`Pre ${formatCompactDateRange(preset.preStart, preset.preEnd)} · Post ${formatCompactDateRange(preset.postStart, preset.postEnd)}`}
                onClick={() => onSelectComparePreset(preset)}
              />
            );
          })}
        </div>
      )}

      {visibleTab === 'custom' && isCustomMode && (
        <p className="text-[10px] text-[var(--text-subtle)] border-t border-[var(--border)] pt-2 leading-snug">
          {preStart && postStart
            ? 'Custom Pre vs Post — edit dates on the right.'
            : 'Set Pre and Post date ranges on the right.'}
        </p>
      )}
    </aside>
  );
}
