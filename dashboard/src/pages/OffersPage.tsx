import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import { OperatorAccountPicker } from "../components/OperatorAccountPicker";

export function OffersPage() {
  const [operatorId, setOperatorId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!operatorId.trim()) {
      setError("Enter an Operator ID.");
      return;
    }
    if (!email.trim() || !password) {
      setError("DoorDash email and password are required.");
      return;
    }

    const formData = new FormData();
    formData.append("operator_id", operatorId.trim());
    formData.append("mode", "auto");
    formData.append("doordash_email", email.trim());
    formData.append("doordash_password", password);

    setLoading(true);
    try {
      const res = await fetch("/api/runs/offers", { method: "POST", body: formData });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 h-full">
      <div>
        <Link
          to="/agents"
          className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to agents
        </Link>
        <h2 className="font-display text-2xl font-semibold text-ink-900">RalphAI - Offers</h2>
        <p className="mt-1 max-w-2xl text-ink-600">
          Offers mode runs the complete browser-use reporting workflow (<code>agents/reporting_browser_use</code>)
          end-to-end using the
          DoorDash login credentials entered here in the UI.
        </p>
        <p className="mt-2 max-w-2xl text-sm text-ink-600">
          Flow: login → report download → analysis/combined workbook → campaign execution in DoorDash.
        </p>
      </div>

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
          <div className="sm:col-span-2 rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">{error}</div>
        ) : null}

        <div className="sm:col-span-2 pt-2">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ink-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-ink-700 disabled:opacity-50 dark:bg-brand-500 dark:text-ink-900 dark:hover:bg-brand-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? "Running full Offers flow..." : "Run RalphAI - Offers"}
          </button>
        </div>
      </form>

      {result ? (
        <div className="brand-card rounded-[24px] p-5">
          <h3 className="font-display text-lg font-semibold text-ink-900">Run result</h3>
          <p className="mt-2 text-sm text-ink-700">Status: {result.status ?? "unknown"}</p>
        </div>
      ) : null}
    </div>
  );
}
