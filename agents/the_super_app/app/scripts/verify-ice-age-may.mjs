/**
 * May 1–31 Ice Age DD reconciliation: totals, slots, stores vs portal.
 * Run: cd agents/the_super_app/app && npx vite-node scripts/verify-ice-age-may.mjs
 */
import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';
import { parseCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdFinancial } from '../src/lib/parsers/ddFinancial.js';
import { buildSlotAnalysis, parseTimeToMinutes, SLOT_NAMES } from '../src/lib/engine/slots.js';
import { buildDdPlatformData } from '../src/lib/engine/periodEngine.js';
import { buildSummaryRow } from '../src/lib/engine/metrics.js';
import { filterByDateRange, filterExcludedDates, groupBy, countUnique } from '../src/lib/engine/aggregator.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '../../../..');
const zipPath = join(root, 'sample_data/ICE-AGE-NEW/financial_2026-04-01_2026-05-31_M1gX0_2026-06-10T13-19-31Z.zip');

const PORTAL_SALES = 1689105.33;
const PORTAL_ORDERS = 86283;

const postStart = new Date('2026-05-01T00:00:00');
const postEnd = new Date('2026-05-31T23:59:59.999');

async function loadDdFinancial() {
  const buf = readFileSync(zipPath);
  const zip = await JSZip.loadAsync(buf);
  let csvText = null;
  for (const [name, entry] of Object.entries(zip.files)) {
    if (!entry.dir && name.toLowerCase().includes('detailed') && name.endsWith('.csv')) {
      csvText = await entry.async('string');
      break;
    }
  }
  const parsed = parseCsv(csvText);
  return normalizeDdFinancial(parsed).filter(Boolean);
}

function sumSub(rows) {
  return rows.reduce((s, r) => s + (r.subtotal || 0), 0);
}

function fmtUsd(n) {
  return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n) {
  return `${Number(n).toFixed(1)}%`;
}

const dd = await loadDdFinancial();
let may = filterByDateRange(dd, 'date', postStart, postEnd);
may = filterExcludedDates(may, 'date', []);

const orderOnly = may.filter((r) => String(r.transactionType || '').toLowerCase() === 'order');
const allSales = sumSub(may);
const orderSales = sumSub(orderOnly);
const allOrders = countUnique(may, 'orderId');
const orderTxnOrders = countUnique(orderOnly, 'orderId');

// App engine path (store tables → summary)
const cfg = {
  preStart: new Date('2026-04-01'),
  preEnd: new Date('2026-04-30'),
  postStart,
  postEnd,
  excludedDates: [],
  excludedStores: [],
};
const storeData = buildDdPlatformData(dd, cfg);
const salesSummary = buildSummaryRow(storeData, 'sales');
const ordersSummary = buildSummaryRow(storeData, 'orders');
const storePostSales = storeData.reduce((s, r) => s + (r.post_sales || 0), 0);
const storePostOrders = storeData.reduce((s, r) => s + (r.post_orders || 0), 0);

// Slots (app engine)
const slots = buildSlotAnalysis(dd, { ...cfg, platform: 'dd' });
const slotSalesRows = slots.salesPrePost || [];
const slotOrderRows = slots.ordersPrePost || [];
const slotSalesSum = slotSalesRows.reduce((s, r) => s + (r.post || 0), 0);
const slotOrdersSum = slotOrderRows.reduce((s, r) => s + (r.post || 0), 0);

// Hour-of-day distribution (for portal chart comparison)
const byOrder = groupBy(may, 'orderId');
const hourSales = Array.from({ length: 24 }, () => 0);
const hourOrders = Array.from({ length: 24 }, () => 0);
let unknownHourSales = 0;
let unknownHourOrders = 0;
for (const [orderId, rs] of byOrder) {
  if (!orderId) continue;
  const sales = rs.reduce((s, r) => s + (r.subtotal || 0), 0);
  const mins = parseTimeToMinutes(rs[0].time);
  if (mins < 0) {
    unknownHourSales += sales;
    unknownHourOrders += 1;
    continue;
  }
  const hour = Math.floor(mins / 60) % 24;
  hourSales[hour] += sales;
  hourOrders[hour] += 1;
}

const lines = [];
const log = (s = '') => lines.push(s);

