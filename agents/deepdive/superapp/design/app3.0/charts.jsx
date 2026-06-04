// Chart primitives — hand-rolled SVG, no chart libs.
// All charts inherit theme via CSS variables.

// ─────────────────────────────────── Trend (multi-series line)
function TrendChart({ series, w = 760, h = 280, yFmt = window.fmt.usdK }) {
  const padL = 44, padR = 16, padT = 12, padB = 28;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;

  const all = series.flatMap(s => s.data);
  const max = Math.max(...all) * 1.08;
  const min = 0;
  const span = max - min || 1;
  const n = series[0].data.length;
  const stepX = innerW / (n - 1);

  const pts = (data) => data.map((v, i) => [padL + i * stepX, padT + innerH - ((v - min) / span) * innerH]);
  const dPath = (data) => pts(data).map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join(' ');

  // Y ticks
  const yTicks = 4;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => min + (span * i) / yTicks);

  // X ticks (every 5)
  const xTicks = Array.from({ length: n }, (_, i) => i).filter(i => i % 5 === 0 || i === n - 1);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="xMidYMid meet">
      {/* Y grid */}
      {ticks.map((t, i) => {
        const y = padT + innerH - ((t - min) / span) * innerH;
        return (
          <g key={i}>
            <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="var(--border)" strokeDasharray={i === 0 ? '0' : '3 3'} />
            <text x={padL - 8} y={y + 3} fontSize="10" textAnchor="end" fill="var(--text-subtle)">{yFmt(t)}</text>
          </g>
        );
      })}
      {/* X labels */}
      {xTicks.map(i => (
        <text key={i} x={padL + i * stepX} y={h - 8} fontSize="10" textAnchor="middle" fill="var(--text-subtle)">D{i + 1}</text>
      ))}
      {/* Series — fill for Post (current focus) only */}
      {series.map((s, idx) => {
        if (!s.fill) return null;
        const id = `tg-${idx}`;
        const dF = dPath(s.data) + ` L ${padL + (n - 1) * stepX} ${padT + innerH} L ${padL} ${padT + innerH} Z`;
        return (
          <g key={'fill-' + idx}>
            <defs>
              <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity="0.18" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={dF} fill={`url(#${id})`} />
          </g>
        );
      })}
      {series.map((s, idx) => (
        <path key={idx} d={dPath(s.data)} fill="none" stroke={s.color}
          strokeWidth={s.bold ? 2 : 1.5}
          strokeDasharray={s.dashed ? '4 4' : '0'}
          strokeLinejoin="round" strokeLinecap="round" opacity={s.dashed ? 0.7 : 1} />
      ))}
    </svg>
  );
}

