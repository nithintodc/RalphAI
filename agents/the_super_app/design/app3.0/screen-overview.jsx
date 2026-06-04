// Overview / Dashboard
// Hero KPIs + Sales trend Pre vs Post + Top movers + Snapshot widgets

function ScreenOverview({ t, onStoreClick }) {
  const heroIds = ['sales','orders','aov','prof'];
  const heroKpis = heroIds.map(id => window.KPIS.find(k => k.id === id));
  const restKpis = window.KPIS.filter(k => !heroIds.includes(k.id));

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Performance snapshot</h1>
          <div className="page-sub">
            <window.PeriodPill /> <span className="subtle" style={{ marginLeft: 12 }}>· Combined platforms · 46 stores</span>
          </div>
        </div>
        <div className="row">
          <span className="tag live"><span className="dot org" style={{ marginRight: 4 }} />Live data</span>
          <button className="chip ghost"><I.Reset /> Refresh</button>
        </div>
      </div>

      {/* Hero KPIs — 4 large with sparklines */}
      <div className="kpi-grid">
        {heroKpis.map(k => <window.KpiCard key={k.id} kpi={k} style={t.heroStyle} />)}
      </div>

      {/* Secondary KPI grid */}
      <div className="section-header">
        <h3 className="section-title">All metrics</h3>
        <span className="section-sub">Tap any card to drill in</span>
      </div>
      <div className="kpi-grid compact">
        {restKpis.map(k => <window.KpiCard key={k.id} kpi={k} style="numeric" />)}
      </div>

      {/* Trend + Origin Mix */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-8">
          <div className="card-head">
            <div>
              <h3 className="card-title">Sales trend</h3>
              <div className="card-sub">Daily — Post vs Pre vs Last Year Post</div>
            </div>
            <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              <span><i style={{display:'inline-block',width:10,height:2,background:'var(--accent)',verticalAlign:'middle',marginRight:6}}/>Post</span>
              <span style={{ marginLeft: 12 }}><i style={{display:'inline-block',width:10,height:2,background:'var(--text-subtle)',verticalAlign:'middle',marginRight:6}}/>Pre</span>
              <span style={{ marginLeft: 12 }}><i style={{display:'inline-block',width:10,borderTop:'1.5px dashed var(--text-subtle)',verticalAlign:'middle',marginRight:6}}/>LY Post</span>
            </div>
          </div>
          <window.TrendChart series={[
            { name: 'Pre',     data: window.TREND_PRE,  color: 'var(--text-subtle)', },
            { name: 'LY Post', data: window.TREND_LY,   color: 'var(--text-subtle)', dashed: true },
            { name: 'Post',    data: window.TREND_POST, color: 'var(--accent)', bold: true, fill: true },
          ]} />
        </div>

        <div className="card col-4">
          <div className="card-head">
            <div>
              <h3 className="card-title">Order origin mix</h3>
              <div className="card-sub">Post period · % of orders</div>
            </div>
            <button className="icon-btn"><I.More /></button>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
            <window.Donut data={window.ORIGIN_MIX} />
          </div>
          <div className="stack-2">
            {window.ORIGIN_MIX.map(o => (
              <div key={o.id} className="row between" style={{ padding: '4px 0' }}>
                <div className="row">
                  <span className="dot" style={{ background: o.color }} />
                  <span style={{ fontSize: 13 }}>{o.label}</span>
                </div>
                <span className="tnum" style={{ fontWeight: 500 }}>{o.value.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top movers */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-6">
          <div className="card-head">
            <div>
              <h3 className="card-title">Top movers ↑</h3>
              <div className="card-sub">Highest Pre→Post sales growth</div>
            </div>
            <button className="chip ghost">View all <I.ChevronRight /></button>
          </div>
          <MoverTable data={window.MOVERS.up} dir="up" onStoreClick={onStoreClick} />
        </div>
        <div className="card col-6">
          <div className="card-head">
            <div>
              <h3 className="card-title">Top movers ↓</h3>
              <div className="card-sub">Largest declines — investigate</div>
            </div>
            <button className="chip ghost">View all <I.ChevronRight /></button>
          </div>
          <MoverTable data={window.MOVERS.down} dir="down" onStoreClick={onStoreClick} />
        </div>
      </div>

      {/* Slot snapshot + AI insights */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-7">
          <div className="card-head">
            <div>
              <h3 className="card-title">Day × Slot heatmap</h3>
              <div className="card-sub">Sales mix · Post period · % of weekly peak</div>
            </div>
            <button className="chip ghost">Open Slots view <I.ChevronRight /></button>
          </div>
          <window.Heatmap data={window.HEATMAP} rowLabels={window.DAY_LABELS} colLabels={window.SLOT_LABELS} />
        </div>

        <div className="card col-5" style={{ background: 'linear-gradient(180deg, var(--accent-soft) 0%, var(--surface) 80%)', borderColor: 'var(--accent-soft-border)' }}>
          <div className="card-head">
            <div className="row">
              <div style={{ width: 24, height: 24, borderRadius: 6, background: 'var(--accent)', color: 'white', display: 'grid', placeItems: 'center' }}>
                <I.Sparkles />
              </div>
              <h3 className="card-title" style={{ marginLeft: 4 }}>Ralph insights</h3>
            </div>
            <span className="tag live">3 new</span>
          </div>
          <div className="stack-3">
            <InsightRow tone="up"
              title="Lunch slot drove 38% of the sales lift"
              body="Lunch sales grew $312K Pre→Post (+11.4%), led by Friday and Saturday lunch covers." />
            <InsightRow tone="down"
              title="Promo orders up, ROAS down"
              body="Promo spend rose +22.4% but ROAS fell to 6.42× (−3.2%). 4 campaigns are flagged as low-ROAS." />
            <InsightRow tone="info"
              title="3 stores account for 62% of decline"
              body="Sunset, Outer Richmond, and Excelsior — review locally." />
          </div>
        </div>
      </div>

      {/* Lower row: bucket distribution + scatter */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-7">
          <div className="card-head">
            <div>
              <h3 className="card-title">Order-count distribution by ticket size</h3>
              <div className="card-sub">Pre vs Post · all 11 buckets</div>
            </div>
            <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              <span><i style={{display:'inline-block',width:10,height:8,background:'var(--surface-3)',verticalAlign:'middle',marginRight:6,borderRadius:2}}/>Pre</span>
              <span style={{ marginLeft: 10 }}><i style={{display:'inline-block',width:10,height:8,background:'var(--accent)',verticalAlign:'middle',marginRight:6,borderRadius:2}}/>Post</span>
            </div>
          </div>
          <window.BucketChart data={window.BUCKETS} />
        </div>

        <div className="card col-5">
          <div className="card-head">
            <div>
              <h3 className="card-title">ROAS vs Spend — by store</h3>
              <div className="card-sub">Bubble size = orders · color = growth direction</div>
            </div>
            <button className="icon-btn"><I.More /></button>
          </div>
          <window.Scatter data={window.SCATTER} h={300} />
        </div>
      </div>
    </>
  );
}

function MoverTable({ data, dir, onStoreClick }) {
  return (
    <div className="scroll-x">
      <table className="dt">
        <thead>
          <tr>
            <th>Store</th>
            <th className="num">Sales</th>
            <th className="num">Δ</th>
            <th className="num">Δ%</th>
          </tr>
        </thead>
        <tbody>
          {data.map(s => {
            const delta = Math.round(s.sales * (s.growth / 100));
            return (
              <tr key={s.id} onClick={onStoreClick} style={{ cursor: 'pointer' }}>
                <td>
                  <div className="row">
                    <div style={{ width: 24, height: 24, background: 'var(--surface-2)', borderRadius: 6, display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>
                      {s.name.slice(0,2).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontWeight: 500 }}>{s.name}</div>
                      <div className="muted" style={{ fontSize: 11 }}>{s.id} · {s.region}</div>
                    </div>
                  </div>
                </td>
                <td className="num strong">{window.fmt.usd(s.sales)}</td>
                <td className="num"><span className={`delta-inline ${delta >= 0 ? 'up' : 'down'}`}>{delta >= 0 ? '+' : '−'}${Math.abs(delta).toLocaleString('en-US')}</span></td>
                <td className="num"><window.Delta value={s.growth} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function InsightRow({ tone, title, body }) {
  const c = tone === 'up' ? 'var(--positive)' : tone === 'down' ? 'var(--negative)' : 'var(--info)';
  return (
    <div className="row" style={{ alignItems: 'flex-start', gap: 10, padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: c, marginTop: 8 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{title}</div>
        <div className="muted" style={{ fontSize: 12 }}>{body}</div>
      </div>
    </div>
  );
}

window.ScreenOverview = ScreenOverview;
