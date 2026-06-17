import { format } from 'date-fns';
import PlatformLogo from '../ui/PlatformLogo';
import { fmt } from '../../lib/utils/formatters';
import {
  buildDdStoreIdToMerchantMapFromFinancial,
  displayStoreId,
} from '../../lib/utils/storeDisplay';

function formatDay(date) {
  if (!date) return '—';
  return format(date, 'MMM d');
}

function InsightList({ title, items, renderItem, empty = 'No data' }) {
  if (!items?.length) {
    return (
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)] mb-1">{title}</p>
        <p className="text-xs text-[var(--text-subtle)]">{empty}</p>
      </div>
    );
  }
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)] mb-1">{title}</p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={item.key ?? i} className="flex items-center justify-between gap-2 text-xs">
            {renderItem(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DateExtremesMini({ label, extremes }) {
  const top = extremes?.top || [];
  const low = extremes?.low || [];
  if (!top.length && !low.length) return null;

  const row = (d, tone) => (
    <span className={`tnum font-medium whitespace-nowrap ${tone === 'high' ? 'text-[var(--positive)]' : 'text-[var(--negative)]'}`}>
      {fmt.usd(d.sales)}
    </span>
  );

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-semibold text-[var(--text)]">{label}</p>
      <div className="grid grid-cols-2 gap-x-3 text-[11px]">
        <div>
          <p className="text-[9px] uppercase text-[var(--positive)] mb-0.5">Highest</p>
          {top.map((d) => (
            <div key={`h-${d.dateKey}`} className="flex justify-between gap-2 py-0.5">
              <span className="text-[var(--text-muted)]">{formatDay(d.date)}</span>
              {row(d, 'high')}
            </div>
          ))}
        </div>
        <div>
          <p className="text-[9px] uppercase text-[var(--negative)] mb-0.5">Lowest</p>
          {low.map((d) => (
            <div key={`l-${d.dateKey}`} className="flex justify-between gap-2 py-0.5">
              <span className="text-[var(--text-muted)]">{formatDay(d.date)}</span>
              {row(d, 'low')}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlatformQuickColumn({ platform, label, insights, ddStoreIdToMerchant }) {
  if (!insights) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <PlatformLogo platform={platform} size={16} />
          <h4 className="text-sm font-semibold text-[var(--text)]">{label}</h4>
        </div>
        <p className="text-xs text-[var(--text-subtle)]">Upload {label} financial data to see quick insights.</p>
      </div>
    );
  }

  const storeLabel = (row) => displayStoreId(row, platform, ddStoreIdToMerchant);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 min-w-0 space-y-4">
      <div className="flex items-center gap-2">
        <PlatformLogo platform={platform} size={16} />
        <h4 className="text-sm font-semibold text-[var(--text)]">{label}</h4>
      </div>

      <InsightList
        title="Stores — least growth (Pre → Post)"
        items={insights.storesLeastGrowth}
        renderItem={(s) => (
          <>
            <span className="font-medium text-[var(--text)] truncate">{storeLabel(s)}</span>
            <span className="tnum text-[var(--negative)] shrink-0">{fmt.delta(s.sales_growth_pct ?? 0)}</span>
          </>
        )}
      />

      <div className="space-y-3 pt-1 border-t border-[var(--border)]">
        <DateExtremesMini label="Pre period — daily sales" extremes={insights.dates?.pre} />
        <DateExtremesMini label="Post period — daily sales" extremes={insights.dates?.post} />
      </div>

      <InsightList
        title="Dayparts — lowest sales (Post)"
        items={insights.slotsLowestSales}
        renderItem={(s) => (
          <>
            <span className="text-[var(--text)]">{s.slot}</span>
            <span className="tnum text-[var(--text-muted)] shrink-0">{fmt.usd(s.sales)}</span>
          </>
        )}
      />
    </div>
  );
}

export default function PrePostQuickInsights({ insights, ddFinancial }) {
  if (!insights?.dd && !insights?.ue) return null;

  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMapFromFinancial(ddFinancial);

  return (
    <section className="card min-w-0 space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-[var(--text)]">Quick Pre vs Post snapshot</h3>
        <p className="text-xs text-[var(--text-subtle)] mt-0.5">
          Lowest-growth stores, highest/lowest sales days, and weakest dayparts — computed when you run analysis.
        </p>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PlatformQuickColumn
          platform="dd"
          label="DoorDash"
          insights={insights.dd}
          ddStoreIdToMerchant={ddStoreIdToMerchant}
        />
        <PlatformQuickColumn
          platform="ue"
          label="Uber Eats"
          insights={insights.ue}
          ddStoreIdToMerchant={ddStoreIdToMerchant}
        />
      </div>
    </section>
  );
}
