// Order buckets screen — order count by ticket size, Pre vs Post

function ScreenBuckets() {
  const data = window.BUCKETS;
  const totalPre  = data.reduce((s, b) => s + b.pre, 0);
  const totalPost = data.reduce((s, b) => s + b.post, 0);

  // Bucket category summary
  const small = data.slice(0, 4); // $0-$20
  const mid   = data.slice(4, 8); // $21-$40
  const high  = data.slice(8);    // $41+
  const sum = arr => ({
    pre: arr.reduce((s, b) => s + b.pre, 0),
    post: arr.reduce((s, b) => s + b.post, 0),
  });
  const ss = sum(small), mm = sum(mid), hh = sum(high);

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Order-count buckets</h1>
          <div className="page-sub">How many orders fall in each ticket-size band · Pre vs Post</div>
        </div>
        <div className="row">
          <div className="tab-row">
            <button className="tab active">Order count</button>
            <button className="tab">% of total</button>
            <button className="tab">$ sales</button>
          </div>
          <button className="chip"><I.Export /> Export</button>
        </div>
      </div>

      {/* Summary tier strip */}
      <div className="grid-12">
        <TierCard label="Small tickets · $0–$20" pre={ss.pre} post={ss.post} hint="4 buckets" color="#A78BFA" />
        <TierCard label="Mid tickets · $21–$40"  pre={mm.pre} post={mm.post} hint="4 buckets" color="var(--accent)" />
        <TierCard label="Large tickets · $41+"   pre={hh.pre} post={hh.post} hint="3 buckets" color="#F59E0B" />
      </div>

      {/* Chart */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <h3 className="card-title">Orders by ticket-size band</h3>
            <div className="card-sub">All 11 buckets · Δ% printed below each pair</div>
          </div>
          <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span><i style={{display:'inline-block',width:10,height:8,background:'var(--surface-3)',verticalAlign:'middle',marginRight:6,borderRadius:2}}/>Pre · {window.fmt.int(totalPre)}</span>
            <span style={{ marginLeft: 14 }}><i style={{display:'inline-block',width:10,height:8,background:'var(--accent)',verticalAlign:'middle',marginRight:6,borderRadius:2}}/>Post · {window.fmt.int(totalPost)}</span>
          </div>
        </div>
        <window.BucketChart data={data} h={320} />
      </div>

      {/* Bucket table */}
      <div className="card" style={{ padding: 0, marginTop: 16 }}>
        <div className="card-head" style={{ padding: '14px 16px 12px', marginBottom: 0 }}>
          <div>
            <h3 className="card-title">Per-bucket Pre vs Post</h3>
            <div className="card-sub">Order count + share of total + Δ% — every bucket</div>
          </div>
        </div>
        <div className="scroll-x">
          <table className="dt">
            <thead>
              <tr>
                <th>Bucket</th>
                <th className="num">Pre orders</th>
                <th className="num">% Pre</th>
                <th className="num">Post orders</th>
                <th className="num">% Post</th>
                <th className="num">Δ orders</th>
                <th className="num">Δ%</th>
                <th>Share shift</th>
              </tr>
            </thead>
            <tbody>
              {data.map(b => {
                const dOrders = b.post - b.pre;
                const dPct    = (dOrders / b.pre) * 100;
                const sharePre  = (b.pre / totalPre) * 100;
                const sharePost = (b.post / totalPost) * 100;
                const shareShift = sharePost - sharePre;
                return (
                  <tr key={b.range}>
                    <td className="strong tnum">{b.range}</td>
                    <td className="num tnum">{window.fmt.int(b.pre)}</td>
                    <td className="num muted tnum">{sharePre.toFixed(1)}%</td>
                    <td className="num tnum strong">{window.fmt.int(b.post)}</td>
                    <td className="num muted tnum">{sharePost.toFixed(1)}%</td>
                    <td className="num"><window.DeltaCell abs={dOrders} pct={dPct} absFmt="int" /></td>
                    <td className="num"><window.Delta value={dPct} /></td>
                    <td style={{ minWidth: 140 }}>
                      <ShareShiftBar value={shareShift} />
                    </td>
                  </tr>
                );
              })}
              <tr style={{ background: 'var(--surface-2)' }}>
                <td className="strong">Total</td>
                <td className="num tnum strong">{window.fmt.int(totalPre)}</td>
                <td className="num muted tnum">100.0%</td>
                <td className="num tnum strong">{window.fmt.int(totalPost)}</td>
                <td className="num muted tnum">100.0%</td>
                <td className="num"><window.DeltaCell abs={totalPost - totalPre} pct={((totalPost - totalPre) / totalPre) * 100} absFmt="int" /></td>
                <td className="num"><window.Delta value={((totalPost - totalPre) / totalPre) * 100} /></td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Mix shift visualization */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-6">
          <div className="card-head">
            <h3 className="card-title">Mix shift Pre → Post</h3>
            <div className="card-sub">Where is the mix moving?</div>
          </div>
          <div className="stack-2">
            {data.map(b => {
              const sharePre = (b.pre / totalPre) * 100;
              const sharePost = (b.post / totalPost) * 100;
              const shift = sharePost - sharePre;
              return (
                <div key={b.range} className="row" style={{ gap: 10 }}>
                  <div style={{ width: 56, fontSize: 12, color: 'var(--text-muted)' }} className="tnum">{b.range}</div>
                  <div style={{ flex: 1, position: 'relative', height: 18, background: 'var(--surface-2)', borderRadius: 4 }}>
                    <div style={{ position: 'absolute', left: 0, top: 0, height: 18, width: `${sharePre}%`, background: 'var(--surface-3)', borderRadius: 4 }} />
                    <div style={{ position: 'absolute', left: 0, top: 4, height: 10, width: `${sharePost}%`, background: 'var(--accent)', borderRadius: 4 }} />
                  </div>
                  <div className={`delta-inline tnum ${shift >= 0 ? 'up' : 'down'}`} style={{ width: 60, textAlign: 'right' }}>
                    {(shift >= 0 ? '+' : '')}{shift.toFixed(2)}pp
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card col-6">
          <div className="card-head">
            <h3 className="card-title">AOV implications</h3>
            <div className="card-sub">Bigger basket share rose</div>
          </div>
          <div className="stack-3">
            <ImplicationRow tone="up"
              title="$50+ orders grew faster than total"
              detail="+24.1% vs +8.4% overall — premium menu mix improving" />
            <ImplicationRow tone="up"
              title="Mid-tier ($21–$40) stable share"
              detail="51.3% → 51.0% of orders — core band intact" />
            <ImplicationRow tone="down"
              title="Small tickets ($0–$15) losing share"
              detail="−0.7pp share — fewer single-item orders" />
            <ImplicationRow tone="info"
              title="AOV moved +$0.60 Pre→Post"
              detail="Driven by basket-size shift, not item prices" />
          </div>
        </div>
      </div>
    </>
  );
}

function TierCard({ label, pre, post, hint, color }) {
  const d = post - pre;
  const pct = (d / pre) * 100;
  return (
    <div className="card" style={{ gridColumn: 'span 4', padding: 14 }}>
      <div className="row between" style={{ marginBottom: 6 }}>
        <span className="kpi-label">{label}</span>
        <span className="dot" style={{ background: color }} />
      </div>
      <div className="kpi-value">{window.fmt.int(post)}</div>
      <div className="kpi-foot">
        <window.DeltaCell abs={d} pct={pct} absFmt="int" />
        <span className="subtle">{hint}</span>
      </div>
    </div>
  );
}

function ShareShiftBar({ value }) {
  const max = 2; // pp scale
  const pct = Math.min(1, Math.abs(value) / max);
  const w = pct * 50; // 50% each side
  return (
    <div style={{ position: 'relative', height: 16, background: 'var(--surface-2)', borderRadius: 4 }}>
      <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--border-strong)' }} />
      {value >= 0 ? (
        <div style={{ position: 'absolute', left: '50%', top: 2, bottom: 2, width: `${w}%`, background: 'var(--accent)', borderRadius: '0 4px 4px 0' }} />
      ) : (
        <div style={{ position: 'absolute', right: '50%', top: 2, bottom: 2, width: `${w}%`, background: 'var(--negative)', borderRadius: '4px 0 0 4px' }} />
      )}
      <div style={{ position: 'absolute', right: 4, top: 1, fontSize: 10, color: 'var(--text-muted)' }} className="tnum">
        {value >= 0 ? '+' : ''}{value.toFixed(2)}pp
      </div>
    </div>
  );
}

function ImplicationRow({ tone, title, detail }) {
  const Tone = tone === 'up' ? I.Up : tone === 'down' ? I.Down : I.Info;
  const c = tone === 'up' ? { bg: 'var(--positive-soft)', fg: 'var(--positive)' }
          : tone === 'down' ? { bg: 'var(--negative-soft)', fg: 'var(--negative)' }
          : { bg: 'var(--info-soft)', fg: 'var(--info)' };
  return (
    <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
      <div style={{ width: 26, height: 26, borderRadius: 6, background: c.bg, color: c.fg, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
        <Tone />
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{title}</div>
        <div className="muted" style={{ fontSize: 12 }}>{detail}</div>
      </div>
    </div>
  );
}

window.ScreenBuckets = ScreenBuckets;
