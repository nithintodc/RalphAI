// Icons + small UI primitives
// All icons inherit currentColor. 16px default.

const Icon = ({ d, size = 16, stroke = 1.6, fill = 'none', children }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className="icon">
    {d ? <path d={d} /> : children}
  </svg>
);

const I = {
  Home:        () => <Icon d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-8.5Z" />,
  Compare:     () => <Icon><path d="M4 6h7" /><path d="M4 18h7" /><path d="M13 12h7" /><circle cx="11" cy="6" r="2" /><circle cx="11" cy="18" r="2" /><circle cx="13" cy="12" r="2" /></Icon>,
  Store:       () => <Icon><path d="M3 9 4 4h16l1 5" /><path d="M4 9v11h16V9" /><path d="M9 13h6v7H9z" /></Icon>,
  Diag:        () => <Icon><path d="M3 17 9 11l4 4 8-9" /><path d="m17 6 4 0 0 4" /></Icon>,
  Slot:        () => <Icon><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Icon>,
  Bucket:      () => <Icon><path d="M4 7h16l-2 12H6L4 7Z" /><path d="M9 11v5" /><path d="M15 11v5" /><path d="M4 7l1-3h14l1 3" /></Icon>,
  Mkt:         () => <Icon><path d="M4 11v2a2 2 0 0 0 2 2h2l5 4V5L8 9H6a2 2 0 0 0-2 2Z" /><path d="M17 9a4 4 0 0 1 0 6" /></Icon>,
  Settings:    () => <Icon><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9 1.65 1.65 0 0 0 4.27 7.18l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9V9c0 .39.23.74.6 1H21a2 2 0 0 1 0 4h-.09c-.37 0-.7.25-.91.6Z" /></Icon>,
  ChevronDown: () => <Icon d="m6 9 6 6 6-6" />,
  ChevronRight:() => <Icon d="m9 6 6 6-6 6" />,
  ChevronLeft: () => <Icon d="m15 6-6 6 6 6" />,
  Cal:         () => <Icon><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18" /><path d="M8 3v4" /><path d="M16 3v4" /></Icon>,
  Filter:      () => <Icon d="M3 5h18l-7 9v6l-4-2v-4L3 5Z" />,
  Search:      () => <Icon><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></Icon>,
  Up:          () => <Icon d="m6 14 6-6 6 6" />,
  Down:        () => <Icon d="m6 10 6 6 6-6" />,
  Plus:        () => <Icon><path d="M12 5v14" /><path d="M5 12h14" /></Icon>,
  Export:      () => <Icon><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 21h14" /></Icon>,
  More:        () => <Icon><circle cx="5" cy="12" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="19" cy="12" r="1.4" /></Icon>,
  Bell:        () => <Icon><path d="M6 8a6 6 0 1 1 12 0v5l2 3H4l2-3V8Z" /><path d="M10 19a2 2 0 0 0 4 0" /></Icon>,
  Sparkles:    () => <Icon d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />,
  Bolt:        () => <Icon d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />,
  Globe:       () => <Icon><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a14 14 0 0 1 0 18" /><path d="M12 3a14 14 0 0 0 0 18" /></Icon>,
  Map:         () => <Icon><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z" /><path d="M9 3v15" /><path d="M15 6v15" /></Icon>,
  Tag:         () => <Icon><path d="M20 12 12 4H4v8l8 8 8-8Z" /><circle cx="8" cy="8" r="1.4" /></Icon>,
  Info:        () => <Icon><circle cx="12" cy="12" r="9" /><path d="M12 8h.01" /><path d="M11 12h1v5h1" /></Icon>,
  Check:       () => <Icon d="m5 12 5 5 9-11" />,
  X:           () => <Icon d="M6 6l12 12M18 6 6 18" />,
  Reset:       () => <Icon><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v6h6" /></Icon>,
};

window.I = I;
window.Icon = Icon;

// ──────────────────────────────────────────────────────── Delta pill & cell

