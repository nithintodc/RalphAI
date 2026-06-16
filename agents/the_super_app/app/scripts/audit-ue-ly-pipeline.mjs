/**
 * UE LY audit — match Ice Age UI periods and overnight totals.
 * Run: cd agents/the_super_app/app && npx vite-node scripts/audit-ue-ly-pipeline.mjs
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { endOfMonth, startOfMonth, subMonths, max as dfMax, min as dfMin } from 'date-fns';
import { parseUeFinancialCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeUeFinancial, getDateRange } from '../src/lib/parsers/ueFinancial.js';
import { buildSlotAnalysis } from '../src/lib/engine/slots.js';
import { parseDate, getLastYearDates } from '../src/lib/utils/dateUtils.js';
import { filterByDateRange } from '../src/lib/engine/aggregator.js';
import { suggestPrePostFromBounds } from '../src/lib/utils/uploadedDataBounds.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '../../../..');
const csvPath = join(root, 'sample_data/ICE-AGE-NEW/UE-2026(2025&2026).csv');

const rows = normalizeUeFinancial(parseUeFinancialCsv(readFileSync(csvPath, 'utf8')));
const range = getDateRange(rows);

function runSlots(label, cfg) {
  const slots = buildSlotAnalysis(rows, { ...cfg, excludedDates: [], platform: 'ue' });
  const o = slots.salesPrePost.find((r) => r.slot === 'Overnight');
  const ly = slots.salesYoY.find((r) => r.slot === 'Overnight');
  const lyPre = getLastYearDates(cfg.preStart, cfg.preEnd);
  const lyPost = getLastYearDates(cfg.postStart, cfg.postEnd);
  const lyPostRows = filterByDateRange(rows, 'date', lyPost.start, lyPost.end);
  console.log(`\n=== ${label} ===`);
  console.log('Pre:', cfg.preStart.toISOString(), '→', cfg.preEnd.toISOString());
  console.log('Post:', cfg.postStart.toISOString(), '→', cfg.postEnd.toISOString());
  console.log('LY post window:', lyPost.start.toISOString(), '→', lyPost.end.toISOString());
  console.log('Rows in LY post window:', lyPostRows.length, 'with orderId:', lyPostRows.filter((r) => r.orderId).length);
  console.log('lyCoverage:', slots.lyCoverage);
  console.log('Overnight:', { pre: o?.pre, post: o?.post, lyPrevspost: o?.lyPrevspost, lyGrowthPct: o?.lyGrowthPct });
  console.log('Overnight YoY postLY:', ly?.postLY);
  return o;
}

// UI screenshot: Pre Apr 1–30, Post May 1–30, 2026
const aprPreStart = parseDate('4/1/2026');
const aprPreEnd = parseDate('4/30/2026');
const mayPostStart = parseDate('5/1/2026');
const mayPostEnd = parseDate('5/30/2026');

runSlots('Manual Apr/May (May 30 end)', {
  preStart: aprPreStart,
  preEnd: aprPreEnd,
  postStart: mayPostStart,
  postEnd: mayPostEnd,
});

runSlots('Auto suggestPrePostFromBounds', suggestPrePostFromBounds(range));

// Match screenshot overnight post $56,730
const target = 56730;
let best = null;
for (let endDay = 28; endDay <= 31; endDay++) {
  const cfg = {
    preStart: aprPreStart,
    preEnd: aprPreEnd,
    postStart: mayPostStart,
    postEnd: parseDate(`5/${endDay}/2026`),
  };
  const o = buildSlotAnalysis(rows, { ...cfg, excludedDates: [], platform: 'ue' })
    .salesPrePost.find((r) => r.slot === 'Overnight');
  const diff = Math.abs((o?.post || 0) - target);
  if (!best || diff < best.diff) best = { endDay, post: o?.post, ly: o?.lyPrevspost, diff };
}
console.log('\nBest overnight post match for $56,730:', best);

// String config dates (would break Date >= string compares)
const badCfg = {
  preStart: '2026-04-01T00:00:00.000Z',
  preEnd: '2026-04-30T00:00:00.000Z',
  postStart: '2026-05-01T00:00:00.000Z',
  postEnd: '2026-05-30T00:00:00.000Z',
};
const bad = buildSlotAnalysis(rows, { ...badCfg, excludedDates: [], platform: 'ue' })
  .salesPrePost.find((r) => r.slot === 'Overnight');
console.log('\nString config dates (invalid compare):', bad);
