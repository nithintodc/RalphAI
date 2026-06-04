// Slots & Heatmap screen

function ScreenSlots() {
  const slots = window.SLOT_LABELS;

  // Per-slot Pre vs Post (sales)
  const slotData = [
    { slot: 'Overnight',  pre: 142000, post: 156400 },
    { slot: 'Breakfast',  pre: 364200, post: 412800 },
    { slot: 'Lunch',      pre: 1284600, post: 1456200 },
    { slot: 'Afternoon',  pre: 482400, post: 524800 },
    { slot: 'Dinner',     pre: 1924800, post: 2042600 },
    { slot: 'Late Night', pre: 240120, post: 219540 },
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Slots & day-parts</h1>
          <div className="page-sub">Sales mix by time-of-day · Mon–Sun × 6 slots</div>
        </div>
        <div className="row">
          <div className="tab-row">
            <button className="tab active">Sales</button>
            <button className="tab">Orders</button>
            <button className="tab">AOV</button>
            <button className="tab">Profitability</button>
          </div>
          <button className="chip ghost"><I.Info /> Slot definitions</button>
        </div>
      </div>

      <div className="grid-12">
        <div className="card col-8">
          <div className="card-head">
            <div>
              <h3 className="card-title">Heatmap — Day × Slot</h3>
              <div className="card-sub">Cell color = sales intensity (% of peak) · numbers shown</div>
            </div>
            <div className="row" style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              <span className="muted">Low</span>
              <div style={{ width: 80, height: 8, background: 'linear-gradient(90deg, rgba(5,150,105,0.08) 0%, rgba(5,150,105,0.9) 100%)', borderRadius: 4 }} />
              <span className="muted">High</span>
            </div>
          </div>
          <window.Heatmap data={window.HEATMAP} rowLabels={window.DAY_LABELS} colLabels={window.SLOT_LABELS} h={300} />
        </div>

        <div className="card col-4">
          <div className="card-head">
            <h3 className="card-title">Slot of week</h3>
            <span className="tag live">Fri Dinner</span>
          </div>
          <div className="stack-3">
            <div>
              <div className="kpi-label">Peak slot · Sales</div>
              <div className="kpi-value">$486K</div>
              <div className="kpi-foot"><window.DeltaCell abs={42000} pct={9.5} absFmt="usd" /><span className="subtle">vs Pre Fri/Dinner</span></div>
            </div>
            <hr className="divider" />
            <div>
              <div className="kpi-label">Quietest slot</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Mon · Overnight</div>
              <div className="muted" style={{ fontSize: 12 }}>$8.4K (1.4% of weekly sales)</div>
            </div>
            <hr className="divider" />
            <div>
              <div className="kpi-label">Biggest slot shift</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Lunch +13.4%</div>
              <div className="muted" style={{ fontSize: 12 }}>Friday lunch covers drove most of the lift</div>
            </div>
          </div>
        </div>
      </div>

      {/* Pre vs Post slot table */}
      <div className="card" style={{ padding: 0, marginTop: 16 }}>
        <div className="card-head" style={{ padding: '14px 16px 12px', marginBottom: 0 }}>
          <div>
            <h3 className="card-title">Sales by slot — Pre vs Post</h3>
            <div className="card-sub">All 6 day-parts</div>
          </div>
        </div>
        <div className="scroll-x">
          <table className="dt">
            <thead>
              <tr>
                <th>Slot</th>
                <th>Time range</th>
                <th className="num">Pre</th>
                <th className="num">Post</th>
                <th className="num">Δ</th>
                <th className="num">Δ%</th>
                <th>Distribution</th>
              </tr>
            </thead>
            <tbody>
              {slotData.map(s => {
                const d = s.post - s.pre;
                const pct = (d / s.pre) * 100;
                const total = slotData.reduce((acc, x) => acc + x.post, 0);
                const share = (s.post / total) * 100;
                return (
                  <tr key={s.slot}>
                    <td className="strong">{s.slot}</td>
                    <td className="muted mono" style={{ fontSize: 12 }}>{slotTimeRange(s.slot)}</td>
                    <td className="num tnum">{window.fmt.usd(s.pre)}</td>
                    <td className="num tnum strong">{window.fmt.usd(s.post)}</td>
                    <td className="num"><window.DeltaCell abs={d} pct={pct} absFmt="usd" /></td>
                    <td className="num"><window.Delta value={pct} /></td>
                    <td style={{ minWidth: 200 }}>
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${share}%` }} />
                      </div>
                      <div className="muted tnum" style={{ fontSize: 11, marginTop: 2 }}>{share.toFixed(1)}% of Post sales</div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bar chart slot view */}
      <div className="grid-12" style={{ marginTop: 16 }}>
        <div className="card col-6">
          <div className="card-head">
            <h3 className="card-title">Per-slot sales — Post</h3>
            <div className="card-sub">$ totals</div>
          </div>
          <window.BarChart
            data={slotData.map(s => ({ label: s.slot.slice(0, 5), value: s.post }))}
            showValue fmt={v => '$' + (v/1000).toFixed(0) + 'k'} h={220}
          />
        </div>
        <div className="card col-6">
          <div className="card-head">
            <h3 className="card-title">Per-slot Δ% — Pre → Post</h3>
            <div className="card-sub">Growth direction</div>
          </div>
          <SlotDeltaBars data={slotData} />
        </div>
      </div>
    </>
  );
}

function slotTimeRange(slot) {
  return {
    'Overnight':  '12:00 AM – 4:59 AM',
    'Breakfast':  '5:00 AM – 10:59 AM',
    'Lunch':      '11:00 AM – 1:59 PM',
    'Afternoon':  '2:00 PM – 4:59 PM',
    'Dinner':     '5:00 PM – 7:59 PM',
    'Late Night': '8:00 PM – 11:59 PM',
  }[slot] || '';
}

function SlotDeltaBars({ data }) {
  const padL = 8, padR = 8, padT = 8, padB = 24, w = 760, h = 220;
  const deltas = data.map(d => ({ label: d.slot.slice(0,5), pct: ((d.post - d.pre) / d.pre) * 100 }));
  const maxAbs = Math.max(...deltas.map(d => Math.abs(d.pct))) * 1.1 || 1;
  const innerH = h - padT - padB;
  const innerW = w - padL - padR;
  const colW = innerW / deltas.length;
  const barW = Math.min(36, colW - 8);
  const zero = padT + innerH / 2;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h}>
      <line x1={padL} x2={w-padR} y1={zero} y2={zero} stroke="var(--border-strong)" />
      {deltas.map((d, i) => {
        const x = padL + i * colW + (colW - barW) / 2;
        const hh = (Math.abs(d.pct) / maxAbs) * (innerH / 2 - 4);
        const y = d.pct >= 0 ? zero - hh : zero;
        const color = d.pct >= 0 ? 'var(--accent)' : 'var(--negative)';
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={Math.max(2, hh)} fill={color} rx="2" />
            <text x={x + barW/2} y={d.pct >= 0 ? y - 6 : y + hh + 12} fontSize="11" textAnchor="middle" fill={color} fontWeight="500">
              {(d.pct >= 0 ? '+' : '')}{d.pct.toFixed(1)}%
            </text>
            <text x={x + barW/2} y={h - 6} fontSize="10" textAnchor="middle" fill="var(--text-muted)">{d.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

window.ScreenSlots = ScreenSlots;
