import { useEffect, useMemo, useState } from "react";

export type AccountOperator = {
  business_name: string;
  operator_id: string;
  doordash_email: string;
  doordash_password: string;
};

type Props = {
  operatorId: string;
  onOperatorIdChange: (v: string) => void;
  email: string;
  onEmailChange: (v: string) => void;
  password: string;
  onPasswordChange: (v: string) => void;
  /** When false, only operator + directory dropdown (e.g. MarketingReco manual). */
  showDoorDashCredentials?: boolean;
  className?: string;
};

const CUSTOM = "__custom__";
const PLACEHOLDER = "";

export function OperatorAccountPicker({
  operatorId,
  onOperatorIdChange,
  email,
  onEmailChange,
  password,
  onPasswordChange,
  showDoorDashCredentials = true,
  className = "",
}: Props) {
  const [operators, setOperators] = useState<AccountOperator[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sourcePath, setSourcePath] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/account-directory");
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = (await res.json()) as {
          operators?: AccountOperator[];
          warning?: string | null;
          path?: string;
        };
        if (cancelled) return;
        setOperators(Array.isArray(data.operators) ? data.operators : []);
        setSourcePath(typeof data.path === "string" ? data.path : null);
        if (data.warning) setLoadError(data.warning);
        else setLoadError(null);
      } catch {
        if (!cancelled) {
          setOperators([]);
          setLoadError("Could not load account directory.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const byName = useMemo(() => {
    const m = new Map<string, AccountOperator>();
    for (const o of operators) m.set(o.business_name, o);
    return m;
  }, [operators]);

  const selectValue = useMemo(() => {
    if (!operatorId.trim()) return PLACEHOLDER;
    if (byName.has(operatorId.trim())) return operatorId.trim();
    return CUSTOM;
  }, [operatorId, byName]);

  function onSelectChange(value: string) {
    if (value === PLACEHOLDER) {
      onOperatorIdChange("");
      return;
    }
    if (value === CUSTOM) {
      onOperatorIdChange("");
      return;
    }
    const row = byName.get(value);
    if (row) {
      onOperatorIdChange(row.operator_id);
      onEmailChange(row.doordash_email);
      onPasswordChange(row.doordash_password);
    }
  }

  const inputClass =
    "rounded-xl border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

  return (
    <div className={`grid gap-3 sm:col-span-2 ${className}`}>
      <label className="flex flex-col gap-1 max-w-xl">
        <span className="text-sm font-medium text-ink-700">Operator (Business Name)</span>
        <select
          className={inputClass}
          value={selectValue}
          onChange={(e) => onSelectChange(e.target.value)}
          aria-label="Select operator from account directory"
        >
          <option value={PLACEHOLDER}>Select operator…</option>
          <option value={CUSTOM}>Custom (type Operator ID below{showDoorDashCredentials ? " and credentials" : ""})</option>
          {operators.map((o) => (
            <option key={o.business_name} value={o.business_name}>
              {o.business_name}
            </option>
          ))}
        </select>
        {sourcePath ? (
          <span className="text-xs text-ink-500 truncate" title={sourcePath}>
            Source: {sourcePath.split("/").slice(-2).join("/")}
          </span>
        ) : null}
        {loadError ? <span className="text-xs text-amber-700">{loadError}</span> : null}
      </label>

      <label className="flex flex-col gap-1 max-w-md">
        <span className="text-sm font-medium text-ink-700">Operator ID (for runs)</span>
        <input
          type="text"
          className={inputClass}
          value={operatorId}
          onChange={(e) => onOperatorIdChange(e.target.value)}
          placeholder="Filled when you pick an operator, or type your own"
          required
        />
      </label>

      {showDoorDashCredentials ? (
        <>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-ink-700">DoorDash Email</span>
            <input
              type="email"
              className={inputClass}
              value={email}
              onChange={(e) => onEmailChange(e.target.value)}
              required={showDoorDashCredentials}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-ink-700">DoorDash Password</span>
            <input
              type="password"
              className={inputClass}
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              required={showDoorDashCredentials}
            />
          </label>
        </>
      ) : null}
    </div>
  );
}
