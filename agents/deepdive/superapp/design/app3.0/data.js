// Mock data for Ralph Analyse

window.PERIOD = {
  pre: { label: 'Pre', start: 'Jan 1, 2026', end: 'Jan 31, 2026', days: 31 },
  post: { label: 'Post', start: 'Feb 1, 2026', end: 'Feb 28, 2026', days: 28 },
  preLY: { label: 'Pre LY', start: 'Jan 1, 2025', end: 'Jan 31, 2025' },
  postLY: { label: 'Post LY', start: 'Feb 1, 2025', end: 'Feb 28, 2025' },
};

// Hero KPIs
window.KPIS = [
  { id: 'sales',  label: 'Sales',          value: 4_812_340,  fmt: 'usd', delta: 8.4,  yoy: 14.2,  hint: 'Post vs Pre' },
  { id: 'payouts',label: 'Payouts',        value: 3_142_820,  fmt: 'usd', delta: 7.1,  yoy: 12.8,  hint: 'Post vs Pre' },
  { id: 'orders', label: 'Orders',         value: 168_204,    fmt: 'int', delta: 6.2,  yoy: 9.4,   hint: 'Post vs Pre' },
  { id: 'aov',    label: 'AOV',            value: 28.61,      fmt: 'usd1',delta: 2.1,  yoy: 4.4,   hint: 'Per order' },
  { id: 'prof',   label: 'Profitability',  value: 65.3,       fmt: 'pct', delta: -0.8, yoy: -1.2,  hint: 'Payout margin' },
  { id: 'promo',  label: 'Promo spend',    value: 312_440,    fmt: 'usd', delta: 22.4, yoy: 34.1,  hint: 'Funded by operator' },
  { id: 'ads',    label: 'Ads spend',      value: 184_220,    fmt: 'usd', delta: 11.6, yoy: 18.2,  hint: 'Sponsored listings' },
  { id: 'roas',   label: 'ROAS',           value: 6.42,       fmt: 'x',   delta: -3.2, yoy: -5.1,  hint: 'Sales / spend' },
  { id: 'nc',     label: 'New customers',  value: 18_412,     fmt: 'int', delta: 4.8,  yoy: 9.2,   hint: 'DD + UE' },
  { id: 'cpo',    label: 'Cost / order',   value: 2.96,       fmt: 'usd1',delta: 9.8,  yoy: 14.6,  hint: 'Promo + ads ÷ orders' },
  { id: 'org',    label: '% Organic orders', value: 58.4,     fmt: 'pct', delta: -3.1, yoy: -5.4,  hint: 'No promo, no ads' },
  { id: 'pdo',    label: '% Promo orders', value: 28.2,       fmt: 'pct', delta: 4.4,  yoy: 6.8,   hint: 'Discount applied' },
];

// Trend lines — 30 daily points (sales) for Pre and Post overlay
function genTrend(seed, base, drift, vol) {
  const out = [];
  let v = base;
  let s = seed;
  for (let i = 0; i < 30; i++) {
    s = (s * 9301 + 49297) % 233280;
    const r = (s / 233280 - 0.5);
    v = base + drift * i + r * vol;
    // weekend bump
    if (i % 7 === 5 || i % 7 === 6) v *= 1.18;
    out.push(Math.max(0, v));
  }
  return out;
}
window.TREND_PRE  = genTrend(7,  150000, 200, 22000);
window.TREND_POST = genTrend(17, 162000, 350, 26000);
window.TREND_LY   = genTrend(31, 138000, 100, 18000);

// Sparklines for kpi cards
window.SPARKS = {
  sales:   genTrend(2, 100, 0.6, 18),
  payouts: genTrend(3, 100, 0.4, 14),
  orders:  genTrend(4, 100, 0.3, 12),
  aov:     genTrend(5, 100, 0.1, 6),
  prof:    genTrend(6, 100, -0.2, 5),
  promo:   genTrend(7, 100, 1.4, 22),
  ads:     genTrend(8, 100, 0.8, 18),
  roas:    genTrend(9, 100, -0.3, 9),
  nc:      genTrend(10,100, 0.4, 11),
  cpo:     genTrend(11,100, 0.5, 8),
  org:     genTrend(12,100,-0.2, 6),
  pdo:     genTrend(13,100, 0.4, 8),
};

