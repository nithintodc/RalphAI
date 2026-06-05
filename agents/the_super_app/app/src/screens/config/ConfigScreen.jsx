import { useState, useMemo, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import { getUniqueStores as getDdStores } from '../../lib/parsers/ddFinancial';
import { getUniqueStores as getUeStores, getDateRange as getUeRange } from '../../lib/parsers/ueFinancial';
import {
  getDdUploadedDateRange,
  getDdSalesStoreIds,
  hasAnyDdSales,
  suggestPrePostFromBounds,
  suggestSinglePeriodFromBounds,
} from '../../lib/utils/uploadedDataBounds';
import { isSinglePeriodMode } from '../../lib/utils/periodMode';
import { parseDate, formatDateShort, dateToKey, parseSlashDateRange, formatSlashDateRange } from '../../lib/utils/dateUtils';
import { buildDdPlatformData, buildUePlatformData } from '../../lib/engine/periodEngine';
import { addDerivedMetrics, buildSummaryTables, buildCombinedStoreTables } from '../../lib/engine/metrics';
import { buildDdStoreCatalog, buildUeStoreCatalog, buildSuggestedMapRows, mapRowsToStoreMap, mapRowsToTagMap } from '../../lib/utils/storeCatalog';
import { buildAnalysisScope, applyStoreTableScope, buildScopedExcludedStores, getIncludedStoreIdsFromMapRows } from '../../lib/utils/abStoreFilter';
import StoreMapEditor from '../../components/config/StoreMapEditor';
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
  const dataStore = useDataStore();
  const { setScreen } = useUiStore();
  const [analyzeError, setAnalyzeError] = useState('');

  const hasDdFinancial = !!dataStore.ddFinancial?.length;
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
  const ueRange = useMemo(() => dataStore.ueFinancial ? getUeRange(dataStore.ueFinancial) : {}, [dataStore.ueFinancial]);

  const hasDd = hasDdFinancial;
  const hasUeFinancial = !!dataStore.ueFinancial?.length;
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
    if (ddPreStart) return;
    const suggested = suggestPrePostFromBounds(ddRange);
    if (!suggested) return;
    setDdDates(
      suggested.preStart,
      suggested.preEnd,
      suggested.postStart,
      suggested.postEnd,
    );
  }, [hasDdPeriods, ddRange, ddPreStart, ddPostStart, isSinglePeriod, setDdDates, setDateAnalysisMode]);

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
    if (uePreStart) return;
    const suggested = suggestPrePostFromBounds(ueRange);
    if (!suggested) return;
    setUeDates(
      suggested.preStart,
      suggested.preEnd,
      suggested.postStart,
      suggested.postEnd,
    );
  }, [ueOnly, ueRange, uePreStart, uePostStart, isSinglePeriod, setUeDates, setDateAnalysisMode]);

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

      const ddConfig = {
        preStart: isSinglePeriod ? config.ddPostStart : config.ddPreStart,
        preEnd: isSinglePeriod ? config.ddPostEnd : config.ddPreEnd,
        postStart: config.ddPostStart,
        postEnd: config.ddPostEnd,
        excludedDates: config.ddExcludedDates,
        excludedStores: ddExcludedStores,
      };
      const ueConfig = {
        preStart: isSinglePeriod ? config.uePostStart : config.uePreStart,
        preEnd: isSinglePeriod ? config.uePostEnd : config.uePreEnd,
        postStart: config.uePostStart,
        postEnd: config.uePostEnd,
        excludedDates: config.ueExcludedDates,
        excludedStores: ueExcludedStores,
      };

      let ddStore = [];
      let ueStore = [];

      const ddReady = isSinglePeriod ? ddConfig.postStart : ddConfig.preStart;
      const ueReady = isSinglePeriod ? ueConfig.postStart : ueConfig.preStart;

      if (hasDd && ddReady) {
        ddStore = buildDdPlatformData(dataStore.ddFinancial, ddConfig);
        ddStore = addDerivedMetrics(ddStore);
      }

      if (hasUe && ueReady) {
        ueStore = buildUePlatformData(dataStore.ueFinancial, ueConfig);
        ueStore = addDerivedMetrics(ueStore);
      }

      let combined = buildCombinedStoreTables(ddStore, ueStore, storeMap);
      let storeTables = { dd: ddStore, ue: ueStore, combined };
      storeTables = applyStoreTableScope(storeTables, scope);
      const summaries = buildSummaryTables(storeTables.dd, storeTables.ue);

      dataStore.setStoreTables(storeTables);
      dataStore.setSummaryTables(summaries);
      dataStore.setProcessing(false);
      setScreen('dashboard');
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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
          <div className="card min-w-0">
            <h3 className="font-semibold text-[var(--text)] mb-3">Operator</h3>
            <OperatorSelect required />
            <div className="mt-4 pt-4 border-t border-[var(--border)]">
              <label htmlFor="account-manager" className="block text-xs text-[var(--text-muted)] mb-1.5">
                Account Manager
              </label>
              <input
                id="account-manager"
                type="text"
                value={config.accountManager}
                onChange={(e) => config.setAccountManager(e.target.value)}
                placeholder="Name shown on partnership reports"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
          </div>

          <div className="card min-w-0">
            <div className="flex flex-col gap-3 mb-4">
              <h3 className="font-semibold text-[var(--text)]">Analysis Periods</h3>
              <div className="space-y-2">
                <label className="text-xs font-medium text-[var(--text-muted)]">Analysis mode</label>
                <PeriodKindToggle kind={periodKind} onChange={switchPeriodKind} />
                <p className="text-[10px] text-[var(--text-subtle)] leading-snug">
                  {isSinglePeriod
                    ? 'Single block of dates — Register and Post tables only (no Pre comparison).'
                    : 'Compare two windows — Pre vs Post deltas across the dashboard.'}
                </p>
              </div>
              <SyncToggle
                synced={config.syncDates}
                onToggle={() => config.setSyncDates(!config.syncDates)}
                label="Same dates for all platforms"
              />
            </div>

            {!hasDdPeriods && !hasUePeriods && (
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Upload DoorDash financial/sales or Uber Eats financial CSV to set analysis periods.
              </p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {showCombinedPeriodEditor && (
                <div className="p-4 rounded-lg bg-[var(--surface-2)] min-w-0 md:col-span-2">
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
                  ) : (
                    <PeriodRangePair
                      key={`combined-${config.ddPreStart || config.uePreStart || ''}-${config.ddPreEnd || config.uePreEnd || ''}-${config.ddPostStart || config.uePostStart || ''}-${config.ddPostEnd || config.uePostEnd || ''}`}
                      preStart={hasDdPeriods ? config.ddPreStart : config.uePreStart}
                      preEnd={hasDdPeriods ? config.ddPreEnd : config.uePreEnd}
                      postStart={hasDdPeriods ? config.ddPostStart : config.uePostStart}
                      postEnd={hasDdPeriods ? config.ddPostEnd : config.uePostEnd}
                      onApply={hasDdPeriods ? config.setDdDates : setUeDates}
                    />
                  )}
                </div>
              )}

              {showDdPeriodEditor && (
                <div className="p-4 rounded-lg bg-[var(--surface-2)] min-w-0">
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
                  ) : (
                    <PeriodRangePair
                      key={`dd-${config.ddPreStart || ''}-${config.ddPreEnd || ''}-${config.ddPostStart || ''}-${config.ddPostEnd || ''}`}
                      preStart={config.ddPreStart}
                      preEnd={config.ddPreEnd}
                      postStart={config.ddPostStart}
                      postEnd={config.ddPostEnd}
                      onApply={config.setDdDates}
                    />
                  )}
                </div>
              )}

              {showUePeriodEditor && (
                <div className="p-4 rounded-lg bg-[var(--surface-2)] min-w-0">
                  <div className="flex flex-col gap-1 mb-3">
                    <div className="flex items-center gap-2">
                      <PlatformLogo platform="ue" size={18} />
                      <span className="text-sm font-medium text-[var(--text)]">Uber Eats</span>
                    </div>
                    {ueRange.min && (
                      <span className="text-[10px] text-[var(--text-subtle)]">
                        Data: {formatDateShort(ueRange.min)} — {formatDateShort(ueRange.max)}
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
                  ) : (
                    <PeriodRangePair
                      key={`ue-${config.uePreStart || ''}-${config.uePreEnd || ''}-${config.uePostStart || ''}-${config.uePostEnd || ''}`}
                      preStart={config.uePreStart}
                      preEnd={config.uePreEnd}
                      postStart={config.uePostStart}
                      postEnd={config.uePostEnd}
                      onApply={setUeDates}
                    />
                  )}
                </div>
              )}

              {hasUePeriods && !ueRange.min && (
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 md:col-span-2">
                  Uber Eats file is in memory but no order dates were parsed. Use the standard UE financial CSV (header on row 2: Store Name, Order date, …).
                </p>
              )}
            </div>
          </div>
        </div>

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
