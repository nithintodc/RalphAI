// Pre vs Post — the main analysis view.
// Summary tables for Combined / DD / UE. Every comparison shows Δ and Δ%.

const SUMMARY_METRICS = [
  { key: 'sales',   label: 'Sales',           fmt: 'usd',  pre: 4438120, post: 4812340, preLY: 4096220, postLY: 4214120 },
  { key: 'payouts', label: 'Payouts',         fmt: 'usd',  pre: 2933280, post: 3142820, preLY: 2701620, postLY: 2785020 },
  { key: 'orders',  label: 'Orders',          fmt: 'int',  pre: 158420,  post: 168204,  preLY: 148820,  postLY: 153720 },
  { key: 'nc',      label: 'New customers',   fmt: 'int',  pre: 17560,   post: 18412,   preLY: 15820,   postLY: 16860 },
  { key: 'prof',    label: 'Profitability',   fmt: 'pct',  pre: 66.1,    post: 65.3,    preLY: 65.9,    postLY: 66.1, isPp: true },
  { key: 'aov',     label: 'Average check',   fmt: 'usd1', pre: 28.01,   post: 28.61,   preLY: 27.52,   postLY: 27.41 },
  { key: 'promo',   label: 'Promo spend',     fmt: 'usd',  pre: 255180,  post: 312440,  preLY: 198440,  postLY: 232940 },
  { key: 'ads',     label: 'Ads spend',       fmt: 'usd',  pre: 165020,  post: 184220,  preLY: 142220,  postLY: 155840 },
  { key: 'corp',    label: 'Corp spend',      fmt: 'usd',  pre: 168240,  post: 192220,  preLY: 142180,  postLY: 158420 },
  { key: 'todc',    label: 'TODC spend',      fmt: 'usd',  pre: 251960,  post: 304440,  preLY: 198480,  postLY: 230360 },
  { key: 'roas',    label: 'ROAS',            fmt: 'x',    pre: 6.64,    post: 6.42,    preLY: 7.06,    postLY: 6.78 },
  { key: 'cpo',     label: 'Cost / order',    fmt: 'usd1', pre: 2.65,    post: 2.96,    preLY: 2.29,    postLY: 2.53 },
];

// Platform-level scale factors (Combined = DD + UE)
const DD_SCALE = 0.68;
const UE_SCALE = 0.32;

function scaleRow(row, scale) {
  if (row.fmt === 'pct') return { ...row, pre: row.pre - (1 - scale) * 0.3, post: row.post - (1 - scale) * 0.5, preLY: row.preLY - 0.2, postLY: row.postLY - 0.4 };
  if (row.fmt === 'usd1' || row.fmt === 'x') return { ...row, pre: row.pre * (0.96 + scale * 0.04), post: row.post * (0.96 + scale * 0.04), preLY: row.preLY * (0.96 + scale * 0.04), postLY: row.postLY * (0.96 + scale * 0.04) };
  return { ...row, pre: row.pre * scale, post: row.post * scale, preLY: row.preLY * scale, postLY: row.postLY * scale };
}

function ScreenCompare({ t }) {
  const [view, setView] = React.useState('prepost'); // prepost | yoy | both

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Pre vs Post comparison</h1>
          <div className="page-sub">Every metric — Pre, Post, Δ absolute, Δ%</div>
        </div>

        <div className="row">
          <div className="tab-row">
            {[
              { id: 'prepost', label: 'Pre vs Post' },
              { id: 'yoy',     label: 'YoY' },
              { id: 'both',    label: 'Both side-by-side' },
            ].map(o => (
              <button key={o.id} className={`tab ${view === o.id ? 'active' : ''}`} onClick={() => setView(o.id)}>{o.label}</button>
            ))}
          </div>
          <button className="chip"><I.Export /> Export</button>
        </div>
      </div>

      {/* Period summary strip */}
      <div className="card" style={{ padding: 12, marginBottom: 16 }}>
        <div className="row" style={{ gap: 24, flexWrap: 'wrap' }}>
          <PeriodChunk label="Pre" range={`${window.PERIOD.pre.start} – ${window.PERIOD.pre.end}`} days={31} />
          <PeriodChunk label="Post" range={`${window.PERIOD.post.start} – ${window.PERIOD.post.end}`} days={28} highlight />
          <PeriodChunk label="LY Pre" range={`${window.PERIOD.preLY.start} – ${window.PERIOD.preLY.end}`} days={31} subtle />
          <PeriodChunk label="LY Post" range={`${window.PERIOD.postLY.start} – ${window.PERIOD.postLY.end}`} days={28} subtle />
          <div style={{ flex: 1 }} />
          <div className="row" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            <I.Info />
            <span>Excluded: <span className="tnum">Jan 15, 2026</span>, <span className="tnum">Jan 20, 2026</span></span>
          </div>
        </div>
      </div>

      <CompareTable title="Combined — DoorDash + UberEats" subtitle="46 active stores" rows={SUMMARY_METRICS} view={view} platform="all" />
      <div style={{ height: 16 }} />
      <div className="grid-12">
        <div className="col-6">
          <CompareTable title="DoorDash" subtitle="41 active stores" tag={<span className="tag dd"><span className="dot dd" />DD</span>} rows={SUMMARY_METRICS.map(r => scaleRow(r, DD_SCALE))} view={view} compact platform="dd" />
        </div>
        <div className="col-6">
          <CompareTable title="UberEats" subtitle="38 active stores" tag={<span className="tag ue"><span className="dot ue" />UE</span>} rows={SUMMARY_METRICS.filter(r => r.key !== 'nc').map(r => scaleRow(r, UE_SCALE))} view={view} compact platform="ue" />
        </div>
      </div>

      {/* Trend chart at the bottom for visual context */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <h3 className="card-title">Daily sales — Pre, Post, LY Post</h3>
            <div className="card-sub">Visual context for the table above</div>
          </div>
          <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span><i style={{display:'inline-block',width:10,height:2,background:'var(--accent)',verticalAlign:'middle',marginRight:6}}/>Post</span>
            <span style={{ marginLeft: 12 }}><i style={{display:'inline-block',width:10,height:2,background:'var(--text-subtle)',verticalAlign:'middle',marginRight:6}}/>Pre</span>
            <span style={{ marginLeft: 12 }}><i style={{display:'inline-block',width:10,borderTop:'1.5px dashed var(--text-subtle)',verticalAlign:'middle',marginRight:6}}/>LY Post</span>
          </div>
        </div>
        <window.TrendChart
          series={[
            { name: 'Pre',     data: window.TREND_PRE,  color: 'var(--text-subtle)' },
            { name: 'LY Post', data: window.TREND_LY,   color: 'var(--text-subtle)', dashed: true },
            { name: 'Post',    data: window.TREND_POST, color: 'var(--accent)', bold: true, fill: true },
          ]}
          h={260}
        />
      </div>
    </>
  );
}

