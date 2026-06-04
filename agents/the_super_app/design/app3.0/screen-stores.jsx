// Stores list + Store detail (single file)

function ScreenStores({ onStoreClick }) {
  const [sort, setSort] = React.useState('growth');
  const [dir, setDir] = React.useState('desc');
  const stores = React.useMemo(() => {
    const sorted = [...window.STORES].sort((a, b) => {
      const av = a[sort], bv = b[sort];
      const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return dir === 'desc' ? -cmp : cmp;
    });
    return sorted;
  }, [sort, dir]);

  const setSortCol = (k) => {
    if (sort === k) setDir(dir === 'desc' ? 'asc' : 'desc');
    else { setSort(k); setDir('desc'); }
  };

  // Aggregates
  const total = window.STORES.reduce((acc, s) => ({
    sales: acc.sales + s.sales,
    orders: acc.orders + s.orders,
    promo: acc.promo + s.promo,
    ads: acc.ads + s.ads,
  }), { sales: 0, orders: 0, promo: 0, ads: 0 });

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Stores</h1>
          <div className="page-sub">46 active · Combined platforms · Pre vs Post</div>
        </div>
        <div className="row">
          <div className="search">
            <I.Search />
            <input placeholder="Filter stores…" />
          </div>
          <button className="chip"><I.Map /> Region <I.ChevronDown /></button>
          <button className="chip"><I.Filter /> Platform <I.ChevronDown /></button>
          <button className="chip"><I.Export /> Export</button>
        </div>
      </div>

      {/* Summary strip */}
      <div className="grid-12">
        <SummaryStrip label="Stores reporting" value="46" sub="of 48 total" />
        <SummaryStrip label="Sales (Post)" value={window.fmt.usdK(total.sales * 1.083)} sub="+8.4% vs Pre" tone="up" />
        <SummaryStrip label="Orders (Post)" value={window.fmt.int(total.orders * 1.062)} sub="+6.2% vs Pre" tone="up" />
        <SummaryStrip label="Stores in decline" value="7" sub="Δ% < −5%" tone="down" />
      </div>

      <div className="card" style={{ padding: 0, marginTop: 16 }}>
        <div className="card-head" style={{ padding: '14px 16px 12px', marginBottom: 0 }}>
          <div>
            <h3 className="card-title">Per-store performance</h3>
            <div className="card-sub">Sort any column · click row to drill in</div>
          </div>
          <div className="row">
            <button className="chip ghost"><I.Filter /> Active columns <I.ChevronDown /></button>
          </div>
        </div>
        <div className="scroll-x">
          <table className="dt">
            <thead>
              <tr>
                <SortHeader k="name"   label="Store"          sort={sort} dir={dir} onClick={setSortCol} />
                <SortHeader k="sales"  label="Sales (Post)"   sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="growth" label="Δ% Sales"       sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="orders" label="Orders"         sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="aov"    label="AOV"            sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="prof"   label="Profitability"  sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="promo"  label="Promo"          sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="ads"    label="Ads"            sort={sort} dir={dir} onClick={setSortCol} num />
                <SortHeader k="roas"   label="ROAS"           sort={sort} dir={dir} onClick={setSortCol} num />
                <th></th>
              </tr>
            </thead>
            <tbody>
              {stores.map(s => {
                const delta = Math.round(s.sales * (s.growth / 100));
                return (
                  <tr key={s.id} onClick={onStoreClick} style={{ cursor: 'pointer' }}>
                    <td>
                      <div className="row">
                        <div style={{ width: 26, height: 26, background: 'var(--surface-2)', borderRadius: 6, display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>
                          {s.name.slice(0,2).toUpperCase()}
                        </div>
                        <div>
                          <div style={{ fontWeight: 500 }}>{s.name}</div>
                          <div className="muted" style={{ fontSize: 11 }}>
                            {s.id} · {s.region}
                            {s.platforms.map(p => (
                              <span key={p} className={`tag ${p.toLowerCase()}`} style={{ marginLeft: 6, height: 16, fontSize: 9.5 }}>{p}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="num strong">{window.fmt.usd(s.sales)}</td>
                    <td className="num"><window.DeltaCell abs={delta} pct={s.growth} absFmt="usd" /></td>
                    <td className="num">{window.fmt.int(s.orders)}</td>
                    <td className="num">${s.aov.toFixed(2)}</td>
                    <td className="num">{s.prof.toFixed(1)}%</td>
                    <td className="num muted">{window.fmt.usd(s.promo)}</td>
                    <td className="num muted">{window.fmt.usd(s.ads)}</td>
                    <td className="num">
                      <span className="tnum" style={{ fontWeight: 500, color: s.roas >= 6 ? 'var(--positive)' : s.roas >= 4 ? 'var(--text)' : 'var(--negative)' }}>
                        {s.roas.toFixed(2)}×
                      </span>
                    </td>
                    <td><I.ChevronRight /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function SummaryStrip({ label, value, sub, tone }) {
  return (
    <div className="card col-4" style={{ padding: 12, gridColumn: 'span 3' }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ fontSize: 20 }}>{value}</div>
      <div className="kpi-foot">
        <span className={`delta-inline ${tone || 'flat'}`}>{sub}</span>
      </div>
    </div>
  );
}

function SortHeader({ k, label, sort, dir, onClick, num }) {
  const active = sort === k;
  return (
    <th className={num ? 'num' : ''} onClick={() => onClick(k)} style={{ cursor: 'pointer', userSelect: 'none' }}>
      <span style={{ color: active ? 'var(--text)' : undefined }}>{label}</span>
      {active && <span style={{ marginLeft: 4, fontSize: 9 }}>{dir === 'desc' ? '▼' : '▲'}</span>}
    </th>
  );
}

// ────────────────────────────────────────────────── Store detail

function ScreenStoreDetail({ setActive }) {
  const store = window.STORES[3]; // Castro
  const delta = Math.round(store.sales * (store.growth / 100));
  const trend = window.genTrend ? null : null;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="row" style={{ marginBottom: 8 }}>
            <button className="chip ghost" onClick={() => setActive('stores')}>
              <I.ChevronLeft /> Back to stores
            </button>
          </div>
          <div className="row" style={{ gap: 14 }}>
            <div style={{ width: 44, height: 44, background: 'var(--surface-2)', borderRadius: 10, display: 'grid', placeItems: 'center', fontSize: 16, fontWeight: 600, color: 'var(--text-muted)' }}>
              {store.name.slice(0,2).toUpperCase()}
            </div>
            <div>
              <h1 className="page-title" style={{ marginBottom: 2 }}>{store.name}</h1>
              <div className="page-sub">
                <span className="tnum">{store.id}</span> · {store.region} ·
                {store.platforms.map(p => (
                  <span key={p} className={`tag ${p.toLowerCase()}`} style={{ marginLeft: 6, height: 18, fontSize: 10 }}>{p}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="row">
          <button className="chip"><I.Tag /> Add markup</button>
          <button className="chip"><I.Export /> Export store report</button>
        </div>
      </div>

      {/* KPI row for this store */}
      <div className="kpi-grid">
        <MiniKpi label="Sales (Post)" value={window.fmt.usd(store.sales)} deltaAbs={delta} deltaPct={store.growth} />
        <MiniKpi label="Orders" value={window.fmt.int(store.orders)} deltaAbs={Math.round(store.orders * 0.058)} deltaPct={5.8} />
        <MiniKpi label="AOV" value={`$${store.aov.toFixed(2)}`} deltaAbs={0.42} deltaPct={1.5} absFmt="usd1" />
        <MiniKpi label="Profitability" value={`${store.prof.toFixed(1)}%`} deltaAbs={-0.6} deltaPct={-0.9} absFmt="pp" />
      </div>

      {/* Trend + sidebar */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-8">
          <div className="card-head">
            <div>
              <h3 className="card-title">Daily sales</h3>
              <div className="card-sub">Post vs Pre vs Last Year Post</div>
            </div>
            <div className="tab-row">
              <button className="tab active">Sales</button>
              <button className="tab">Orders</button>
              <button className="tab">AOV</button>
              <button className="tab">Payouts</button>
            </div>
          </div>
          <window.TrendChart series={[
            { name: 'Pre',     data: window.TREND_PRE.map(v => v * 0.04),  color: 'var(--text-subtle)' },
            { name: 'LY Post', data: window.TREND_LY.map(v => v * 0.038),   color: 'var(--text-subtle)', dashed: true },
            { name: 'Post',    data: window.TREND_POST.map(v => v * 0.043), color: 'var(--accent)', bold: true, fill: true },
          ]} h={240} />
        </div>

        <div className="card col-4">
          <div className="card-head">
            <h3 className="card-title">Highlights</h3>
            <span className="tag live">3</span>
          </div>
          <div className="stack-3">
            <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <div style={{ width: 28, height: 28, background: 'var(--accent-soft)', color: 'var(--accent-text)', borderRadius: 6, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <I.Up />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>Strongest growth in lunch slot</div>
                <div className="muted" style={{ fontSize: 12 }}>Lunch sales +18.2% Pre→Post, lifting weekday performance.</div>
              </div>
            </div>
            <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <div style={{ width: 28, height: 28, background: 'var(--negative-soft)', color: 'var(--negative)', borderRadius: 6, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <I.Down />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>ROAS declined 4.2%</div>
                <div className="muted" style={{ fontSize: 12 }}>Promo spend up 26% but sales only +12%. Review campaign mix.</div>
              </div>
            </div>
            <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <div style={{ width: 28, height: 28, background: 'var(--info-soft)', color: 'var(--info)', borderRadius: 6, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <I.Info />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>$50+ basket share rising</div>
                <div className="muted" style={{ fontSize: 12 }}>Up 2.4pp Pre→Post. Premium menu items driving check size.</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Platform split table */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-12">
          <div className="card-head">
            <h3 className="card-title">Platform split — Pre vs Post</h3>
            <div className="card-sub">DD and UE side-by-side</div>
          </div>
          <div className="scroll-x">
            <table className="dt">
              <thead>
                <tr>
                  <th>Platform</th>
                  <th className="num">Pre</th>
                  <th className="num">Post</th>
                  <th className="num">Δ</th>
                  <th className="num">Δ%</th>
                  <th className="num">Orders Pre</th>
                  <th className="num">Orders Post</th>
                  <th className="num">Δ Orders</th>
                  <th className="num">AOV Pre</th>
                  <th className="num">AOV Post</th>
                  <th className="num">ROAS</th>
                </tr>
              </thead>
              <tbody>
                <PlatformRow tag="DD" sales={[112340, 124680]} orders={[4120, 4520]} aov={[27.27, 27.58]} roas={6.84} />
                <PlatformRow tag="UE" sales={[58220, 64880]}    orders={[2180, 2380]} aov={[26.71, 27.26]} roas={5.92} />
                <tr style={{ background: 'var(--surface-2)' }}>
                  <td className="strong">Combined</td>
                  <td className="num tnum">{window.fmt.usd(170560)}</td>
                  <td className="num tnum strong">{window.fmt.usd(189560)}</td>
                  <td className="num"><window.DeltaCell abs={19000} pct={11.14} absFmt="usd" /></td>
                  <td className="num"><window.Delta value={11.14} /></td>
                  <td className="num tnum">{window.fmt.int(6300)}</td>
                  <td className="num tnum">{window.fmt.int(6900)}</td>
                  <td className="num"><window.DeltaCell abs={600} pct={9.52} absFmt="int" /></td>
                  <td className="num">$27.07</td>
                  <td className="num">$27.47</td>
                  <td className="num strong">6.47×</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Slot breakdown + bucket */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-6">
          <div className="card-head">
            <h3 className="card-title">Slot performance — Sales</h3>
            <div className="card-sub">Pre vs Post · this store</div>
          </div>
          <window.BarChart
            data={[
              { label: 'O/night',   value: 4800 },
              { label: 'Breakfast', value: 18400 },
              { label: 'Lunch',     value: 64200, dim: false },
              { label: 'Aft.',      value: 22100 },
              { label: 'Dinner',    value: 72800 },
              { label: 'Late',      value: 7260 },
            ]}
            showValue
            fmt={v => '$' + (v/1000).toFixed(0) + 'k'}
            h={220}
          />
        </div>
        <div className="card col-6">
          <div className="card-head">
            <h3 className="card-title">Ticket size distribution</h3>
            <div className="card-sub">Pre (gray) vs Post (green)</div>
          </div>
          <window.BucketChart data={window.BUCKETS.map(b => ({ range: b.range, pre: Math.round(b.pre * 0.042), post: Math.round(b.post * 0.042) }))} h={240} />
        </div>
      </div>
    </>
  );
}

function MiniKpi({ label, value, deltaAbs, deltaPct, absFmt = 'usd' }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot">
        <window.DeltaCell abs={deltaAbs} pct={deltaPct} absFmt={absFmt} />
        <span className="subtle">vs Pre</span>
      </div>
    </div>
  );
}

function PlatformRow({ tag, sales, orders, aov, roas }) {
  const dSales = sales[1] - sales[0];
  const pSales = (dSales / sales[0]) * 100;
  const dOrders = orders[1] - orders[0];
  return (
    <tr>
      <td><span className={`tag ${tag.toLowerCase()}`}><span className={`dot ${tag.toLowerCase()}`} />{tag}</span></td>
      <td className="num tnum">{window.fmt.usd(sales[0])}</td>
      <td className="num tnum strong">{window.fmt.usd(sales[1])}</td>
      <td className="num"><window.DeltaCell abs={dSales} pct={pSales} absFmt="usd" /></td>
      <td className="num"><window.Delta value={pSales} /></td>
      <td className="num tnum">{window.fmt.int(orders[0])}</td>
      <td className="num tnum">{window.fmt.int(orders[1])}</td>
      <td className="num"><window.DeltaCell abs={dOrders} pct={(dOrders/orders[0])*100} absFmt="int" /></td>
      <td className="num">${aov[0].toFixed(2)}</td>
      <td className="num">${aov[1].toFixed(2)}</td>
      <td className="num">{roas.toFixed(2)}×</td>
    </tr>
  );
}

window.ScreenStores = ScreenStores;
window.ScreenStoreDetail = ScreenStoreDetail;
