/**
 * Bican DD sales-by-order reconciliation: May 1–31 vs portal.
 * Run: cd agents/the_super_app/app && npx vite-node scripts/verify-bican-may.mjs
 */
import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parseCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdSalesByOrder } from '../src/lib/parsers/ddSalesByOrder.js';
import { buildSlotAnalysis, parseTimeToMinutes, SLOT_NAMES } from '../src/lib/engine/slots.js';
import { normalizeDdFinancial } from '../src/lib/parsers/ddFinancial.js';
import { filterByDateRange, filterExcludedDates, groupBy } from '../src/lib/engine/aggregator.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '../../../..');
const salesPath = join(
  root,
  'sample_data/bican-sample-data/SALES_BY_ORDER_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.csv',
);

const PORTAL_SALES = 87678.43;
const PORTAL_ORDERS = 4454;
const PORTAL_AOV = 19.67;

const STORE_NAMES = {
  493: "McDonald's (493-S BND-N MICHIGAN)",
  3206: "McDonald's (3206-S BEND-WESTERN)",
  574: "McDonald's (574-S BND-S MICHIGAN)",
};

const postStart = new Date('2026-05-01T00:00:00');
const postEnd = new Date('2026-05-31T23:59:59.999');

function fmtUsd(n) {
  return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n) {
  return `${Number(n).toFixed(1)}%`;
}

const parsed = parseCsv(readFileSync(salesPath, 'utf8'));
const allOrders = normalizeDdSalesByOrder(parsed);

const finPath = join(root, 'sample_data/bican-sample-data/financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z/FINANCIAL_SIMPLIFIED_TRANSACTIONS_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv');
const ddFinancial = normalizeDdFinancial(parseCsv(readFileSync(finPath, 'utf8')));
const slotCfg = {
  preStart: new Date('2026-04-01'),
  preEnd: new Date('2026-04-30'),
  postStart,
  postEnd,
  excludedDates: [],
  platform: 'dd',
  salesOrders: allOrders,
};
const appSlots = buildSlotAnalysis(ddFinancial, slotCfg);
const appSlotSales = (appSlots.salesPrePost || []).reduce((s, r) => s + (r.post || 0), 0);
const appSlotOrders = (appSlots.ordersPrePost || []).reduce((s, r) => s + (r.post || 0), 0);

let may = filterByDateRange(allOrders, 'date', postStart, postEnd);
may = filterExcludedDates(may, 'date', []);

// Raw CSV May (no parser filters) for comparison
const rawMay = (parsed.data || []).filter((r) => {
  const d = String(r['Order placed date'] || '').trim();
  return d >= '2026-05-01' && d <= '2026-05-31';
});
const rawSales = rawMay.reduce((s, r) => s + (Number(r.Subtotal) || 0), 0);
const rawOrders = rawMay.length;
const rawCancelledRows = rawMay.filter(
  (r) => String(r['Is cancelled'] || r['Was Cancelled'] || '').toLowerCase() === 'true',
);
const rawCancelled = rawCancelledRows.length;
const rawCancelledSales = rawCancelledRows.reduce((s, r) => s + (Number(r.Subtotal) || 0), 0);
const rawNonCancelled = rawMay.filter(
  (r) => String(r['Is cancelled'] || r['Was Cancelled'] || '').toLowerCase() !== 'true',
);
const rawNonCancelledSales = rawNonCancelled.reduce((s, r) => s + (Number(r.Subtotal) || 0), 0);

const totalSales = may.reduce((s, o) => s + (o.subtotal || 0), 0);
const totalOrders = may.length;
const aov = totalOrders ? totalSales / totalOrders : 0;

// Store-wise
const byStore = groupBy(may, 'storeId');
const storeRows = [...byStore.entries()]
  .map(([storeId, rs]) => ({
    storeId,
    storeName: STORE_NAMES[storeId] || storeId,
    sales: rs.reduce((s, o) => s + (o.subtotal || 0), 0),
    orders: rs.length,
  }))
  .sort((a, b) => b.sales - a.sales);

// Slot-wise
const bySlot = groupBy(may, 'slot');
const slotRows = SLOT_NAMES.map((slot) => {
  const rs = bySlot.get(slot) || [];
  return {
    slot,
    sales: rs.reduce((s, o) => s + (o.subtotal || 0), 0),
    orders: rs.length,
  };
});
const slotSalesSum = slotRows.reduce((s, r) => s + r.sales, 0);
const slotOrdersSum = slotRows.reduce((s, r) => s + r.orders, 0);

// Hour-of-day (portal chart)
const hourSales = Array.from({ length: 24 }, () => 0);
const hourOrders = Array.from({ length: 24 }, () => 0);
let unknownTime = 0;
for (const o of may) {
  const mins = parseTimeToMinutes(o.time);
  if (mins < 0) {
    unknownTime += 1;
    continue;
  }
  const hour = Math.floor(mins / 60) % 24;
  hourSales[hour] += o.subtotal || 0;
  hourOrders[hour] += 1;
}

const hourLabels = [
  '12am', '1am', '2am', '3am', '4am', '5am', '6am', '7am', '8am', '9am', '10am', '11am',
  '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm',
];

