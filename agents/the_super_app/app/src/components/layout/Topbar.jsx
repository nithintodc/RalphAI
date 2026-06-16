import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { ChevronDown, ChevronRight, Download, Filter, Calendar, X, Search, RotateCw } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';
import { useDataStore } from '../../stores/dataStore';
import { STORE_TAG_LABELS } from '../../lib/export/exportSheetSummaries';
import { getUniqueStores as getDdStores } from '../../lib/parsers/ddFinancial';
import { getUniqueStores as getUeStores } from '../../lib/parsers/ueFinancial';
import { ddMerchantStoreIdFromKey } from '../../lib/utils/storeDisplay';
import { runComparisonAnalysis } from '../../lib/engine/comparisonAnalysis';
import { buildAnalysisScope, buildScopedExcludedStores } from '../../lib/utils/abStoreFilter';
import { isSinglePeriodMode } from '../../lib/utils/periodMode';
import DateFilterDropdown from './DateFilterDropdown';
import PlatformLogo from '../ui/PlatformLogo';

function useClickOutside(ref, handler) {
  useEffect(() => {
    const listener = (e) => {
      if (!ref.current || ref.current.contains(e.target)) return;
      handler();
    };
    document.addEventListener('mousedown', listener);
    return () => document.removeEventListener('mousedown', listener);
  }, [ref, handler]);
}

