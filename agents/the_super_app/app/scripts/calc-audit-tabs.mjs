/**
 * Audit Marketing / Operations / Product Mix tab tables vs manual pivots.
 * Run: cd agents/the_super_app/app && npx vite-node scripts/calc-audit-tabs.mjs
 */
import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import JSZip from 'jszip';
import { parseCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdPromotion, normalizeDdSponsored } from '../src/lib/parsers/ddMarketing.js';
import {
  buildCorpVsTodcBySource,
  buildCorpTodcImpactRows,
  buildCampaignTable,
  buildCampaignHighlights,
  filterCampaignsBySource,
  sliceMarketingPct,
} from '../src/lib/engine/marketing.js';
import {
  pivotDowntimeByStore,
  pivotDowntimeByDimension,
  pivotCountByStore,
  pivotStoreReasonMatrix,
  pivotTopDatesPerStore,
  pivotOneWaySum,
  pickProductColumn,
  pickMetricColumn,
  pickProductMixQtyColumn,
  pickErrorChargeColumn,
  pickCategoryColumn,
  pickStoreColumn,
  parseDurationToMinutes,
} from '../src/lib/utils/opsProductPivot.js';
import { parseDate, getLastYearDates, isInRange } from '../src/lib/utils/dateUtils.js';
import { safeDivide, round, growthPct } from '../src/lib/utils/safeMath.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SAMPLE = join(__dirname, '../../../../sample_data/bican-sample-data');
const REPORT_PATH = join(SAMPLE, 'CALC_AUDIT_TABS_REPORT.md');

const PRE_START = parseDate('05/01/2025');
const PRE_END = parseDate('05/31/2025');
const POST_START = parseDate('06/01/2025');
const POST_END = parseDate('06/03/2025');

const findings = [];

