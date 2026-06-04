// Diagnostics — why did sales change? Metric bridge, decomposition, exceptions.

function ScreenDiagnostics() {
  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Diagnostics</h1>
          <div className="page-sub">Why did the metrics move? · Pre → Post sales bridge</div>
        </div>
        <div className="row">
          <div className="tab-row">
            <button className="tab active">Sales</button>
            <button className="tab">Payouts</button>
            <button className="tab">Orders</button>
            <button className="tab">Profitability</button>
          </div>
          <button className="chip"><I.Export /> Export</button>
        </div>
      </div>

      {/* Headline numbers */}
      <div className="grid-12">
        <div className="card col-4" style={{ background: 'var(--surface-2)' }}>
          <div className="kpi-label">Pre sales</div>
          <div className="kpi-value">{window.fmt.usd(4438120)}</div>
          <div className="kpi-foot subtle">Jan 1 – Jan 31, 2026 · 31 days</div>
        </div>
        <div className="card col-4" style={{ borderColor: 'var(--accent-soft-border)', background: 'linear-gradient(180deg, var(--accent-soft) 0%, var(--surface) 60%)' }}>
          <div className="kpi-label">Post sales</div>
          <div className="kpi-value">{window.fmt.usd(4812340)}</div>
          <div className="kpi-foot">
            <window.DeltaCell abs={374220} pct={8.43} absFmt="usd" />
          </div>
        </div>
        <div className="card col-4">
          <div className="kpi-label">Net change explained</div>
          <div className="kpi-value">{window.fmt.usd(374220)}</div>
          <div className="kpi-foot subtle">8 drivers · 100% accounted for</div>
        </div>
      </div>

      {/* Waterfall */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <h3 className="card-title">Sales bridge — Pre → Post</h3>
            <div className="card-sub">Positive drivers in green, negative in red. Hover for assumptions.</div>
          </div>
          <button className="chip ghost"><I.Info /> Methodology</button>
        </div>
        <window.Waterfall data={window.WATERFALL} h={340} />
      </div>

      {/* Decomposition cards */}
      <div className="section-header" style={{ marginTop: 24 }}>
        <h3 className="section-title">Decomposition</h3>
        <span className="section-sub">Volume vs price · Margin vs scale</span>
      </div>

      <div className="grid-12">
        <DecompCard col="col-6"
          title="Sales change = Volume + AOV"
          subtitle="(post_orders − pre_orders) × pre_AOV  +  (post_AOV − pre_AOV) × post_orders"
          parts={[
            { label: 'Order volume effect', value: 232180,  share: 62, color: 'var(--accent)' },
            { label: 'AOV effect',          value: 142040,  share: 38, color: '#A78BFA' },
          ]}
          total={374220}
        />
        <DecompCard col="col-6"
          title="Payout change = Sales × Margin"
          subtitle="(post_sales − pre_sales) × pre_margin  +  (post_margin − pre_margin) × post_sales"
          parts={[
            { label: 'Sales effect',  value: 247420, share: 118, color: 'var(--accent)' },
            { label: 'Margin effect', value: -37880, share: -18, color: 'var(--negative)' },
          ]}
          total={209540}
        />
      </div>

      {/* Contribution by store + exceptions */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-7">
          <div className="card-head">
            <div>
              <h3 className="card-title">Top contributors to net change</h3>
              <div className="card-sub">Store-level Δ Sales sorted by absolute impact</div>
            </div>
            <span className="tag">11 of 46 = 78%</span>
          </div>
          <ContribTable />
        </div>

        <div className="card col-5">
          <div className="card-head">
            <div>
              <h3 className="card-title">Exceptions flagged</h3>
              <div className="card-sub">Patterns that warrant a closer look</div>
            </div>
            <span className="tag" style={{ background: 'var(--warning-soft)', color: 'var(--warning)', borderColor: 'transparent' }}>4</span>
          </div>
          <div className="stack-3">
            <ExceptionRow tone="warn"  title="Sales down, spend up"        n={3} body="Sunset, Excelsior, Outer Richmond" />
            <ExceptionRow tone="warn"  title="ROAS down, spend up"          n={4} body="DD promo spend +28% with ROAS −7%" />
            <ExceptionRow tone="info"  title="Orders up, AOV down"          n={6} body="Discount-heavy mix in 6 stores" />
            <ExceptionRow tone="neg"   title="Sales up, payouts down"       n={2} body="Higher commission/fee categories" />
          </div>
        </div>
      </div>

      {/* Percentile rank scatter */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <h3 className="card-title">Store performance percentile</h3>
            <div className="card-sub">ROAS vs Spend · top-right = scale + efficiency · color = growth</div>
          </div>
          <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            <span><span className="dot" style={{ background: 'var(--accent)' }} />Growing</span>
            <span style={{ marginLeft: 12 }}><span className="dot" style={{ background: 'var(--negative)' }} />Declining</span>
          </div>
        </div>
        <window.Scatter data={window.SCATTER} h={340} />
      </div>
    </>
  );
}

function DecompCard({ col, title, subtitle, parts, total }) {
  return (
    <div className={`card ${col}`}>
      <div className="card-head">
        <div>
          <h3 className="card-title">{title}</h3>
          <div className="card-sub mono" style={{ fontSize: 11 }}>{subtitle}</div>
        </div>
      </div>
      <div className="stack-3">
        {parts.map(p => (
          <div key={p.label}>
            <div className="row between" style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{p.label}</span>
              <span className="tnum" style={{ fontWeight: 500, color: p.value >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
                {p.value >= 0 ? '+' : '−'}{window.fmt.usd(Math.abs(p.value))} <span className="muted" style={{ fontWeight: 400 }}>· {p.share >= 0 ? '+' : ''}{p.share}%</span>
              </span>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${Math.min(100, Math.abs(p.share))}%`, background: p.color }} />
            </div>
          </div>
        ))}
        <hr className="divider" />
        <div className="row between">
          <span style={{ fontWeight: 600 }}>Net change</span>
          <span className="tnum" style={{ fontWeight: 600, color: total >= 0 ? 'var(--positive)' : 'var(--negative)' }}>
            {total >= 0 ? '+' : '−'}{window.fmt.usd(Math.abs(total))}
          </span>
        </div>
      </div>
    </div>
  );
}

function ContribTable() {
  // Top contributors — mix from STORES
  const contributors = window.STORES
    .map(s => ({ ...s, contrib: Math.round(s.sales * (s.growth / 100)) }))
    .sort((a, b) => Math.abs(b.contrib) - Math.abs(a.contrib))
    .slice(0, 12);
  const total = contributors.reduce((sum, s) => sum + Math.abs(s.contrib), 0);

  return (
    <div className="scroll-x">
      <table className="dt">
        <thead>
          <tr>
            <th>#</th>
            <th>Store</th>
            <th className="num">Δ Sales</th>
            <th className="num">Δ%</th>
            <th>Contribution</th>
            <th className="num">% of net</th>
          </tr>
        </thead>
        <tbody>
          {contributors.map((s, i) => {
            const pct = (Math.abs(s.contrib) / total) * 100;
            const up = s.contrib >= 0;
            return (
              <tr key={s.id}>
                <td className="muted tnum">{i + 1}</td>
                <td>
                  <div style={{ fontWeight: 500 }}>{s.name}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{s.id}</div>
                </td>
                <td className="num">
                  <span className={`delta-inline ${up ? 'up' : 'down'}`}>
                    {up ? '+' : '−'}${Math.abs(s.contrib).toLocaleString('en-US')}
                  </span>
                </td>
                <td className="num"><window.Delta value={s.growth} /></td>
                <td style={{ minWidth: 160 }}>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${pct}%`, background: up ? 'var(--accent)' : 'var(--negative)' }} />
                  </div>
                </td>
                <td className="num tnum">{pct.toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ExceptionRow({ tone, title, n, body }) {
  const colors = {
    warn: { bg: 'var(--warning-soft)', fg: 'var(--warning)' },
    info: { bg: 'var(--info-soft)',    fg: 'var(--info)' },
    neg:  { bg: 'var(--negative-soft)',fg: 'var(--negative)' },
  };
  const c = colors[tone] || colors.info;
  return (
    <div className="row" style={{ gap: 10, padding: '10px 12px', background: 'var(--surface-2)', borderRadius: 8 }}>
      <div style={{ width: 28, height: 28, background: c.bg, color: c.fg, borderRadius: 6, display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 600 }}>
        {n}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{title}</div>
        <div className="muted" style={{ fontSize: 12 }}>{body}</div>
      </div>
      <I.ChevronRight />
    </div>
  );
}

window.ScreenDiagnostics = ScreenDiagnostics;
