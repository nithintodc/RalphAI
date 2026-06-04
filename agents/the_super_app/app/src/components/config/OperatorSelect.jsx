import { useEffect, useState } from 'react';
import { useConfigStore } from '../../stores/configStore';

const OPERATORS_CACHE_KEY = 'superapp_operator_names';

function readCachedOperators() {
  try {
    const raw = sessionStorage.getItem(OPERATORS_CACHE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export default function OperatorSelect({ required = false }) {
  const operatorName = useConfigStore((s) => s.operatorName);
  const setOperatorName = useConfigStore((s) => s.setOperatorName);
  const [operators, setOperators] = useState(readCachedOperators);
  const [loading, setLoading] = useState(() => readCachedOperators().length === 0);
  const [warning, setWarning] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/account-directory');
        const data = await res.json();
        if (cancelled) return;
        const names = (data.operators || [])
          .map((o) => o.business_name)
          .filter(Boolean)
          .sort((a, b) => a.localeCompare(b));
        setOperators(names);
        setWarning(data.warning || '');
        try {
          sessionStorage.setItem(OPERATORS_CACHE_KEY, JSON.stringify(names));
        } catch {
          /* ignore quota errors */
        }
      } catch (err) {
        if (!cancelled) setWarning(String(err.message || err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="space-y-2">
      <label className="block text-xs text-[var(--text-muted)]">
        Operator (Business Name from Airtable)
        {required && <span className="text-[var(--negative)] ml-0.5">*</span>}
      </label>
      <select
        value={operatorName}
        onChange={(e) => setOperatorName(e.target.value)}
        disabled={loading}
        className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)] cursor-pointer"
      >
        <option value="">{loading ? 'Loading operators…' : 'Select operator…'}</option>
        {operators.map((name) => (
          <option key={name} value={name}>{name}</option>
        ))}
      </select>
      {warning && (
        <p className="text-[11px] text-[var(--warning)]">{warning}</p>
      )}
      <p className="text-[11px] text-[var(--text-subtle)] leading-relaxed">
        Reporting and the store map are scoped to this operator&apos;s Airtable stores.
      </p>
    </div>
  );
}
