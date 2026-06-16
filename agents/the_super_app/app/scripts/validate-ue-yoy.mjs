#!/usr/bin/env node
/** Quick check: UE CSV parses with 2025 rows and LY post window has sales. */
import fs from 'fs';
import { parseUeFinancialCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeUeFinancial } from '../src/lib/parsers/ueFinancial.js';
import { buildUePlatformData } from '../src/lib/engine/periodEngine.js';
import { buildSummaryTables } from '../src/lib/engine/metrics.js';
import { parseDate } from '../src/lib/utils/dateUtils.js';

const csvPath = process.argv[2];
if (!csvPath) {
  console.error('Usage: node scripts/validate-ue-yoy.mjs <ue-financial.csv>');
  process.exit(1);
}

const text = fs.readFileSync(csvPath, 'utf8');
const parsed = parseUeFinancialCsv(text);
const rows = normalizeUeFinancial(parsed);
const years = {};
for (const r of rows) {
  const y = r.date.getFullYear();
  years[y] = (years[y] || 0) + 1;
}

const config = {
  preStart: parseDate('4/1/2026'),
  preEnd: parseDate('4/30/2026'),
  postStart: parseDate('5/1/2026'),
  postEnd: parseDate('5/31/2026'),
  excludedDates: [],
  excludedStores: [],
};

const ueStore = buildUePlatformData(rows, config);
const { ue } = buildSummaryTables([], ueStore);
const sales = ue.find((r) => r.metric === 'sales');

console.log('Parsed rows:', rows.length);
console.log('Years:', years);
console.log('UE sales summary:', {
  pre: sales?.pre,
  post: sales?.post,
  preLY: sales?.preLY,
  postLY: sales?.postLY,
  yoyPct: sales?.yoyPct,
  lyGrowthPct: sales?.lyGrowthPct,
});

if (!sales?.postLY) {
  console.error('FAIL: postLY is still 0 — check CSV dates or period config');
  process.exit(1);
}
console.log('OK: LY post sales present');