log('# Ice Age DD — May 1–31, 2026 reconciliation');
log();
log('## Portal reference (DoorDash Sales dashboard)');
log(`- Gross sales: ${fmtUsd(PORTAL_SALES)}`);
log(`- Total orders: ${PORTAL_ORDERS.toLocaleString()}`);
log(`- Avg ticket: ${fmtUsd(PORTAL_SALES / PORTAL_ORDERS)}`);
log();

log('## Totals from raw financial (May rows)');
log('| Metric | All txn rows | Order txn only | App summary (post) | Portal | Match? |');
log('|--------|--------------|----------------|---------------------|--------|--------|');
log(`| Sales | ${fmtUsd(allSales)} | ${fmtUsd(orderSales)} | ${fmtUsd(salesSummary.post)} | ${fmtUsd(PORTAL_SALES)} | ${Math.abs(salesSummary.post - PORTAL_SALES) < 1 ? 'YES' : `diff ${fmtUsd(salesSummary.post - PORTAL_SALES)}`} |`);
log(`| Orders | ${allOrders.toLocaleString()} | ${orderTxnOrders.toLocaleString()} | ${Math.round(ordersSummary.post).toLocaleString()} | ${PORTAL_ORDERS.toLocaleString()} | ${Math.round(ordersSummary.post) === PORTAL_ORDERS ? 'YES' : `diff ${Math.round(ordersSummary.post - PORTAL_ORDERS)}`} |`);
log();

log('## Store-level rollup (post period)');
log(`- Stores: ${storeData.length}`);
log(`- Sum of store post sales: ${fmtUsd(storePostSales)} (diff vs summary ${fmtUsd(storePostSales - salesSummary.post)})`);
log(`- Sum of store post orders: ${Math.round(storePostOrders).toLocaleString()} (diff vs summary ${Math.round(storePostOrders - ordersSummary.post)})`);
log();

log('## Slot-level (6 day-parts, post period absolutes)');
log('| Slot | Sales | Orders | Sales % |');
log('|------|-------|--------|---------|');
for (const name of SLOT_NAMES) {
  const s = slotSalesRows.find((r) => r.slot === name);
  const o = slotOrderRows.find((r) => r.slot === name);
  const sales = s?.post || 0;
  const orders = o?.post || 0;
  log(`| ${name} | ${fmtUsd(sales)} | ${Math.round(orders).toLocaleString()} | ${fmtPct((sales / slotSalesSum) * 100)} |`);
}
log(`| **Total** | **${fmtUsd(slotSalesSum)}** | **${Math.round(slotOrdersSum).toLocaleString()}** | 100% |`);
log();
log(`- Slot sales vs summary: diff ${fmtUsd(slotSalesSum - salesSummary.post)}`);
log(`- Slot orders vs summary: diff ${Math.round(slotOrdersSum - ordersSummary.post)}`);
log();

log('## Hour-of-day sales (order time → clock hour)');
log('| Hour | Sales | Orders | Chart bucket (portal) |');
log('|------|-------|--------|------------------------|');
const hourLabels = ['12am', '1am', '2am', '3am', '4am', '5am', '6am', '7am', '8am', '9am', '10am', '11am', '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm'];
for (let h = 0; h < 24; h++) {
  log(`| ${hourLabels[h]} | ${fmtUsd(hourSales[h])} | ${hourOrders[h].toLocaleString()} | — |`);
}
log(`| Unknown time | ${fmtUsd(unknownHourSales)} | ${unknownHourOrders} | — |`);
log(`| **Total** | **${fmtUsd(hourSales.reduce((a, b) => a + b, 0) + unknownHourSales)}** | **${hourOrders.reduce((a, b) => a + b, 0) + unknownHourOrders}** | — |`);
log();

log('## Top 10 stores by post sales');
const top = [...storeData].sort((a, b) => (b.post_sales || 0) - (a.post_sales || 0)).slice(0, 10);
log('| Store ID | Store name | Post sales | Post orders |');
log('|----------|------------|------------|-------------|');
for (const s of top) {
  log(`| ${s.storeId} | ${(s.storeName || '').slice(0, 30)} | ${fmtUsd(s.post_sales)} | ${Math.round(s.post_orders || 0)} |`);
}

const outPath = join(root, 'sample_data/ICE-AGE-NEW/MAY_RECONCILIATION.md');
writeFileSync(outPath, lines.join('\n'));
console.log(lines.join('\n'));
console.log(`\nWrote ${outPath}`);