// ─────────────────────────────────── Stacked Bars (Pre vs Post by bucket)
function BucketChart({ data, w = 760, h = 300 }) {
  const padL = 44, padR = 16, padT = 16, padB = 36;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const max = Math.max(...data.map(d => Math.max(d.pre, d.post))) * 1.1;
  const groupW = innerW / data.length;
  const barW = (groupW - 8) / 2;

  const yTicks = 4;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => (max * i) / yTicks);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h}>
      {ticks.map((t, i) => {
        const y = padT + innerH - (t / max) * innerH;
        return (
          <g key={i}>
            <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="var(--border)" strokeDasharray={i === 0 ? '0' : '3 3'} />
            <text x={padL - 8} y={y + 3} fontSize="10" textAnchor="end" fill="var(--text-subtle)">{(t/1000).toFixed(0)}k</text>
          </g>
        );
      })}
      {data.map((d, i) => {
        const x0 = padL + i * groupW + 4;
        const hPre = (d.pre / max) * innerH;
        const hPost = (d.post / max) * innerH;
        const delta = ((d.post - d.pre) / d.pre) * 100;
        const dCol = delta >= 0 ? 'var(--positive)' : 'var(--negative)';
        return (
          <g key={d.range}>
            <rect x={x0} y={padT + innerH - hPre} width={barW} height={hPre} fill="var(--surface-3)" rx="2" />
            <rect x={x0 + barW + 4} y={padT + innerH - hPost} width={barW} height={hPost} fill="var(--accent)" rx="2" />
            <text x={x0 + groupW / 2 - 2} y={h - 16} fontSize="10" textAnchor="middle" fill="var(--text-muted)">{d.range}</text>
            <text x={x0 + groupW / 2 - 2} y={h - 4} fontSize="9.5" textAnchor="middle" fill={dCol} fontWeight="500">
              {(delta >= 0 ? '+' : '')}{delta.toFixed(1)}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─────────────────────────────────── Heatmap (Day × Slot)
function Heatmap({ data, rowLabels, colLabels, w = 560, h = 260, valueFmt = v => (v*100).toFixed(0) }) {
  const padL = 56, padR = 12, padT = 28, padB = 12;
  const cellW = (w - padL - padR) / colLabels.length;
  const cellH = (h - padT - padB) / rowLabels.length;
  // Colors: accent ramp
  const colorFor = (v) => {
    // v 0..1
    const t = Math.min(1, Math.max(0, v));
    // mix between surface-3 and accent
    const a = t;
    return `rgba(5, 150, 105, ${0.05 + a * 0.85})`;
  };
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h}>
      {colLabels.map((c, j) => (
        <text key={c} x={padL + j * cellW + cellW / 2} y={padT - 10} fontSize="10.5" textAnchor="middle" fill="var(--text-muted)">{c}</text>
      ))}
      {rowLabels.map((r, i) => (
        <text key={r} x={padL - 10} y={padT + i * cellH + cellH / 2 + 3} fontSize="11" textAnchor="end" fill="var(--text-muted)" fontWeight="500">{r}</text>
      ))}
      {data.map((row, i) =>
        row.map((v, j) => (
          <g key={i + '-' + j}>
            <rect x={padL + j * cellW + 1} y={padT + i * cellH + 1} width={cellW - 2} height={cellH - 2}
                  rx="3" fill={colorFor(v)} stroke="var(--border)" strokeWidth="0.5" />
            <text x={padL + j * cellW + cellW / 2} y={padT + i * cellH + cellH / 2 + 4}
                  fontSize="11" textAnchor="middle"
                  fill={v > 0.55 ? 'white' : 'var(--text-muted)'}
                  fontWeight={v > 0.55 ? 600 : 500}>{valueFmt(v)}</text>
          </g>
        ))
      )}
    </svg>
  );
}

// ─────────────────────────────────── Scatter (ROAS vs Spend)
function Scatter({ data, w = 760, h = 320 }) {
  const padL = 44, padR = 16, padT = 16, padB = 32;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const xMax = Math.max(...data.map(d => d.x)) * 1.06;
  const yMax = Math.max(...data.map(d => d.y)) * 1.1;
  const yMin = 0;

  const xTicks = 5;
  const yTicks = 4;
  const xVals = Array.from({ length: xTicks + 1 }, (_, i) => (xMax * i) / xTicks);
  const yVals = Array.from({ length: yTicks + 1 }, (_, i) => yMin + ((yMax - yMin) * i) / yTicks);

  // Benchmark line for ROAS = avg
  const avgRoas = data.reduce((s, d) => s + d.y, 0) / data.length;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h}>
      {yVals.map((t, i) => {
        const y = padT + innerH - ((t - yMin) / (yMax - yMin)) * innerH;
        return (
          <g key={i}>
            <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="var(--border)" strokeDasharray={i === 0 ? '0' : '3 3'} />
            <text x={padL - 8} y={y + 3} fontSize="10" textAnchor="end" fill="var(--text-subtle)">{t.toFixed(1)}×</text>
          </g>
        );
      })}
      {xVals.map((t, i) => {
        const x = padL + (t / xMax) * innerW;
        return (
          <g key={i}>
            <text x={x} y={h - 12} fontSize="10" textAnchor="middle" fill="var(--text-subtle)">${(t/1000).toFixed(0)}k</text>
          </g>
        );
      })}
      {/* Avg line */}
      {(() => {
        const y = padT + innerH - ((avgRoas - yMin) / (yMax - yMin)) * innerH;
        return (
          <g>
            <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="var(--text-muted)" strokeDasharray="2 4" />
            <text x={w - padR} y={y - 4} fontSize="10" textAnchor="end" fill="var(--text-muted)">Avg ROAS {avgRoas.toFixed(2)}×</text>
          </g>
        );
      })()}
      {/* Points */}
      {data.map((d, i) => {
        const cx = padL + (d.x / xMax) * innerW;
        const cy = padT + innerH - ((d.y - yMin) / (yMax - yMin)) * innerH;
        const r  = 3 + Math.min(7, d.size / 4);
        const c = d.growth >= 0 ? 'var(--accent)' : 'var(--negative)';
        return (
          <g key={d.id}>
            <circle cx={cx} cy={cy} r={r} fill={c} opacity="0.35" />
            <circle cx={cx} cy={cy} r={r} fill="none" stroke={c} strokeWidth="1.2" />
          </g>
        );
      })}
      {/* Axis labels */}
      <text x={padL} y={padT - 4} fontSize="10" fill="var(--text-muted)">ROAS (×)</text>
      <text x={w - padR} y={h - 0} fontSize="10" fill="var(--text-muted)" textAnchor="end">Spend ($)</text>
    </svg>
  );
}

