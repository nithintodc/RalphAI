import { useEffect } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import { buildCorpVsTodcBySource, buildCampaignTable, MARKETING_SUMMARY_METRICS } from '../../lib/engine/marketing';
import { fmt } from '../../lib/utils/formatters';

const PERIOD_SUBHEADS = ['Pre', 'Post', 'LY Pre', 'LY Post', 'Δ PvP', 'Δ PvP %', 'Δ YoY', 'Δ YoY %'];

function formatMetricCell(kind, v) {
  if (v == null || Number.isNaN(v)) return '—';
  switch (kind) {
    case 'int':
      return fmt.int(v);
    case 'usd':
      return fmt.usd(v);
    case 'usd2':
      return fmt.usd2(v);
    case 'roas':
      return fmt.x(v);
    default:
      return String(v);
  }
}

/** Absolute change for ROAS uses ±×; other kinds match level formatting. */
function formatMetricDelta(kind, v) {
  if (v == null || Number.isNaN(v)) return '—';
  if (kind === 'roas') {
    const s = v >= 0 ? '+' : '';
    return `${s}${Number(v).toFixed(2)}×`;
  }
  return formatMetricCell(kind, v);
}

function MarketingSummaryCard({ data }) {
  if (!data?.corp) return null;
  const rows = [data.corp, data.todc, data.total];
  const hasPre = data.meta?.hasPre;

  return (
    <div className="card p-0 overflow-hidden">
      {!hasPre && (
        <p className="px-4 py-2 text-[10px] text-amber-800 bg-amber-50 border-b border-[var(--border)]">
          Pre period is not set. Pre, LY Pre, and Δ PvP columns default to zero; configure Pre dates for a real Pre vs Post comparison.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs min-w-[1280px]">
          <thead>
            <tr className="bg-[var(--surface-2)]">
              <th
                rowSpan={2}
                className="sticky left-0 z-[1] bg-[var(--surface-2)] px-3 py-2 text-left align-bottom text-[11px] font-semibold text-[var(--text-muted)] border-r border-[var(--border)]"
              >
                Group
              </th>
              {MARKETING_SUMMARY_METRICS.map((m) => (
                <th
                  key={m.key}
                  colSpan={8}
                  className="px-1 py-2 text-center text-[11px] font-semibold text-[var(--text-muted)] border-r border-[var(--border)] last:border-r-0"
                >
                  {m.label}
                </th>
              ))}
            </tr>
            <tr className="bg-[var(--surface-2)]">
              {MARKETING_SUMMARY_METRICS.flatMap((m) =>
                PERIOD_SUBHEADS.map((s) => (
                  <th
                    key={`${m.key}-${s}`}
                    className="px-1 py-1.5 text-right font-medium text-[var(--text-subtle)] whitespace-nowrap border-r border-[var(--border)]"
                  >
                    {s}
                  </th>
                )),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.label}
                className={`border-b border-[var(--border)] ${r.label === 'Total' ? 'font-semibold bg-[var(--surface-2)]' : ''}`}
              >
                <td
                  className={`sticky left-0 z-[1] px-3 py-2 font-medium text-[var(--text)] border-r border-[var(--border)] ${
                    r.label === 'Total' ? 'bg-[var(--surface-2)]' : 'bg-[var(--card)]'
                  }`}
                >
                  {r.label}
                </td>
                {MARKETING_SUMMARY_METRICS.flatMap((m) => {
                  const k = m.key;
                  const kind = m.kind;
                  const cells = [
                    formatMetricCell(kind, r[`${k}Pre`]),
                    formatMetricCell(kind, r[`${k}Post`]),
                    formatMetricCell(kind, r[`${k}LyPre`]),
                    formatMetricCell(kind, r[`${k}LyPost`]),
                    formatMetricDelta(kind, r[`${k}Pvp`]),
                    fmt.delta(r[`${k}PvpPct`]),
                    formatMetricDelta(kind, r[`${k}Yoy`]),
                    fmt.delta(r[`${k}YoyPct`]),
                  ];
                  return cells.map((content, i) => (
                    <td key={`${k}-${i}`} className="px-1 py-2 text-right tnum tabular-nums border-r border-[var(--border)] last:border-r-0">
                      {content}
                    </td>
                  ));
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function MarketingScreen() {
  const { ddMarketing, marketingTables, setMarketingTables } = useDataStore();
  const config = useConfigStore();

  useEffect(() => {
    const promo = ddMarketing?.promotion;
    const sponsored = ddMarketing?.sponsored;
    if (!promo && !sponsored) return;

    const postStart = config.ddPostStart;
    const postEnd = config.ddPostEnd;
    if (!postStart || !postEnd) return;

    const bySource = buildCorpVsTodcBySource(promo, sponsored, {
      preStart: config.ddPreStart,
      preEnd: config.ddPreEnd,
      postStart,
      postEnd,
      excludedDates: config.ddExcludedDates || [],
    });
    const campaigns = buildCampaignTable(promo, sponsored, postStart, postEnd);
    setMarketingTables({ bySource, campaigns });
  }, [
    ddMarketing,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
    setMarketingTables,
  ]);

  const mt = marketingTables;

  if (!ddMarketing?.promotion && !ddMarketing?.sponsored) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Marketing data not uploaded.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">Upload the DoorDash Marketing ZIP to see Corp vs TODC analysis.</p>
      </div>
    );
  }

  const campaignCols = [
    { key: 'campaignName', label: 'Campaign', render: (v) => <span className="font-medium">{v}</span> },
    { key: 'source', label: 'Source', render: (v) => <span className="text-xs capitalize">{v}</span> },
    { key: 'isSelfServe', label: 'Type', render: (v) => <span className={`text-xs px-1.5 py-0.5 rounded ${v ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]' : 'bg-purple-50 text-purple-700'}`}>{v ? 'TODC' : 'Corp'}</span> },
    { key: 'orders', label: 'Orders', align: 'right', render: (v) => fmt.int(v) },
    { key: 'sales', label: 'Sales', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'spend', label: 'Spend', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'promoAov', label: 'Promo AOV', align: 'right', render: (v) => fmt.usd2(v) },
    { key: 'roas', label: 'ROAS', align: 'right', render: (v) => fmt.x(v) },
    { key: 'cpo', label: 'Cost/Order', align: 'right', render: (v) => fmt.usd2(v) },
    { key: 'checkAfterPromo', label: 'Check After Promo', align: 'right', render: (v) => fmt.usd2(v) },
  ];

  return (
    <div className="space-y-6">
      <p className="text-xs text-[var(--text-subtle)]">
        Corp vs TODC summary uses your Pre and Post windows plus last-year mirrors of those ranges. Δ PvP is Post − Pre; Δ YoY is Post − LY Post (with % vs the prior-year level). Campaign performance remains Post period only.
      </p>

      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-[var(--text)]">Combined (Promotions + Sponsored)</h3>
        <MarketingSummaryCard data={mt?.bySource?.combined} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Promotions</h3>
          <MarketingSummaryCard data={mt?.bySource?.promotion} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Sponsored Listings</h3>
          <MarketingSummaryCard data={mt?.bySource?.sponsored} />
        </div>
      </div>

      {mt?.campaigns?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Campaign Performance</h3>
          <DataTable columns={campaignCols} data={mt.campaigns} maxHeight="400px" />
        </div>
      )}
    </div>
  );
}
