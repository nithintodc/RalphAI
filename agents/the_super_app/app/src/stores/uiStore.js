import { create } from 'zustand';

export const useUiStore = create((set) => ({
  screen: 'upload',
  activeTab: 'overview',
  theme: 'light',
  selectedStore: null,
  selectedStorePlatform: null,
  /** Right drawer: App 2.0–style analysis modules */
  sidePanel: null,

  setScreen: (screen) => set({ screen }),
  setActiveTab: (activeTab) => set({ activeTab }),
  toggleTheme: () => set((s) => {
    const next = s.theme === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = next;
    return { theme: next };
  }),
  setSelectedStore: (selectedStore, selectedStorePlatform = null) => set({ selectedStore, selectedStorePlatform }),
  setSidePanel: (sidePanel) => set({ sidePanel }),
}));