// ─────────────────────────────────── Waterfall
function Waterfall({ data, w = 760, h = 320, fmt = window.fmt.usdK }) {
  const padL = 56, padR = 16, padT = 16, padB = 56;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  // Compute cumulative for non-end items
  let cum = 0;
  const bars = data.map((d, i) => {
    if (d.type === 'start') { cum = d.value; return { ...d, y0: 0, y1: d.value }; }
    if (d.type === 'end')   { return { ...d, y0: 0, y1: d.value }; }
    const y0 = cum;
    cum += d.value;
    const y1 = cum;
    return { ...d, y0: Math.min(y0, y1), y1: Math.max(y0, y1) };
  });
  const max = Math.max(...bars.map(b => b.y1)) * 1.04;
  const min = Math.min(0, ...bars.map(b => b.y0));
  const span = max - min || 1;
  const colW = innerW / bars.length;
  const barW = colW - 14;

  const yToPx = v => padT + innerH - ((v - min) / span) * innerH;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h}>
      {/* baseline */}
      <line x1={padL} x2={w - padR} y1={yToPx(0)} y2={yToPx(0)} stroke="var(--border)" />
      {bars.map((b, i) => {
        const x = padL + i * colW + 7;
        const y = yToPx(b.y1);
        const hh = yToPx(b.y0) - yToPx(b.y1);
        const isStart = b.type === 'start';
        const isEnd   = b.type === 'end';
        const isPos   = b.type === 'pos';
        const isNeg   = b.type === 'neg';
        const fill =
          isStart ? 'var(--surface-3)' :
          isEnd   ? 'var(--text)' :
          isPos   ? 'var(--accent)' :
                    'var(--negative)';
        const txt =
          isStart || isEnd ? fmt(b.value) :
          (b.value >= 0 ? '+' : '−') + fmt(Math.abs(b.value));
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={Math.max(2, hh)} fill={fill} rx="2"
                  opacity={isStart || isEnd ? 1 : 0.9} />
            {/* connector */}
            {i < bars.length - 1 && (
              <line
                x1={x + barW}
                x2={x + barW + 14}
                y1={isStart || isEnd ? yToPx(b.value) : yToPx(b.type === 'pos' ? b.y1 : b.y0)}
                y2={isStart || isEnd ? yToPx(b.value) : yToPx(b.type === 'pos' ? b.y1 : b.y0)}
                stroke="var(--border-strong)" strokeDasharray="2 3"
              />
            )}
            <text x={x + barW/2} y={y - 6} fontSize="10.5" textAnchor="middle"
                  fill={isPos ? 'var(--positive)' : isNeg ? 'var(--negative)' : 'var(--text)'}
                  fontWeight="500">{txt}</text>
            <text x={x + barW/2} y={h - 30} fontSize="10" textAnchor="middle" fill="var(--text-muted)">{b.label}</text>
            {(isStart || isEnd) && (
              <text x={x + barW/2} y={h - 14} fontSize="10" textAnchor="middle" fill="var(--text-subtle)">
                {isStart ? window.PERIOD.pre.start.replace(', 2026','') : window.PERIOD.post.end.replace(', 2026','')}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ─────────────────────────────────── Donut
function Donut({ data, w = 220, h = 220, inner = 0.62 }) {
  const cx = w/2, cy = h/2;
  const R = Math.min(w, h)/2 - 4;
  const r = R * inner;
  const total = data.reduce((s, d) => s + d.value, 0);
  let a = -Math.PI / 2;
  const arcs = data.map(d => {
    const angle = (d.value / total) * Math.PI * 2;
    const a0 = a, a1 = a + angle;
    a = a1;
    const large = angle > Math.PI ? 1 : 0;
    const x0 = cx + R * Math.cos(a0), y0 = cy + R * Math.sin(a0);
    const x1 = cx + R * Math.cos(a1), y1 = cy + R * Math.sin(a1);
    const xi0 = cx + r * Math.cos(a0), yi0 = cy + r * Math.sin(a0);
    const xi1 = cx + r * Math.cos(a1), yi1 = cy + r * Math.sin(a1);
    const path = `M ${x0} ${y0} A ${R} ${R} 0 ${large} 1 ${x1} ${y1} L ${xi1} ${yi1} A ${r} ${r} 0 ${large} 0 ${xi0} ${yi0} Z`;
    return { ...d, path };
  });
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h}>
      {arcs.map((a, i) => <path key={i} d={a.path} fill={a.color} />)}
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="11" fill="var(--text-muted)">Total orders</text>
      <text x={cx} y={cy + 16} textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--text)" style={{ fontVariantNumeric: 'tabular-nums' }}>168,204</text>
    </svg>
  );
}

// ─────────────────────────────────── Bar chart (single dataset)
function BarChart({ data, w = 760, h = 200, color = 'var(--accent)', fmt = v => v.toFixed(0), showValue = false }) {
  const padL = 8, padR = 8, padT = 8, padB = 24;
  const max = Math.max(...data.map(d => d.value)) * 1.08 || 1;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const colW = innerW / data.length;
  const barW = Math.min(28, colW - 6);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h}>
      {data.map((d, i) => {
        const hh = (d.value / max) * innerH;
        const x  = padL + i * colW + (colW - barW) / 2;
        const y  = padT + innerH - hh;
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={Math.max(2, hh)} rx="2" fill={color} opacity={d.dim ? 0.4 : 1} />
            <text x={x + barW/2} y={h - 8} fontSize="10" textAnchor="middle" fill="var(--text-muted)">{d.label}</text>
            {showValue && <text x={x + barW/2} y={y - 4} fontSize="10" textAnchor="middle" fill="var(--text)" fontWeight="500">{fmt(d.value)}</text>}
          </g>
        );
      })}
    </svg>
  );
}

Object.assign(window, { TrendChart, BucketChart, Heatmap, Scatter, Waterfall, Donut, BarChart });
