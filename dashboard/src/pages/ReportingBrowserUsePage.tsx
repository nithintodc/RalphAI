import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Loader2, Play, XCircle } from "lucide-react";
import { OperatorAccountPicker } from "../components/OperatorAccountPicker";

type ForkMeta = {
  id: string;
  name: string;
  description: string;
  llm: string;
  llm_env_key: string;
  runnable: boolean;
  path: string;
  note?: string;
  env?: {
    configured: Record<string, boolean>;
    ready_to_run: boolean;
  };
};

const ENV_LABELS: Record<string, string> = {
  DOORDASH_EMAIL: "DoorDash email (.env fallback)",
  DOORDASH_PASSWORD: "DoorDash password (.env fallback)",
  GEMINI_API_KEY: "Gemini API key",
  BROWSER_USE_API_KEY: "Browser Use API key",
  USE_MULTILOGIN: "Multilogin enabled",
  MULTILOGIN_USERNAME: "Multilogin username",
  MULTILOGIN_PASSWORD: "Multilogin password",
  OPERATOR_PROFILE_MAPPING: "Operator ↔ Multilogin mapping (multilogin/ JSON)",
  MULTILOGIN_PROFILES_CSV: "Legacy Multilogin profiles CSV (fallback)",
  LOCAL_BROWSER_CDP_URL: "Chrome CDP URL",
  FORCE_FULL_RUN: "Force full run (skip resume)",
};

export function ReportingBrowserUsePage() {
  const { forkId = "" } = useParams<{ forkId: string }>();
  const [fork, setFork] = useState<ForkMeta | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [operatorId, setOperatorId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!forkId) return;
      setLoadError(null);
      try {
        const res = await fetch(`/api/reporting-browser-use/forks/${encodeURIComponent(forkId)}`);
        if (!res.ok) throw new Error(await res.text());
        const data = (await res.json()) as ForkMeta;
        if (!cancelled) setFork(data);
      } catch (err) {
        if (!cancelled) {
          setFork(null);
          setLoadError(err instanceof Error ? err.message : "Could not load fork");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [forkId]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!fork?.runnable) {
      setError(fork?.note || "This fork is not runnable.");
      return;
    }

    const formData = new FormData();
    if (operatorId.trim()) formData.append("operator_id", operatorId.trim());
    if (email.trim()) formData.append("doordash_email", email.trim());
    if (password) formData.append("doordash_password", password);

    setLoading(true);
    try {
      const res = await fetch(
        `/api/runs/reporting-browser-use/${encodeURIComponent(forkId)}`,
        { method: "POST", body: formData }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setResult((await res.json()) as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const configured = fork?.env?.configured ?? {};

  return (
    <div className="flex h-full flex-col gap-6">
      <div>
        <Link
          to="/agents"
          className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>
        <h2 className="font-display text-2xl font-semibold text-ink-900">
          {fork?.name ?? "Reporting Browser Use"}
        </h2>
        <p className="mt-1 max-w-3xl text-ink-600">
          {fork?.description ??
            "DoorDash browser-use pipeline: login → download → analysis → campaign execution."}
        </p>
        {fork?.path ? (
          <p className="mt-2 font-mono text-xs text-ink-500">{fork.path}</p>
        ) : null}
        {fork && !fork.runnable ? (
          <p className="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {fork.note || "main.py is missing — this fork cannot run yet."}
          </p>
        ) : null}
      </div>

      {loadError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {loadError}
        </div>
      ) : null}

      {fork ? (
        <div className="brand-card rounded-[28px] p-6">
          <h3 className="font-display text-lg font-semibold text-ink-900">Server .env status</h3>
          <p className="mt-1 text-sm text-ink-600">
            Secrets and browser settings are loaded from the API server&apos;s <code>.env</code>.
            DoorDash login can be entered below or taken from <code>DOORDASH_EMAIL</code> /{" "}
            <code>DOORDASH_PASSWORD</code>.
          </p>
          <ul className="mt-4 grid gap-2 sm:grid-cols-2">
            {Object.entries(configured).map(([key, ok]) => {
              if (!ENV_LABELS[key] && !key.startsWith("MULTILOGIN") && key !== fork.llm_env_key) {
                return null;
              }
              const label = ENV_LABELS[key] || key;
              return (
                <li key={key} className="flex items-center gap-2 text-sm text-ink-700">
                  {ok ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-ink-300" />
                  )}
                  <span>
                    <span className="font-medium">{label}</span>
                    <span className="ml-1 font-mono text-xs text-ink-500">({key})</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="brand-card grid gap-4 rounded-[28px] p-6 sm:grid-cols-2">
        <OperatorAccountPicker
          operatorId={operatorId}
          onOperatorIdChange={setOperatorId}
          email={email}
          onEmailChange={setEmail}
          password={password}
          onPasswordChange={setPassword}
          showDoorDashCredentials
        />

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 sm:col-span-2">
            {error}
          </div>
        ) : null}

        <div className="sm:col-span-2 pt-2">
          <button
            type="submit"
            disabled={loading || !fork?.runnable}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? "Running pipeline…" : "Run agent"}
          </button>
        </div>
      </form>

      {result ? (
        <div className="brand-card rounded-[24px] p-5">
          <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
          <p className="mt-2 text-sm text-ink-700">Status: {String(result.status ?? "unknown")}</p>
          {result.run_id ? (
            <p className="mt-1 font-mono text-xs text-ink-500">Run ID: {String(result.run_id)}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
