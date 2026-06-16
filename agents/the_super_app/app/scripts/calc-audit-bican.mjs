/**
 * Audit app calculation logic vs manual pivots on bican sample data.
 * Run: cd agents/the_super_app/app && npx vite-node scripts/calc-audit-bican.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';
import { parseCsv, parseUeFinancialCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdFinancial, normalizeDdErrorCharges } from '../src/lib/parsers/ddFinancial.js';
import { normalizeUeFinancial } from '../src/lib/parsers/ueFinancial.js';
import { normalizeDdSalesByOrder } from '../src/lib/parsers/ddSalesByOrder.js';
import { normalizeDdPromotion, normalizeDdSponsored } from '../src/lib/parsers/ddMarketing.js';
import { buildDdRegister, buildUeRegister } from '../src/lib/engine/register.js';
import { buildDdPlatformData, buildUePlatformData } from '../src/lib/engine/periodEngine.js';
import { addDerivedMetrics, buildSummaryTables } from '../src/lib/engine/metrics.js';
import { buildCorpVsTodcTable } from '../src/lib/engine/marketing.js';
import { parseDate } from '../src/lib/utils/dateUtils.js';
import { safeDivide, round, cleanInfinity } from '../src/lib/utils/safeMath.js';
import { getSlot, SLOT_NAMES, DAY_NAMES } from '../src/lib/engine/slots.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SAMPLE = join(__dirname, '../../../../sample_data/bican-sample-data');
const REPORT_PATH = join(__dirname, '../../../../sample_data/bican-sample-data/CALC_AUDIT_REPORT.md');

const PRE_START = parseDate('05/01/2025');
const PRE_END = parseDate('05/31/2025');
const POST_START = parseDate('06/01/2025');
const POST_END = parseDate('06/03/2025');

const findings = [];

function pctDiff(a, b) {
  if (a === b) return 0;
  const denom = Math.abs(a) || Math.abs(b) || 1;
  return round(((a - b) / denom) * 100, 2);
}

function compare(name, appVal, manualVal, { tol = 0.01, note = '' } = {}) {
  const diff = round(appVal - manualVal, 4);
  const drift = Math.abs(diff) > tol;
  const entry = {
    name,
    app: round(appVal, 4),
    manual: round(manualVal, 4),
    diff,
    driftPct: pctDiff(appVal, manualVal),
    status: drift ? 'DRIFT' : 'OK',
    note,
  };
  findings.push(entry);
  return entry;
}

async function loadZipCsv(zipPath, matcher) {
  const buf = readFileSync(zipPath);
  const zip = await JSZip.loadAsync(buf);
  for (const [name, entry] of Object.entries(zip.files)) {
    if (entry.dir || !name.toLowerCase().endsWith('.csv')) continue;
    if (!matcher(name.toLowerCase())) continue;
    return parseCsv(await entry.async('string'));
  }
  return null;
}

function loadCsv(path) {
  return parseCsv(readFileSync(path, 'utf8'));
}

function sumCol(rows, key) {
  return rows.reduce((s, r) => s + (Number(r[key]) || 0), 0);
}

function inWindow(d, start, end) {
  return d && d >= start && d <= end;
}

function filterWindow(rows, start, end) {
  return rows.filter((r) => inWindow(r.date, start, end));
}

function manualDdFinancialAgg(financial, start, end) {
  const scoped = filterWindow(financial, start, end);
  let sales = 0;
  let payouts = 0;
  const orderIds = new Set();
  for (const r of scoped) {
    sales += r.subtotal || 0;
    payouts += r.netTotal || 0;
    if (r.orderId) orderIds.add(r.orderId);
  }
  return { sales: round(sales), payouts: round(payouts), orders: orderIds.size };
}

function manualDdFinancialOrdersOnly(financial, start, end) {
  const scoped = filterWindow(financial, start, end).filter(
    (r) => String(r.transactionType || '').toLowerCase() === 'order',
  );
  let sales = 0;
  let payouts = 0;
  return {
    sales: round(scoped.reduce((s, r) => s + (r.subtotal || 0), 0)),
    payouts: round(scoped.reduce((s, r) => s + (r.netTotal || 0), 0)),
    orders: scoped.length,
  };
}

function platformTotals(storeData, window, metric) {
  return round(sumCol(storeData, `${window}_${metric}`));
}

function manualSalesByOrderCounts(parsed) {
  const orders = normalizeDdSalesByOrder(parsed);
  let newC = 0;
  let repeatC = 0;
  let unknownC = 0;
  let dashYes = 0;
  let dashNo = 0;
  let items = 0;
  let sales = 0;
  for (const o of orders) {
    if (o.customerType === 'new') newC += 1;
    else if (o.customerType === 'repeat') repeatC += 1;
    else unknownC += 1;
    if (o.isDashPass === true) dashYes += 1;
    else if (o.isDashPass === false) dashNo += 1;
    items += o.itemCount || 0;
    sales += Number(o.subtotal) || 0;
  }
  return { orders: orders.length, newC, repeatC, unknownC, dashYes, dashNo, items, sales: round(sales) };
}

function manualRawSalesCounts(parsed) {
  const { data } = parsed;
  const bool = (v) => String(v ?? '').trim().toLowerCase() === 'true';
  let newC = 0;
  let repeatC = 0;
  let dashYes = 0;
  let items = 0;
  let sales = 0;
  for (const row of data) {
    const ct = String(row['Customer type'] || row['Customer Type'] || '').toLowerCase();
    if (ct === 'new') newC += 1;
    else if (ct === 'repeat' || ct.includes('existing')) repeatC += 1;
    if (bool(row['Is DashPass'] ?? row['Is Dashpass'])) dashYes += 1;
    items += Number(row['Total item count'] || row['Item count'] || 0) || 0;
    sales += Number(row.Subtotal || 0) || 0;
  }
  return { orders: data.length, newC, repeatC, dashYes, items, sales: round(sales) };
}

function manualMarketingCorpTodc(promo, sponsored, start, end) {
  const all = [...filterWindow(promo, start, end), ...filterWindow(sponsored, start, end)];
  const calc = (rows) => {
    const orders = rows.reduce((s, r) => s + (r.orders || 0), 0);
    const sales = rows.reduce((s, r) => s + (r.sales || 0), 0);
    const spend = rows.reduce((s, r) => s + Math.abs(r.spend || 0), 0);
    return { orders: Math.round(orders), sales: round(sales), spend: round(spend) };
  };
  const corp = calc(all.filter((r) => !r.isSelfServe));
  const todc = calc(all.filter((r) => r.isSelfServe));
  const total = calc(all);
  return { corp, todc, total };
}

function dayOfWeekLabel(date) {
  return DAY_NAMES[(date.getDay() + 6) % 7] ?? '';
}

/** Manual register sales metrics BEFORE weekday averaging (raw order counts). */
function manualRawRegisterSalesCounts(salesParsed, ddFinancial) {
  const orders = normalizeDdSalesByOrder(salesParsed);
  const merchantIds = new Set(ddFinancial.map((r) => r.merchantStoreId).filter(Boolean));
  const ddToMerchant = new Map();
  for (const r of ddFinancial) {
    if (r.ddStoreId && r.merchantStoreId) ddToMerchant.set(String(r.ddStoreId), r.merchantStoreId);
  }
  let newC = 0;
  let repeatC = 0;
  let dashYes = 0;
  let items = 0;
  for (const o of orders) {
    let storeId = String(o.storeId || '').trim();
    if (ddToMerchant.has(storeId)) storeId = ddToMerchant.get(storeId);
    if (!storeId) continue;
    if (o.customerType === 'new') newC += 1;
    else if (o.customerType === 'repeat') repeatC += 1;
    if (o.isDashPass === true) dashYes += 1;
    items += o.itemCount || 0;
  }
  return { newC, repeatC, dashYes, items, merchantStoreCount: merchantIds.size };
}

