import { formatValue, formatSignedDelta, formatPrePostRange } from '../../lib/utils/formatters';
import DeltaPill from './DeltaPill';
import Sparkline from './Sparkline';

export default function KpiCard({
  label,
  value,
  format = 'usd',
  pre,
  post,
  rangeFormat,
  delta,
  yoyDelta,
  hint,
  sparkData,
  compact = false,
}) {
  const showDeltaLayout = pre != null && post != null;

  if (showDeltaLayout) {
    const formatted = formatSignedDelta(value, format);
    const rangeStr = formatPrePostRange(pre, post, rangeFormat || format);
    const deltaColor = value > 0
      ? 'text-[var(--positive)]'
      : value < 0
        ? 'text-[var(--negative)]'
        : 'text-[var(--text)]';

    return (
      <div className={`card flex flex-col min-w-0 overflow-hidden ${compact ? '!p-3 gap-1' : '!p-3.5 gap-1'}`}>
        <span className="text-xs font-medium text-[var(--text-muted)] truncate">{label}</span>
        <div
          className={`font-semibold tnum leading-tight min-w-0 ${deltaColor} ${compact ? 'text-lg' : 'text-xl xl:text-2xl'}`}
          title={formatted}
        >
          {formatted}
        </div>
        <div className="text-[11px] text-[var(--text-muted)] tnum truncate" title={rangeStr}>
          {rangeStr}
        </div>
        {(delta != null || yoyDelta != null) && (
          <div className="flex flex-col gap-0.5 mt-0.5">
            {delta != null && (
              <div className="flex items-center gap-1 min-w-0">
                <span className="text-[10px] text-[var(--text-subtle)] shrink-0 w-6">PvP</span>
                <DeltaPill value={delta} />
              </div>
            )}
            {yoyDelta != null && (
              <div className="flex items-center gap-1 min-w-0">
                <span className="text-[10px] text-[var(--text-subtle)] shrink-0 w-6">YoY</span>
                <DeltaPill value={yoyDelta} subtle />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  const formatted = formatValue(value, format);

  return (
    <div className={`card flex flex-col min-w-0 overflow-hidden ${compact ? '!p-3 gap-1' : '!p-3.5 gap-1.5'}`}>
      <div className="flex items-start justify-between gap-2 min-w-0">
        <span className="text-xs font-medium text-[var(--text-muted)] truncate">{label}</span>
        {hint && (
          <span className="text-[10px] text-[var(--text-subtle)] shrink-0 leading-tight text-right">
            {hint}
          </span>
        )}
      </div>
      <div
        className={`font-semibold tnum leading-tight text-[var(--text)] min-w-0 ${compact ? 'text-lg' : 'text-xl xl:text-2xl'}`}
        title={formatted}
      >
        {formatted}
      </div>
      {(delta != null || yoyDelta != null || sparkData) && (
        <div className="flex items-end justify-between gap-2 min-w-0">
          <div className="flex flex-wrap items-center gap-1 min-w-0">
            {delta != null && <DeltaPill value={delta} label="PvP" />}
            {yoyDelta != null && <DeltaPill value={yoyDelta} label="YoY" subtle />}
          </div>
          {sparkData && (
            <Sparkline data={sparkData} width={compact ? 56 : 72} height={compact ? 22 : 28} />
          )}
        </div>
      )}
    </div>
  );
}
