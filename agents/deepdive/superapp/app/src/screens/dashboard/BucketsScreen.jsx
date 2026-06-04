import { useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { PieChart, Pie, Cell } from 'recharts';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import { buildBucketAnalysis, buildOrderOriginMix } from '../../lib/engine/buckets';
import { fmt } from '../../lib/utils/formatters';
import { DATA_PLATFORM_SECTIONS } from '../../lib/platforms';

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
        return (
          <div key={key} className="space-y-4">
            <div className="flex items-center gap-2">
              <span className={`platform-dot ${key}`} />
              <h2 className="text-base font-semibold text-[var(--text)]">{label}</h2>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="card col-span-2">
                <h3 className="text-sm font-semibold text-[var(--text)] mb-4">Order Count by Ticket Size</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={ba?.buckets || []} barGap={2}>
                    <XAxis dataKey="range" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: 'var(--text-subtle)' }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="pre_orders" name="Pre" fill="var(--border-strong)" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="post_orders" name="Post" fill="var(--accent)" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="card">
                <h3 className="text-sm font-semibold text-[var(--text)] mb-4">Order Origin Mix (Post)</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={ba?.mix || []} dataKey="value" nameKey="label" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2}>
                      {(ba?.mix || []).map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} formatter={(v) => v + '%'} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-1 mt-2">
                  {(ba?.mix || []).map(m => (
                    <div key={m.id} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ background: m.color }} />
                        {m.label}
                      </span>
                      <span className="tnum font-medium">{m.value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <DataTable columns={columns} data={ba?.buckets || []} sortable={false} />
          </div>
        );
      })}
    </div>
  );
}
