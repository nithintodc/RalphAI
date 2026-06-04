import { useMemo, useState } from 'react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { fmt } from '../../lib/utils/formatters';

const METRICS = [
  { key: 'sales', label: 'Sales', render: (v) => fmt.usd(v || 0), precision: 0 },
  { key: 'payouts', label: 'Payouts', render: (v) => fmt.usd(v || 0), precision: 0 },
  { key: 'orders', label: 'Orders', render: (v) => fmt.int(v || 0), precision: 0 },
  { key: 'mktSpend', label: 'Marketing Spend', render: (v) => fmt.usd(v || 0), precision: 0 },
  { key: 'aov', label: 'AOV', render: (v) => fmt.usd2(v || 0), precision: 2 },
  { key: 'avg_payout', label: 'Avg Payout / Order', render: (v) => fmt.usd2(v || 0), precision: 2 },
  { key: 'profitability', label: 'Profitability %', render: (v) => fmt.pct(v || 0), precision: 2 },
];

function roundTo(v, precision = 0) {
  const n = Number(v || 0);
  if (!Number.isFinite(n)) return 0;
  const factor = 10 ** precision;
  return Math.round(n * factor) / factor;
}

function aggregateGroup(rows) {
  const totals = {
    pre_sales: 0, post_sales: 0, postLY_sales: 0,
    pre_payouts: 0, post_payouts: 0, postLY_payouts: 0,
    pre_orders: 0, post_orders: 0, postLY_orders: 0,
    pre_mktSpend: 0, post_mktSpend: 0, postLY_mktSpend: 0,
  };
  for (const r of rows) {
    totals.pre_sales += r.pre_sales || 0;
    totals.post_sales += r.post_sales || 0;
    totals.postLY_sales += r.postLY_sales || 0;
    totals.pre_payouts += r.pre_payouts || 0;
    totals.post_payouts += r.post_payouts || 0;
    totals.postLY_payouts += r.postLY_payouts || 0;
    totals.pre_orders += r.pre_orders || 0;
    totals.post_orders += r.post_orders || 0;
    totals.postLY_orders += r.postLY_orders || 0;
    totals.pre_mktSpend += r.pre_mktSpend || 0;
    totals.post_mktSpend += r.post_mktSpend || 0;
    totals.postLY_mktSpend += r.postLY_mktSpend || 0;
  }
  const preOrders = totals.pre_orders || 0;
  const postOrders = totals.post_orders || 0;
  const postLyOrders = totals.postLY_orders || 0;
  const preSales = totals.pre_sales || 0;
  const postSales = totals.post_sales || 0;
  const postLySales = totals.postLY_sales || 0;
  const prePayouts = totals.pre_payouts || 0;
  const postPayouts = totals.post_payouts || 0;
  const postLyPayouts = totals.postLY_payouts || 0;
  return {
    sales: { pre: totals.pre_sales, post: totals.post_sales, postLY: totals.postLY_sales },
    payouts: { pre: totals.pre_payouts, post: totals.post_payouts, postLY: totals.postLY_payouts },
    orders: { pre: totals.pre_orders, post: totals.post_orders, postLY: totals.postLY_orders },
    mktSpend: { pre: totals.pre_mktSpend, post: totals.post_mktSpend, postLY: totals.postLY_mktSpend },
    aov: {
      pre: preOrders ? preSales / preOrders : 0,
      post: postOrders ? postSales / postOrders : 0,
      postLY: postLyOrders ? postLySales / postLyOrders : 0,
    },
    avg_payout: {
      pre: preOrders ? prePayouts / preOrders : 0,
      post: postOrders ? postPayouts / postOrders : 0,
      postLY: postLyOrders ? postLyPayouts / postLyOrders : 0,
    },
    profitability: {
      pre: preSales ? (prePayouts / preSales) * 100 : 0,
      post: postSales ? (postPayouts / postSales) * 100 : 0,
      postLY: postLySales ? (postLyPayouts / postLySales) * 100 : 0,
    },
  };
}

