import { useState, useMemo, useEffect } from 'react';
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
} from '../../lib/utils/uploadedDataBounds';
import { parseDate, formatDateShort, dateToKey, parseSlashDateRange, formatSlashDateRange } from '../../lib/utils/dateUtils';
import { buildDdPlatformData, buildUePlatformData } from '../../lib/engine/periodEngine';
import { addDerivedMetrics, buildSummaryTables, buildCombinedStoreTables } from '../../lib/engine/metrics';
import { buildDdStoreCatalog, buildUeStoreCatalog, buildSuggestedMapRows, mapRowsToStoreMap, mapRowsToTagMap } from '../../lib/utils/storeCatalog';
import StoreMapEditor from '../../components/config/StoreMapEditor';
import OperatorSelect from '../../components/config/OperatorSelect';
import PlatformLogo from '../../components/ui/PlatformLogo';

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
  const ddPreStart = useConfigStore((s) => s.ddPreStart);
  const uePreStart = useConfigStore((s) => s.uePreStart);
  const syncDates = useConfigStore((s) => s.syncDates);
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

  useEffect(() => {
    if (!hasDdPeriods || ddPreStart || !ddRange.min || !ddRange.max) return;
    const suggested = suggestPrePostFromBounds(ddRange);
    if (!suggested) return;
    setDdDates(
      suggested.preStart,
      suggested.preEnd,
      suggested.postStart,
      suggested.postEnd,
    );
  }, [hasDdPeriods, ddRange, ddPreStart, setDdDates]);

  useEffect(() => {
    if (!ueOnly || uePreStart || !ueRange.min || !ueRange.max) return;
    const suggested = suggestPrePostFromBounds(ueRange);
    if (!suggested) return;
    setUeDates(
      suggested.preStart,
      suggested.preEnd,
      suggested.postStart,
      suggested.postEnd,
    );
  }, [ueOnly, ueRange, uePreStart, setUeDates]);

  const canRunFullAnalysis = hasDd || hasUe;
  const canAnalyze = config.isConfigured()
    && !!config.operatorName?.trim()
    && canRunFullAnalysis
    && !dataStore.isProcessing;

  const handleAnalyze = () => {
    setAnalyzeError('');
    if (!config.isConfigured()) {
      setAnalyzeError('Set Pre and Post date ranges for at least one platform.');
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
      config.setDdToUeStoreMap(storeMap);
      config.setStoreTagMap(tagMap);

      const ddConfig = {
        preStart: config.ddPreStart, preEnd: config.ddPreEnd,
        postStart: config.ddPostStart, postEnd: config.ddPostEnd,
        excludedDates: config.ddExcludedDates,
        excludedStores: config.ddExcludedStores,
      };
      const ueConfig = {
        preStart: config.uePreStart, preEnd: config.uePreEnd,
        postStart: config.uePostStart, postEnd: config.uePostEnd,
        excludedDates: config.ueExcludedDates,
        excludedStores: config.ueExcludedStores,
      };

      let ddStore = [];
      let ueStore = [];

      if (hasDd && ddConfig.preStart) {
        ddStore = buildDdPlatformData(dataStore.ddFinancial, ddConfig);
        ddStore = addDerivedMetrics(ddStore);
      }

      if (hasUe && ueConfig.preStart) {
        ueStore = buildUePlatformData(dataStore.ueFinancial, ueConfig);
        ueStore = addDerivedMetrics(ueStore);
      }

      const combined = buildCombinedStoreTables(ddStore, ueStore, storeMap);
      const summaries = buildSummaryTables(ddStore, ueStore);

      dataStore.setStoreTables({ dd: ddStore, ue: ueStore, combined });
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
                  <PeriodRangePair
                    key={`combined-${config.ddPreStart || config.uePreStart || ''}-${config.ddPreEnd || config.uePreEnd || ''}-${config.ddPostStart || config.uePostStart || ''}-${config.ddPostEnd || config.uePostEnd || ''}`}
                    preStart={hasDdPeriods ? config.ddPreStart : config.uePreStart}
                    preEnd={hasDdPeriods ? config.ddPreEnd : config.uePreEnd}
                    postStart={hasDdPeriods ? config.ddPostStart : config.uePostStart}
                    postEnd={hasDdPeriods ? config.ddPostEnd : config.uePostEnd}
                    onApply={hasDdPeriods ? config.setDdDates : setUeDates}
                  />
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
                  <PeriodRangePair
                    key={`dd-${config.ddPreStart || ''}-${config.ddPreEnd || ''}-${config.ddPostStart || ''}-${config.ddPostEnd || ''}`}
                    preStart={config.ddPreStart}
                    preEnd={config.ddPreEnd}
                    postStart={config.ddPostStart}
                    postEnd={config.ddPostEnd}
                    onApply={config.setDdDates}
                  />
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
                  <PeriodRangePair
                    key={`ue-${config.uePreStart || ''}-${config.uePreEnd || ''}-${config.uePostStart || ''}-${config.uePostEnd || ''}`}
                    preStart={config.uePreStart}
                    preEnd={config.uePreEnd}
                    postStart={config.uePostStart}
                    postEnd={config.uePostEnd}
                    onApply={setUeDates}
                  />
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
              setRows={setEditedMapRows}
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