function StoreFilterDropdown({
  onClose,
  onApply,
  allStores,
  allDdStores,
  allUeStores,
  hasDd,
  hasUe,
  syncStoreExclusions,
  setSyncStoreExclusions,
  linkedExcludedIds,
  setLinkedExcluded,
  ddExcludedStores,
  ueExcludedStores,
  setDdExcludedStores,
  setUeExcludedStores,
  ddFinancial,
}) {
  const [search, setSearch] = useState('');
  const [platformTab, setPlatformTab] = useState('dd');
  const ref = useRef(null);
  useClickOutside(ref, onClose);

  const splitMode = hasDd && hasUe && !syncStoreExclusions;
  const activeTab = platformTab === 'ue' && hasUe ? 'ue' : 'dd';

  const listStores = splitMode ? (activeTab === 'dd' ? allDdStores : allUeStores) : allStores;
  const excludedStores = splitMode
    ? (activeTab === 'dd' ? ddExcludedStores : ueExcludedStores)
    : linkedExcludedIds;

  const storeLabel = useCallback((storeId) => {
    if (ddFinancial?.length && allDdStores.includes(storeId)) {
      return ddMerchantStoreIdFromKey(storeId, ddFinancial);
    }
    return storeId;
  }, [ddFinancial, allDdStores]);

  const filtered = useMemo(() => {
    if (!search) return listStores;
    const q = search.toLowerCase();
    return listStores.filter((s) => {
      const label = storeLabel(s);
      return s.toLowerCase().includes(q) || String(label).toLowerCase().includes(q);
    });
  }, [listStores, search, storeLabel]);

  const activeStores = listStores.filter(s => !excludedStores.includes(s));
  const isExcluded = (s) => excludedStores.includes(s);

  const toggle = (storeId) => {
    if (splitMode) {
      if (activeTab === 'dd') {
        if (ddExcludedStores.includes(storeId)) {
          setDdExcludedStores(ddExcludedStores.filter(s => s !== storeId));
        } else {
          setDdExcludedStores([...ddExcludedStores, storeId]);
        }
      } else if (ueExcludedStores.includes(storeId)) {
        setUeExcludedStores(ueExcludedStores.filter(s => s !== storeId));
      } else {
        setUeExcludedStores([...ueExcludedStores, storeId]);
      }
      return;
    }
    if (isExcluded(storeId)) {
      setLinkedExcluded(linkedExcludedIds.filter(s => s !== storeId));
    } else {
      setLinkedExcluded([...linkedExcludedIds, storeId]);
    }
  };

  const selectAll = () => {
    if (splitMode) {
      if (activeTab === 'dd') setDdExcludedStores([]);
      else setUeExcludedStores([]);
    } else {
      setLinkedExcluded([]);
    }
  };

  const deselectAll = () => {
    if (splitMode) {
      if (activeTab === 'dd') setDdExcludedStores([...allDdStores]);
      else setUeExcludedStores([...allUeStores]);
    } else {
      setLinkedExcluded([...allStores]);
    }
  };

  const handleLinkedToggle = (checked) => {
    if (checked) {
      const merged = new Set([...ddExcludedStores, ...ueExcludedStores]);
      const ddEx = allDdStores.filter(s => merged.has(s));
      const ueEx = allUeStores.filter(s => merged.has(s));
      setSyncStoreExclusions(false);
      setDdExcludedStores(ddEx);
      setUeExcludedStores(ueEx);
      setSyncStoreExclusions(true);
      setUeExcludedStores(ueEx);
    } else {
      setSyncStoreExclusions(false);
    }
  };

  const handleApply = () => {
    onApply();
    onClose();
  };

  const subtitle = splitMode
    ? `${activeTab === 'dd' ? 'DoorDash' : 'Uber Eats'} · ${activeStores.length}/${listStores.length} active`
    : `${activeStores.length}/${listStores.length} active`;

  return (
    <div ref={ref} className="absolute top-full right-0 mt-1 w-[min(100vw-1.5rem,380px)] max-w-[380px] bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg z-50 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-[var(--text)]">
          Filter Stores
          <span className="ml-1.5 text-xs font-normal text-[var(--text-muted)]">({subtitle})</span>
        </h4>
        <button type="button" onClick={onClose} className="p-1 rounded hover:bg-[var(--surface-2)] cursor-pointer text-[var(--text-muted)]"><X size={14} /></button>
      </div>

      {hasDd && hasUe && (
        <label
          className={`flex items-start gap-2.5 mb-3 p-2.5 rounded-lg border cursor-pointer transition-colors
            ${syncStoreExclusions
              ? 'bg-[var(--accent-soft)] text-[var(--accent-text)] border-[var(--accent-border)]'
              : 'bg-[var(--surface-2)] text-[var(--text-muted)] border-[var(--border)]'}`}
        >
          <input
            type="checkbox"
            checked={syncStoreExclusions}
            onChange={(e) => handleLinkedToggle(e.target.checked)}
            className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-[var(--accent)]"
          />
          <span className="text-[11px] leading-snug font-medium">
            Same store selection for DoorDash & Uber Eats
            {!syncStoreExclusions && (
              <span className="block font-normal text-[var(--text-subtle)] mt-1">
                Uncheck to pick stores separately per platform.
              </span>
            )}
          </span>
        </label>
      )}

      {splitMode && (
        <div className="flex rounded-lg border border-[var(--border)] p-0.5 mb-2 bg-[var(--surface-2)]">
          <button
            type="button"
            disabled={!hasDd}
            onClick={() => setPlatformTab('dd')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[11px] font-medium transition-colors cursor-pointer
              ${activeTab === 'dd' ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text)]'}`}
          >
            <PlatformLogo platform="dd" size={16} />
            DoorDash
          </button>
          <button
            type="button"
            disabled={!hasUe}
            onClick={() => setPlatformTab('ue')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[11px] font-medium transition-colors cursor-pointer
              ${activeTab === 'ue' ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text)]'}`}
          >
            <PlatformLogo platform="ue" size={16} />
            Uber Eats
          </button>
        </div>
      )}

      <div className="relative mb-2">
        <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-subtle)]" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search store IDs..."
          className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
        />
      </div>

      <div className="flex gap-2 mb-2">
        <button type="button" onClick={selectAll} className="text-[11px] text-[var(--accent)] hover:underline cursor-pointer">Select All</button>
        <span className="text-[var(--border)]">|</span>
        <button type="button" onClick={deselectAll} className="text-[11px] text-[var(--negative)] hover:underline cursor-pointer">Deselect All</button>
      </div>

      <div className="max-h-[280px] overflow-y-auto border border-[var(--border)] rounded-lg">
        {filtered.map(storeId => (
          <label
            key={`${activeTab}-${storeId}`}
            className="flex items-center gap-2.5 px-3 py-1.5 hover:bg-[var(--surface-2)] cursor-pointer border-b border-[var(--border)] last:border-0"
          >
            <input
              type="checkbox"
              checked={!isExcluded(storeId)}
              onChange={() => toggle(storeId)}
              className="w-3.5 h-3.5 rounded border-[var(--border-strong)] accent-[var(--accent)]"
            />
            <span className={`text-xs ${isExcluded(storeId) ? 'text-[var(--text-subtle)] line-through' : 'text-[var(--text)]'}`}>
              {storeLabel(storeId)}
            </span>
          </label>
        ))}
        {filtered.length === 0 && (
          <div className="px-3 py-4 text-center text-xs text-[var(--text-subtle)]">No stores match</div>
        )}
      </div>

      <div className="flex justify-end mt-3 gap-2">
        <button type="button" onClick={onClose} className="px-3 py-1.5 rounded-lg text-xs text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer">Cancel</button>
        <button type="button" onClick={handleApply} className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer">
          <RotateCw size={12} /> Apply & Re-analyze
        </button>
      </div>
    </div>
  );
}