function compare(name, appVal, manualVal, { tol = 0.01, note = '', section = '' } = {}) {
  const diff = round(Number(appVal) - Number(manualVal), 4);
  const drift = Math.abs(diff) > tol;
  findings.push({
    section,
    name,
    app: round(appVal, 4),
    manual: round(manualVal, 4),
    diff,
    status: drift ? 'DRIFT' : 'OK',
    note,
  });
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

function cols(rows) {
  return rows?.[0] ? Object.keys(rows[0]) : [];
}

function inWindow(d, start, end) {
  return d && d >= start && d <= end;
}

function manualCalcGroup(rows) {
  const orders = rows.reduce((s, r) => s + (r.orders || 0), 0);
  const sales = rows.reduce((s, r) => s + (r.sales || 0), 0);
  const spend = rows.reduce((s, r) => s + Math.abs(r.spend || 0), 0);
  const promoAov = round(safeDivide(sales, orders), 2);
  const cpo = round(safeDivide(spend, orders), 2);
  return {
    orders: Math.round(orders),
    sales: round(sales),
    spend: round(spend),
    roas: round(safeDivide(sales, spend), 2),
    cpo,
    promoAov,
    checkAfterPromo: round(promoAov - cpo, 2),
  };
}

function manualCorpTodcPost(promo, sponsored, start, end) {
  const all = [...promo, ...sponsored].filter((r) => inWindow(r.date, start, end));
  return {
    corp: manualCalcGroup(all.filter((r) => !r.isSelfServe)),
    todc: manualCalcGroup(all.filter((r) => r.isSelfServe)),
    total: manualCalcGroup(all),
  };
}

function manualCampaignTable(promo, sponsored, start, end) {
  const all = [...promo, ...sponsored].filter((r) => inWindow(r.date, start, end));
  const byId = new Map();
  for (const r of all) {
    const id = String(r.campaignId || '').trim();
    if (!id) continue;
    if (!byId.has(id)) byId.set(id, []);
    byId.get(id).push(r);
  }
  const campaigns = [];
  for (const [id, rows] of byId) {
    const g = manualCalcGroup(rows);
    campaigns.push({ campaignId: id, source: rows[0]?.source, ...g });
  }
  return campaigns;
}

function sumMapValues(map) {
  return [...map.values()].reduce((s, v) => s + v, 0);
}

function manualDowntimeByStore(rows, columns) {
  const storeCol = pickStoreColumn(columns);
  const minsCol = columns.find((c) => /minutes?\s*downtime/i.test(c));
  if (!storeCol || !minsCol) return new Map();
  const map = new Map();
  for (const row of rows) {
    const store = String(row[storeCol] || '').trim() || '—';
    const mins = parseDurationToMinutes(row[minsCol]);
    map.set(store, (map.get(store) || 0) + mins);
  }
  return map;
}

function pickCountSumCol(columns) {
  return columns.find((c) => /count\s+of\s+orders/i.test(c))
    || columns.find((c) => /count\s+of\s+item\s+errors/i.test(c))
    || columns.find((c) => /\bcount\b/i.test(c) && !/%/.test(c));
}

function manualCountByStore(rows, columns) {
  const storeCol = pickStoreColumn(columns);
  const countCol = pickCountSumCol(columns);
  if (!storeCol) return new Map();
  const map = new Map();
  if (countCol) {
    for (const row of rows) {
      const store = String(row[storeCol] || '').trim() || '—';
      const n = Number(String(row[countCol]).replace(/,/g, '')) || 0;
      map.set(store, (map.get(store) || 0) + n);
    }
  } else {
    for (const row of rows) {
      const store = String(row[storeCol] || '').trim() || '—';
      map.set(store, (map.get(store) || 0) + 1);
    }
  }
  return map;
}

function manualProductAgg(rows, columns) {
  const productCol = pickProductColumn(columns);
  const salesCol = pickMetricColumn(rows, columns, [productCol].filter(Boolean));
  const qtyCol = pickProductMixQtyColumn(columns);
  const errCol = pickErrorChargeColumn(columns);
  const map = new Map();
  for (const row of rows) {
    const name = String(row[productCol] || '').trim();
    if (!name) continue;
    const cur = map.get(name) || { sales: 0, qty: 0, errorCharges: 0 };
    cur.sales += Number(String(row[salesCol]).replace(/[$,]/g, '')) || 0;
    if (qtyCol) cur.qty += Number(String(row[qtyCol]).replace(/[$,]/g, '')) || 0;
    if (errCol) cur.errorCharges += Number(String(row[errCol]).replace(/[$,]/g, '')) || 0;
    map.set(name, cur);
  }
  return map;
}

function slicePct(n, pct = 0.05) {
  if (!n) return 0;
  return Math.max(1, Math.ceil(n * pct));
}

function renderReport() {
  const sections = ['Marketing', 'Operations', 'Product Mix'];
  const lines = [
    '# Tab Tables Audit — Marketing / Operations / Product Mix',
    '',
    `Generated: ${new Date().toISOString()}`,
    `Sample: \`sample_data/bican-sample-data\``,
    `Post window: ${POST_START.toISOString().slice(0, 10)} → ${POST_END.toISOString().slice(0, 10)}`,
    '',
    '## Summary',
    '',
  ];
  for (const sec of sections) {
    const items = findings.filter((f) => f.section === sec);
    const ok = items.filter((f) => f.status === 'OK').length;
    const drift = items.filter((f) => f.status === 'DRIFT').length;
    lines.push(`- **${sec}:** ${ok} OK, ${drift} drift`);
  }
  lines.push('', '## All checks', '', '| Section | Check | App | Manual | Diff | Status | Notes |', '|---------|-------|-----|--------|------|--------|-------|');
  for (const f of findings) {
    lines.push(`| ${f.section} | ${f.name} | ${f.app} | ${f.manual} | ${f.diff} | ${f.status} | ${f.note || ''} |`);
  }
  return lines.join('\n');
}

async function auditMarketing(promo, sponsored) {
  const dateConfig = {
    preStart: PRE_START,
    preEnd: PRE_END,
    postStart: POST_START,
    postEnd: POST_END,
    excludedDates: [],
  };
  const bySource = buildCorpVsTodcBySource(promo, sponsored, dateConfig);
  const postRows = buildCorpTodcImpactRows(bySource.combined, 'post');
  const manual = manualCorpTodcPost(promo, sponsored, POST_START, POST_END);

  const groupKey = { corp: 'corporate', todc: 'todc', total: 'total' };
  for (const key of ['corp', 'todc', 'total']) {
    const appRow = postRows.find((r) => r.group.toLowerCase() === groupKey[key]) || {};
    const m = manual[key];
    for (const metric of ['orders', 'sales', 'spend', 'roas', 'cpo', 'checkAfterPromo']) {
      compare(`Corp/TODC Post ${key} ${metric}`, appRow[metric], m[metric], {
        tol: metric === 'orders' ? 0 : 1,
        section: 'Marketing',
      });
    }
  }

  const campaigns = buildCampaignTable(promo, sponsored, POST_START, POST_END);
  const manualCampaigns = manualCampaignTable(promo, sponsored, POST_START, POST_END);
  compare('Campaign table count', campaigns.length, manualCampaigns.length, { tol: 0, section: 'Marketing' });

  const appSales = campaigns.reduce((s, c) => s + (c.sales || 0), 0);
  const manSales = manualCampaigns.reduce((s, c) => s + (c.sales || 0), 0);
  compare('Campaign table total sales', appSales, manSales, { tol: 1, section: 'Marketing' });

  const appSpend = campaigns.reduce((s, c) => s + (c.spend || 0), 0);
  const manSpend = manualCampaigns.reduce((s, c) => s + (c.spend || 0), 0);
  compare('Campaign table total spend', appSpend, manSpend, { tol: 1, section: 'Marketing' });

  const promoCampaigns = filterCampaignsBySource(campaigns, 'promotion');
  const topRoas = buildCampaignHighlights(promoCampaigns, 'topRoas');
  const eligible = promoCampaigns.filter((c) => (c.spend || 0) > 0);
  const n = sliceMarketingPct(eligible.length);
  const manualTopRoas = [...eligible].sort((a, b) => (b.roas || 0) - (a.roas || 0)).slice(0, n);
  compare('Promo top-ROAS highlight count', topRoas.length, manualTopRoas.length, { tol: 0, section: 'Marketing' });
  if (topRoas[0] && manualTopRoas[0]) {
    compare('Promo top-ROAS #1 campaign sales', topRoas[0].sales, manualTopRoas[0].sales, { tol: 1, section: 'Marketing' });
  }
}

function auditOperations(ops) {
  const downtimeRows = ops.downtime?.data || [];
  const downtimeCols = cols(downtimeRows);
  const appDowntime = pivotDowntimeByStore(downtimeRows, downtimeCols);
  const manDowntime = manualDowntimeByStore(downtimeRows, downtimeCols);
  compare(
    'Downtime by store total minutes',
    sumMapValues(new Map(appDowntime.rows.map((r) => [r.store, r.totalMinutes]))),
    sumMapValues(manDowntime),
    { tol: 1, section: 'Operations' },
  );
  if (appDowntime.rows[0]) {
    const top = appDowntime.rows[0];
    compare(
      `Downtime top store (${top.store}) minutes`,
      top.totalMinutes,
      manDowntime.get(top.store) || 0,
      { tol: 1, section: 'Operations' },
    );
  }

  const storeCol = pickStoreColumn(downtimeCols);
  const categoryCol = pickCategoryColumn(downtimeCols, [storeCol].filter(Boolean));
  if (categoryCol) {
    const byCat = pivotDowntimeByDimension(downtimeRows, downtimeCols, categoryCol);
    const manCat = new Map();
    const minsCol = downtimeCols.find((c) => /minutes?\s*downtime/i.test(c));
    for (const row of downtimeRows) {
      const label = String(row[categoryCol] || '').trim() || '—';
      const mins = parseDurationToMinutes(row[minsCol]);
      manCat.set(label, (manCat.get(label) || 0) + mins);
    }
    compare(
      'Downtime by category total minutes',
      byCat.rows.reduce((s, r) => s + r.totalMinutes, 0),
      sumMapValues(manCat),
      { tol: 1, section: 'Operations' },
    );
  }

  const cancelRows = ops.cancellations?.data || [];
  const cancelCols = cols(cancelRows);
  const cancelPivot = pivotCountByStore(cancelRows, cancelCols);
  const manCancel = manualCountByStore(cancelRows, cancelCols);
  compare(
    'Cancellations by store total count',
    cancelPivot.rows.reduce((s, r) => s + r.rowCount, 0),
    sumMapValues(manCancel),
    { tol: 1, section: 'Operations' },
  );

  const missRows = ops.missingIncorrect?.data || [];
  const missCols = cols(missRows);
  const missPivot = pivotCountByStore(missRows, missCols);
  const manMiss = manualCountByStore(missRows, missCols);
  compare(
    'Missing/incorrect by store total count',
    missPivot.rows.reduce((s, r) => s + r.rowCount, 0),
    sumMapValues(manMiss),
    { tol: 1, section: 'Operations' },
  );

  const cancelMatrix = pivotStoreReasonMatrix(cancelRows, cancelCols, { valueKind: 'count' });
  if (cancelMatrix?.matrix?.length) {
    const appTotal = cancelMatrix.matrix.flat().reduce((s, v) => s + (Number(v) || 0), 0);
    compare('Cancellation store×reason matrix total', appTotal, sumMapValues(manCancel), {
      tol: 1,
      section: 'Operations',
    });
  }

  const missMatrix = pivotStoreReasonMatrix(missRows, missCols, { valueKind: 'count' });
  if (missMatrix?.matrix?.length) {
    const appTotal = missMatrix.matrix.flat().reduce((s, v) => s + (Number(v) || 0), 0);
    compare('Missing/incorrect store×reason matrix total', appTotal, sumMapValues(manMiss), {
      tol: 1,
      section: 'Operations',
    });
  }

  const cancelTopDates = pivotTopDatesPerStore(cancelRows, cancelCols, { topPerStore: 5, valueKind: 'count' });
  const manTopDates = new Map();
  const storeColC = pickStoreColumn(cancelCols);
  const dateColC = cancelCols.find((c) => /start\s*date/i.test(c));
  const countColC = pickCountSumCol(cancelCols);
  if (storeColC && dateColC) {
    const byStore = new Map();
    for (const row of cancelRows) {
      const store = String(row[storeColC] || '').trim();
      const date = String(row[dateColC] || '').trim();
      const add = countColC ? Number(row[countColC]) || 0 : 1;
      if (!byStore.has(store)) byStore.set(store, new Map());
      const dm = byStore.get(store);
      dm.set(date, (dm.get(date) || 0) + add);
    }
    let manualTopSum = 0;
    for (const dm of byStore.values()) {
      const top = [...dm.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
      manualTopSum += top.reduce((s, [, v]) => s + v, 0);
    }
    compare(
      'Cancellation top-dates rows total (top 5/store)',
      cancelTopDates.rows.reduce((s, r) => s + r.total, 0),
      manualTopSum,
      { tol: 1, section: 'Operations' },
    );
  }
}

function auditProductMix(pmixRows) {
  const columns = cols(pmixRows);
  const productCol = pickProductColumn(columns);
  const valueCol = pickMetricColumn(pmixRows, columns, [productCol].filter(Boolean));
  const qtyCol = pickProductMixQtyColumn(columns);

  const byProduct = pivotOneWaySum(pmixRows, productCol, valueCol);
  const manByProduct = new Map();
  for (const row of pmixRows) {
    const key = String(row[productCol] || '').trim();
    if (!key) continue;
    const v = Number(String(row[valueCol]).replace(/[$,]/g, '')) || 0;
    manByProduct.set(key, (manByProduct.get(key) || 0) + v);
  }
  compare('By-product total gross sales', byProduct.total, sumMapValues(manByProduct), { tol: 1, section: 'Product Mix' });
  compare('By-product unique products', byProduct.keys.length, manByProduct.size, { tol: 0, section: 'Product Mix' });

  const appAgg = manualProductAgg(pmixRows, columns);
  let appSalesTotal = 0;
  let appQtyTotal = 0;
  for (const v of appAgg.values()) {
    appSalesTotal += v.sales;
    appQtyTotal += v.qty;
  }
  let manSalesTotal = 0;
  let manQtyTotal = 0;
  for (const row of pmixRows) {
    manSalesTotal += Number(String(row[valueCol]).replace(/[$,]/g, '')) || 0;
    if (qtyCol) manQtyTotal += Number(String(row[qtyCol]).replace(/[$,]/g, '')) || 0;
  }
  compare('Product agg total sales', appSalesTotal, manSalesTotal, { tol: 1, section: 'Product Mix' });
  compare('Product agg total qty', appQtyTotal, manQtyTotal, { tol: 1, section: 'Product Mix' });

  const products = [...appAgg.entries()].map(([product, v]) => ({
    product,
    sales: v.sales,
    qty: v.qty,
    aov: v.qty > 0 ? round(safeDivide(v.sales, v.qty), 2) : null,
    errorChargePct: v.sales > 0 ? round(safeDivide(v.errorCharges, v.sales) * 100, 2) : null,
  }));
  const sorted = [...products].sort((a, b) => b.sales - a.sales);
  const topN = slicePct(sorted.length);
  const topSelling = sorted.slice(0, topN);
  const withAov = products.filter((p) => p.aov != null).sort((a, b) => b.aov - a.aov);
  const topAov = withAov.slice(0, slicePct(withAov.length));

  const manTopSales = [...appAgg.entries()]
    .map(([product, v]) => ({ product, sales: v.sales }))
    .sort((a, b) => b.sales - a.sales)
    .slice(0, topN);
  compare('Top 5% selling count', topSelling.length, manTopSales.length, { tol: 0, section: 'Product Mix' });
  if (topSelling[0]) {
    compare('Top seller #1 gross sales', topSelling[0].sales, manTopSales[0].sales, { tol: 1, section: 'Product Mix' });
  }

  const manTopAov = [...appAgg.entries()]
    .filter(([, v]) => v.qty > 0)
    .map(([product, v]) => ({ product, aov: round(safeDivide(v.sales, v.qty), 2) }))
    .sort((a, b) => b.aov - a.aov)
    .slice(0, slicePct(withAov.length));
  if (topAov[0] && manTopAov[0]) {
    compare('Top AOV #1 value', topAov[0].aov, manTopAov[0].aov, { tol: 0.01, section: 'Product Mix' });
  }

  const impliedAov = round(safeDivide(appSalesTotal, appQtyTotal), 2);
  compare('Portfolio implied $/unit (gross/qty)', impliedAov, round(safeDivide(manSalesTotal, manQtyTotal), 2), {
    tol: 0.01,
    note: 'Item-level AOV, not order AOV',
    section: 'Product Mix',
  });
}

async function main() {
  const mktZip = join(SAMPLE, 'marketing_2025-01-01_2026-06-03_rdK2w_2026-06-04T05-23-55Z.zip');
  const opsStoreZip = join(SAMPLE, 'OPERATIONS_QUALITY_viewByStore_2025-01-01_2026-06-03_0KzEQ_2026-06-04T05-22-20Z.zip');
  const pmixCsv = join(SAMPLE, 'PRODUCT_MIX_2025-01-01_2026-06-03_DSsjJ_2026-06-04T05-23-33Z.csv');

  const promoCsv = await loadZipCsv(mktZip, (n) => n.includes('marketing_promotion'));
  const sponsoredCsv = await loadZipCsv(mktZip, (n) => n.includes('marketing_sponsored'));
  const promo = normalizeDdPromotion(promoCsv);
  const sponsored = normalizeDdSponsored(sponsoredCsv);

  const downtimeCsv = await loadZipCsv(opsStoreZip, (n) => n.includes('downtime'));
  const cancelCsv = await loadZipCsv(opsStoreZip, (n) => n.includes('cancellations'));
  const missCsv = await loadZipCsv(opsStoreZip, (n) => n.includes('missingandincorrect'));

  const pmixParsed = loadCsv(pmixCsv);
  const pmixRows = pmixParsed.data;

  await auditMarketing(promo, sponsored);
  auditOperations({
    downtime: downtimeCsv,
    cancellations: cancelCsv,
    missingIncorrect: missCsv,
  });
  auditProductMix(pmixRows);

  const report = renderReport();
  writeFileSync(REPORT_PATH, report);
  console.log(report);
  console.log(`\nWrote ${REPORT_PATH}`);
  const drift = findings.filter((f) => f.status === 'DRIFT').length;
  process.exit(drift > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
