/**
 * Register week-over-week comparison (store × weekday × slot).
 * Mirrors ``shared/register_wow.py`` for Super App + Health Check parity.
 */

export const REGISTER_WOW_METRICS = ['Sales', 'Payouts', 'Orders', 'AOV'];

function num(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function aov(sales, orders) {
  if (orders <= 0) return 0;
  return Math.round((sales / orders) * 100) / 100;
}

function pctChange(w1, w2) {
  if (w1 === 0 && w2 === 0) return 0;
  if (w1 === 0) return null;
  return Math.round(((w2 - w1) / Math.abs(w1)) * 1000) / 10;
}

function delta(w1, w2) {
  return Math.round((w2 - w1) * 100) / 100;
}

/** Normalize a health-check weekly CSV row or register row to slot metrics. */
export function slotMetricsFromRow(row) {
  const sales = num(row.Sales ?? row.sales);
  const orders = num(row.Orders ?? row.orders);
  return {
    Sales: sales,
    Payouts: num(row.Payouts ?? row.payouts),
    Orders: orders,
    AOV: num(row.AOV ?? row.aov) || aov(sales, orders),
  };
}

export function slotKeyFromRow(row) {
  const storeId = String(row['Merchant Store ID'] ?? row.storeId ?? '').trim();
  const day = String(row.Day ?? row.dayOfWeek ?? '').trim();
  const daypart = String(row['Day part'] ?? row.slot ?? '').trim();
  return `${storeId}|${day}|${daypart}`;
}

export function slotLabel(storeId, day, daypart, { includeStore = true } = {}) {
  const base = day && daypart ? `${day} · ${daypart}` : day || daypart || 'Unknown';
  return includeStore && storeId ? `Store ${storeId} · ${base}` : base;
}

export function topMoverCount(slotCount, { fraction = 0.1, floor = 5 } = {}) {
  if (slotCount <= 0) return 0;
  return Math.max(floor, Math.min(slotCount, Math.ceil(slotCount * fraction)));
}

function rowsToSlotMap(rows) {
  const map = new Map();
  for (const row of rows || []) {
    const storeId = String(row['Merchant Store ID'] ?? row.storeId ?? '').trim();
    if (!storeId) continue;
    const key = slotKeyFromRow(row);
    map.set(key, slotMetricsFromRow(row));
  }
  return map;
}

/**
 * Compare two weeks of register-style rows (weekly CSV or collapsed register export).
 */
export function compareRegisterWeekSlots(week1Rows, week2Rows, labels = {}) {
  const w1 = rowsToSlotMap(week1Rows);
  const w2 = rowsToSlotMap(week2Rows);
  const keys = [...new Set([...w1.keys(), ...w2.keys()])].sort();

  const empty = () => ({ Sales: 0, Payouts: 0, Orders: 0, AOV: 0 });
  const slots = keys.map((key) => {
    const [storeId, day, daypart] = key.split('|');
    const v1 = w1.get(key) || empty();
    const v2 = w2.get(key) || empty();
    const metrics = {};
    for (const m of REGISTER_WOW_METRICS) {
      metrics[m] = {
        week1: v1[m],
        week2: v2[m],
        delta: delta(v1[m], v2[m]),
        pct: pctChange(v1[m], v2[m]),
      };
    }
    return { storeId, day, daypart, label: slotLabel(storeId, day, daypart), metrics };
  });

  const totals = {};
  for (const m of REGISTER_WOW_METRICS) {
    if (m === 'AOV') {
      const s1 = [...w1.values()].reduce((s, v) => s + v.Sales, 0);
      const o1 = [...w1.values()].reduce((s, v) => s + v.Orders, 0);
      const s2 = [...w2.values()].reduce((s, v) => s + v.Sales, 0);
      const o2 = [...w2.values()].reduce((s, v) => s + v.Orders, 0);
      totals[m] = {
        week1: aov(s1, o1),
        week2: aov(s2, o2),
        delta: delta(aov(s1, o1), aov(s2, o2)),
        pct: pctChange(aov(s1, o1), aov(s2, o2)),
      };
    } else {
      const a = [...w1.values()].reduce((s, v) => s + v[m], 0);
      const b = [...w2.values()].reduce((s, v) => s + v[m], 0);
      totals[m] = { week1: a, week2: b, delta: delta(a, b), pct: pctChange(a, b) };
    }
  }

  const k = topMoverCount(keys.length);
  const movers = {};
  for (const m of REGISTER_WOW_METRICS) {
    const ranked = [...slots].sort((a, b) => a.metrics[m].delta - b.metrics[m].delta);
    movers[m] = { top_up: ranked.slice(-k), top_down: ranked.slice(0, k) };
  }

  return {
    labels: { week1: labels.week1 || 'Week 1', week2: labels.week2 || 'Week 2' },
    slotCount: keys.length,
    topK: k,
    totals,
    slots,
    movers,
  };
}