function renderReport() {
  const drift = findings.filter((f) => f.status === 'DRIFT');
  const ok = findings.filter((f) => f.status === 'OK');
  const lines = [
    '# Bican Sample Data — Calculation Audit Report',
    '',
    `Generated: ${new Date().toISOString()}`,
    `Sample path: \`sample_data/bican-sample-data\``,
    `Period windows: Pre ${PRE_START.toISOString().slice(0, 10)} → ${PRE_END.toISOString().slice(0, 10)}, Post ${POST_START.toISOString().slice(0, 10)} → ${POST_END.toISOString().slice(0, 10)}`,
    '',
    '## Summary',
    '',
    `| Status | Count |`,
    `|--------|-------|`,
    `| OK | ${ok.length} |`,
    `| DRIFT | ${drift.length} |`,
    '',
    '## All Checks',
    '',
    '| Check | App | Manual | Diff | Drift% | Status | Notes |',
    '|-------|-----|--------|------|--------|--------|-------|',
  ];
  for (const f of findings) {
    lines.push(`| ${f.name} | ${f.app} | ${f.manual} | ${f.diff} | ${f.driftPct}% | ${f.status} | ${f.note || ''} |`);
  }
  lines.push('', '## Logic Notes', '');
  lines.push(...logicNotes);
  return lines.join('\n');
}

