import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function DeltaPill({ value, label, subtle = false }) {
  if (value == null || isNaN(value)) return null;
  const isPositive = value > 0;
  const isNeutral = value === 0;
  const color = isNeutral ? 'text-[var(--text-subtle)]' : isPositive ? 'text-[var(--positive)]' : 'text-[var(--negative)]';
  const bg = isNeutral ? 'bg-[var(--surface-2)]' : isPositive ? 'bg-emerald-50' : 'bg-red-50';
  const Icon = isNeutral ? Minus : isPositive ? TrendingUp : TrendingDown;

  return (
    <span className={`inline-flex items-center gap-0.5 max-w-full px-1 py-0.5 rounded text-[10px] leading-tight font-medium tnum whitespace-nowrap ${color} ${subtle ? '' : bg}`}>
      <Icon size={10} className="shrink-0" />
      <span>{(value >= 0 ? '+' : '') + value.toFixed(1)}%</span>
      {label && <span className="text-[var(--text-subtle)] font-normal">{label}</span>}
    </span>
  );
}
