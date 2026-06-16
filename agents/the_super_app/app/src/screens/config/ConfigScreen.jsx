import { useState, useMemo, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import { getUniqueStores as getDdStores } from '../../lib/parsers/ddFinancial';
import { getUniqueStores as getUeStores, getDateRange as getUeRange, summarizeUeFinancialYears } from '../../lib/parsers/ueFinancial';
import {
  getDdUploadedDateRange,
  getDdSalesStoreIds,
  hasAnyDdSales,
  suggestPrePostFromBounds,
  suggestSinglePeriodFromBounds,
} from '../../lib/utils/uploadedDataBounds';
import { isSinglePeriodMode, isPresetRangeMode } from '../../lib/utils/periodMode';
import { parseDate, formatDateShort, dateToKey, parseSlashDateRange, formatSlashDateRange } from '../../lib/utils/dateUtils';
import { buildDdStoreCatalog, buildUeStoreCatalog, buildSuggestedMapRows, mapRowsToStoreMap, mapRowsToTagMap } from '../../lib/utils/storeCatalog';
import { buildAnalysisScope, buildScopedExcludedStores, getIncludedStoreIdsFromMapRows } from '../../lib/utils/abStoreFilter';
import { STORE_PERIOD_LABELS } from '../../lib/utils/storePeriodCounts';
import {
  buildStorePeriodAlignment,
  countActiveStoreIdsByPeriod,
  getActiveStoreIdsByPeriod,
} from '../../lib/utils/storePeriodAlignment';
import {
  mergeUploadedDataBounds,
  buildComparePeriodPresetGroups,
  buildSinglePeriodPresetGroups,
  buildPeriodsInAnalysisRange,
} from '../../lib/utils/analysisPeriodSelectors';
import { WEEK_DEFINITION_OPTIONS, resolveWeekStartsOn } from '../../lib/utils/weekDefinition';
import { runComparisonAnalysis } from '../../lib/engine/comparisonAnalysis';
import { resolveMarketingTables } from '../../lib/export/marketingExport';
import StoreComparisonNotice from '../../components/ui/StoreComparisonNotice';
import StoreMapEditor from '../../components/config/StoreMapEditor';
import PeriodPresetPanel from '../../components/config/PeriodPresetPanel';
import OperatorSelect from '../../components/config/OperatorSelect';
import PlatformLogo from '../../components/ui/PlatformLogo';

function PeriodKindToggle({ kind, onChange }) {
  return (
    <div className="flex gap-1 p-0.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] w-fit max-w-full">
      <button
        type="button"
        onClick={() => onChange('compare')}
        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer
          ${kind === 'compare'
            ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
            : 'text-[var(--text-muted)] hover:text-[var(--text)]'
          }`}
      >
        Pre vs Post
      </button>
      <button
        type="button"
        onClick={() => onChange('single')}
        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer
          ${kind === 'single'
            ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
            : 'text-[var(--text-muted)] hover:text-[var(--text)]'
          }`}
      >
        Single period
      </button>
    </div>
  );
}

function AnalysisRangeInput({ start, end, onApply, modeLabel = 'Analysis range' }) {
  const canon = formatSlashDateRange(start, end);
  const [input, setInput] = useState(canon);

  const getInclusiveDayCount = (range) => {
    if (!range?.start || !range?.end) return null;
    const s = Date.UTC(range.start.getFullYear(), range.start.getMonth(), range.start.getDate());
    const e = Date.UTC(range.end.getFullYear(), range.end.getMonth(), range.end.getDate());
    return Math.floor((e - s) / 86400000) + 1;
  };

  const parsed = parseSlashDateRange(input);
  const dayCount = getInclusiveDayCount(parsed);

  const commit = () => {
    const r = parseSlashDateRange(input);
    if (r) onApply(r.start, r.end);
    else setInput(canon);
  };

  return (
    <div className="flex flex-col gap-1 max-w-full">
      <label className="text-xs text-[var(--text-muted)]">{modeLabel}</label>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
        }}
        placeholder="1/1/2026-5/31/2026"
        className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
      />
      {dayCount != null && (
        <p className="text-[10px] text-[var(--text-subtle)]">{dayCount} day{dayCount === 1 ? '' : 's'} (inclusive)</p>
      )}
      <p className="text-[10px] text-[var(--text-subtle)] leading-snug">
        All weeks, months, or quarters in this range are included in the analysis — no separate Pre vs Post dates.
      </p>
    </div>
  );
}

function SinglePeriodRange({ start, end, onApply }) {
  const canon = formatSlashDateRange(start, end);
  const [input, setInput] = useState(canon);

  const getInclusiveDayCount = (range) => {
    if (!range?.start || !range?.end) return null;
    const s = Date.UTC(range.start.getFullYear(), range.start.getMonth(), range.start.getDate());
    const e = Date.UTC(range.end.getFullYear(), range.end.getMonth(), range.end.getDate());
    return Math.floor((e - s) / 86400000) + 1;
  };

  const parsed = parseSlashDateRange(input);
  const dayCount = getInclusiveDayCount(parsed);

  const commit = () => {
    const r = parseSlashDateRange(input);
    if (r) onApply(r.start, r.end);
    else setInput(canon);
  };

  return (
    <div className="flex flex-col gap-1 max-w-full">
      <label className="text-xs text-[var(--text-muted)]">Period</label>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
        }}
        placeholder="1/1/2026-3/31/2026"
        className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
      />
      {dayCount != null && (
        <p className="text-[10px] text-[var(--text-subtle)]">{dayCount} day{dayCount === 1 ? '' : 's'} (inclusive)</p>
      )}
      <p className="text-[10px] text-[var(--text-subtle)] leading-snug">
        One date block — no Pre vs Post comparison. Dashboard shows Register and Post-period tables only.
      </p>
    </div>
  );
}