const logicNotes = [];

async function main() {
  const finZip = join(SAMPLE, 'financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.zip');
  const salesZip = join(SAMPLE, 'sales_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.zip');
  const mktZip = join(SAMPLE, 'marketing_2025-01-01_2026-06-03_rdK2w_2026-06-04T05-23-55Z.zip');
  const ueCsv = join(SAMPLE, '6c2e1824-8f9c-49db-be72-d30749f33337-united_states.csv');
  const salesByStoreCsv = join(SAMPLE, 'SALES_BY_STORE_2025-01-01_2026-06-03_NE9lv_2026-06-04T05-23-17Z.csv');
  const productMixCsv = join(SAMPLE, 'PRODUCT_MIX_2025-01-01_2026-06-03_DSsjJ_2026-06-04T05-23-33Z.csv');
  const payoutSummaryCsv = join(
    SAMPLE,
    'financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z/FINANCIAL_PAYOUT_SUMMARY_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv',
  );

  const detailed = await loadZipCsv(finZip, (n) => n.includes('financial_detailed'));
  const errorCsv = await loadZipCsv(finZip, (n) => n.includes('error_charges'));
  const salesOrder = await loadZipCsv(salesZip, (n) => n.includes('sales_by_order'));
  const promoCsv = await loadZipCsv(mktZip, (n) => n.includes('marketing_promotion'));
  const sponsoredCsv = await loadZipCsv(mktZip, (n) => n.includes('marketing_sponsored'));

  const ddFinancial = normalizeDdFinancial(detailed);
  const ddFinancialError = errorCsv ? normalizeDdErrorCharges(errorCsv) : [];
  const promo = normalizeDdPromotion(promoCsv);
  const sponsored = normalizeDdSponsored(sponsoredCsv);

  const periodConfig = {
    preStart: PRE_START,
    preEnd: PRE_END,
    postStart: POST_START,
    postEnd: POST_END,
    excludedDates: [],
    excludedStores: [],
  };
  const registerConfig = {
    ddPostStart: POST_START,
    ddPostEnd: POST_END,
    uePostStart: POST_START,
    uePostEnd: POST_END,
    excludedDates: [],
    ddExcludedStores: [],
    ueExcludedStores: [],
  };

  const ddStoreData = addDerivedMetrics(buildDdPlatformData(ddFinancial, periodConfig));
  const { combined: ddSummary } = buildSummaryTables(ddStoreData, []);

  // --- 1. DD Financial platform totals (post window) ---
  const manualPost = manualDdFinancialAgg(ddFinancial, POST_START, POST_END);
  const appPost = {
    sales: platformTotals(ddStoreData, 'post', 'sales'),
    payouts: platformTotals(ddStoreData, 'post', 'payouts'),
    orders: platformTotals(ddStoreData, 'post', 'orders'),
  };
  compare('DD Financial POST sales (all txn rows)', appPost.sales, manualPost.sales, { tol: 1 });
  compare('DD Financial POST payouts (all txn rows)', appPost.payouts, manualPost.payouts, { tol: 1 });
  compare('DD Financial POST orders (nunique orderId)', appPost.orders, manualPost.orders, { tol: 0 });

  const manualPostOrdersOnly = manualDdFinancialOrdersOnly(ddFinancial, POST_START, POST_END);
  compare(
    'DD Financial POST sales — app vs Order-only rows',
    appPost.sales,
    manualPostOrdersOnly.sales,
    {
      tol: 1,
      note: 'DeepDive filters Transaction type=Order; app sums all rows',
    },
  );

  // --- 2. Derived metrics ---
  const salesRow = ddSummary.find((r) => r.metric === 'sales');
  const payoutsRow = ddSummary.find((r) => r.metric === 'payouts');
  const ordersRow = ddSummary.find((r) => r.metric === 'orders');
  const profRow = ddSummary.find((r) => r.metric === 'profitability');
  const aovRow = ddSummary.find((r) => r.metric === 'aov');

  const manualProfPost = round(safeDivide(payoutsRow.post, salesRow.post) * 100);
  const manualAovPost = round(safeDivide(salesRow.post, ordersRow.post), 2);
  compare('Summary profitability POST %', profRow.post, manualProfPost, { tol: 0.1 });
  compare('Summary AOV POST', aovRow.post, manualAovPost, { tol: 0.01 });

  const manualGrowth = round(cleanInfinity(safeDivide(salesRow.post - salesRow.pre, salesRow.pre) * 100));
  compare('Summary sales growth% pre→post', salesRow.growthPct, manualGrowth, { tol: 0.1 });

  // --- 3. Register ---
  const ddRegister = buildDdRegister(
    { ddFinancial, ddSales: { byOrder: salesOrder }, ddFinancialError },
    registerConfig,
  );
  const regSums = {
    newCustomerOrders: sumCol(ddRegister, 'newCustomerOrders'),
    repeatCustomerOrders: sumCol(ddRegister, 'repeatCustomerOrders'),
    dashPassOrders: sumCol(ddRegister, 'dashPassOrders'),
    totalItems: sumCol(ddRegister, 'totalItems'),
    orders: sumCol(ddRegister, 'orders'),
    sales: sumCol(ddRegister, 'sales'),
    errorCharges: sumCol(ddRegister, 'errorCharges'),
  };

  const rawSales = manualRawRegisterSalesCounts(salesOrder, ddFinancial);
  const scopedSalesOrders = normalizeDdSalesByOrder(salesOrder).filter((o) =>
    inWindow(o.date, periodConfig.preStart, periodConfig.postEnd),
  );
  let rawNew = 0;
  let rawRepeat = 0;
  let rawDash = 0;
  let rawItems = 0;
  for (const o of scopedSalesOrders) {
    if (o.customerType === 'new') rawNew += 1;
    else if (o.customerType === 'repeat') rawRepeat += 1;
    if (o.isDashPass === true) rawDash += 1;
    rawItems += o.itemCount || 0;
  }

  compare(
    'Register newCustomerOrders (averaged) vs raw period count',
    regSums.newCustomerOrders,
    rawNew,
    { tol: rawNew * 0.15, note: 'Register averages by weekday×slot; totals differ from raw sums' },
  );
  compare(
    'Register dashPassOrders (averaged) vs raw period count',
    regSums.dashPassOrders,
    rawDash,
    { tol: rawDash * 0.15, note: 'Expected drift: weekday averaging rounds per cell' },
  );

  logicNotes.push(
    '- **Register averaging**: Financial metrics collapse calendar days → weekday×slot averages (`Math.round` for counts). SALES_BY_ORDER customer metrics use the same grain — totals will NOT match raw order sums.',
  );

  // --- 4. SALES_BY_ORDER parser vs raw CSV ---
  const appSales = manualSalesByOrderCounts(salesOrder);
  const rawCsv = manualRawSalesCounts(salesOrder);
  // Parser drops cancelled orders + rows missing order-placed time
  function manualFilteredSalesCounts(parsed) {
    const { data, columns } = parsed;
    const timeCol = columns.find((c) => /order placed time/i.test(c));
    const cancelCol = columns.find((c) => /cancel/i.test(c) && /is|was/i.test(c));
    const bool = (v) => String(v ?? '').trim().toLowerCase() === 'true';
    let n = 0;
    let newC = 0;
    let repeatC = 0;
    let dashYes = 0;
    let items = 0;
    let sales = 0;
    for (const row of data) {
      if (cancelCol && bool(row[cancelCol])) continue;
      const t = timeCol ? row[timeCol] : null;
      if (!t || String(t).trim() === '' || String(t).toUpperCase() === 'NULL') continue;
      n += 1;
      const ct = String(row['Customer type'] || row['Customer Type'] || '').toLowerCase();
      if (ct === 'new') newC += 1;
      else if (ct === 'repeat' || ct.includes('existing')) repeatC += 1;
      if (bool(row['Is DashPass'] ?? row['Is Dashpass'])) dashYes += 1;
      items += Number(row['Total item count'] || row['Item count'] || 0) || 0;
      sales += Number(row.Subtotal || 0) || 0;
    }
    return { orders: n, newC, repeatC, dashYes, items, sales: round(sales) };
  }
  const filteredCsv = manualFilteredSalesCounts(salesOrder);
  compare('SALES_BY_ORDER total orders (after cancel+time filter)', appSales.orders, filteredCsv.orders);
  compare('SALES_BY_ORDER new customers (filtered)', appSales.newC, filteredCsv.newC);
  compare('SALES_BY_ORDER repeat customers (filtered)', appSales.repeatC, filteredCsv.repeatC);
  compare('SALES_BY_ORDER DashPass orders (filtered)', appSales.dashYes, filteredCsv.dashYes);
  compare('SALES_BY_ORDER total items (filtered)', appSales.items, filteredCsv.items);
  compare('SALES_BY_ORDER subtotal sum (filtered)', appSales.sales, filteredCsv.sales, { tol: 1 });

  // --- 5. Marketing Corp vs TODC ---
  const appMkt = buildCorpVsTodcTable(promo, sponsored, POST_START, POST_END);
  const manualMkt = manualMarketingCorpTodc(promo, sponsored, POST_START, POST_END);
  compare('Marketing POST corp spend', appMkt.corp.spend, manualMkt.corp.spend, { tol: 1 });
  compare('Marketing POST todc spend', appMkt.todc.spend, manualMkt.todc.spend, { tol: 1 });
  compare('Marketing POST total orders', appMkt.total.orders, manualMkt.total.orders);
  compare('Marketing POST total sales', appMkt.total.sales, manualMkt.total.sales, { tol: 1 });
  compare('Marketing POST total spend', appMkt.total.spend, manualMkt.total.spend, { tol: 1 });

  // --- 6. UE financial ---
  const ueParsed = parseUeFinancialCsv(readFileSync(ueCsv, 'utf8'));
  const ueFinancial = normalizeUeFinancial(ueParsed);
  const ueStoreData = addDerivedMetrics(buildUePlatformData(ueFinancial, periodConfig));
  const manualUePost = manualDdFinancialAgg(
    ueFinancial.map((r) => ({ ...r, subtotal: r.sales, netTotal: r.totalPayout, orderId: r.orderId })),
    POST_START,
    POST_END,
  );
  compare('UE Financial POST sales', platformTotals(ueStoreData, 'post', 'sales'), manualUePost.sales, { tol: 1 });
  compare('UE Financial POST payouts', platformTotals(ueStoreData, 'post', 'payouts'), manualUePost.payouts, { tol: 1 });
  compare('UE Financial POST orders', platformTotals(ueStoreData, 'post', 'orders'), manualUePost.orders);

  const ueRegister = buildUeRegister({ ueFinancial }, registerConfig);
  compare('UE Register sales sum (post window)', sumCol(ueRegister, 'sales'), platformTotals(ueStoreData, 'post', 'sales'), {
    tol: 50,
    note: 'Register sums weekday-averaged cells; platform sums raw financial rows',
  });

  // --- 7. Cross-file: SALES_BY_STORE vs SALES_BY_ORDER (June subset) ---
  const storeAgg = loadCsv(salesByStoreCsv);
  const storeGross = storeAgg.data.reduce((s, r) => s + (Number(r['Gross sales'] || r['Gross Sales'] || 0) || 0), 0);
  const storeOrders = storeAgg.data.reduce(
    (s, r) => s + (Number(r['Total orders/deliveries (including cancelled)'] || 0) || 0),
    0,
  );
  compare(
    'SALES_BY_STORE gross sales vs order-file subtotal',
    storeGross,
    rawCsv.sales,
    {
      tol: storeGross * 0.02,
      note: 'Cross-file check: store rollup vs raw SALES_BY_ORDER subtotal sum',
    },
  );
  compare(
    'SALES_BY_STORE order count vs raw SALES_BY_ORDER rows',
    storeOrders,
    rawCsv.orders,
    { tol: storeOrders * 0.02, note: 'Store file includes cancelled; order file is row-level' },
  );

  // --- 8. Payout summary vs detailed ---
  const payoutParsed = loadCsv(payoutSummaryCsv);
  const payoutNet = payoutParsed.data.reduce((s, r) => s + (Number(r['Net total'] || 0) || 0), 0);
  const allTimeManual = manualDdFinancialAgg(ddFinancial, parseDate('01/01/2025'), parseDate('06/03/2026'));
  compare(
    'Payout summary net total vs detailed all-time payouts',
    payoutNet,
    allTimeManual.payouts,
    { tol: Math.max(100, payoutNet * 0.01), note: 'Payout summary may use different grain than row-sum' },
  );

  // --- 9. Product mix AOV ---
  const pmix = loadCsv(productMixCsv);
  const grossCol = 'Gross sales';
  const qtyCol = 'Total sold';
  const pmixGross = pmix.data.reduce((s, r) => s + (Number(r[grossCol] || 0) || 0), 0);
  const pmixQty = pmix.data.reduce((s, r) => s + (Number(r[qtyCol] || 0) || 0), 0);
  const pmixAov = round(safeDivide(pmixGross, pmixQty), 2);
  logicNotes.push(`- **Product mix implied AOV** (gross/qty): $${pmixAov} — item-level, not order-level AOV.`);

  // --- 10. Transaction type mix (explains financial drift) ---
  const txnTypes = {};
  for (const r of ddFinancial) {
    const t = String(r.transactionType || 'unknown');
    txnTypes[t] = (txnTypes[t] || 0) + 1;
  }
  logicNotes.push(`- **DD financial transaction types**: ${JSON.stringify(txnTypes)}`);
  logicNotes.push(
    '- **App financial engine** sums ALL transaction rows; **DeepDive analyzer** filters `Transaction type == Order` only.',
  );
  logicNotes.push(
    '- **Orders metric** uses `nunique(DoorDash order ID)` across all rows in window, not row count.',
  );
  logicNotes.push(
    '- **Marketing spend** = abs(promo customer discounts) + abs(sponsored marketing fees); Corp = `Is self serve campaign` false.',
  );

  const report = renderReport();
  writeFileSync(REPORT_PATH, report);
  console.log(report);
  console.log(`\nWrote ${REPORT_PATH}`);
  const driftCount = findings.filter((f) => f.status === 'DRIFT').length;
  process.exit(driftCount > 0 ? 0 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
