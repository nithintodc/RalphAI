/** reporting_browser_use fork agents — ids match directory names under agents/. */
export const REPORTING_BROWSER_USE_FORKS = [
  {
    id: "reporting_browser_use",
    shortLabel: "Main",
    desc: "Default production fork (Multilogin + Gemini).",
    color: "from-brand-500 to-ink-800",
  },
  {
    id: "reporting_browser_use_browser",
    shortLabel: "Browser API",
    desc: "Browser Use cloud LLM (BROWSER_USE_API_KEY).",
    color: "from-sky-500 to-blue-800",
  },
  {
    id: "reporting_browser_use_melt",
    shortLabel: "Melt",
    desc: "Store-ID normalization in analysis (Gemini).",
    color: "from-violet-500 to-purple-800",
  },
  {
    id: "reporting_browser_use_savvy",
    shortLabel: "Savvy",
    desc: "Savvy variant — melt lineage (Gemini).",
    color: "from-fuchsia-500 to-pink-800",
  },
  {
    id: "reporting_browser_use_new",
    shortLabel: "New",
    desc: "Reserved stub — main.py not installed.",
    color: "from-ink-400 to-ink-600",
    stub: true,
  },
] as const;

export function reportingBrowserUseRoute(forkId: string): string {
  return `/agents/reporting-browser-use/${forkId}`;
}
