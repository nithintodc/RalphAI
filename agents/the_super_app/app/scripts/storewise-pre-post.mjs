/**
 * Store-wise pre / post pivot using the same engine as the Super App.
 *
 * Metrics per store:
 *   Sales, Payouts, Profitability %, AOV, Orders — pre, post, pre vs post.
 *   DD spend (marketing exports): Promo, Sponsored, Total.
 *   UE spend (financial): Offers, Delivery, Ads, Total.
 *   DD new customers: Promo + Sponsored.
 *
 * Usage:
 *   cd agents/the_super_app/app && npx vite-node scripts/storewise-pre-post.mjs
 *   npx vite-node scripts/storewise-pre-post.mjs /path/to/data \
 *     --pre-start 3/20/2026 --pre-end 4/30/2026 \
 *     --post-start 5/1/2026 --post-end 6/11/2026 \
 *     --prefix storewise-mar20-jun11
 */
import { readFileSync, readdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { format } from 'date-fns';
import { parseCsv, parseUeFinancialCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdFinancial } from '../src/lib/parsers/ddFinancial.js';
import { normalizeDdPromotion, normalizeDdSponsored } from '../src/lib/parsers/ddMarketing.js';
import { normalizeUeFinancial } from '../src/lib/parsers/ueFinancial.js';
import { filterByDateRange } from '../src/lib/engine/aggregator.js';
import { buildDdPlatformData, buildUePlatformData } from '../src/lib/engine/periodEngine.js';
import { addDerivedMetrics } from '../src/lib/engine/metrics.js';
import { parseDate } from '../src/lib/utils/dateUtils.js';
import { round } from '../src/lib/utils/safeMath.js';
import { buildMarketingStoreResolver } from '../src/lib/utils/marketingStoreMatch.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '../../../..');
const DEFAULT_DATA_DIR = join(REPO_ROOT, 'sample_data/savvy-today');

const BASE_CSV_COLUMNS = [
  'platform',
  'store_id',
  'store',
  'sales_pre',
  'sales_post',
  'sales_prevspost',
  'payouts_pre',
  'payouts_post',
  'payouts_prevspost',
  'profitability_pre',
  'profitability_post',
  'profitability_prevspost',
  'aov_pre',
  'aov_post',
  'aov_prevspost',
  'orders_pre',
  'orders_post',
  'orders_prevspost',
];

const DD_SPEND_COLUMNS = [
  'promo_spend_pre',
  'promo_spend_post',
  'promo_spend_prevspost',
  'sponsored_spend_pre',
  'sponsored_spend_post',
  'sponsored_spend_prevspost',
  'total_spend_pre',
  'total_spend_post',
  'total_spend_prevspost',
];

const UE_SPEND_COLUMNS = [
  'offers_spend_pre',
  'offers_spend_post',
  'offers_spend_prevspost',
  'delivery_spend_pre',
  'delivery_spend_post',
  'delivery_spend_prevspost',
  'ads_spend_pre',
  'ads_spend_post',
  'ads_spend_prevspost',
  'total_spend_pre',
  'total_spend_post',
  'total_spend_prevspost',
];

const DD_NEW_CUSTOMER_COLUMNS = [
  'new_customers_promo_pre',
  'new_customers_promo_post',
  'new_customers_promo_prevspost',
  'new_customers_sponsored_pre',
  'new_customers_sponsored_post',
  'new_customers_sponsored_prevspost',
  'new_customers_total_pre',
  'new_customers_total_post',
  'new_customers_total_prevspost',
];

const DEFAULT_PERIODS = {
  preStart: parseDate('4/15/2026'),
  preEnd: parseDate('5/12/2026'),
  postStart: parseDate('5/13/2026'),
  postEnd: parseDate('6/9/2026'),
};

function findDdFinancialCsv(dir) {
  const hit = readdirSync(dir).find(
    (f) => f.toLowerCase().endsWith('.csv') && f.toLowerCase().includes('financial_detailed'),
  );
  if (!hit) throw new Error(`No FINANCIAL_DETAILED CSV in ${dir}`);
  return join(dir, hit);
}

function findUeFinancialCsv(dir) {
  const files = readdirSync(dir).filter((f) => f.toLowerCase().endsWith('.csv'));
  const hit = files.find((f) => f.toLowerCase().includes('united_states'))
    || files.find((f) => !f.toLowerCase().includes('financial_detailed')
      && !f.toLowerCase().includes('marketing_promotion')
      && !f.toLowerCase().includes('marketing_sponsored'));
  if (!hit) throw new Error(`No UE financial CSV in ${dir}`);
  return join(dir, hit);
}

function findMarketingCsv(dir, kind) {
  const hit = readdirSync(dir).find(
    (f) => f.toLowerCase().endsWith('.csv') && f.toLowerCase().includes(`marketing_${kind}`),
  );
  return hit ? join(dir, hit) : null;
}

function metricBlock(row, preKey, postKey, { decimals = 1, kind = 'usd' } = {}) {
  const pre = row[preKey] || 0;
  const post = row[postKey] || 0;
  const delta = post - pre;
  if (kind === 'int') {
    return { pre: Math.round(pre), post: Math.round(post), delta: Math.round(delta) };
  }
  const d = kind === 'usd2' ? 2 : decimals;
  return { pre: round(pre, d), post: round(post, d), delta: round(delta, d) };
}

function spendBlock(pre, post) {
  return { pre: round(pre, 1), post: round(post, 1), delta: round(post - pre, 1) };
}

function sumByStore(rows, start, end, resolveStoreId, pickValue) {
  const map = new Map();
  if (!rows?.length || !start || !end) return map;
  const filtered = filterByDateRange(rows, 'date', start, end);
  for (const row of filtered) {
    const storeId = resolveStoreId(row.storeId) || row.storeId;
    if (!storeId) continue;
    map.set(storeId, (map.get(storeId) || 0) + pickValue(row));
  }
  return map;
}

function buildDdMarketingMaps(promotion, sponsored, periods, ddFinancial) {
  const resolve = buildMarketingStoreResolver(ddFinancial);
  const promoPick = (row) => Number(row.spend) || Number(row.customerDiscounts) || 0;
  const sponsoredPick = (row) => Number(row.spend) || Number(row.marketingFees) || 0;
  return {
    promoPre: sumByStore(promotion, periods.preStart, periods.preEnd, resolve, promoPick),
    promoPost: sumByStore(promotion, periods.postStart, periods.postEnd, resolve, promoPick),
    sponsoredPre: sumByStore(sponsored, periods.preStart, periods.preEnd, resolve, sponsoredPick),
    sponsoredPost: sumByStore(sponsored, periods.postStart, periods.postEnd, resolve, sponsoredPick),
    newCustomers: {
      promoPre: sumByStore(promotion, periods.preStart, periods.preEnd, resolve, (r) => Math.round(Number(r.newCustomers) || 0)),
      promoPost: sumByStore(promotion, periods.postStart, periods.postEnd, resolve, (r) => Math.round(Number(r.newCustomers) || 0)),
      sponsoredPre: sumByStore(sponsored, periods.preStart, periods.preEnd, resolve, (r) => Math.round(Number(r.newCustomers) || 0)),
      sponsoredPost: sumByStore(sponsored, periods.postStart, periods.postEnd, resolve, (r) => Math.round(Number(r.newCustomers) || 0)),
    },
  };
}

function threePartBlock(preA, postA, preB, postB) {
  const a = spendBlock(preA, postA);
  const b = spendBlock(preB, postB);
  const total = spendBlock(preA + preB, postA + postB);
  return { a, b, total };
}

function fourPartUeSpend(row) {
  const offersPre = Math.abs(row.pre_offers || 0);
  const offersPost = Math.abs(row.post_offers || 0);
  const deliveryPre = Math.abs(row.pre_deliveryOffers || 0);
  const deliveryPost = Math.abs(row.post_deliveryOffers || 0);
  const adsPre = Number(row.pre_adSpend) || 0;
  const adsPost = Number(row.post_adSpend) || 0;
  return {
    offers: spendBlock(offersPre, offersPost),
    delivery: spendBlock(deliveryPre, deliveryPost),
    ads: spendBlock(adsPre, adsPost),
    total: spendBlock(offersPre + deliveryPre + adsPre, offersPost + deliveryPost + adsPost),
  };
}

function buildDdStoreRows(storeRows, marketingMaps) {
  const derived = addDerivedMetrics(storeRows);
  return derived
    .map((row) => {
      const prePromo = marketingMaps.promoPre.get(row.storeId) || 0;
      const postPromo = marketingMaps.promoPost.get(row.storeId) || 0;
      const preSponsored = marketingMaps.sponsoredPre.get(row.storeId) || 0;
      const postSponsored = marketingMaps.sponsoredPost.get(row.storeId) || 0;
      const spend = {
        promo: spendBlock(prePromo, postPromo),
        sponsored: spendBlock(preSponsored, postSponsored),
        total: spendBlock(prePromo + preSponsored, postPromo + postSponsored),
      };
      const nc = marketingMaps.newCustomers;
      const newCustomers = threePartBlock(
        nc.promoPre.get(row.storeId) || 0,
        nc.promoPost.get(row.storeId) || 0,
        nc.sponsoredPre.get(row.storeId) || 0,
        nc.sponsoredPost.get(row.storeId) || 0,
      );
      return {
        platform: 'dd',
        storeId: row.storeId,
        store: row.storeName || row.storeId,
        sales: metricBlock(row, 'pre_sales', 'post_sales'),
        payouts: metricBlock(row, 'pre_payouts', 'post_payouts'),
        spend,
        newCustomers: {
          promo: newCustomers.a,
          sponsored: newCustomers.b,
          total: newCustomers.total,
        },
        profitability: metricBlock(row, 'pre_profitability', 'post_profitability'),
        aov: metricBlock(row, 'pre_aov', 'post_aov', { kind: 'usd2' }),
        orders: metricBlock(row, 'pre_orders', 'post_orders', { kind: 'int' }),
      };
    })
    .sort((a, b) => String(a.store).localeCompare(String(b.store), undefined, { numeric: true }));
}

function buildUeStoreRows(storeRows) {
  const derived = addDerivedMetrics(storeRows);
  return derived
    .map((row) => ({
      platform: 'ue',
      storeId: row.storeId,
      store: row.storeName || row.storeId,
      sales: metricBlock(row, 'pre_sales', 'post_sales'),
      payouts: metricBlock(row, 'pre_payouts', 'post_payouts'),
      spend: fourPartUeSpend(row),
      profitability: metricBlock(row, 'pre_profitability', 'post_profitability'),
      aov: metricBlock(row, 'pre_aov', 'post_aov', { kind: 'usd2' }),
      orders: metricBlock(row, 'pre_orders', 'post_orders', { kind: 'int' }),
    }))
    .sort((a, b) => String(a.store).localeCompare(String(b.store), undefined, { numeric: true }));
}

function flattenDdRow(r) {
  return {
    platform: r.platform,
    store_id: r.storeId,
    store: r.store,
    sales_pre: r.sales.pre,
    sales_post: r.sales.post,
    sales_prevspost: r.sales.delta,
    payouts_pre: r.payouts.pre,
    payouts_post: r.payouts.post,
    payouts_prevspost: r.payouts.delta,
    promo_spend_pre: r.spend.promo.pre,
    promo_spend_post: r.spend.promo.post,
    promo_spend_prevspost: r.spend.promo.delta,
    sponsored_spend_pre: r.spend.sponsored.pre,
    sponsored_spend_post: r.spend.sponsored.post,
    sponsored_spend_prevspost: r.spend.sponsored.delta,
    total_spend_pre: r.spend.total.pre,
    total_spend_post: r.spend.total.post,
    total_spend_prevspost: r.spend.total.delta,
    profitability_pre: r.profitability.pre,
    profitability_post: r.profitability.post,
    profitability_prevspost: r.profitability.delta,
    aov_pre: r.aov.pre,
    aov_post: r.aov.post,
    aov_prevspost: r.aov.delta,
    orders_pre: r.orders.pre,
    orders_post: r.orders.post,
    orders_prevspost: r.orders.delta,
    new_customers_promo_pre: r.newCustomers.promo.pre,
    new_customers_promo_post: r.newCustomers.promo.post,
    new_customers_promo_prevspost: r.newCustomers.promo.delta,
    new_customers_sponsored_pre: r.newCustomers.sponsored.pre,
    new_customers_sponsored_post: r.newCustomers.sponsored.post,
    new_customers_sponsored_prevspost: r.newCustomers.sponsored.delta,
    new_customers_total_pre: r.newCustomers.total.pre,
    new_customers_total_post: r.newCustomers.total.post,
    new_customers_total_prevspost: r.newCustomers.total.delta,
  };
}

function flattenUeRow(r) {
  return {
    platform: r.platform,
    store_id: r.storeId,
    store: r.store,
    sales_pre: r.sales.pre,
    sales_post: r.sales.post,
    sales_prevspost: r.sales.delta,
    payouts_pre: r.payouts.pre,
    payouts_post: r.payouts.post,
    payouts_prevspost: r.payouts.delta,
    offers_spend_pre: r.spend.offers.pre,
    offers_spend_post: r.spend.offers.post,
    offers_spend_prevspost: r.spend.offers.delta,
    delivery_spend_pre: r.spend.delivery.pre,
    delivery_spend_post: r.spend.delivery.post,
    delivery_spend_prevspost: r.spend.delivery.delta,
    ads_spend_pre: r.spend.ads.pre,
    ads_spend_post: r.spend.ads.post,
    ads_spend_prevspost: r.spend.ads.delta,
    total_spend_pre: r.spend.total.pre,
    total_spend_post: r.spend.total.post,
    total_spend_prevspost: r.spend.total.delta,
    profitability_pre: r.profitability.pre,
    profitability_post: r.profitability.post,
    profitability_prevspost: r.profitability.delta,
    aov_pre: r.aov.pre,
    aov_post: r.aov.post,
    aov_prevspost: r.aov.delta,
    orders_pre: r.orders.pre,
    orders_post: r.orders.post,
    orders_prevspost: r.orders.delta,
  };
}

function flattenCombinedRow(r) {
  if (r.platform === 'dd') return flattenDdRow(r);
  const ue = flattenUeRow(r);
  const ddBlank = Object.fromEntries(
    [...DD_SPEND_COLUMNS.filter((k) => !k.startsWith('total_spend')), ...DD_NEW_CUSTOMER_COLUMNS].map((k) => [k, '']),
  );
  return { ...ddBlank, ...ue };
}

const UE_ONLY_SPEND_COLUMNS = UE_SPEND_COLUMNS.filter((c) => !c.startsWith('total_spend'));

const DD_COLUMNS = [...BASE_CSV_COLUMNS, ...DD_SPEND_COLUMNS, ...DD_NEW_CUSTOMER_COLUMNS];
const UE_COLUMNS = [...BASE_CSV_COLUMNS, ...UE_SPEND_COLUMNS];
const COMBINED_COLUMNS = [
  ...BASE_CSV_COLUMNS,
  ...DD_SPEND_COLUMNS.filter((c) => !c.startsWith('total_spend')),
  ...DD_NEW_CUSTOMER_COLUMNS,
  ...UE_ONLY_SPEND_COLUMNS,
  'total_spend_pre',
  'total_spend_post',
  'total_spend_prevspost',
];

function csvEscape(value) {
  const s = value == null ? '' : String(value);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function rowsToCsv(rows, columns, flattenFn) {
  const lines = [columns.join(',')];
  for (const r of rows) {
    const flat = flattenFn(r);
    lines.push(columns.map((col) => csvEscape(flat[col])).join(','));
  }
  return `${lines.join('\n')}\n`;
}

function fmtDate(d) {
  return d ? format(d, 'M/d/yyyy') : '—';
}

function fmtIso(d) {
  return d ? format(d, 'yyyy-MM-dd') : '';
}

function argValue(argv, flag) {
  const i = argv.indexOf(flag);
  return i >= 0 ? argv[i + 1] : null;
}

function parseArgs(argv) {
  const positional = argv.filter((a) => !a.startsWith('--'));
  const outDirFlag = argv.indexOf('--out-dir');
  const periods = {
    preStart: parseDate(argValue(argv, '--pre-start')) || DEFAULT_PERIODS.preStart,
    preEnd: parseDate(argValue(argv, '--pre-end')) || DEFAULT_PERIODS.preEnd,
    postStart: parseDate(argValue(argv, '--post-start')) || DEFAULT_PERIODS.postStart,
    postEnd: parseDate(argValue(argv, '--post-end')) || DEFAULT_PERIODS.postEnd,
  };
  return {
    dataDir: positional[0] || DEFAULT_DATA_DIR,
    outDir: outDirFlag >= 0 ? argv[outDirFlag + 1] : (positional[0] || DEFAULT_DATA_DIR),
    prefix: argValue(argv, '--prefix') || 'storewise-pre-post',
    periods,
    writeJson: argv.includes('--json'),
  };
}

function fmtDelta(v, kind = 'usd') {
  if (v == null || Number.isNaN(v)) return '—';
  const sign = v > 0 ? '+' : '';
  if (kind === 'int') return `${sign}${Math.round(v)}`;
  return `${sign}${v.toFixed(1)}`;
}

function printSection(title, rows) {
  console.log(`\n${'='.repeat(72)}`);
  console.log(title);
  console.log('='.repeat(72));
  for (const r of rows.slice(0, 5)) {
    const spendDelta = r.spend?.total?.delta;
    const ncDelta = r.newCustomers?.total?.delta;
    console.log(
      `${String(r.store).slice(0, 36).padEnd(36)} sales ${fmtDelta(r.sales.delta)} spend ${fmtDelta(spendDelta)} nc ${fmtDelta(ncDelta, 'int')}`,
    );
  }
  if (rows.length > 5) console.log(`... ${rows.length - 5} more stores`);
}

async function main() {
  const { dataDir, outDir, prefix, periods, writeJson } = parseArgs(process.argv.slice(2));
  const config = {
    ...periods,
    excludedDates: [],
    ddExcludedStores: [],
    ueExcludedStores: [],
  };

  console.log('Data folder:', dataDir);
  console.log('Pre :', `${fmtDate(periods.preStart)} → ${fmtDate(periods.preEnd)}`);
  console.log('Post:', `${fmtDate(periods.postStart)} → ${fmtDate(periods.postEnd)}`);
  console.log('Output prefix:', prefix);

  const ddCsv = findDdFinancialCsv(dataDir);
  const ueCsv = findUeFinancialCsv(dataDir);
  const promoCsv = findMarketingCsv(dataDir, 'promotion');
  const sponsoredCsv = findMarketingCsv(dataDir, 'sponsored');

  const ddFinancial = normalizeDdFinancial(parseCsv(readFileSync(ddCsv, 'utf8')));
  const ueFinancial = normalizeUeFinancial(parseUeFinancialCsv(readFileSync(ueCsv, 'utf8')));
  const promotion = promoCsv
    ? normalizeDdPromotion(parseCsv(readFileSync(promoCsv, 'utf8')))
    : [];
  const sponsored = sponsoredCsv
    ? normalizeDdSponsored(parseCsv(readFileSync(sponsoredCsv, 'utf8')))
    : [];

  const marketingMaps = buildDdMarketingMaps(promotion, sponsored, periods, ddFinancial);
  const ddStores = buildDdStoreRows(buildDdPlatformData(ddFinancial, config), marketingMaps);
  const ueStores = buildUeStoreRows(buildUePlatformData(ueFinancial, config));

  const ddPath = join(outDir, `${prefix}-dd.csv`);
  const uePath = join(outDir, `${prefix}-ue.csv`);
  const combinedPath = join(outDir, `${prefix}.csv`);

  writeFileSync(ddPath, rowsToCsv(ddStores, DD_COLUMNS, flattenDdRow));
  writeFileSync(uePath, rowsToCsv(ueStores, UE_COLUMNS, flattenUeRow));
  writeFileSync(combinedPath, rowsToCsv([...ddStores, ...ueStores], COMBINED_COLUMNS, flattenCombinedRow));

  console.log('\nWrote:');
  console.log(' ', ddPath);
  console.log(' ', uePath);
  console.log(' ', combinedPath);

  if (writeJson) {
    const jsonPath = join(outDir, `${prefix}.json`);
    writeFileSync(jsonPath, `${JSON.stringify({
      periods: {
        pre: { start: fmtIso(periods.preStart), end: fmtIso(periods.preEnd) },
        post: { start: fmtIso(periods.postStart), end: fmtIso(periods.postEnd) },
      },
      spendDefinitions: {
        dd: {
          promo: 'MARKETING_PROMOTION customer discounts (funded by you)',
          sponsored: 'MARKETING_SPONSORED_LISTING marketing fees',
          total: 'Promo + Sponsored',
        },
        ue: {
          offers: 'Offers on items',
          delivery: 'Delivery offer redemptions',
          ads: 'Ad Spend (Other payments)',
          total: 'Offers + Delivery + Ads',
        },
      },
      dd: ddStores,
      ue: ueStores,
    }, null, 2)}\n`);
    console.log(' ', jsonPath);
  }

  printSection('DD Storewise', ddStores);
  printSection('UE Storewise', ueStores);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