const lines = [];
const log = (s = '') => lines.push(s);

log('# Bican DD — May 1–31, 2026 reconciliation (sales-by-order)');
log();
log('## Portal reference (DoorDash Sales dashboard)');
log(`- Gross sales: ${fmtUsd(PORTAL_SALES)}`);
log(`- Total orders: ${PORTAL_ORDERS.toLocaleString()}`);
log(`- Avg ticket: ${fmtUsd(PORTAL_AOV)}`);
log(`- Stores: 3`);
log();

log('## Totals from SALES_BY_ORDER');
log('| Metric | All May rows | Excl. cancelled | App normalized | Portal |');
log('|--------|--------------|-----------------|----------------|--------|');
log(`| Sales | ${fmtUsd(rawSales)} | ${fmtUsd(rawNonCancelledSales)} | ${fmtUsd(totalSales)} | ${fmtUsd(PORTAL_SALES)} |`);
log(`| Orders | ${rawOrders.toLocaleString()} | ${rawNonCancelled.length.toLocaleString()} | ${totalOrders.toLocaleString()} | ${PORTAL_ORDERS.toLocaleString()} |`);
log(`| AOV | ${fmtUsd(rawSales / rawOrders)} | ${fmtUsd(rawNonCancelledSales / rawNonCancelled.length)} | ${fmtUsd(aov)} | ${fmtUsd(PORTAL_AOV)} |`);
log();
log(`- Cancelled rows in May: ${rawCancelled.toLocaleString()} (${fmtUsd(rawCancelledSales)} subtotal)`);
log(`- Portal vs all rows: sales diff ${fmtUsd(PORTAL_SALES - rawSales)}, orders diff ${PORTAL_ORDERS - rawOrders}`);
log(`- Portal vs excl. cancelled: sales diff ${fmtUsd(PORTAL_SALES - totalSales)}, orders diff ${PORTAL_ORDERS - totalOrders}`);
log(`- Note: portal likely includes cancelled orders/deliveries in totals; export snapshot is Jun 3 vs portal Jun 12.`);
log();

log('## Store-wise sales & orders (excl. cancelled)');
log('| Store | Merchant ID | Sales | Orders | Sales % |');
log('|-------|-------------|-------|--------|---------|');
for (const s of storeRows) {
  log(`| ${s.storeName} | ${s.storeId} | ${fmtUsd(s.sales)} | ${s.orders.toLocaleString()} | ${fmtPct((s.sales / totalSales) * 100)} |`);
}
log(`| **Total** | **${fmtUsd(storeRows.reduce((a, b) => a + b.sales, 0))}** | **${storeRows.reduce((a, b) => a + b.orders, 0).toLocaleString()}** | 100% |`);
log();

log('## Slot-wise sales & orders (6 day-parts, order placed time)');
log('| Slot | Sales | Orders | Sales % | Orders % |');
log('|------|-------|--------|---------|----------|');
for (const s of slotRows) {
  log(`| ${s.slot} | ${fmtUsd(s.sales)} | ${s.orders.toLocaleString()} | ${fmtPct((s.sales / slotSalesSum) * 100)} | ${fmtPct((s.orders / slotOrdersSum) * 100)} |`);
}
log(`| **Total** | **${fmtUsd(slotSalesSum)}** | **${slotOrdersSum.toLocaleString()}** | 100% | 100% |`);
log();
log(`- Slot sales vs total: diff ${fmtUsd(slotSalesSum - totalSales)}`);
log(`- Slot orders vs total: diff ${slotOrdersSum - totalOrders}`);
log(`- App buildSlotAnalysis (sales-based) post sales: ${fmtUsd(appSlotSales)} (diff ${fmtUsd(appSlotSales - totalSales)})`);
log(`- App buildSlotAnalysis (sales-based) post orders: ${appSlotOrders.toLocaleString()} (diff ${appSlotOrders - totalOrders})`);
log();

log('## Hour-of-day (order placed time → clock hour)');
log('| Hour | Sales | Orders |');
log('|------|-------|--------|');
for (let h = 0; h < 24; h++) {
  log(`| ${hourLabels[h]} | ${fmtUsd(hourSales[h])} | ${hourOrders[h].toLocaleString()} |`);
}
log(`| Unknown time | — | ${unknownTime} |`);
log(`| **Total** | **${fmtUsd(hourSales.reduce((a, b) => a + b, 0))}** | **${hourOrders.reduce((a, b) => a + b, 0)}** |`);
log();

log('## Portal chart checkpoints (approximate from screenshot)');
log('| Hour | Portal (~) | Our sales |');
log('|------|------------|-----------|');
const checkpoints = [
  [0, 2800], [1, 5000], [4, 1100], [10, 6500], [14, 3200], [16, 4200],
];
for (const [h, portal] of checkpoints) {
  log(`| ${hourLabels[h]} | ${fmtUsd(portal)} | ${fmtUsd(hourSales[h])} |`);
}

const outPath = join(root, 'sample_data/bican-sample-data/MAY_2026_RECONCILIATION.md');
writeFileSync(outPath, lines.join('\n'));
console.log(lines.join('\n'));
console.log(`\nWrote ${outPath}`);