function PeriodRangePair({ preStart, preEnd, postStart, postEnd, onApply }) {
  const preCanon = formatSlashDateRange(preStart, preEnd);
  const postCanon = formatSlashDateRange(postStart, postEnd);
  const [preInput, setPreInput] = useState(preCanon);
  const [postInput, setPostInput] = useState(postCanon);

  const getInclusiveDayCount = (range) => {
    if (!range?.start || !range?.end) return null;
    const s = Date.UTC(range.start.getFullYear(), range.start.getMonth(), range.start.getDate());
    const e = Date.UTC(range.end.getFullYear(), range.end.getMonth(), range.end.getDate());
    return Math.floor((e - s) / 86400000) + 1;
  };

  const preParsed = parseSlashDateRange(preInput);
  const postParsed = parseSlashDateRange(postInput);
  const preCount = getInclusiveDayCount(preParsed);
  const postCount = getInclusiveDayCount(postParsed);

  const commitPre = () => {
    const r = parseSlashDateRange(preInput);
    if (r) onApply(r.start, r.end, postStart, postEnd);
    else setPreInput(preCanon);
  };
  const commitPost = () => {
    const r = parseSlashDateRange(postInput);
    if (r) onApply(preStart, preEnd, r.start, r.end);
    else setPostInput(postCanon);
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-full">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-[var(--text-muted)]">Pre</label>
        <input
          type="text"
          value={preInput}
          onChange={(e) => setPreInput(e.target.value)}
          onBlur={commitPre}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitPre();
          }}
          placeholder="1/1/2026-1/31/2026"
          className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
        />
        {preCount != null && (
          <p className="text-[10px] text-[var(--text-subtle)]">{preCount} day{preCount === 1 ? '' : 's'} (inclusive)</p>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-[var(--text-muted)]">Post</label>
        <input
          type="text"
          value={postInput}
          onChange={(e) => setPostInput(e.target.value)}
          onBlur={commitPost}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitPost();
          }}
          placeholder="2/1/2026-2/28/2026"
          className="px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
        />
        {postCount != null && (
          <p className="text-[10px] text-[var(--text-subtle)]">{postCount} day{postCount === 1 ? '' : 's'} (inclusive)</p>
        )}
      </div>
    </div>
  );
}

function StorePeriodSummary({ label, platform, counts, alignment }) {
  if (!counts) return null;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 space-y-2 min-w-0">
      <div className="flex items-center gap-2 min-w-0">
        <PlatformLogo platform={platform} size={14} />
        <span className="text-xs font-medium text-[var(--text)] truncate">{label}</span>
      </div>
      <div className="grid grid-cols-4 gap-1.5">
        {Object.entries(STORE_PERIOD_LABELS).map(([key, periodLabel]) => (
          <div key={key} className="rounded-md bg-[var(--surface)] border border-[var(--border)] px-1.5 py-1 text-center min-w-0">
            <div className="text-[9px] uppercase tracking-wide text-[var(--text-subtle)] truncate">{periodLabel}</div>
            <div className="text-sm font-semibold tabular-nums text-[var(--text)]">{counts[key] ?? '—'}</div>
          </div>
        ))}
      </div>
      <StoreComparisonNotice platform={platform} alignment={alignment} compact />
    </div>
  );
}

function SyncToggle({ synced, onToggle, label }) {
  return (
    <label
      className={`inline-flex w-fit max-w-full items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer border
        ${synced ? 'bg-[var(--accent-soft)] text-[var(--accent-text)] border-[var(--accent-border)]' : 'bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--border)]'}`}
    >
      <input
        type="checkbox"
        checked={synced}
        onChange={onToggle}
        className="h-3.5 w-3.5 accent-[var(--accent)]"
      />
      {label}
    </label>
  );
}