function Delta({ value, suffix = '%', fmtAbs }) {
  const up = value > 0.001;
  const down = value < -0.001;
  const cls = up ? 'up' : down ? 'down' : 'flat';
  const arrow = up ? '▲' : down ? '▼' : '–';
  const v = (up ? '+' : '') + value.toFixed(1) + suffix;
  return (
    <span className={`delta ${cls}`}>
      <span className="arrow">{arrow}</span>
      <span className="tnum">{v}</span>
    </span>
  );
}
function DeltaInline({ value, suffix = '%' }) {
  const up = value > 0.001;
  const down = value < -0.001;
  const cls = up ? 'up' : down ? 'down' : 'flat';
  const v = (up ? '+' : '') + value.toFixed(1) + suffix;
  return <span className={`delta-inline ${cls}`}>{v}</span>;
}
function DeltaCell({ abs, pct, absFmt = 'usd' }) {
  const up = pct > 0.001;
  const down = pct < -0.001;
  const cls = up ? 'up' : down ? 'down' : 'flat';
  const sign = up ? '+' : '';
  const absStr = absFmt === 'int'
    ? (sign + Math.round(abs).toLocaleString('en-US'))
    : absFmt === 'pp'
      ? (sign + abs.toFixed(1) + 'pp')
      : (sign + '$' + Math.round(Math.abs(abs)).toLocaleString('en-US')).replace('+$-', '−$').replace('$-', '−$');
  // Show absolute + pct stacked
  return (
    <div className="tnum" style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6 }}>
      <span className={`delta-inline ${cls}`}>{absStr}</span>
      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{sign}{pct.toFixed(1)}%</span>
    </div>
  );
}

window.Delta = Delta;
window.DeltaInline = DeltaInline;
window.DeltaCell = DeltaCell;

// ──────────────────────────────────────────────────────── Sparkline

function Sparkline({ data, w = 84, h = 28, color, stroke = 1.5, fill = true }) {
  if (!data || !data.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = (max - min) || 1;
  const stepX = w / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, h - ((v - min) / span) * (h - 2) - 1]);
  const dPath = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join(' ');
  const dFill = dPath + ` L ${w} ${h} L 0 ${h} Z`;
  const c = color || 'var(--accent)';
  const id = 'sg' + Math.random().toString(36).slice(2, 8);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      {fill && (
        <>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stopColor={c} stopOpacity="0.22" />
              <stop offset="100%" stopColor={c} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={dFill} fill={`url(#${id})`} />
        </>
      )}
      <path d={dPath} fill="none" stroke={c} strokeWidth={stroke} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
window.Sparkline = Sparkline;

// ──────────────────────────────────────────────────────── KPI card

function KpiCard({ kpi, style }) {
  const v = window.formatValue(kpi.value, kpi.fmt);
  if (style === 'spark') {
    return (
      <div className="kpi spark-hero">
        <div className="kpi-label">{kpi.label}</div>
        <div className="kpi-value">{v}</div>
        <div className="kpi-foot">
          <Delta value={kpi.delta} />
          <span className="subtle">vs Pre</span>
          <span style={{ marginLeft: 'auto' }} className="subtle">YoY <DeltaInline value={kpi.yoy} /></span>
        </div>
        <Sparkline data={window.SPARKS[kpi.id]} w={400} h={56} color="var(--accent)" />
      </div>
    );
  }
  return (
    <div className="kpi">
      <div className="kpi-label">{kpi.label}</div>
      <div className="kpi-value">{v}</div>
      <div className="kpi-foot">
        <Delta value={kpi.delta} />
        <span className="subtle">vs Pre</span>
      </div>
      <svg className="kpi-spark" viewBox="0 0 84 28" preserveAspectRatio="none">
        <g>
          {(() => {
            const data = window.SPARKS[kpi.id];
            const min = Math.min(...data), max = Math.max(...data), span = (max - min) || 1;
            const step = 84 / (data.length - 1);
            const pts = data.map((vv, i) => [i*step, 28 - ((vv-min)/span)*26 - 1]);
            const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
            const positive = kpi.delta >= 0;
            const c = positive ? 'var(--accent)' : 'var(--negative)';
            return <path d={d} fill="none" stroke={c} strokeWidth="1.3" strokeLinejoin="round" />;
          })()}
        </g>
      </svg>
    </div>
  );
}
window.KpiCard = KpiCard;

// ──────────────────────────────────────────────────────── Period pill

function PeriodPill() {
  const p = window.PERIOD;
  return (
    <div className="period-pill">
      <span className="seg"><span className="lbl">Pre</span>{p.pre.start} – {p.pre.end}</span>
      <span className="seg"><span className="lbl">Post</span>{p.post.start} – {p.post.end}</span>
    </div>
  );
}
window.PeriodPill = PeriodPill;

Object.assign(window, { I, Icon, Delta, DeltaInline, DeltaCell, Sparkline, KpiCard, PeriodPill });
