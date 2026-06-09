import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Link2, ChevronRight, Globe, Monitor } from "lucide-react";

type BrowserMode = "multilogin" | "native";

type BrowserSettings = {
  mode: BrowserMode;
  multilogin: boolean;
  native: boolean;
};

export function SettingsPage() {
  const [savedMode, setSavedMode] = useState<BrowserMode>("native");
  const [selectedMode, setSelectedMode] = useState<BrowserMode>("native");
  const [browserLoading, setBrowserLoading] = useState(true);
  const [browserSaving, setBrowserSaving] = useState(false);
  const [browserError, setBrowserError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const hasUnsavedChanges = selectedMode !== savedMode;

  const loadBrowserSettings = useCallback(async () => {
    setBrowserLoading(true);
    setBrowserError(null);
    try {
      const res = await fetch("/api/browser-settings");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BrowserSettings = await res.json();
      setSavedMode(data.mode);
      setSelectedMode(data.mode);
    } catch (err) {
      setBrowserError(err instanceof Error ? err.message : "Failed to load browser settings");
    } finally {
      setBrowserLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBrowserSettings();
  }, [loadBrowserSettings]);

  async function handleSaveBrowserMode() {
    setBrowserSaving(true);
    setBrowserError(null);
    setSaveSuccess(false);
    try {
      const res = await fetch("/api/browser-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: selectedMode }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data: BrowserSettings = await res.json();
      setSavedMode(data.mode);
      setSelectedMode(data.mode);
      setSaveSuccess(true);
    } catch (err) {
      setBrowserError(err instanceof Error ? err.message : "Failed to save");
      void loadBrowserSettings();
    } finally {
      setBrowserSaving(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8">
      <div>
        <h2 className="font-display text-2xl font-semibold text-ink-900 dark:text-white">
          Settings
        </h2>
        <p className="mt-1 text-ink-600 dark:text-white/65">
          API connection and browser automation for all agents.
        </p>
      </div>

      <section className="brand-card rounded-[28px] p-6">
        <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
          API
        </h3>
        <p className="mt-1 text-sm text-ink-500 dark:text-white/55">
          Point the dashboard at your FastAPI or orchestrator host. Dev proxy
          maps <code className="rounded bg-brand-100 px-1 dark:bg-white/10">/api</code>{" "}
          → <code className="rounded bg-brand-100 px-1 dark:bg-white/10">127.0.0.1:8000</code>.
        </p>
        <label className="mt-4 block">
          <span className="text-sm font-medium text-ink-700 dark:text-slate-300">
            Base URL
          </span>
          <input
            type="url"
            defaultValue="http://127.0.0.1:8000"
            className="mt-2 w-full rounded-2xl border border-brand-100 bg-white px-4 py-3 text-sm text-ink-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-white/10 dark:bg-white/5 dark:text-slate-100"
          />
        </label>
      </section>

      <section className="brand-card rounded-[28px] p-6">
        <h3 className="font-display text-lg font-semibold text-ink-900 dark:text-white">
          Browser automation
        </h3>
        <p className="mt-1 text-sm text-ink-500 dark:text-white/55">
          Choose how agents open DoorDash: Multilogin profiles (pre-logged-in) or local
          browser-use with operator portal login. Applies to Health Check, Data Run,
          Strategist, Offers, Ads, and reporting browser-use forks.
        </p>

        {browserError && (
          <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200">
            {browserError}
          </p>
        )}

        {saveSuccess && !hasUnsavedChanges && (
          <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
            Browser mode saved. All agents will use this setting on their next run.
          </p>
        )}

        <div className="mt-4 flex flex-col gap-3">
          <button
            type="button"
            disabled={browserLoading || browserSaving}
            onClick={() => {
              setSelectedMode("multilogin");
              setSaveSuccess(false);
            }}
            className={`flex items-start gap-4 rounded-2xl border p-4 text-left transition ${
              selectedMode === "multilogin"
                ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/20 dark:border-brand-400 dark:bg-brand-500/10"
                : "border-brand-100 bg-brand-50/70 hover:border-brand-300 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-500/40"
            }`}
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
              <Globe className="h-5 w-5" />
            </span>
            <div>
              <p className="font-medium text-ink-900 dark:text-white">
                Multilogin profiles
              </p>
              <p className="mt-0.5 text-sm text-ink-500 dark:text-white/55">
                Connect via MLX APIs to the operator&apos;s mapped profile — session already
                logged in. Requires Multilogin desktop app and operator ↔ profile mapping.
              </p>
            </div>
          </button>

          <button
            type="button"
            disabled={browserLoading || browserSaving}
            onClick={() => {
              setSelectedMode("native");
              setSaveSuccess(false);
            }}
            className={`flex items-start gap-4 rounded-2xl border p-4 text-left transition ${
              selectedMode === "native"
                ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500/20 dark:border-brand-400 dark:bg-brand-500/10"
                : "border-brand-100 bg-brand-50/70 hover:border-brand-300 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-500/40"
            }`}
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
              <Monitor className="h-5 w-5" />
            </span>
            <div>
              <p className="font-medium text-ink-900 dark:text-white">
                Local browser (browser-use)
              </p>
              <p className="mt-0.5 text-sm text-ink-500 dark:text-white/55">
                Launch local Chrome via Python browser-use; agents log in with operator
                email and password from Airtable / mapping.
              </p>
            </div>
          </button>
        </div>

        <div className="mt-4 flex items-center justify-end gap-3">
          {hasUnsavedChanges && (
            <span className="text-sm text-ink-500 dark:text-white/55">Unsaved changes</span>
          )}
          <button
            type="button"
            disabled={browserLoading || browserSaving || !hasUnsavedChanges}
            onClick={() => void handleSaveBrowserMode()}
            className="rounded-2xl bg-brand-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-brand-500 dark:hover:bg-brand-600"
          >
            {browserSaving ? "Saving…" : "Save browser mode"}
          </button>
        </div>

        <Link
          to="/settings/operator-mapping"
          className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-brand-100 bg-brand-50/70 p-4 transition hover:border-brand-300 hover:bg-brand-50 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-500/40"
        >
          <div className="flex items-start gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300">
              <Link2 className="h-5 w-5" />
            </span>
            <div>
              <p className="font-medium text-ink-900 dark:text-white">
                Operator ↔ Multilogin mapping
              </p>
              <p className="mt-0.5 text-sm text-ink-500 dark:text-white/55">
                Required for Multilogin mode — Venn view, edit assignments, save JSON + CSV
              </p>
            </div>
          </div>
          <ChevronRight className="h-5 w-5 shrink-0 text-ink-400" />
        </Link>
      </section>
    </div>
  );
}