function PeriodChunk({ label, range, days, highlight, subtle }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 11, color: 'var(--text-subtle)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 3, fontWeight: 500 }}>
        {label}
      </div>
      <div className="tnum" style={{ fontSize: 13, fontWeight: highlight ? 600 : 500, color: subtle ? 'var(--text-muted)' : 'var(--text)', whiteSpace: 'nowrap' }}>{range}</div>
      <div className="muted tnum" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{days} days</div>
    </div>
  );
}

function CompareTable({ title, subtitle, tag, rows, view, compact, platform }) {
  const showPP = view === 'prepost' || view === 'both';
  const showYOY = view === 'yoy' || view === 'both';
  return (
    <div className="card" style={{ padding: 0 }}>
      <div className="card-head" style={{ padding: '16px 16px 12px', marginBottom: 0 }}>
        <div>
          <h3 className="card-title">
            {title} {tag && <span style={{ marginLeft: 6 }}>{tag}</span>}
          </h3>
          <div className="card-sub">{subtitle}</div>
        </div>
        <button className="chip ghost"><I.More /></button>
      </div>
      <div className="scroll-x">
        <table className="dt">
          <thead>
            <tr>
              <th>Metric</th>
              {showPP && <>
                <th className="num">Pre</th>
                <th className="num">Post</th>
                <th className="num">Δ</th>
                <th className="num">Δ%</th>
                {!compact && <th className="num">LY Pre vs Post</th>}
              </>}
              {showYOY && <>
                <th className="num">LY Post</th>
                <th className="num">Post</th>
                <th className="num">YoY Δ</th>
                <th className="num">YoY Δ%</th>
              </>}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => {
              const delta = row.post - row.pre;
              const deltaPct = row.pre === 0 ? 0 : (delta / row.pre) * 100;
              const lyDelta = row.postLY - row.preLY;
              const yoyDelta = row.post - row.postLY;
              const yoyPct = row.postLY === 0 ? 0 : (yoyDelta / row.postLY) * 100;
              const fmt = window.formatValue;
              return (
                <tr key={row.key}>
                  <td className="strong">{row.label}</td>
                  {showPP && <>
                    <td className="num tnum">{fmt(row.pre, row.fmt)}</td>
                    <td className="num tnum strong">{fmt(row.post, row.fmt)}</td>
                    <td className="num"><window.DeltaCell abs={delta} pct={deltaPct} absFmt={absFmtFor(row)} /></td>
                    <td className="num"><window.Delta value={deltaPct} /></td>
                    {!compact && <td className="num tnum muted">{fmt(lyDelta, row.fmt)}</td>}
                  </>}
                  {showYOY && <>
                    <td className="num tnum muted">{fmt(row.postLY, row.fmt)}</td>
                    <td className="num tnum strong">{fmt(row.post, row.fmt)}</td>
                    <td className="num"><window.DeltaCell abs={yoyDelta} pct={yoyPct} absFmt={absFmtFor(row)} /></td>
                    <td className="num"><window.Delta value={yoyPct} /></td>
                  </>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function absFmtFor(row) {
  if (row.fmt === 'int') return 'int';
  if (row.fmt === 'pct') return 'pp';
  if (row.fmt === 'x') return 'pp';
  return 'usd';
}

window.ScreenCompare = ScreenCompare;
