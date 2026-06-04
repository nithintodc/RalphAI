import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function DeltaPill({ value, label, subtle = false }) {
  if (value == null || isNaN(value)) return null;
  const isPositive = value > 0;
  const isNeutral = value === 0;
  const color = isNeutral ? 'text-[var(--text-subtle)]' : isPositive ? 'text-[var(--positive)]' : 'text-[var(--negative)]';
  const bg = isNeutral ? 'bg-[var(--surface-2)]' : isPositive ? 'bg-emerald-50' : 'bg-red-50';
  const Icon = isNeutral ? Minus : isPositive ? TrendingUp : TrendingDown;

  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium tnum ${color} ${subtle ? '' : bg}`}>
      <Icon size={11} />
      {(value >= 0 ? '+' : '') + value.toFixed(1)}%
      {label && <span className="text-[var(--text-subtle)] font-normal ml-0.5">{label}</span>}
    </span>
  );
}
