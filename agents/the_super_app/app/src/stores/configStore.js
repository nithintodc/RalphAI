import { create } from 'zustand';
import { subYears } from 'date-fns';
import { isSinglePeriodMode, isPresetRangeMode } from '../lib/utils/periodMode';

export const useConfigStore = create((set, get) => ({
  ddPreStart: null,
  ddPreEnd: null,
  ddPostStart: null,
  ddPostEnd: null,
  uePreStart: null,
  uePreEnd: null,
  uePostStart: null,
  uePostEnd: null,

  ddExcludedStores: [],
  ueExcludedStores: [],
  ddExcludedDates: [],
  ueExcludedDates: [],

  syncDates: true,
  syncStoreExclusions: true,
  syncDateExclusions: true,

  // Last choice in Analysis periods dropdown: pvp | qoq | mom | wow | singleRange | singleWeek | …
  dateAnalysisMode: 'pvp',

  // Business week: Mon–Sun default (see weekDefinition.js).
  weekDefinitionId: 'mon-sun',
  setWeekDefinitionId: (weekDefinitionId) => set({ weekDefinitionId: String(weekDefinitionId || 'mon-sun') }),

  // Operator/client name shown across exported reports (cover, meta, footer).
  operatorName: '',
  setOperatorName: (operatorName) => set({ operatorName: String(operatorName || '') }),

  // TODC account manager name on partnership reports.
  accountManager: '',
  setAccountManager: (accountManager) => set({ accountManager: String(accountManager || '') }),

  // DoorDash Merchant store ID (string) -> Uber Eats Store ID (string) for combined rows.
  ddToUeStoreMap: {},
  // Canonical combined store ID (UE mapped ID or DD ID) -> tag label (e.g. A/B).
  storeTagMap: {},
  // Canonical store IDs included in analysis (mapping rows not deleted).
  includedStoreIds: [],
  // App-wide A/B scope: all | A | B
  abGroupFilter: 'all',

  setDdToUeStoreMap: (map) => {
    const next = map && typeof map === 'object' && !Array.isArray(map) ? { ...map } : {};
    set({ ddToUeStoreMap: next });
  },
  setStoreTagMap: (map) => {
    const next = map && typeof map === 'object' && !Array.isArray(map) ? { ...map } : {};
    set({ storeTagMap: next });
  },
  setIncludedStoreIds: (ids) => {
    const next = Array.isArray(ids) ? ids.map((id) => String(id).trim()).filter(Boolean) : [];
    set({ includedStoreIds: next });
  },
  setAbGroupFilter: (abGroupFilter) => {
    const next = abGroupFilter === 'A' || abGroupFilter === 'B' ? abGroupFilter : 'all';
    set({ abGroupFilter: next });
  },

  setDateAnalysisMode: (dateAnalysisMode) => set({ dateAnalysisMode }),

  setDdDates: (preStart, preEnd, postStart, postEnd) => {
    const updates = { ddPreStart: preStart, ddPreEnd: preEnd, ddPostStart: postStart, ddPostEnd: postEnd };
    if (get().syncDates) {
      updates.uePreStart = preStart;
      updates.uePreEnd = preEnd;
      updates.uePostStart = postStart;
      updates.uePostEnd = postEnd;
    }
    set(updates);
  },

  setUeDates: (preStart, preEnd, postStart, postEnd) => {
    const updates = { uePreStart: preStart, uePreEnd: preEnd, uePostStart: postStart, uePostEnd: postEnd };
    if (get().syncDates) {
      updates.ddPreStart = preStart;
      updates.ddPreEnd = preEnd;
      updates.ddPostStart = postStart;
      updates.ddPostEnd = postEnd;
    }
    set(updates);
  },

  setSyncDates: (v) => {
    const updates = { syncDates: v };
    if (v) {
      const s = get();
      updates.uePreStart = s.ddPreStart;
      updates.uePreEnd = s.ddPreEnd;
      updates.uePostStart = s.ddPostStart;
      updates.uePostEnd = s.ddPostEnd;
    }
    set(updates);
  },

  setDdExcludedStores: (stores) => {
    const updates = { ddExcludedStores: stores };
    if (get().syncStoreExclusions) updates.ueExcludedStores = stores;
    set(updates);
  },
  setUeExcludedStores: (stores) => set({ ueExcludedStores: stores }),

  setDdExcludedDates: (dates) => {
    const updates = { ddExcludedDates: dates };
    if (get().syncDateExclusions) updates.ueExcludedDates = dates;
    set(updates);
  },
  setUeExcludedDates: (dates) => set({ ueExcludedDates: dates }),

  setSyncStoreExclusions: (v) => {
    const updates = { syncStoreExclusions: v };
    if (v) updates.ueExcludedStores = get().ddExcludedStores;
    set(updates);
  },
  setSyncDateExclusions: (v) => {
    const updates = { syncDateExclusions: v };
    if (v) updates.ueExcludedDates = get().ddExcludedDates;
    set(updates);
  },

  getLYDates: (platform) => {
    const s = get();
    const pre = platform === 'dd' ? s.ddPreStart : s.uePreStart;
    const preE = platform === 'dd' ? s.ddPreEnd : s.uePreEnd;
    const post = platform === 'dd' ? s.ddPostStart : s.uePostStart;
    const postE = platform === 'dd' ? s.ddPostEnd : s.uePostEnd;
    if (!pre || !preE || !post || !postE) return null;
    return {
      preLYStart: subYears(pre, 1),
      preLYEnd: subYears(preE, 1),
      postLYStart: subYears(post, 1),
      postLYEnd: subYears(postE, 1),
    };
  },

  isConfigured: () => {
    const s = get();
    if (isSinglePeriodMode(s.dateAnalysisMode)) {
      const ddReady = s.ddPostStart && s.ddPostEnd;
      const ueReady = s.uePostStart && s.uePostEnd;
      return !!(ddReady || ueReady);
    }
    if (isPresetRangeMode(s.dateAnalysisMode)) {
      const ddReady = s.ddPostStart && s.ddPostEnd;
      const ueReady = s.uePostStart && s.uePostEnd;
      return !!(ddReady || ueReady);
    }
    const ddReady = s.ddPreStart && s.ddPreEnd && s.ddPostStart && s.ddPostEnd;
    const ueReady = s.uePreStart && s.uePreEnd && s.uePostStart && s.uePostEnd;
    return !!(ddReady || ueReady);
  },
}));