// Order count buckets (stacked-bar dataset)
window.BUCKETS = [
  { range: '$0-5',   pre: 1280, post: 1410 },
  { range: '$6-10',  pre: 4220, post: 4640 },
  { range: '$11-15', pre: 8840, post: 9180 },
  { range: '$16-20', pre: 14210, post: 15640 },
  { range: '$21-25', pre: 18420, post: 20210 },
  { range: '$26-30', pre: 21340, post: 23120 },
  { range: '$31-35', pre: 19840, post: 21940 },
  { range: '$36-40', pre: 16210, post: 18020 },
  { range: '$41-45', pre: 12140, post: 13880 },
  { range: '$46-50', pre: 8420, post: 9510 },
  { range: '$50+',   pre: 13420, post: 16654 },
];

// Day × slot heatmap (rows=days, cols=slots)
window.SLOT_LABELS = ['Overnight','Breakfast','Lunch','Afternoon','Dinner','Late Night'];
window.DAY_LABELS  = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
window.HEATMAP = (() => {
  const m = [];
  const base = [
    [0.05, 0.18, 0.74, 0.32, 0.88, 0.21], // Mon
    [0.04, 0.21, 0.78, 0.34, 0.91, 0.19],
    [0.06, 0.20, 0.81, 0.36, 0.94, 0.22],
    [0.05, 0.22, 0.85, 0.38, 0.96, 0.27],
    [0.07, 0.26, 0.92, 0.42, 1.00, 0.41], // Fri
    [0.10, 0.34, 0.86, 0.48, 0.98, 0.58], // Sat
    [0.08, 0.42, 0.80, 0.44, 0.84, 0.31], // Sun
  ];
  return base;
})();

// Stores list (mid-size, ~46 stores)
const STORE_NAMES_LIST = [
  'Mission District','SoMa','Hayes Valley','Castro','Marina','North Beach','Russian Hill',
  'Sunset','Richmond','Pacific Heights','Nob Hill','Tenderloin','Bernal Heights',
  'Glen Park','Noe Valley','Inner Sunset','Outer Sunset','Cole Valley','Haight',
  'Lower Haight','Western Addition','Japantown','Fillmore','Civic Center','Embarcadero',
  'Financial District','Chinatown','Excelsior','Visitacion','Ingleside','Lakeshore',
  'Parkside','West Portal','Twin Peaks','Diamond Heights','Potrero Hill','Dogpatch',
  'Mission Bay','South Beach','Yerba Buena','Treasure Island','Presidio','Sea Cliff',
  'Outer Richmond','Inner Richmond','Bayview'
];

function rand(s) { return ((s * 9301 + 49297) % 233280) / 233280; }
window.STORES = STORE_NAMES_LIST.map((name, i) => {
  const s = i + 1;
  const sales  = 60000 + rand(s*3) * 280000;
  const orders = Math.round(sales / (22 + rand(s*5) * 14));
  const aov    = sales / orders;
  const growth = (rand(s*7) - 0.35) * 40;
  const prof   = 58 + (rand(s*11) - 0.5) * 22;
  const promo  = sales * (0.04 + rand(s*13) * 0.10);
  const ads    = sales * (0.02 + rand(s*17) * 0.08);
  const roas   = sales / (promo + ads);
  return {
    id: `S-${1000 + i}`,
    name,
    region: ['Bay Area','East Bay','Peninsula','South Bay'][i % 4],
    platforms: i % 11 === 0 ? ['DD'] : (i % 7 === 0 ? ['UE'] : ['DD','UE']),
    sales: Math.round(sales),
    orders,
    aov: +aov.toFixed(2),
    growth: +growth.toFixed(1),
    prof: +prof.toFixed(1),
    promo: Math.round(promo),
    ads: Math.round(ads),
    roas: +roas.toFixed(2),
  };
});

// Scatter (ROAS vs Spend) — built from stores
window.SCATTER = window.STORES.map(s => ({
  id: s.id, name: s.name,
  x: s.promo + s.ads,    // spend
  y: s.roas,
  size: s.orders / 200,
  growth: s.growth,
}));