function StoreIdExcludeSelect({ label, options, selected, onChange, selectPrompt }) {
  const available = options.filter(o => !selected.includes(o));

  return (
    <div className="space-y-2">
      <label className="text-xs text-[var(--text-muted)]">{label}</label>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map(s => (
            <span
              key={s}
              className="inline-flex items-center gap-1 max-w-full pl-2 pr-1 py-1 rounded-md border border-[var(--border)] bg-[var(--surface-2)] text-xs text-[var(--text)]"
            >
              <span className="truncate min-w-0" title={s}>{s}</span>
              <button
                type="button"
                onClick={() => onChange(selected.filter(x => x !== s))}
                className="shrink-0 inline-flex items-center justify-center rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--negative)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                aria-label={`Remove ${s} from exclusions`}
              >
                <X size={14} strokeWidth={2.25} />
              </button>
            </span>
          ))}
        </div>
      )}
      <select
        value=""
        onChange={(e) => {
          const v = e.target.value;
          if (v && !selected.includes(v)) onChange([...selected, v]);
          e.target.value = '';
        }}
        className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)] cursor-pointer"
        aria-label={selectPrompt}
      >
        <option value="">{selectPrompt}</option>
        {available.map(o => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

function DateExcluder({ label, dates, onChange }) {
  const [input, setInput] = useState('');

  const addDatesFromInput = () => {
    if (!input.trim()) return;
    const existingKeys = new Set(dates.map((d) => dateToKey(d)));
    const toAdd = [];
    for (const part of input.split(',')) {
      const parsed = parseDate(part.trim());
      if (!parsed) continue;
      const key = dateToKey(parsed);
      if (existingKeys.has(key)) continue;
      existingKeys.add(key);
      toAdd.push(parsed);
    }
    if (toAdd.length > 0) onChange([...dates, ...toAdd]);
    setInput('');
  };

  return (
    <div className="space-y-2">
      <label className="text-xs text-[var(--text-muted)]">{label}</label>
      {dates.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {dates.map((d, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 pl-2 pr-1 py-1 rounded-md border border-[var(--border)] bg-[var(--surface-2)] text-xs text-[var(--text)]"
            >
              <span>{formatDateShort(d)}</span>
              <button
                type="button"
                onClick={() => onChange(dates.filter((_, j) => j !== i))}
                className="shrink-0 inline-flex items-center justify-center rounded p-1 text-[var(--text-muted)] hover:bg-[var(--surface-3)] hover:text-[var(--warning)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                aria-label={`Remove excluded date ${formatDateShort(d)}`}
              >
                <X size={14} strokeWidth={2.25} />
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') addDatesFromInput();
        }}
        placeholder="YYYY-MM-DD, YYYY-MM-DD, ..."
        className="w-full px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
      />
    </div>
  );
}

export default function ConfigScreen() {
  const config = useConfigStore();
  const setDdDates = useConfigStore((s) => s.setDdDates);
  const setUeDates = useConfigStore((s) => s.setUeDates);
  const setDateAnalysisMode = useConfigStore((s) => s.setDateAnalysisMode);
  const dateAnalysisMode = useConfigStore((s) => s.dateAnalysisMode);
  const ddPreStart = useConfigStore((s) => s.ddPreStart);
  const ddPostStart = useConfigStore((s) => s.ddPostStart);
  const uePreStart = useConfigStore((s) => s.uePreStart);
  const uePostStart = useConfigStore((s) => s.uePostStart);
  const syncDates = useConfigStore((s) => s.syncDates);
  const [periodKind, setPeriodKind] = useState(
    () => (isSinglePeriodMode(dateAnalysisMode) ? 'single' : 'compare'),
  );
  const isSinglePeriod = periodKind === 'single';
  const isPresetRange = isPresetRangeMode(dateAnalysisMode);
  const showCustomPrePost = !isSinglePeriod && !isPresetRange;
  const dataStore = useDataStore();
  const { setScreen, setActiveTab } = useUiStore();
  const [analyzeError, setAnalyzeError] = useState('');

  const hasDdFinancial = !!dataStore.ddFinancial?.length;
  const hasUeFinancial = !!dataStore.ueFinancial?.length;
  const hasDdSales = useMemo(() => hasAnyDdSales(dataStore.ddSales), [dataStore.ddSales]);
  const hasDdPeriods = hasDdFinancial || hasDdSales;

  const ddStores = useMemo(() => {
    if (hasDdFinancial) return getDdStores(dataStore.ddFinancial);
    if (hasDdSales) return getDdSalesStoreIds(dataStore.ddSales);
    return [];
  }, [hasDdFinancial, hasDdSales, dataStore.ddFinancial, dataStore.ddSales]);

  const ueStores = useMemo(() => dataStore.ueFinancial ? getUeStores(dataStore.ueFinancial) : [], [dataStore.ueFinancial]);
  const ddRange = useMemo(
    () => getDdUploadedDateRange(dataStore.ddFinancial, dataStore.ddSales),
    [dataStore.ddFinancial, dataStore.ddSales],
  );
  const ueRange = useMemo(() => (dataStore.ueFinancial ? getUeRange(dataStore.ueFinancial) : {}), [dataStore.ueFinancial]);
  const ueYearSummary = useMemo(
    () => (dataStore.ueFinancial ? summarizeUeFinancialYears(dataStore.ueFinancial) : null),
    [dataStore.ueFinancial],
  );

  const ddStorePeriodCounts = useMemo(() => {
    if (isSinglePeriod || isPresetRange || !hasDdFinancial || !config.ddPreStart || !config.ddPreEnd || !config.ddPostStart || !config.ddPostEnd) {
      return null;
    }
    return countActiveStoreIdsByPeriod(dataStore.ddFinancial, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart: config.ddPostStart,
      postEnd: config.ddPostEnd,
      excludedDates: config.ddExcludedDates,
      excludedStores: config.ddExcludedStores,
    });
  }, [
    isSinglePeriod,
    isPresetRange,
    hasDdFinancial,
    dataStore.ddFinancial,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
    config.ddExcludedStores,
  ]);

  const ddAlignmentPreview = useMemo(() => {
    if (isSinglePeriod || isPresetRange || !hasDdFinancial || !config.ddPreStart) return null;
    const sets = getActiveStoreIdsByPeriod(dataStore.ddFinancial, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart: config.ddPostStart,
      postEnd: config.ddPostEnd,
      excludedDates: config.ddExcludedDates,
      excludedStores: config.ddExcludedStores,
    });
    return buildStorePeriodAlignment(sets);
  }, [
    isSinglePeriod,
    isPresetRange,
    hasDdFinancial,
    dataStore.ddFinancial,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
    config.ddExcludedStores,
  ]);

  const ueStorePeriodCounts = useMemo(() => {
    if (isSinglePeriod || isPresetRange || !hasUeFinancial) return null;
    const preStart = config.uePreStart || config.ddPreStart;
    const preEnd = config.uePreEnd || config.ddPreEnd;
    const postStart = config.uePostStart || config.ddPostStart;
    const postEnd = config.uePostEnd || config.ddPostEnd;
    if (!preStart || !preEnd || !postStart || !postEnd) return null;
    return countActiveStoreIdsByPeriod(dataStore.ueFinancial, {
      preStart,
      preEnd,
      postStart,
      postEnd,
      excludedDates: config.ueExcludedDates,
      excludedStores: config.ueExcludedStores,
    }, { salesField: 'sales', orderField: 'orderId' });
  }, [
    isSinglePeriod,
    isPresetRange,
    hasUeFinancial,
    dataStore.ueFinancial,
    config.uePreStart,
    config.uePreEnd,
    config.uePostStart,
    config.uePostEnd,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ueExcludedDates,
    config.ueExcludedStores,
  ]);

  const ueAlignmentPreview = useMemo(() => {
    if (isSinglePeriod || isPresetRange || !hasUeFinancial) return null;
    const preStart = config.uePreStart || config.ddPreStart;
    const preEnd = config.uePreEnd || config.ddPreEnd;
    const postStart = config.uePostStart || config.ddPostStart;
    const postEnd = config.uePostEnd || config.ddPostEnd;
    if (!preStart || !preEnd || !postStart || !postEnd) return null;
    const sets = getActiveStoreIdsByPeriod(dataStore.ueFinancial, {
      preStart,
      preEnd,
      postStart,
      postEnd,
      excludedDates: config.ueExcludedDates,
      excludedStores: config.ueExcludedStores,
    }, { salesField: 'sales', orderField: 'orderId' });
    return buildStorePeriodAlignment(sets);
  }, [
    isSinglePeriod,
    isPresetRange,
    hasUeFinancial,
    dataStore.ueFinancial,
    config.uePreStart,
    config.uePreEnd,
    config.uePostStart,
    config.uePostEnd,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ueExcludedDates,
    config.ueExcludedStores,
  ]);

  useEffect(() => {
    if (isSinglePeriod) return;
    if (ddStorePeriodCounts) {
      console.log('[Store IDs] DoorDash financial');
      console.table({
        Pre: ddStorePeriodCounts.pre,
        Post: ddStorePeriodCounts.post,
        'LY Pre': ddStorePeriodCounts.preLY,
        'LY Post': ddStorePeriodCounts.postLY,
      });
    }
    if (ueStorePeriodCounts) {
      console.log('[Store IDs] Uber Eats financial');
      console.table({
        Pre: ueStorePeriodCounts.pre,
        Post: ueStorePeriodCounts.post,
        'LY Pre': ueStorePeriodCounts.preLY,
        'LY Post': ueStorePeriodCounts.postLY,
      });
    }
  }, [isSinglePeriod, ddStorePeriodCounts, ueStorePeriodCounts]);

  const hasDd = hasDdFinancial;
  const hasUe = hasUeFinancial;
  const hasUePeriods = hasUeFinancial;
  const ueOnly = hasUePeriods && !hasDdPeriods;
  const showCombinedPeriodEditor = syncDates && (hasDdPeriods || hasUePeriods);
  const showDdPeriodEditor = !syncDates && hasDdPeriods;
  const showUePeriodEditor = !syncDates && hasUePeriods;

  const ddCatalog = useMemo(() => buildDdStoreCatalog(dataStore.ddFinancial), [dataStore.ddFinancial]);
  const ueCatalog = useMemo(() => buildUeStoreCatalog(dataStore.ueFinancial), [dataStore.ueFinancial]);

  const suggestedMapRows = useMemo(() => {
    if (!ddCatalog.length) return [];
    return buildSuggestedMapRows(ddCatalog, ueCatalog, config.ddToUeStoreMap || {}, config.storeTagMap || {});
  }, [ddCatalog, ueCatalog, config.ddToUeStoreMap, config.storeTagMap]);
  const [editedMapRows, setEditedMapRows] = useState(null);
  const mapRows = editedMapRows ?? suggestedMapRows;

  const setMapRows = useCallback((next) => {
    setEditedMapRows((prev) => {
      const base = prev ?? suggestedMapRows;
      return typeof next === 'function' ? next(base) : next;
    });
  }, [suggestedMapRows]);

  useEffect(() => {
    setEditedMapRows(null);
  }, [ddCatalog, ueCatalog]);

  const applySinglePeriod = (setter) => (start, end) => {
    setter(start, end, start, end);
    setDateAnalysisMode('singleRange');
  };

  const mergedBounds = useMemo(
    () => mergeUploadedDataBounds(dataStore.ddFinancial, dataStore.ueFinancial, dataStore.ddSales),
    [dataStore.ddFinancial, dataStore.ueFinancial, dataStore.ddSales],
  );

  const weekStartsOn = resolveWeekStartsOn(config.weekDefinitionId);

  const comparePresetGroups = useMemo(
    () => buildComparePeriodPresetGroups(mergedBounds, { weekStartsOn }),
    [mergedBounds, weekStartsOn],
  );

  const singlePresetGroups = useMemo(
    () => buildSinglePeriodPresetGroups(mergedBounds),
    [mergedBounds],
  );

  const analysisRangeStart = hasDdPeriods ? config.ddPostStart : config.uePostStart;
  const analysisRangeEnd = hasDdPeriods ? config.ddPostEnd : config.uePostEnd;

  const periodsInRange = useMemo(() => {
    if (!isPresetRange || !analysisRangeStart || !analysisRangeEnd) return [];
    return buildPeriodsInAnalysisRange(
      dateAnalysisMode,
      analysisRangeStart,
      analysisRangeEnd,
      mergedBounds,
      weekStartsOn,
    );
  }, [isPresetRange, dateAnalysisMode, analysisRangeStart, analysisRangeEnd, mergedBounds, weekStartsOn]);

  const applyAnalysisRange = useCallback((setter) => (start, end) => {
    setter(null, null, start, end);
  }, []);

  const applyCustomCompareDates = useCallback((setter) => (preStart, preEnd, postStart, postEnd) => {
    setter(preStart, preEnd, postStart, postEnd);
    setDateAnalysisMode('pvp');
  }, [setDateAnalysisMode]);

  const applyCompareMode = useCallback((mode) => {
    setDateAnalysisMode(mode);
    if (isPresetRangeMode(mode)) {
      const rangeStart = analysisRangeStart;
      const rangeEnd = analysisRangeEnd;
      const setter = hasDdPeriods ? setDdDates : setUeDates;
      if (!rangeStart || !rangeEnd) {
        const bounds = hasDdPeriods ? ddRange : ueRange;
        const suggested = suggestSinglePeriodFromBounds(bounds);
        if (suggested) {
          setter(null, null, suggested.start, suggested.end);
        }
      } else {
        setter(null, null, rangeStart, rangeEnd);
      }
      if (mode === 'wow') {
        setActiveTab('wow');
      }
    }
  }, [
    setDateAnalysisMode,
    analysisRangeStart,
    analysisRangeEnd,
    hasDdPeriods,
    setDdDates,
    setUeDates,
    ddRange,
    ueRange,
    setActiveTab,
  ]);

  const applyComparePreset = useCallback((preset) => {
    const setter = hasDdPeriods ? setDdDates : setUeDates;
    setter(preset.preStart, preset.preEnd, preset.postStart, preset.postEnd);
    setDateAnalysisMode(preset.mode || 'pvp');
  }, [hasDdPeriods, setDdDates, setUeDates, setDateAnalysisMode]);

  const applySinglePreset = useCallback((preset) => {
    const setter = hasDdPeriods ? setDdDates : setUeDates;
    setter(preset.start, preset.end, preset.start, preset.end);
    setDateAnalysisMode(preset.mode);
  }, [hasDdPeriods, setDdDates, setUeDates, setDateAnalysisMode]);

  const presetPreStart = hasDdPeriods ? config.ddPreStart : config.uePreStart;
  const presetPreEnd = hasDdPeriods ? config.ddPreEnd : config.uePreEnd;
  const presetPostStart = hasDdPeriods ? config.ddPostStart : config.uePostStart;
  const presetPostEnd = hasDdPeriods ? config.ddPostEnd : config.uePostEnd;
  const presetSingleStart = hasDdPeriods ? config.ddPostStart : config.uePostStart;
  const presetSingleEnd = hasDdPeriods ? config.ddPostEnd : config.uePostEnd;

  const switchPeriodKind = (kind) => {
    setPeriodKind(kind);
    if (kind === 'single') {
      setDateAnalysisMode('singleRange');
      const postStart = hasDdPeriods ? config.ddPostStart : config.uePostStart;
      const postEnd = hasDdPeriods ? config.ddPostEnd : config.uePostEnd;
      if (postStart && postEnd) {
        if (hasDdPeriods) setDdDates(postStart, postEnd, postStart, postEnd);
        else setUeDates(postStart, postEnd, postStart, postEnd);
      }
    } else {
      setDateAnalysisMode('pvp');
    }
  };

  useEffect(() => {
    if (!hasDdPeriods || !ddRange.min || !ddRange.max) return;
    if (isSinglePeriod) {
      if (ddPostStart) return;
      const suggested = suggestSinglePeriodFromBounds(ddRange);
      if (!suggested) return;
      setDdDates(suggested.start, suggested.end, suggested.start, suggested.end);
      setDateAnalysisMode('singleRange');
      return;
    }
    if (isPresetRangeMode(dateAnalysisMode)) {
      if (ddPostStart) return;
      const suggested = suggestSinglePeriodFromBounds(ddRange);
      if (!suggested) return;
      setDdDates(null, null, suggested.start, suggested.end);
      return;
    }
    if (ddPreStart) return;
    const suggested = suggestPrePostFromBounds(ddRange);
    if (!suggested) return;
    setDdDates(
      suggested.preStart,
      suggested.preEnd,
      suggested.postStart,
      suggested.postEnd,
    );
  }, [hasDdPeriods, ddRange, ddPreStart, ddPostStart, isSinglePeriod, dateAnalysisMode, setDdDates, setDateAnalysisMode]);

  useEffect(() => {
    if (!ueOnly || !ueRange.min || !ueRange.max) return;
    if (isSinglePeriod) {
      if (uePostStart) return;
      const suggested = suggestSinglePeriodFromBounds(ueRange);
      if (!suggested) return;
      setUeDates(suggested.start, suggested.end, suggested.start, suggested.end);
      setDateAnalysisMode('singleRange');
      return;
    }
    if (isPresetRangeMode(dateAnalysisMode)) {
      if (uePostStart) return;
      const suggested = suggestSinglePeriodFromBounds(ueRange);
      if (!suggested) return;
      setUeDates(null, null, suggested.start, suggested.end);
      return;
    }
    if (uePreStart) return;
    const suggested = suggestPrePostFromBounds(ueRange);
    if (!suggested) return;
    setUeDates(
      suggested.preStart,
      suggested.preEnd,
      suggested.postStart,
      suggested.postEnd,
    );
  }, [ueOnly, ueRange, uePreStart, uePostStart, isSinglePeriod, dateAnalysisMode, setUeDates, setDateAnalysisMode]);

  const canRunFullAnalysis = hasDd || hasUe;
  const canAnalyze = config.isConfigured()
    && !!config.operatorName?.trim()
    && canRunFullAnalysis
    && !dataStore.isProcessing;

  const handleAnalyze = () => {
    setAnalyzeError('');
    if (!config.isConfigured()) {
      setAnalyzeError(
        isSinglePeriod
          ? 'Set a period date range for at least one platform.'
          : isPresetRange
            ? 'Set an analysis start and end date for at least one platform.'
            : 'Set Pre and Post date ranges for at least one platform.',
      );
      return;
    }
    if (!config.operatorName?.trim()) {
      setAnalyzeError('Select an operator before running analysis.');
      return;
    }
    dataStore.setProcessing(true);

    try {
      const storeMap = mapRowsToStoreMap(mapRows);
      const tagMap = mapRowsToTagMap(mapRows);
      const includedStoreIds = [...getIncludedStoreIdsFromMapRows(mapRows)];
      config.setDdToUeStoreMap(storeMap);
      config.setStoreTagMap(tagMap);
      config.setIncludedStoreIds(includedStoreIds);

      const scope = buildAnalysisScope({ ...config, storeTagMap: tagMap, ddToUeStoreMap: storeMap, includedStoreIds }, mapRows);
      const scopeDdExcluded = buildScopedExcludedStores(ddStores, 'dd', scope);
      const scopeUeExcluded = buildScopedExcludedStores(ueStores, 'ue', scope);
      const ddExcludedStores = [...new Set([...(config.ddExcludedStores || []), ...scopeDdExcluded])];
      const ueExcludedStores = [...new Set([...(config.ueExcludedStores || []), ...scopeUeExcluded])];

      const ddConfig = isPresetRange
        ? (() => {
          const rangeStart = config.ddPostStart;
          const rangeEnd = config.ddPostEnd;
          const periods = buildPeriodsInAnalysisRange(
            config.dateAnalysisMode,
            rangeStart,
            rangeEnd,
            mergedBounds,
            weekStartsOn,
          );
          const first = periods[0];
          return {
            preStart: first?.priorStart || first?.start || rangeStart,
            preEnd: first?.priorEnd || first?.end || rangeEnd,
            postStart: rangeStart,
            postEnd: rangeEnd,
            excludedDates: config.ddExcludedDates,
            excludedStores: ddExcludedStores,
          };
        })()
        : {
          preStart: isSinglePeriod ? config.ddPostStart : config.ddPreStart,
          preEnd: isSinglePeriod ? config.ddPostEnd : config.ddPreEnd,
          postStart: config.ddPostStart,
          postEnd: config.ddPostEnd,
          excludedDates: config.ddExcludedDates,
          excludedStores: ddExcludedStores,
        };
      const ueConfig = isPresetRange
        ? (() => {
          const rangeStart = config.uePostStart || config.ddPostStart;
          const rangeEnd = config.uePostEnd || config.ddPostEnd;
          const periods = buildPeriodsInAnalysisRange(
            config.dateAnalysisMode,
            rangeStart,
            rangeEnd,
            mergedBounds,
            weekStartsOn,
          );
          const first = periods[0];
          return {
            preStart: first?.priorStart || first?.start || rangeStart,
            preEnd: first?.priorEnd || first?.end || rangeEnd,
            postStart: rangeStart,
            postEnd: rangeEnd,
            excludedDates: config.ueExcludedDates,
            excludedStores: ueExcludedStores,
          };
        })()
        : {
          preStart: isSinglePeriod ? config.uePostStart : config.uePreStart,
          preEnd: isSinglePeriod ? config.uePostEnd : config.uePreEnd,
          postStart: config.uePostStart,
          postEnd: config.uePostEnd,
          excludedDates: config.ueExcludedDates,
          excludedStores: ueExcludedStores,
        };

      const ddReady = isSinglePeriod || isPresetRange ? ddConfig.postStart : ddConfig.preStart;
      const ueReady = isSinglePeriod || isPresetRange ? ueConfig.postStart : ueConfig.preStart;

      const { storeTables, summaries, storePeriodAlignment, crossPlatformAlignment } = runComparisonAnalysis({
        ddFinancial: dataStore.ddFinancial,
        ueFinancial: dataStore.ueFinancial,
        ddConfig,
        ueConfig,
        hasDd,
        hasUe,
        ddReady,
        ueReady,
        scope,
        storeMap,
        isSinglePeriod,
      });

      dataStore.setStoreTables(storeTables);
      dataStore.setSummaryTables(summaries);
      dataStore.setStorePeriodAlignment(storePeriodAlignment);
      dataStore.setCrossPlatformAlignment(crossPlatformAlignment);

      const marketingTables = resolveMarketingTables(
        {
          ddFinancial: dataStore.ddFinancial,
          ddMarketing: dataStore.ddMarketing,
          marketingTables: dataStore.marketingTables,
        },
        {
          ...config,
          storeTagMap: tagMap,
          ddToUeStoreMap: storeMap,
          includedStoreIds,
          ddPreStart: ddConfig.preStart,
          ddPreEnd: ddConfig.preEnd,
          ddPostStart: ddConfig.postStart,
          ddPostEnd: ddConfig.postEnd,
          ddExcludedDates: ddConfig.excludedDates,
        },
      );
      if (marketingTables) {
        dataStore.setMarketingTables(marketingTables);
      }

      dataStore.setProcessing(false);
      setScreen('dashboard');
      if (config.dateAnalysisMode === 'wow') {
        setActiveTab('wow');
      }
    } catch (err) {
      console.error('Analysis error:', err);
      setAnalyzeError(err?.message || String(err) || 'Analysis failed. Check the browser console for details.');
      dataStore.setProcessing(false);
    }
  };

  return (
    <div className="standalone-screen bg-[var(--bg)]">
      <div className="standalone-screen-body p-4 sm:p-6">
      <div className="w-full max-w-[96rem] mx-auto space-y-5 min-w-0">
        <div className="mb-2">
          <h1 className="text-xl font-bold text-[var(--text)]">Configure Analysis</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Select operator, set date ranges, and exclusions</p>
        </div>

        <div className="card min-w-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
            <OperatorSelect required compact />
            <div className="space-y-2">
              <label htmlFor="account-manager" className="block text-xs text-[var(--text-muted)]">
                Account Manager
              </label>
              <input
                id="account-manager"
                type="text"
                value={config.accountManager}
                onChange={(e) => config.setAccountManager(e.target.value)}
                placeholder="Name on reports"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
          </div>
          <p className="text-[11px] text-[var(--text-subtle)] leading-relaxed mt-3 pt-3 border-t border-[var(--border)]">
            Pick an operator from Airtable or choose <strong>Other</strong> to type a custom name. Reporting and the store map use this operator.
          </p>
        </div>

        <div className="card min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
            <div className="min-w-0">
              <h3 className="font-semibold text-[var(--text)]">Analysis Periods</h3>
              <p className="text-[10px] text-[var(--text-subtle)] mt-1 leading-snug">
                {isSinglePeriod
                  ? 'Single date block — no Pre comparison.'
                  : isPresetRange
                    ? 'WoW, MoM, or QoQ: one start–end range. Pre vs Post is for Custom and YoY only.'
                    : 'Custom Pre vs Post, or pick a YoY preset from your uploaded data.'}
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:items-end shrink-0">
              <PeriodKindToggle kind={periodKind} onChange={switchPeriodKind} />
              <SyncToggle
                synced={config.syncDates}
                onToggle={() => config.setSyncDates(!config.syncDates)}
                label="Same dates for all platforms"
              />
              {dateAnalysisMode === 'wow' && (
              <label className="flex flex-col gap-1 w-full sm:w-auto sm:min-w-[160px]">
                <span className="text-[10px] font-medium text-[var(--text-subtle)]">Business week</span>
                <select
                  value={config.weekDefinitionId || 'mon-sun'}
                  onChange={(e) => config.setWeekDefinitionId(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] cursor-pointer focus:outline-none focus:border-[var(--accent)]"
                >
                  {WEEK_DEFINITION_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>{opt.label}</option>
                  ))}
                </select>
              </label>
              )}
            </div>
          </div>

          {!hasDdPeriods && !hasUePeriods && (
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              Upload DoorDash financial/sales or Uber Eats financial CSV to set analysis periods.
            </p>
          )}

          {(hasDdPeriods || hasUePeriods) && (
            <div className="grid grid-cols-1 lg:grid-cols-[min(260px,32%)_minmax(0,1fr)] gap-4 items-start">
              <PeriodPresetPanel
                isSinglePeriod={isSinglePeriod}
                dateAnalysisMode={dateAnalysisMode}
                compareGroups={comparePresetGroups}
                singleGroups={singlePresetGroups}
                periodsInRange={periodsInRange}
                rangeStart={analysisRangeStart}
                rangeEnd={analysisRangeEnd}
                preStart={presetPreStart}
                preEnd={presetPreEnd}
                postStart={presetPostStart}
                postEnd={presetPostEnd}
                singleStart={presetSingleStart}
                singleEnd={presetSingleEnd}
                onSelectCompareMode={applyCompareMode}
                onSelectComparePreset={applyComparePreset}
                onSelectSinglePreset={applySinglePreset}
              />

              <div className="min-w-0 space-y-4">
              {showCombinedPeriodEditor && (
                <div className="p-4 rounded-lg bg-[var(--surface-2)] min-w-0 border border-[var(--border)]">
                  <div className="flex flex-col gap-1 mb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {hasDdPeriods && <PlatformLogo platform="dd" size={18} />}
                      {hasUePeriods && <PlatformLogo platform="ue" size={18} />}
                      <span className="text-sm font-medium text-[var(--text)]">
                        {hasDdPeriods && hasUePeriods
                          ? 'DoorDash & Uber Eats'
                          : hasDdPeriods
                            ? 'All platforms (DoorDash data)'
                            : 'All platforms (Uber Eats data)'}
                      </span>
                    </div>
                    <div className="flex flex-col gap-0.5 text-[10px] text-[var(--text-subtle)]">
                      {hasDdPeriods && ddRange.min && (
                        <span>
                          DoorDash data: {formatDateShort(ddRange.min)} — {formatDateShort(ddRange.max)}
                          {hasDdSales && !hasDdFinancial ? ' · from sales export' : ''}
                        </span>
                      )}
                      {hasUePeriods && ueRange.min && (
                        <span>
                          Uber Eats data: {formatDateShort(ueRange.min)} — {formatDateShort(ueRange.max)}
                        </span>
                      )}
                    </div>
                  </div>
                  {hasDdSales && !hasDdFinancial && (
                    <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 mb-3">
                      Sales ZIP only — date ranges come from your sales file. Upload <strong>Financial</strong> to run full analysis (Overview, Register, Buckets, etc.).
                    </p>
                  )}
                  {isSinglePeriod ? (
                    <SinglePeriodRange
                      key={`combined-single-${config.ddPostStart || config.uePostStart || ''}-${config.ddPostEnd || config.uePostEnd || ''}`}
                      start={hasDdPeriods ? config.ddPostStart : config.uePostStart}
                      end={hasDdPeriods ? config.ddPostEnd : config.uePostEnd}
                      onApply={hasDdPeriods ? applySinglePeriod(config.setDdDates) : applySinglePeriod(setUeDates)}
                    />
                  ) : isPresetRange ? (
                    <AnalysisRangeInput
                      key={`combined-range-${config.ddPostStart || config.uePostStart || ''}-${config.ddPostEnd || config.uePostEnd || ''}-${dateAnalysisMode}`}
                      start={hasDdPeriods ? config.ddPostStart : config.uePostStart}
                      end={hasDdPeriods ? config.ddPostEnd : config.uePostEnd}
                      modeLabel={dateAnalysisMode === 'wow' ? 'Analysis range (WoW)' : dateAnalysisMode === 'mom' ? 'Analysis range (MoM)' : 'Analysis range (QoQ)'}
                      onApply={hasDdPeriods ? applyAnalysisRange(config.setDdDates) : applyAnalysisRange(setUeDates)}
                    />
                  ) : showCustomPrePost ? (
                    <PeriodRangePair
                      key={`combined-${config.ddPreStart || config.uePreStart || ''}-${config.ddPreEnd || config.uePreEnd || ''}-${config.ddPostStart || config.uePostStart || ''}-${config.ddPostEnd || config.uePostEnd || ''}`}
                      preStart={hasDdPeriods ? config.ddPreStart : config.uePreStart}
                      preEnd={hasDdPeriods ? config.ddPreEnd : config.uePreEnd}
                      postStart={hasDdPeriods ? config.ddPostStart : config.uePostStart}
                      postEnd={hasDdPeriods ? config.ddPostEnd : config.uePostEnd}
                      onApply={
                        hasDdPeriods
                          ? applyCustomCompareDates(config.setDdDates)
                          : applyCustomCompareDates(setUeDates)
                      }
                    />
                  ) : null}
                </div>
              )}

              {(showDdPeriodEditor || showUePeriodEditor) && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {showDdPeriodEditor && (
                <div className="p-4 rounded-lg bg-[var(--surface-2)] min-w-0 border border-[var(--border)]">
                  <div className="flex flex-col gap-1 mb-3">
                    <div className="flex items-center gap-2">
                      <PlatformLogo platform="dd" size={18} />
                      <span className="text-sm font-medium text-[var(--text)]">DoorDash</span>
                    </div>
                    {ddRange.min && (
                      <span className="text-[10px] text-[var(--text-subtle)]">
                        Data: {formatDateShort(ddRange.min)} — {formatDateShort(ddRange.max)}
                        {hasDdSales && !hasDdFinancial ? ' · from sales export' : ''}
                      </span>
                    )}
                  </div>
                  {hasDdSales && !hasDdFinancial && (
                    <p className="text-[10px] text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 mb-3">
                      Sales ZIP only — date ranges come from your sales file. Upload <strong>Financial</strong> to run full analysis (Overview, Register, Buckets, etc.).
                    </p>
                  )}
                  {isSinglePeriod ? (
                    <SinglePeriodRange
                      key={`dd-single-${config.ddPostStart || ''}-${config.ddPostEnd || ''}`}
                      start={config.ddPostStart}
                      end={config.ddPostEnd}
                      onApply={applySinglePeriod(config.setDdDates)}
                    />
                  ) : isPresetRange ? (
                    <AnalysisRangeInput
                      key={`dd-range-${config.ddPostStart || ''}-${config.ddPostEnd || ''}-${dateAnalysisMode}`}
                      start={config.ddPostStart}
                      end={config.ddPostEnd}
                      modeLabel={dateAnalysisMode === 'wow' ? 'Analysis range (WoW)' : dateAnalysisMode === 'mom' ? 'Analysis range (MoM)' : 'Analysis range (QoQ)'}
                      onApply={applyAnalysisRange(config.setDdDates)}
                    />
                  ) : showCustomPrePost ? (
                    <PeriodRangePair
                      key={`dd-${config.ddPreStart || ''}-${config.ddPreEnd || ''}-${config.ddPostStart || ''}-${config.ddPostEnd || ''}`}
                      preStart={config.ddPreStart}
                      preEnd={config.ddPreEnd}
                      postStart={config.ddPostStart}
                      postEnd={config.ddPostEnd}
                      onApply={applyCustomCompareDates(config.setDdDates)}
                    />
                  ) : null}
                </div>
              )}

              {showUePeriodEditor && (
                <div className="p-4 rounded-lg bg-[var(--surface-2)] min-w-0 border border-[var(--border)]">
                  <div className="flex flex-col gap-1 mb-3">
                    <div className="flex items-center gap-2">
                      <PlatformLogo platform="ue" size={18} />
                      <span className="text-sm font-medium text-[var(--text)]">Uber Eats</span>
                    </div>
                    {ueRange.min && (
                      <span className="text-[10px] text-[var(--text-subtle)]">
                        Data: {formatDateShort(ueRange.min)} — {formatDateShort(ueRange.max)}
                        {ueYearSummary?.sortedYears?.length > 0 && (
                          <> · {ueYearSummary.sortedYears.map((y) => `${y}: ${ueYearSummary.years[y]?.toLocaleString()}`).join(', ')}</>
                        )}
                      </span>
                    )}
                  </div>
                  {isSinglePeriod ? (
                    <SinglePeriodRange
                      key={`ue-single-${config.uePostStart || ''}-${config.uePostEnd || ''}`}
                      start={config.uePostStart}
                      end={config.uePostEnd}
                      onApply={applySinglePeriod(setUeDates)}
                    />
                  ) : isPresetRange ? (
                    <AnalysisRangeInput
                      key={`ue-range-${config.uePostStart || ''}-${config.uePostEnd || ''}-${dateAnalysisMode}`}
                      start={config.uePostStart}
                      end={config.uePostEnd}
                      modeLabel={dateAnalysisMode === 'wow' ? 'Analysis range (WoW)' : dateAnalysisMode === 'mom' ? 'Analysis range (MoM)' : 'Analysis range (QoQ)'}
                      onApply={applyAnalysisRange(setUeDates)}
                    />
                  ) : showCustomPrePost ? (
                    <PeriodRangePair
                      key={`ue-${config.uePreStart || ''}-${config.uePreEnd || ''}-${config.uePostStart || ''}-${config.uePostEnd || ''}`}
                      preStart={config.uePreStart}
                      preEnd={config.uePreEnd}
                      postStart={config.uePostStart}
                      postEnd={config.uePostEnd}
                      onApply={applyCustomCompareDates(setUeDates)}
                    />
                  ) : null}
                </div>
              )}
                </div>
              )}

              {hasUePeriods && !ueRange.min && (
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  Uber Eats file is in memory but no order dates were parsed. Use the standard UE financial CSV (header on row 2: Store Name, Order date, …).
                </p>
              )}
              </div>
            </div>
          )}
        </div>

        {!isSinglePeriod && (ddStorePeriodCounts || ueStorePeriodCounts) && (
          <div className="card min-w-0">
            <div className="mb-3">
              <h3 className="font-semibold text-[var(--text)]">Store coverage</h3>
              <p className="text-[10px] text-[var(--text-subtle)] mt-1">
                Active stores per window. Comparisons use only stores with activity in both sides.
              </p>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {ddStorePeriodCounts && (
                <StorePeriodSummary
                  label="DoorDash"
                  platform="dd"
                  counts={ddStorePeriodCounts}
                  alignment={ddAlignmentPreview}
                />
              )}
              {ueStorePeriodCounts && (
                <StorePeriodSummary
                  label="Uber Eats"
                  platform="ue"
                  counts={ueStorePeriodCounts}
                  alignment={ueAlignmentPreview}
                />
              )}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
          <div className="card min-w-0">
          <div className="flex flex-col gap-3 mb-4">
            <h3 className="font-semibold text-[var(--text)]">Exclude Stores</h3>
            <SyncToggle
              synced={config.syncStoreExclusions}
              onToggle={() => config.setSyncStoreExclusions(!config.syncStoreExclusions)}
              label="Same for all platforms"
            />
          </div>
          <div className="space-y-4">
            {hasDdPeriods && (
              <StoreIdExcludeSelect
                label={`DoorDash (${ddStores.length} store IDs detected${hasDdSales && !hasDdFinancial ? ' · sales' : ''})`}
                options={ddStores}
                selected={config.ddExcludedStores}
                onChange={config.setDdExcludedStores}
                selectPrompt={ddStores.length ? 'Select a DoorDash store ID to exclude…' : 'No store IDs in file'}
              />
            )}
            {hasUePeriods && (ueOnly || !config.syncStoreExclusions) && (
              <StoreIdExcludeSelect
                label={`Uber Eats (${ueStores.length} store IDs detected)`}
                options={ueStores}
                selected={config.ueExcludedStores}
                onChange={config.setUeExcludedStores}
                selectPrompt={ueStores.length ? 'Select an UberEats store ID to exclude…' : 'No store IDs in file'}
              />
            )}
          </div>
        </div>

        <div className="card min-w-0">
          <div className="flex flex-col gap-3 mb-4">
            <h3 className="font-semibold text-[var(--text)]">Exclude Dates</h3>
            <SyncToggle
              synced={config.syncDateExclusions}
              onToggle={() => config.setSyncDateExclusions(!config.syncDateExclusions)}
              label="Same for all platforms"
            />
          </div>
          <div className="space-y-4">
            {hasDdPeriods && (
              <DateExcluder
                label="DoorDash"
                dates={config.ddExcludedDates}
                onChange={config.setDdExcludedDates}
              />
            )}
            {hasUePeriods && (ueOnly || !config.syncDateExclusions) && (
              <DateExcluder
                label="Uber Eats"
                dates={config.ueExcludedDates}
                onChange={config.setUeExcludedDates}
              />
            )}
          </div>
        </div>
        </div>

        {(analyzeError || (!config.operatorName?.trim() && config.isConfigured() && canRunFullAnalysis) || (config.isConfigured() && !canRunFullAnalysis && hasDdPeriods)) && (
          <div className="space-y-2">
            {analyzeError && (
              <p className="text-sm text-[var(--negative)] bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {analyzeError}
              </p>
            )}
            {!config.operatorName?.trim() && config.isConfigured() && canRunFullAnalysis && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Select an operator above — Analyze stays disabled until you do.
              </p>
            )}
            {config.isConfigured() && !canRunFullAnalysis && hasDdPeriods && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Periods are set from your sales upload. Upload <strong>Financial</strong> (DoorDash and/or Uber Eats) to enable Analyze.
              </p>
            )}
          </div>
        )}

        {hasDd && hasUe && (
          <div className="card min-w-0">
            <h3 className="font-semibold text-[var(--text)] mb-2">Combined: DD ↔ UE store map</h3>
            <StoreMapEditor
              ddFinancial={dataStore.ddFinancial}
              ueFinancial={dataStore.ueFinancial}
              rows={mapRows}
              setRows={setMapRows}
              operatorName={config.operatorName}
            />
          </div>
        )}
      </div>
      </div>

      <div className="standalone-screen-footer px-4 py-3">
        <div className="mx-auto flex w-full max-w-[96rem] items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setScreen('upload')}
            className="flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-sm text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
          >
            <ChevronLeft size={16} />
            Back
          </button>
          <button
            type="button"
            disabled={!canAnalyze}
            onClick={handleAnalyze}
            className={`flex shrink-0 items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold transition-all
              ${canAnalyze
                ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] cursor-pointer'
                : 'bg-[var(--surface-3)] text-[var(--text-subtle)] cursor-not-allowed'}`}
          >
            {dataStore.isProcessing ? 'Analyzing...' : 'Analyze'}
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
