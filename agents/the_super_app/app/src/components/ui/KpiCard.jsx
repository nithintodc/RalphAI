import { formatValue } from '../../lib/utils/formatters';
import DeltaPill from './DeltaPill';
import Sparkline from './Sparkline';

export default function KpiCard({ label, value, format = 'usd', delta, yoyDelta, hint, sparkData, compact = false }) {
  return (
    <div className={`card flex flex-col ${compact ? 'p-3 gap-1' : 'p-4 gap-2'}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-muted)]">{label}</span>
        {hint && <span className="text-[10px] text-[var(--text-subtle)]">{hint}</span>}
      </div>
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className={`font-semibold tnum ${compact ? 'text-lg' : 'text-2xl'} text-[var(--text)]`}>
            {formatValue(value, format)}
          </div>
          <div className="flex items-center gap-2 mt-1">
            {delta != null && <DeltaPill value={delta} label="PvP" />}
            {yoyDelta != null && <DeltaPill value={yoyDelta} label="YoY" subtle />}
          </div>
        </div>
        {sparkData && <Sparkline data={sparkData} width={compact ? 60 : 80} height={compact ? 24 : 32} />}
      </div>
    </div>
  );
}
