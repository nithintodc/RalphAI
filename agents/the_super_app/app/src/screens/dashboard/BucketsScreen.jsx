import { useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { PieChart, Pie, Cell } from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import BarShareLabels from '../../components/charts/BarShareLabels';
import { buildBucketAnalysis, buildOrderOriginMix } from '../../lib/engine/buckets';
import { addBarSharePct } from '../../lib/utils/barChartShare';
import { fmt } from '../../lib/utils/formatters';
import { DATA_PLATFORM_SECTIONS } from '../../lib/platforms';
import PlatformLogo from '../../components/ui/PlatformLogo';

function MixDonut({ title, mix }) {
  return (
    <div className="flex flex-col items-center">
      <p className="text-xs font-semibold text-[var(--text-muted)] mb-1">{title}</p>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={mix || []} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={45} outerRadius={72} paddingAngle={2}>
            {(mix || []).map((entry, i) => <Cell key={i} fill={entry.color} />)}
          </Pie>
          <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} formatter={(v) => v + '%'} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function buildMixChange(mixPre, mixPost) {
  return (mixPost || []).map((pm) => {
    const prem = (mixPre || []).find((x) => x.id === pm.id) || { value: 0 };
    return {
      id: pm.id,
      label: pm.label,
      color: pm.color,
      pre: prem.value || 0,
      post: pm.value || 0,
      delta: Math.round(((pm.value || 0) - (prem.value || 0)) * 10) / 10,
    };
  });
}

const mixChangeColumns = [
  {
    key: 'label',
    label: 'Segment',
    sortable: false,
    render: (v, row) => (
      <span className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full" style={{ background: row.color }} />
        {v}
      </span>
    ),
  },
  { key: 'pre', label: 'Pre share', align: 'right', sortable: false, render: (v) => fmt.pct(v) },
  { key: 'post', label: 'Post share', align: 'right', sortable: false, render: (v) => fmt.pct(v) },
  { key: 'delta', label: 'Δ (pp)', align: 'right', sortable: false, delta: true, render: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)} pp` },
];

export default function BucketsScreen() {
  const { ddFinancial, ueFinancial, bucketAnalysis, setBucketAnalysis } = useDataStore();
  const config = useConfigStore();

  useEffect(() => {
    const out = {};
    if (ddFinancial && config.ddPreStart && config.ddPostStart) {
      out.dd = {
        buckets: buildBucketAnalysis(ddFinancial, {
          preStart: config.ddPreStart,
          preEnd: config.ddPreEnd,
          postStart: config.ddPostStart,
          postEnd: config.ddPostEnd,
          excludedDates: config.ddExcludedDates,
          platform: 'dd',
        }),
        mix: buildOrderOriginMix(ddFinancial, config.ddPostStart, config.ddPostEnd, config.ddExcludedDates, 'dd'),
        mixPre: config.ddPreStart && config.ddPreEnd
          ? buildOrderOriginMix(ddFinancial, config.ddPreStart, config.ddPreEnd, config.ddExcludedDates, 'dd')
          : null,
      };
    }
    if (ueFinancial && config.uePreStart && config.uePostStart) {
      out.ue = {
        buckets: buildBucketAnalysis(ueFinancial, {
          preStart: config.uePreStart,
          preEnd: config.uePreEnd,
          postStart: config.uePostStart,
          postEnd: config.uePostEnd,
          excludedDates: config.ueExcludedDates,
          platform: 'ue',
        }),
        mix: buildOrderOriginMix(ueFinancial, config.uePostStart, config.uePostEnd, config.ueExcludedDates, 'ue'),
        mixPre: config.uePreStart && config.uePreEnd
          ? buildOrderOriginMix(ueFinancial, config.uePreStart, config.uePreEnd, config.ueExcludedDates, 'ue')
          : null,
      };
    }
    setBucketAnalysis(out);
  }, [
    ddFinancial,
    ueFinancial,
    config.ddPreStart,
    config.ddPreEnd,
    config.ddPostStart,
    config.ddPostEnd,
    config.ddExcludedDates,
    config.uePreStart,
    config.uePreEnd,
    config.uePostStart,
    config.uePostEnd,
    config.ueExcludedDates,
    setBucketAnalysis,
  ]);

  const columns = [
    { key: 'range', label: 'Bucket', sortable: false },
    { key: 'pre_orders', label: 'Pre Orders', align: 'right', render: (v) => fmt.int(v) },
    { key: 'post_orders', label: 'Post Orders', align: 'right', render: (v) => fmt.int(v) },
    { key: 'orders_change', label: 'Change', align: 'right', delta: true, render: (v) => (v >= 0 ? '+' : '') + fmt.int(v) },
    { key: 'orders_growth_pct', label: 'Growth%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'pre_sales', label: 'Pre Sales', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'post_sales', label: 'Post Sales', align: 'right', render: (v) => fmt.usd(v) },
    { key: 'sales_growth_pct', label: 'Sales Growth%', align: 'right', delta: true, render: (v) => fmt.delta(v) },
  ];

  if (!ddFinancial && !ueFinancial) {
    return (
      <div className="card text-center py-12">
        <p className="text-[var(--text-muted)]">Order bucketing requires platform financial data (order-level detail).</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {DATA_PLATFORM_SECTIONS.map(({ key, label }) => {
        const ba = bucketAnalysis?.[key];
        if (!ba?.buckets?.length) return null;
        const chartData = addBarSharePct(ba.buckets, ['pre_orders', 'post_orders']);
        return (
          <div key={key} className="space-y-4">
            <div className="flex items-center gap-2">
              <PlatformLogo platform={key} size={18} />
              <h2 className="text-base font-semibold text-[var(--text)]">{label}</h2>
            </div>
            <div className="card">
              <h3 className="text-sm font-semibold text-[var(--text)] mb-4">Order Count by Ticket Size</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData} barGap={2} margin={{ top: 20, right: 4, left: 0, bottom: 0 }}>
                  <XAxis dataKey="range" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: 'var(--text-subtle)' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    formatter={(v, name, props) => {
                      const pctKey = `${props?.dataKey}_pct`;
                      const pct = props?.payload?.[pctKey];
                      const count = fmt.int(v);
                      return pct != null && pct > 0 ? [`${count} (${Number(pct).toFixed(1)}% of orders)`, name] : [count, name];
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="pre_orders" name="Pre" fill="var(--border-strong)" radius={[3, 3, 0, 0]}>
                    <BarShareLabels dataKey="pre_orders" fill="var(--text-subtle)" />
                  </Bar>
                  <Bar dataKey="post_orders" name="Post" fill="var(--accent)" radius={[3, 3, 0, 0]}>
                    <BarShareLabels dataKey="post_orders" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h3 className="text-sm font-semibold text-[var(--text)] mb-1">Order Origin Mix — Pre vs Post</h3>
              <p className="text-[10px] text-[var(--text-subtle)] mb-4">
                Share of orders by origin. Δ is the change in share (percentage points) from Pre to Post.
                {key === 'ue' && (
                  <> Uber Eats: <strong>Promo</strong> = non-zero Offers on items; <strong>Ads</strong> = Marketing Adjustment (not Marketplace Fee, which is commission on most orders).</>
                )}
                {key === 'dd' && (
                  <> DoorDash: <strong>Promo</strong> = customer discounts; <strong>Ads</strong> = marketing fees on the order.</>
                )}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                <div className="grid grid-cols-2 gap-2">
                  {ba?.mixPre
                    ? <MixDonut title="Pre" mix={ba.mixPre} />
                    : <div className="flex items-center justify-center text-[10px] text-[var(--text-subtle)] py-8 text-center">Set a Pre period to compare</div>}
                  <MixDonut title="Post" mix={ba?.mix} />
                </div>
                <DataTable columns={mixChangeColumns} data={buildMixChange(ba?.mixPre, ba?.mix)} sortable={false} />
              </div>
            </div>

            <DataTable columns={columns} data={ba?.buckets || []} sortable={false} />
          </div>
        );
      })}
    </div>
  );
}