// Donut: order origin mix (Post period)
window.ORIGIN_MIX = [
  { id: 'organic',     label: 'Organic',          value: 58.4, color: 'var(--accent)' },
  { id: 'promo',       label: 'Promo-driven',     value: 22.1, color: '#A78BFA' },
  { id: 'ads',         label: 'Ads-driven',       value: 13.6, color: '#F59E0B' },
  { id: 'promo_ads',   label: 'Promo + Ads',      value: 5.9,  color: '#2563EB' },
];

// Waterfall — sales decomposition
window.WATERFALL = [
  { label: 'Pre sales',         value: 4_438_120, type: 'start' },
  { label: 'Order volume',      value:  248_400,  type: 'pos' },
  { label: 'AOV',               value:  142_220,  type: 'pos' },
  { label: 'Promo lift',        value:   78_600,  type: 'pos' },
  { label: 'Ads lift',          value:   42_180,  type: 'pos' },
  { label: 'Excluded dates',    value:  -28_440,  type: 'neg' },
  { label: 'Refunds / errors',  value:  -47_220,  type: 'neg' },
  { label: 'Lost stores',       value:  -61_520,  type: 'neg' },
  { label: 'Post sales',        value: 4_812_340, type: 'end' },
];

// Marketing — Corp vs TODC
window.MARKETING = {
  corp: { label: 'Corporate', orders: 8_240, sales: 248_120, spend: 41_220, roas: 6.02, cpo: 5.00 },
  todc: { label: 'TODC',      orders: 18_640, sales: 542_180, spend: 86_440, roas: 6.27, cpo: 4.64 },
};

window.CAMPAIGNS = [
  { id: 'C-201', name: '20% off Lunch',         source: 'Promotion',         platform: 'DD', orders: 4820, sales: 142_180, spend: 22_440, roas: 6.34, status: 'live' },
  { id: 'C-205', name: 'New Customer $10 off',  source: 'Promotion',         platform: 'DD', orders: 3120, sales:  89_220, spend: 18_640, roas: 4.79, status: 'live' },
  { id: 'C-209', name: 'Sponsored — Top of Feed', source: 'Sponsored Listing', platform: 'DD', orders: 6240, sales: 184_420, spend: 28_120, roas: 6.56, status: 'live' },
  { id: 'C-212', name: 'Weekend Boost',         source: 'Promotion',         platform: 'UE', orders: 2820, sales:  74_120, spend: 11_640, roas: 6.37, status: 'paused' },
  { id: 'C-215', name: 'UE Eats Pass',          source: 'Sponsored Listing', platform: 'UE', orders: 4820, sales: 132_180, spend: 22_440, roas: 5.89, status: 'live' },
  { id: 'C-218', name: 'Dinner Discount',       source: 'Promotion',         platform: 'DD', orders: 1840, sales:  48_220, spend:  9_240, roas: 5.22, status: 'ended' },
];

// Top movers (overview)
window.MOVERS = {
  up: window.STORES.slice().sort((a,b) => b.growth - a.growth).slice(0, 5),
  down: window.STORES.slice().sort((a,b) => a.growth - b.growth).slice(0, 5),
};

// Formatters
window.fmt = {
  usd: v => '$' + Math.round(v).toLocaleString('en-US'),
  usd1: v => '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  usdK: v => v >= 1e6 ? '$' + (v/1e6).toFixed(2) + 'M' : '$' + (v/1e3).toFixed(0) + 'K',
  int: v => Math.round(v).toLocaleString('en-US'),
  pct: v => v.toFixed(1) + '%',
  pct0: v => Math.round(v) + '%',
  x:   v => v.toFixed(2) + '×',
  delta: v => (v >= 0 ? '+' : '') + v.toFixed(1) + '%',
};

window.formatValue = (v, fmt) => {
  if (fmt === 'usd') return window.fmt.usd(v);
  if (fmt === 'usd1') return window.fmt.usd1(v);
  if (fmt === 'usdK') return window.fmt.usdK(v);
  if (fmt === 'int') return window.fmt.int(v);
  if (fmt === 'pct') return window.fmt.pct(v);
  if (fmt === 'x')  return window.fmt.x(v);
  return String(v);
};
