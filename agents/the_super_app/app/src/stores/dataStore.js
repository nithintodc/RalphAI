import { create } from 'zustand';

const initialState = {
  ddFinancial: null,
  ddFinancialError: null,
  ddMarketing: { promotion: null, sponsored: null },
  /** Raw parsed CSV rows for marketing breakdown pivots (promotion file). */
  ddMarketingRaw: { promotion: null, sponsored: null },
  ddSales: { byOrder: null, byTime: null, byStore: null },
  ddOps: { byOrder: null, byStore: null, byTime: null },
  ddProductMix: null,
  ueFinancial: null,
  uploadedFiles: {},
  isProcessing: false,
  processingMessage: null,
  aggregated: null,
  storeTables: null,
  summaryTables: null,
  marketingTables: null,
  slotAnalysis: null,
  bucketAnalysis: null,
  diagnosticsData: null,
};

export const useDataStore = create((set, get) => ({
  ...initialState,

  setDdFinancial: (data) => set({ ddFinancial: data }),
  setDdFinancialError: (data) => set({ ddFinancialError: data }),
  setUeFinancial: (data) => set({ ueFinancial: data }),
  setDdMarketing: (type, data) => set((s) => ({
    ddMarketing: { ...s.ddMarketing, [type]: data },
  })),
  setDdMarketingRaw: (type, parsed, fileLabel) => set((s) => ({
    ddMarketingRaw: {
      ...s.ddMarketingRaw,
      [type]: parsed ? { data: parsed.data, columns: parsed.columns, fileLabel } : null,
    },
  })),
  setDdSales: (view, data) => set((s) => ({
    ddSales: { ...s.ddSales, [view]: data },
  })),
  setDdOps: (view, data) => set((s) => {
    const prev = s.ddOps[view];
    if (
      (view === 'byStore' || view === 'byOrder')
      && prev
      && data
      && typeof data === 'object'
      && !Array.isArray(data)
    ) {
      const merged = { ...prev };
      for (const [k, v] of Object.entries(data)) {
        if (v !== undefined) merged[k] = v;
      }
      return { ddOps: { ...s.ddOps, [view]: merged } };
    }
    return { ddOps: { ...s.ddOps, [view]: data } };
  }),
  setDdProductMix: (data) => set({ ddProductMix: data }),
  setUploadedFile: (key, info) => set((s) => ({
    uploadedFiles: { ...s.uploadedFiles, [key]: info },
  })),
  setProcessing: (v, message = null) => set({
    isProcessing: v,
    processingMessage: v ? (message || 'Updating analysis…') : null,
  }),
  setAggregated: (data) => set({ aggregated: data }),
  setStoreTables: (data) => set({ storeTables: data }),
  setSummaryTables: (data) => set({ summaryTables: data }),
  setMarketingTables: (data) => set({ marketingTables: data }),
  setSlotAnalysis: (data) => set({ slotAnalysis: data }),
  setBucketAnalysis: (data) => set({ bucketAnalysis: data }),
  setDiagnosticsData: (data) => set({ diagnosticsData: data }),
  reset: () => set(initialState),

  getAvailableAnalysis: () => {
    const s = get();
    return {
      financials: !!(s.ddFinancial || s.ueFinancial),
      marketing: !!(s.ddMarketing.promotion),
      operations: !!(s.ddOps.byOrder || s.ddOps.byStore || s.ddOps.byTime),
      productMix: !!s.ddProductMix,
      salesViews: !!(s.ddSales.byOrder || s.ddSales.byTime || s.ddSales.byStore),
      slots: !!s.ddFinancial,
      buckets: !!s.ddFinancial,
    };
  },

  getUploadCount: () => Object.keys(get().uploadedFiles).length,
}));
