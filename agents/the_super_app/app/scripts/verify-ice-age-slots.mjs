/**
 * Verify slot sales sum vs summary post total for ICE-AGE-NEW sample data.
 * Run: cd agents/the_super_app/app && npx vite-node scripts/verify-ice-age-slots.mjs
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';
import { parseCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdFinancial } from '../src/lib/parsers/ddFinancial.js';
import { buildSlotAnalysis, getSlot } from '../src/lib/engine/slots.js';
import { groupBy } from '../src/lib/engine/aggregator.js';
import { buildFourWindowAggregation } from '../src/lib/engine/periodEngine.js';
import { differenceInCalendarDays } from 'date-fns';
import { parseDate } from '../src/lib/utils/dateUtils.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '../../../..');
const zipPath = join(root, 'sample_data/ICE-AGE-NEW/financial_2026-04-01_2026-05-31_M1gX0_2026-06-10T13-19-31Z.zip');

const buf = readFileSync(zipPath);
const zip = await JSZip.loadAsync(buf);
let csvText = null;
for (const [name, entry] of Object.entries(zip.files)) {
  if (!entry.dir && name.toLowerCase().includes('detailed') && name.endsWith('.csv')) {
    csvText = await entry.async('string');
    break;
  }
}
if (!csvText) {
  for (const [name, entry] of Object.entries(zip.files)) {
    if (!entry.dir && name.endsWith('.csv')) {
      csvText = await entry.async('string');
      break;
    }
  }
}

const parsed = parseCsv(csvText);
const dd = normalizeDdFinancial(parsed).filter(Boolean);

const preStart = parseDate('2026-04-01');
const preEnd = parseDate('2026-04-30');
const postStart = parseDate('2026-05-01');
const postEnd = parseDate('2026-05-31');
const postDays = differenceInCalendarDays(postEnd, postStart) + 1;

const slotCfg = { preStart, preEnd, postStart, postEnd, excludedDates: [], platform: 'dd' };
const slots = buildSlotAnalysis(dd, slotCfg);

const slotPostSum = slots.salesPrePost.reduce((s, r) => s + (r.post || 0), 0);

const windows = buildFourWindowAggregation(dd, {
  preStart,
  preEnd,
  postStart,
  postEnd,
  excludedDates: [],
  excludedStores: [],
  dateField: 'date',
  storeField: 'storeId',
  sumFields: ['subtotal'],
  uniqueFields: ['orderId'],
});
const postTotal = windows.post.reduce((s, r) => s + (r.subtotal || 0), 0);

console.log('ICE-AGE-NEW DoorDash financial');
console.log(`Post: ${postStart.toISOString().slice(0, 10)} → ${postEnd.toISOString().slice(0, 10)} (${postDays} days)`);
console.log(`Summary post sales (absolute): $${postTotal.toFixed(2)}`);
console.log(`Sum of slot Post column (absolute): $${slotPostSum.toFixed(2)}`);
console.log(`Reconciles with summary post sales? ${Math.abs(slotPostSum - postTotal) < 1 ? 'YES' : `NO (diff $${(slotPostSum - postTotal).toFixed(2)})`}`);
console.log('\nPer-slot Post (absolute):');
for (const r of slots.salesPrePost) {
  console.log(`  ${r.slot.padEnd(12)} $${Number(r.post).toFixed(1)}`);
}

import { filterByDateRange, filterExcludedDates } from '../src/lib/engine/aggregator.js';
import { isPresentTimeValue } from '../src/lib/constants/orderTimeColumns.js';

let postRows = filterByDateRange(dd, 'date', postStart, postEnd);
postRows = filterExcludedDates(postRows, 'date', []);
const withTime = postRows.filter((r) => isPresentTimeValue(r.time));
const withoutTime = postRows.filter((r) => !isPresentTimeValue(r.time));
const sumSub = (rows) => rows.reduce((s, r) => s + (r.subtotal || 0), 0);
console.log('\nPost-period order time coverage:');
console.log(`  Rows with slot time: ${withTime.length} ($${sumSub(withTime).toFixed(2)} subtotal)`);
console.log(`  Rows without time: ${withoutTime.length} ($${sumSub(withoutTime).toFixed(2)} subtotal)`);
console.log(`  Expected daily avg total sales: $${(sumSub(withTime) / postDays).toFixed(2)}/day`);
console.log(`  Slot sum should ≈ daily avg if all timed orders slotted: $${slotPostSum.toFixed(2)}/day`);

// Unknown / unslotted orders
const byOrder = groupBy(postRows, 'orderId');
let slottedSales = 0;
let unknownSales = 0;
let noOrderIdSales = 0;
for (const [orderId, rs] of byOrder) {
  const sales = rs.reduce((s, r) => s + (r.subtotal || 0), 0);
  if (!orderId) { noOrderIdSales += sales; continue; }
  const slot = getSlot(rs[0].time, 'dd');
  if (slot === 'Unknown' || !['Overnight', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late Night'].includes(slot)) {
    unknownSales += sales;
  } else {
    slottedSales += sales;
  }
}
console.log('\nPost-period sales by slot assignment:');
console.log(`  Assigned to day-part slots: $${slottedSales.toFixed(2)} (${(100 * slottedSales / postTotal).toFixed(1)}%)`);
console.log(`  Unknown / unassigned slot: $${unknownSales.toFixed(2)} (${(100 * unknownSales / postTotal).toFixed(1)}%)`);
console.log(`  Missing order ID: $${noOrderIdSales.toFixed(2)}`);
console.log(`  Slotted daily avg: $${(slottedSales / postDays).toFixed(2)}/day (should match slot sum $${slotPostSum.toFixed(2)})`);
console.log(`  Slotted absolute total: $${slottedSales.toFixed(2)} (sum of slots should equal this after dailyAvg fix)`);

const unknownSamples = new Map();
for (const [orderId, rs] of byOrder) {
  if (!orderId) continue;
  const slot = getSlot(rs[0].time, 'dd');
  if (slot !== 'Unknown') continue;
  const t = String(rs[0].time ?? '').slice(0, 50);
  unknownSamples.set(t, (unknownSamples.get(t) || 0) + 1);
  if (unknownSamples.size >= 8) break;
}
console.log('\nSample Unknown time values:', [...unknownSamples.entries()]);