export default function Topbar({ title, crumb, periodLabel, onExport, isExporting }) {
  const [showDateFilter, setShowDateFilter] = useState(false);
  const [showStoreFilter, setShowStoreFilter] = useState(false);

  const config = useConfigStore();
  const dataStore = useDataStore();

  const allDdStores = useMemo(() => dataStore.ddFinancial ? getDdStores(dataStore.ddFinancial) : [], [dataStore.ddFinancial]);
  const allUeStores = useMemo(() => dataStore.ueFinancial ? getUeStores(dataStore.ueFinancial) : [], [dataStore.ueFinancial]);

  const hasDd = allDdStores.length > 0;
  const hasUe = allUeStores.length > 0;

  const currentAllStores = useMemo(() => [...new Set([...allDdStores, ...allUeStores])].sort(), [allDdStores, allUeStores]);
  const linkedUnionExcluded = useMemo(
    () => [...new Set([...(config.ddExcludedStores || []), ...(config.ueExcludedStores || [])])].sort(),
    [config.ddExcludedStores, config.ueExcludedStores],
  );
  const setLinkedExcluded = useCallback((stores) => {
    const excluded = new Set(stores);
    config.setDdExcludedStores(allDdStores.filter(store => excluded.has(store)));
    config.setUeExcludedStores(allUeStores.filter(store => excluded.has(store)));
  }, [config, allDdStores, allUeStores]);

  const activeStoreCount = currentAllStores.length - linkedUnionExcluded.length;
  const ddActiveCount = useMemo(
    () => allDdStores.filter(s => !(config.ddExcludedStores || []).includes(s)).length,
    [allDdStores, config.ddExcludedStores],
  );
  const ueActiveCount = useMemo(
    () => allUeStores.filter(s => !(config.ueExcludedStores || []).includes(s)).length,
    [allUeStores, config.ueExcludedStores],
  );
  const storeChipLabel = hasDd && hasUe && !config.syncStoreExclusions
    ? `${ddActiveCount} · ${ueActiveCount} stores`
    : `${activeStoreCount} stores`;

  const reanalyze = useCallback((message = 'Updating analysis…') => {
    dataStore.setProcessing(true, message);
    window.setTimeout(() => {
      try {
        const latestConfig = useConfigStore.getState();
        const scope = buildAnalysisScope(latestConfig);
        const scopeDdExcluded = buildScopedExcludedStores(allDdStores, 'dd', scope);
        const scopeUeExcluded = buildScopedExcludedStores(allUeStores, 'ue', scope);
        const ddExcludedStores = [...new Set([...(latestConfig.ddExcludedStores || []), ...scopeDdExcluded])];
        const ueExcludedStores = [...new Set([...(latestConfig.ueExcludedStores || []), ...scopeUeExcluded])];
        const isSinglePeriod = isSinglePeriodMode(latestConfig.dateAnalysisMode);

        const ddConfig = {
          preStart: isSinglePeriod ? latestConfig.ddPostStart : latestConfig.ddPreStart,
          preEnd: isSinglePeriod ? latestConfig.ddPostEnd : latestConfig.ddPreEnd,
          postStart: latestConfig.ddPostStart,
          postEnd: latestConfig.ddPostEnd,
          excludedDates: latestConfig.ddExcludedDates,
          excludedStores: ddExcludedStores,
        };
        const ueConfig = {
          preStart: isSinglePeriod ? latestConfig.uePostStart : latestConfig.uePreStart,
          preEnd: isSinglePeriod ? latestConfig.uePostEnd : latestConfig.uePreEnd,
          postStart: latestConfig.uePostStart,
          postEnd: latestConfig.uePostEnd,
          excludedDates: latestConfig.ueExcludedDates,
          excludedStores: ueExcludedStores,
        };

        const hasDd = !!dataStore.ddFinancial?.length;
        const hasUe = !!dataStore.ueFinancial?.length;
        const ddReady = isSinglePeriod ? ddConfig.postStart : ddConfig.preStart;
        const ueReady = isSinglePeriod ? ueConfig.postStart : ueConfig.preStart;

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
          storeMap: latestConfig.ddToUeStoreMap || {},
          isSinglePeriod,
        });

        dataStore.setStoreTables(storeTables);
        dataStore.setSummaryTables(summaries);
        dataStore.setStorePeriodAlignment(storePeriodAlignment);
        dataStore.setCrossPlatformAlignment(crossPlatformAlignment);
      } catch (err) {
        console.error('Re-analysis error:', err);
      }
      dataStore.setProcessing(false);
    }, 50);
  }, [dataStore, allDdStores, allUeStores]);

  return (
    <div className="sticky top-0 z-20 flex items-center gap-3 h-14 px-5 bg-[var(--surface)] border-b border-[var(--border)] min-w-0">
      <div className="font-semibold text-[var(--text)] shrink-0">{title}</div>
      {crumb && (
        <>
          <ChevronRight size={14} className="text-[var(--text-subtle)]" />
          <span className="text-xs text-[var(--text-muted)]">{crumb}</span>
        </>
      )}

      <div className="flex-1 min-w-0" />

      {/* Date Filter Chip */}
      <div className="relative">
        <button
          onClick={() => { setShowDateFilter(!showDateFilter); setShowStoreFilter(false); }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors
            ${showDateFilter
              ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-text)]'
              : 'border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--surface-2)]'
            }`}
        >
          <Calendar size={13} />
          <span
            className="tnum font-medium max-w-[min(44vw,300px)] truncate"
            title={periodLabel || 'Set dates'}
          >
            {periodLabel || 'Set dates'}
          </span>
          <ChevronDown size={13} className={`transition-transform ${showDateFilter ? 'rotate-180' : ''}`} />
        </button>
        {showDateFilter && (
          <DateFilterDropdown
            onClose={() => setShowDateFilter(false)}
            onApply={reanalyze}
          />
        )}
      </div>

      {/* Store Filter Chip */}
      <div className="relative">
        <button
          onClick={() => { setShowStoreFilter(!showStoreFilter); setShowDateFilter(false); }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors
            ${showStoreFilter
              ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-text)]'
              : linkedUnionExcluded.length > 0
                ? 'border-[var(--warning)] bg-amber-50 text-[var(--warning)]'
                : 'border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--surface-2)]'
            }`}
        >
          <Filter size={13} />
          <span>{storeChipLabel}</span>
          {linkedUnionExcluded.length > 0 && (
            <span className="text-[10px] bg-[var(--warning)] text-white rounded-full min-w-[1rem] h-4 px-1 flex items-center justify-center">
              {linkedUnionExcluded.length}
            </span>
          )}
          <ChevronDown size={13} className={`transition-transform ${showStoreFilter ? 'rotate-180' : ''}`} />
        </button>
        {showStoreFilter && (
          <StoreFilterDropdown
            onClose={() => setShowStoreFilter(false)}
            onApply={reanalyze}
            allStores={currentAllStores}
            allDdStores={allDdStores}
            allUeStores={allUeStores}
            hasDd={hasDd}
            hasUe={hasUe}
            syncStoreExclusions={config.syncStoreExclusions}
            setSyncStoreExclusions={config.setSyncStoreExclusions}
            linkedExcludedIds={linkedUnionExcluded}
            setLinkedExcluded={setLinkedExcluded}
            ddExcludedStores={config.ddExcludedStores || []}
            ueExcludedStores={config.ueExcludedStores || []}
            setDdExcludedStores={config.setDdExcludedStores}
            setUeExcludedStores={config.setUeExcludedStores}
            ddFinancial={dataStore.ddFinancial}
          />
        )}
      </div>

      {/* A/B group scope */}
      {Object.keys(config.storeTagMap || {}).length > 0 && (
        <div className="flex items-center rounded-lg border border-[var(--border)] p-0.5 bg-[var(--surface-2)]">
          {[
            { id: 'all', label: 'All' },
            { id: 'A', label: STORE_TAG_LABELS.A },
            { id: 'B', label: STORE_TAG_LABELS.B },
          ].map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => {
                if (config.abGroupFilter === opt.id) return;
                config.setAbGroupFilter(opt.id);
                const label = opt.id === 'all' ? 'All stores' : STORE_TAG_LABELS[opt.id] || `Group ${opt.id}`;
                reanalyze(`Applying ${label}…`);
              }}
              disabled={dataStore.isProcessing}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors
                ${dataStore.isProcessing ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                ${(config.abGroupFilter || 'all') === opt.id
                  ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)]'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      <div className="w-px h-5 bg-[var(--border)]" />

      <button
        onClick={onExport}
        disabled={isExporting}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer"
      >
        <Download size={13} />
        {isExporting ? 'Exporting...' : 'Export'}
      </button>
    </div>
  );
}
