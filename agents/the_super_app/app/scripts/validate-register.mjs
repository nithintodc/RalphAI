/**
 * Smoke-test register columns against bican-sample-data.
 *
 * From repo root:
 *   ./scripts/validate-register.sh
 *   # or
 *   cd agents/the_super_app/app && npm run validate-register
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';
import { parseCsv, parseUeFinancialCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdFinancial, normalizeDdErrorCharges } from '../src/lib/parsers/ddFinancial.js';
import { applyDdOrderPlacedTiming } from '../src/lib/parsers/ddOrderTiming.js';
import { normalizeUeFinancial } from '../src/lib/parsers/ueFinancial.js';
import { buildDdRegister, buildUeRegister } from '../src/lib/engine/register.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SAMPLE = join(__dirname, '../../../../bican-sample-data');

async function loadZipCsv(zipPath, matcher) {
  const buf = readFileSync(zipPath);
  const zip = await JSZip.loadAsync(buf);
  for (const [name, entry] of Object.entries(zip.files)) {
    if (entry.dir || !name.toLowerCase().endsWith('.csv')) continue;
    if (!matcher(name.toLowerCase())) continue;
    const text = await entry.async('string');
    return parseCsv(text);
  }
  return null;
}

function sumCol(rows, key) {
  return rows.reduce((s, r) => s + (Number(r[key]) || 0), 0);
}

function report(platform, rows, keys) {
  console.log(`\n=== ${platform} Register (${rows.length} rows) ===`);
  for (const k of keys) {
    console.log(`  ${k}: ${sumCol(rows, k).toFixed(2)}`);
  }
}

async function main() {
  const finZip = join(SAMPLE, 'financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.zip');
  const salesZip = join(SAMPLE, 'sales_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.zip');
  const ueCsv = join(SAMPLE, '6c2e1824-8f9c-49db-be72-d30749f33337-united_states.csv');

  const detailed = await loadZipCsv(finZip, (n) => n.includes('financial_detailed'));
  const errorCsv = await loadZipCsv(finZip, (n) => n.includes('error_charges'));
  const salesOrder = await loadZipCsv(salesZip, (n) => n.includes('sales_by_order'));

  let ddFinancial = normalizeDdFinancial(detailed);
  let ddFinancialError = errorCsv ? normalizeDdErrorCharges(errorCsv) : [];
  ddFinancial = applyDdOrderPlacedTiming(ddFinancial, salesOrder);
  ddFinancialError = applyDdOrderPlacedTiming(ddFinancialError, salesOrder);
  const ddRows = buildDdRegister({
    ddFinancial,
    ddSales: { byOrder: salesOrder },
    ddFinancialError,
  });

  report('DD', ddRows, [
    'newCustomerOrders',
    'repeatCustomerOrders',
    'dashPassOrders',
    'errorCharges',
    'adjustments',
    'totalItems',
  ]);

  const ueText = readFileSync(ueCsv, 'utf8');
  const ueParsed = parseUeFinancialCsv(ueText);
  const ueFinancial = normalizeUeFinancial(ueParsed);
  const ueRows = buildUeRegister({ ueFinancial });

  report('UE', ueRows, [
    'sales',
    'payouts',
    'marketplaceFee',
    'offers',
    'orderErrorAdjustments',
    'newCustomersFinancial',
  ]);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
