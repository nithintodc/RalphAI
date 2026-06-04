#!/usr/bin/env node
/**
 * Count SALES_BY_ORDER columns and show register customer/DashPass totals.
 *
 *   node scripts/show-sales-register.mjs
 *   node scripts/show-sales-register.mjs path/to/SALES_BY_ORDER.csv
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';
import { parseCsv } from '../agents/the_super_app/app/src/lib/parsers/zipHandler.js';
import { normalizeDdFinancial, normalizeDdErrorCharges } from '../agents/the_super_app/app/src/lib/parsers/ddFinancial.js';
import { applyDdOrderPlacedTiming } from '../agents/the_super_app/app/src/lib/parsers/ddOrderTiming.js';
import { normalizeDdSalesByOrder } from '../agents/the_super_app/app/src/lib/parsers/ddSalesByOrder.js';
import { buildDdRegister } from '../agents/the_super_app/app/src/lib/engine/register.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const DEFAULT_CSV = join(
  ROOT,
  'bican-sample-data/SALES_BY_ORDER_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.csv',
);

async function loadFinancialAndSales() {
  const finZip = join(ROOT, 'bican-sample-data/financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.zip');
  const salesZip = join(ROOT, 'bican-sample-data/sales_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.zip');
  const loadFromZip = async (zipPath, matcher) => {
    const buf = readFileSync(zipPath);
    const zip = await JSZip.loadAsync(buf);
    for (const [name, entry] of Object.entries(zip.files)) {
      if (entry.dir || !name.toLowerCase().endsWith('.csv')) continue;
      if (!matcher(name.toLowerCase())) continue;
      return parseCsv(await entry.async('string'));
    }
    return null;
  };
  const detailed = await loadFromZip(finZip, (n) => n.includes('financial_detailed'));
  const errorCsv = await loadFromZip(finZip, (n) => n.includes('error_charges'));
  const salesOrder = await loadFromZip(salesZip, (n) => n.includes('sales_by_order'));
  return { detailed, errorCsv, salesOrder };
}

function sumCol(rows, key) {
  return rows.reduce((s, r) => s + (Number(r[key]) || 0), 0);
}

async function main() {
  const csvPath = process.argv[2] || DEFAULT_CSV;
  const text = readFileSync(csvPath, 'utf8');
  const parsed = parseCsv(text);

  console.log('\n=== SALES_BY_ORDER file ===');
  console.log('Path:', csvPath);
  console.log('Columns:', parsed.columns.length);
  parsed.columns.forEach((c, i) => console.log(`  ${i + 1}. ${c}`));

  const normalized = normalizeDdSalesByOrder(parsed);
  let newC = 0;
  let repeatC = 0;
  let unknownC = 0;
  let dashYes = 0;
  let dashNo = 0;
  let items = 0;
  const slots = new Set();
  for (const o of normalized) {
    if (o.customerType === 'new') newC += 1;
    else if (o.customerType === 'repeat') repeatC += 1;
    else unknownC += 1;
    if (o.isDashPass === true) dashYes += 1;
    else if (o.isDashPass === false) dashNo += 1;
    items += o.itemCount || 0;
    slots.add(o.slot);
  }
  console.log('\nParsed orders:', normalized.length);
  console.log('  New customer:', newC);
  console.log('  Repeat:', repeatC);
  console.log('  Unknown:', unknownC);
  console.log('  DashPass:', dashYes);
  console.log('  Non-DashPass:', dashNo);
  console.log('  Total items:', items);
  console.log('  Slots seen:', [...slots].sort().join(', '));

  const { detailed, errorCsv, salesOrder } = await loadFinancialAndSales();
  let ddFinancial = normalizeDdFinancial(detailed);
  let ddFinancialError = errorCsv ? normalizeDdErrorCharges(errorCsv) : [];
  ddFinancial = applyDdOrderPlacedTiming(ddFinancial, salesOrder);
  ddFinancialError = applyDdOrderPlacedTiming(ddFinancialError, salesOrder);

  const register = buildDdRegister({
    ddFinancial,
    ddSales: { byOrder: salesOrder },
    ddFinancialError,
  });

  console.log('\n=== DD Register (weekday × slot averages) ===');
  console.log('Rows:', register.length);
  for (const k of [
    'newCustomerOrders',
    'repeatCustomerOrders',
    'unknownCustomerOrders',
    'dashPassOrders',
    'nonDashPassOrders',
    'totalItems',
  ]) {
    console.log(`  ${k}: ${sumCol(register, k).toFixed(2)}`);
  }
  console.log('\nSample rows (first 3):');
  register.slice(0, 3).forEach((r) => {
    console.log(
      `  ${r.storeId} · ${r.dayOfWeek} · ${r.slot} → new=${r.newCustomerOrders} repeat=${r.repeatCustomerOrders} dash=${r.dashPassOrders} items=${r.totalItems}`,
    );
  });
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
