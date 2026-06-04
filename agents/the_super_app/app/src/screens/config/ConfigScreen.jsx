import { useState, useMemo, useEffect } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import { getUniqueStores as getDdStores, getDateRange as getDdRange } from '../../lib/parsers/ddFinancial';
import { getUniqueStores as getUeStores, getDateRange as getUeRange } from '../../lib/parsers/ueFinancial';
import { parseDate, formatDateShort, dateToKey, parseSlashDateRange, formatSlashDateRange } from '../../lib/utils/dateUtils';
import { buildDdPlatformData, buildUePlatformData } from '../../lib/engine/periodEngine';
import { addDerivedMetrics, buildSummaryTables, buildCombinedStoreTables } from '../../lib/engine/metrics';
import { buildDdStoreCatalog, buildUeStoreCatalog, buildSuggestedMapRows, mapRowsToStoreMap, mapRowsToTagMap } from '../../lib/utils/storeCatalog';
import StoreMapEditor from '../../components/config/StoreMapEditor';

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

  useEffect(() => {
    setPreInput(preCanon);
  }, [preCanon]);
  useEffect(() => {
    setPostInput(postCanon);
  }, [postCanon]);

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
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer border
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
  const dataStore = useDataStore();
  const { setScreen } = useUiStore();

  const ddStores = useMemo(() => dataStore.ddFinancial ? getDdStores(dataStore.ddFinancial) : [], [dataStore.ddFinancial]);
  const ueStores = useMemo(() => dataStore.ueFinancial ? getUeStores(dataStore.ueFinancial) : [], [dataStore.ueFinancial]);
  const ddRange = useMemo(() => dataStore.ddFinancial ? getDdRange(dataStore.ddFinancial) : {}, [dataStore.ddFinancial]);
  const ueRange = useMemo(() => dataStore.ueFinancial ? getUeRange(dataStore.ueFinancial) : {}, [dataStore.ueFinancial]);

  const hasDd = !!dataStore.ddFinancial;
  const hasUe = !!dataStore.ueFinancial;

  const ddCatalog = useMemo(() => buildDdStoreCatalog(dataStore.ddFinancial), [dataStore.ddFinancial]);
  const ueCatalog = useMemo(() => buildUeStoreCatalog(dataStore.ueFinancial), [dataStore.ueFinancial]);

  const [mapRows, setMapRows] = useState([]);

  useEffect(() => {
    if (!ddCatalog.length) return;
    setMapRows((prev) => {
      if (prev.length > 0) return prev;
      return buildSuggestedMapRows(ddCatalog, ueCatalog, config.ddToUeStoreMap || {}, config.storeTagMap || {});
    });
  }, [ddCatalog, ueCatalog, config.ddToUeStoreMap, config.storeTagMap]);

  const handleAnalyze = () => {
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
      dataStore.setProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4">
      <div className="w-full max-w-[96vw] space-y-6">
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold text-[var(--text)]">Configure Analysis</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">Set date ranges and exclusions for your analysis</p>
        </div>

        {/* Date Ranges */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--text)]">Analysis Periods</h3>
            <SyncToggle
              synced={config.syncDates}
              onToggle={() => config.setSyncDates(!config.syncDates)}
              label="Same dates for all platforms"
            />
          </div>

          {hasDd && (
            <div className="mb-4 p-4 rounded-lg bg-[var(--surface-2)]">
              <div className="flex items-center gap-2 mb-3">
                <span className="platform-dot dd" />
                <span className="text-sm font-medium text-[var(--text)]">DoorDash</span>
                {ddRange.min && (
                  <span className="text-[10px] text-[var(--text-subtle)] ml-auto">
                    Data: {formatDateShort(ddRange.min)} — {formatDateShort(ddRange.max)}
                  </span>
                )}
              </div>
              <PeriodRangePair
                preStart={config.ddPreStart}
                preEnd={config.ddPreEnd}
                postStart={config.ddPostStart}
                postEnd={config.ddPostEnd}
                onApply={config.setDdDates}
              />
            </div>
          )}

          {hasUe && !config.syncDates && (
            <div className="p-4 rounded-lg bg-[var(--surface-2)]">
              <div className="flex items-center gap-2 mb-3">
                <span className="platform-dot ue" />
                <span className="text-sm font-medium text-[var(--text)]">UberEats</span>
                {ueRange.min && (
                  <span className="text-[10px] text-[var(--text-subtle)] ml-auto">
                    Data: {formatDateShort(ueRange.min)} — {formatDateShort(ueRange.max)}
                  </span>
                )}
              </div>
              <PeriodRangePair
                preStart={config.uePreStart}
                preEnd={config.uePreEnd}
                postStart={config.uePostStart}
                postEnd={config.uePostEnd}
                onApply={config.setUeDates}
              />
            </div>
          )}
        </div>

        {/* Store Exclusions */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--text)]">Exclude Stores</h3>
            <SyncToggle
              synced={config.syncStoreExclusions}
              onToggle={() => config.setSyncStoreExclusions(!config.syncStoreExclusions)}
              label="Same for all platforms"
            />
          </div>
          <div className="space-y-4">
            {hasDd && (
              <StoreIdExcludeSelect
                label={`DoorDash (${ddStores.length} store IDs detected)`}
                options={ddStores}
                selected={config.ddExcludedStores}
                onChange={config.setDdExcludedStores}
                selectPrompt={ddStores.length ? 'Select a DoorDash store ID to exclude…' : 'No store IDs in file'}
              />
            )}
            {hasUe && !config.syncStoreExclusions && (
              <StoreIdExcludeSelect
                label={`UberEats (${ueStores.length} store IDs detected)`}
                options={ueStores}
                selected={config.ueExcludedStores}
                onChange={config.setUeExcludedStores}
                selectPrompt={ueStores.length ? 'Select an UberEats store ID to exclude…' : 'No store IDs in file'}
              />
            )}
          </div>
        </div>

        {/* Date Exclusions */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--text)]">Exclude Dates</h3>
            <SyncToggle
              synced={config.syncDateExclusions}
              onToggle={() => config.setSyncDateExclusions(!config.syncDateExclusions)}
              label="Same for all platforms"
            />
          </div>
          <div className="space-y-4">
            {hasDd && (
              <DateExcluder
                label="DoorDash"
                dates={config.ddExcludedDates}
                onChange={config.setDdExcludedDates}
              />
            )}
            {hasUe && !config.syncDateExclusions && (
              <DateExcluder
                label="UberEats"
                dates={config.ueExcludedDates}
                onChange={config.setUeExcludedDates}
              />
            )}
          </div>
        </div>

        {hasDd && hasUe && (
          <div className="card">
            <h3 className="font-semibold text-[var(--text)] mb-2">Combined: DD ↔ UE store map</h3>
            <StoreMapEditor
              ddFinancial={dataStore.ddFinancial}
              ueFinancial={dataStore.ueFinancial}
              rows={mapRows}
              setRows={setMapRows}
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setScreen('upload')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
          >
            <ChevronLeft size={16} />
            Back
          </button>
          <button
            disabled={!config.isConfigured() || dataStore.isProcessing}
            onClick={handleAnalyze}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium text-sm transition-all
              ${config.isConfigured()
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
