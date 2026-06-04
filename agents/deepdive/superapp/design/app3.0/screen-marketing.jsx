// Marketing screen — Corp vs TODC, campaigns, ROAS

function ScreenMarketing() {
  const { corp, todc } = window.MARKETING;
  const total = {
    orders: corp.orders + todc.orders,
    sales:  corp.sales  + todc.sales,
    spend:  corp.spend  + todc.spend,
  };
  total.roas = total.sales / total.spend;
  total.cpo  = total.spend / total.orders;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Marketing</h1>
          <div className="page-sub">Corporate vs TODC · ROAS · campaign performance · Post period only</div>
        </div>
        <div className="row">
          <div className="tab-row">
            <button className="tab active">Combined</button>
            <button className="tab"><span className="dot dd" />DoorDash</button>
            <button className="tab"><span className="dot ue" />UberEats</button>
          </div>
          <button className="chip"><I.Export /> Export</button>
        </div>
      </div>

      {/* Headline KPIs */}
      <div className="kpi-grid">
        <MktKpi label="Total spend" value={window.fmt.usd(total.spend)} deltaPct={17.2} deltaAbs={18640} tone="warn" />
        <MktKpi label="Marketing-driven sales" value={window.fmt.usd(total.sales)} deltaPct={14.8} deltaAbs={101400} tone="up" />
        <MktKpi label="ROAS"  value={`${total.roas.toFixed(2)}×`} deltaPct={-2.1} deltaAbs={-0.14} tone="down" abs="x" />
        <MktKpi label="Cost / order" value={`$${total.cpo.toFixed(2)}`} deltaPct={6.8} deltaAbs={0.30} tone="down" abs="usd1" />
      </div>

      {/* Corp vs TODC split */}
      <div className="card" style={{ marginTop: 16, padding: 0 }}>
        <div className="card-head" style={{ padding: '14px 16px 12px', marginBottom: 0 }}>
          <div>
            <h3 className="card-title">Corporate vs TODC</h3>
            <div className="card-sub">Operator-funded (TODC) vs platform-funded (Corp) marketing — Post period</div>
          </div>
          <span className="muted" style={{ fontSize: 12 }}>Source: Promotion + Sponsored Listing</span>
        </div>
        <div className="scroll-x">
          <table className="dt">
            <thead>
              <tr>
                <th>Source</th>
                <th className="num">Orders</th>
                <th className="num">Sales</th>
                <th className="num">Spend</th>
                <th className="num">ROAS</th>
                <th className="num">Cost / order</th>
                <th>% of spend</th>
              </tr>
            </thead>
            <tbody>
              <MktRow row={corp} total={total.spend} color="#A78BFA" />
              <MktRow row={todc} total={total.spend} color="var(--accent)" />
              <tr style={{ background: 'var(--surface-2)' }}>
                <td className="strong">Combined</td>
                <td className="num tnum strong">{window.fmt.int(total.orders)}</td>
                <td className="num tnum strong">{window.fmt.usd(total.sales)}</td>
                <td className="num tnum strong">{window.fmt.usd(total.spend)}</td>
                <td className="num strong">{total.roas.toFixed(2)}×</td>
                <td className="num strong">${total.cpo.toFixed(2)}</td>
                <td></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Scatter + donut */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-7">
          <div className="card-head">
            <div>
              <h3 className="card-title">ROAS vs Spend — by store</h3>
              <div className="card-sub">Identify low-ROAS spend concentrations</div>
            </div>
            <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              <span><span className="dot" style={{ background: 'var(--accent)' }} />Growing</span>
              <span style={{ marginLeft: 12 }}><span className="dot" style={{ background: 'var(--negative)' }} />Declining</span>
            </div>
          </div>
          <window.Scatter data={window.SCATTER} h={320} />
        </div>

        <div className="card col-5">
          <div className="card-head">
            <h3 className="card-title">Promo vs Ads mix</h3>
            <div className="card-sub">How spend is allocated</div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <window.Donut data={[
              { label: 'Promo (TODC)', value: 56, color: 'var(--accent)' },
              { label: 'Ads (TODC)',   value: 22, color: '#F59E0B' },
              { label: 'Promo (Corp)', value: 14, color: '#A78BFA' },
              { label: 'Ads (Corp)',   value: 8,  color: '#2563EB' },
            ]} />
          </div>
          <div className="stack-2">
            {[
              { label: 'Promo (TODC)', value: 56, color: 'var(--accent)' },
              { label: 'Ads (TODC)',   value: 22, color: '#F59E0B' },
              { label: 'Promo (Corp)', value: 14, color: '#A78BFA' },
              { label: 'Ads (Corp)',   value: 8,  color: '#2563EB' },
            ].map(p => (
              <div key={p.label} className="row between" style={{ padding: '4px 0' }}>
                <div className="row">
                  <span className="dot" style={{ background: p.color }} />
                  <span style={{ fontSize: 13 }}>{p.label}</span>
                </div>
                <span className="tnum" style={{ fontWeight: 500 }}>{p.value.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Campaigns table */}
      <div className="card" style={{ padding: 0, marginTop: 16 }}>
        <div className="card-head" style={{ padding: '14px 16px 12px', marginBottom: 0 }}>
          <div>
            <h3 className="card-title">Campaign performance</h3>
            <div className="card-sub">{window.CAMPAIGNS.length} campaigns · sorted by spend</div>
          </div>
          <div className="row">
            <button className="chip ghost">All sources <I.ChevronDown /></button>
            <button className="chip ghost">All status <I.ChevronDown /></button>
          </div>
        </div>
        <div className="scroll-x">
          <table className="dt">
            <thead>
              <tr>
                <th>Campaign</th>
                <th>Source</th>
                <th>Platform</th>
                <th className="num">Orders</th>
                <th className="num">Sales</th>
                <th className="num">Spend</th>
                <th className="num">ROAS</th>
                <th className="num">Cost / order</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {window.CAMPAIGNS.map(c => (
                <tr key={c.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{c.name}</div>
                    <div className="muted tnum" style={{ fontSize: 11 }}>{c.id}</div>
                  </td>
                  <td><span className="tag">{c.source}</span></td>
                  <td><span className={`tag ${c.platform.toLowerCase()}`}><span className={`dot ${c.platform.toLowerCase()}`} />{c.platform}</span></td>
                  <td className="num tnum">{window.fmt.int(c.orders)}</td>
                  <td className="num tnum strong">{window.fmt.usd(c.sales)}</td>
                  <td className="num tnum">{window.fmt.usd(c.spend)}</td>
                  <td className="num">
                    <span className="tnum" style={{ fontWeight: 500, color: c.roas >= 6 ? 'var(--positive)' : c.roas >= 5 ? 'var(--text)' : 'var(--negative)' }}>
                      {c.roas.toFixed(2)}×
                    </span>
                  </td>
                  <td className="num tnum">${(c.spend / c.orders).toFixed(2)}</td>
                  <td>
                    <span className={`tag ${c.status === 'live' ? 'live' : ''}`} style={
                      c.status === 'paused' ? { background: 'var(--warning-soft)', color: 'var(--warning)', borderColor: 'transparent' } :
                      c.status === 'ended'  ? {} :
                      {}
                    }>
                      {c.status === 'live' && <span className="dot" style={{ width: 6, height: 6, background: 'var(--positive)', marginRight: 4 }} />}
                      {c.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function MktKpi({ label, value, deltaPct, deltaAbs, tone, abs = 'usd' }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot">
        <window.DeltaCell abs={deltaAbs} pct={deltaPct} absFmt={abs} />
        <span className="subtle">vs Pre</span>
      </div>
    </div>
  );
}

function MktRow({ row, total, color }) {
  const share = (row.spend / total) * 100;
  return (
    <tr>
      <td>
        <div className="row">
          <span className="dot" style={{ background: color }} />
          <span className="strong">{row.label}</span>
        </div>
      </td>
      <td className="num tnum">{window.fmt.int(row.orders)}</td>
      <td className="num tnum">{window.fmt.usd(row.sales)}</td>
      <td className="num tnum">{window.fmt.usd(row.spend)}</td>
      <td className="num">
        <span className="tnum" style={{ fontWeight: 500, color: row.roas >= 6 ? 'var(--positive)' : 'var(--text)' }}>
          {row.roas.toFixed(2)}×
        </span>
      </td>
      <td className="num tnum">${row.cpo.toFixed(2)}</td>
      <td style={{ minWidth: 160 }}>
        <div className="bar-track">
          <div className="bar-fill" style={{ width: `${share}%`, background: color }} />
        </div>
        <div className="muted tnum" style={{ fontSize: 11, marginTop: 2 }}>{share.toFixed(1)}% of spend</div>
      </td>
    </tr>
  );
}

window.ScreenMarketing = ScreenMarketing;
