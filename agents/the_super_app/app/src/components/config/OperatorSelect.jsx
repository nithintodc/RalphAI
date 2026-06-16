import { useEffect, useState } from 'react';
import { useConfigStore } from '../../stores/configStore';

const OPERATORS_CACHE_KEY = 'superapp_operator_names';
const OTHER_OPTION = '__other__';

function readCachedOperators() {
  try {
    const raw = sessionStorage.getItem(OPERATORS_CACHE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function isManualOperator(name, operatorList) {
  const trimmed = String(name || '').trim();
  return !!trimmed && !operatorList.includes(trimmed);
}

export default function OperatorSelect({ required = false, compact = false }) {
  const operatorName = useConfigStore((s) => s.operatorName);
  const setOperatorName = useConfigStore((s) => s.setOperatorName);
  const [operators, setOperators] = useState(readCachedOperators);
  const [loading, setLoading] = useState(() => readCachedOperators().length === 0);
  const [warning, setWarning] = useState('');
  const [manualMode, setManualMode] = useState(() => isManualOperator(
    useConfigStore.getState().operatorName,
    readCachedOperators(),
  ));

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

  useEffect(() => {
    if (isManualOperator(operatorName, operators)) {
      setManualMode(true);
    }
  }, [operatorName, operators]);

  const inList = operatorName && operators.includes(operatorName);
  const selectValue = manualMode ? OTHER_OPTION : (operatorName || '');

  const handleSelect = (e) => {
    const value = e.target.value;
    if (!value) {
      setManualMode(false);
      setOperatorName('');
      return;
    }
    if (value === OTHER_OPTION) {
      setManualMode(true);
      if (inList) setOperatorName('');
      return;
    }
    setManualMode(false);
    setOperatorName(value);
  };

  return (
    <div className="space-y-2">
      <label className="block text-xs text-[var(--text-muted)]">
        Operator (Business Name from Airtable)
        {required && <span className="text-[var(--negative)] ml-0.5">*</span>}
      </label>
      <select
        value={selectValue}
        onChange={handleSelect}
        disabled={loading}
        className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)] cursor-pointer"
      >
        <option value="">{loading ? 'Loading operators…' : 'Select operator…'}</option>
        {operators.map((name) => (
          <option key={name} value={name}>{name}</option>
        ))}
        <option value={OTHER_OPTION}>Other (type manually)…</option>
      </select>
      {manualMode && (
        <input
          type="text"
          value={operatorName}
          onChange={(e) => setOperatorName(e.target.value)}
          placeholder="Enter operator / business name"
          className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
          autoFocus
        />
      )}
      {warning && (
        <p className="text-[11px] text-[var(--warning)]">{warning}</p>
      )}
      {!compact && (
        <p className="text-[11px] text-[var(--text-subtle)] leading-relaxed">
          Pick from Airtable or choose <strong>Other</strong> to type a custom name. Reporting and the store map use this operator.
        </p>
      )}
    </div>
  );
}