export default function AbComparisonScreen() {
  const combined = useDataStore((s) => s.storeTables?.combined || []);
  const tagMap = useConfigStore((s) => s.storeTagMap || {});
  const [leftTag, setLeftTag] = useState('A');
  const [rightTag, setRightTag] = useState('B');

  const tags = useMemo(
    () => [...new Set(Object.values(tagMap).map((t) => String(t || '').trim()).filter(Boolean))].sort(),
    [tagMap],
  );

  const taggedRows = useMemo(
    () => combined.map((r) => ({ ...r, _tag: String(tagMap[r.storeId] || '').trim() })).filter((r) => r._tag),
    [combined, tagMap],
  );

  const leftRows = useMemo(() => taggedRows.filter((r) => r._tag === leftTag), [taggedRows, leftTag]);
  const rightRows = useMemo(() => taggedRows.filter((r) => r._tag === rightTag), [taggedRows, rightTag]);
  const taggedCounts = useMemo(() => {
    const out = {};
    for (const t of Object.values(tagMap)) {
      const key = String(t || '').trim();
      if (!key) continue;
      out[key] = (out[key] || 0) + 1;
    }
    return out;
  }, [tagMap]);

  const leftAgg = useMemo(() => aggregateGroup(leftRows), [leftRows]);
  const rightAgg = useMemo(() => aggregateGroup(rightRows), [rightRows]);

  const pct = (a, b) => (a ? ((b - a) / a) * 100 : 0);
  const data = useMemo(() => METRICS.map((m) => {
    const left = leftAgg[m.key] || { pre: 0, post: 0, postLY: 0 };
    const right = rightAgg[m.key] || { pre: 0, post: 0, postLY: 0 };
    const leftPvpPct = pct(left.pre, left.post);
    const rightPvpPct = pct(right.pre, right.post);
    const leftYoyPct = pct(left.postLY, left.post);
    const rightYoyPct = pct(right.postLY, right.post);
    return {
      metric: m.label,
      leftPre: roundTo(left.pre, m.precision),
      leftPost: roundTo(left.post, m.precision),
      rightPre: roundTo(right.pre, m.precision),
      rightPost: roundTo(right.post, m.precision),
      leftPvpPct: roundTo(leftPvpPct, 1),
      rightPvpPct: roundTo(rightPvpPct, 1),
      growthGap: roundTo(leftPvpPct - rightPvpPct, 1),
      leftYoyPct: roundTo(leftYoyPct, 1),
      rightYoyPct: roundTo(rightYoyPct, 1),
      yoyGap: roundTo(leftYoyPct - rightYoyPct, 1),
      preDelta: roundTo((left.pre || 0) - (right.pre || 0), m.precision),
      postDelta: roundTo((left.post || 0) - (right.post || 0), m.precision),
      m,
    };
  }), [leftAgg, rightAgg]);

  const storeLevelRows = useMemo(
    () => taggedRows.filter((r) => r._tag === leftTag || r._tag === rightTag).map((r) => ({
      tag: r._tag,
      storeId: r.storeId,
      post_sales: r.post_sales || 0,
      sales_growth_pct: r.sales_growth_pct || 0,
      sales_yoy_pct: r.sales_yoy_pct || 0,
      post_orders: r.post_orders || 0,
      post_payouts: r.post_payouts || 0,
      post_aov: r.post_aov || 0,
    })),
    [taggedRows, leftTag, rightTag],
  );

  if (!tags.length) {
    return <div className="card text-sm text-[var(--text-muted)]">No store tags found. Add Tag values in Config → store map first.</div>;
  }

  const columns = [
    { key: 'metric', label: 'Metric', sortable: false },
    { key: 'leftPre', label: `${leftTag} Pre`, align: 'right', render: (v, r) => r.m.render(v) },
    { key: 'leftPost', label: `${leftTag} Post`, align: 'right', render: (v, r) => r.m.render(v) },
    { key: 'rightPre', label: `${rightTag} Pre`, align: 'right', render: (v, r) => r.m.render(v) },
    { key: 'rightPost', label: `${rightTag} Post`, align: 'right', render: (v, r) => r.m.render(v) },
    { key: 'leftPvpPct', label: `${leftTag} PvP%`, align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'rightPvpPct', label: `${rightTag} PvP%`, align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'growthGap', label: 'PvP Gap', align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'leftYoyPct', label: `${leftTag} YoY%`, align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'rightYoyPct', label: `${rightTag} YoY%`, align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'yoyGap', label: 'YoY Gap', align: 'right', delta: true, render: (v) => fmt.delta(v) },
    { key: 'preDelta', label: 'Pre Δ', align: 'right', delta: true, render: (v, r) => r.m.render(v) },
    { key: 'postDelta', label: 'Post Δ', align: 'right', delta: true, render: (v, r) => r.m.render(v) },
  ];

  const storeColumns = [
    { key: 'tag', label: 'Tag', sortable: true },
    { key: 'storeId', label: 'Store', sortable: true },
    { key: 'post_sales', label: 'Sales (Post)', align: 'right', sortable: true, render: (v) => fmt.usd(v) },
    { key: 'sales_growth_pct', label: 'Sales PvP %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v) },
    { key: 'sales_yoy_pct', label: 'Sales YoY %', align: 'right', sortable: true, delta: true, render: (v) => fmt.delta(v) },
    { key: 'post_orders', label: 'Orders (Post)', align: 'right', sortable: true, render: (v) => fmt.int(v) },
    { key: 'post_payouts', label: 'Payouts (Post)', align: 'right', sortable: true, render: (v) => fmt.usd(v) },
    { key: 'post_aov', label: 'AOV (Post)', align: 'right', sortable: true, render: (v) => fmt.usd2(v) },
  ];

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-xs text-[var(--text-muted)]">Compare groups</div>
          <select value={leftTag} onChange={(e) => setLeftTag(e.target.value)} className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--surface)] text-xs">
            {tags.map((t) => <option key={`l-${t}`} value={t}>{t}</option>)}
          </select>
          <span className="text-xs text-[var(--text-subtle)]">vs</span>
          <select value={rightTag} onChange={(e) => setRightTag(e.target.value)} className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--surface)] text-xs">
            {tags.map((t) => <option key={`r-${t}`} value={t}>{t}</option>)}
          </select>
          <span className="text-xs text-[var(--text-subtle)] ml-auto">
            {leftTag}: {taggedCounts[leftTag] || 0} tagged ({leftRows.length} in analysis) · {rightTag}: {taggedCounts[rightTag] || 0} tagged ({rightRows.length} in analysis)
          </span>
        </div>
      </div>
      <SplitDataTable
        columns={columns}
        data={data}
        sortable={false}
        dense
        splitAt={4}
        chunkTitles={['Group values', 'Pre vs Post growth', 'YoY and deltas']}
      />
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--text)] mb-2">Store-level breakdown ({leftTag}/{rightTag})</h3>
        <SplitDataTable columns={storeColumns} data={storeLevelRows} maxHeight="420px" dense />
      </div>
    </div>
  );
}
