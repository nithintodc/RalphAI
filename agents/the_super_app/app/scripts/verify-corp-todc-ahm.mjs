import { readFileSync } from 'fs';
import { parseCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdPromotion, normalizeDdSponsored } from '../src/lib/parsers/ddMarketing.js';
import { normalizeDdFinancial } from '../src/lib/parsers/ddFinancial.js';
import { buildCorpVsTodcBySource, buildCorpTodcImpactRows } from '../src/lib/engine/marketing.js';
import { buildMarketingStoreResolver } from '../src/lib/utils/marketingStoreMatch.js';
import { buildDdStoreCatalog } from '../src/lib/utils/storeCatalog.js';
import { buildAnalysisScope } from '../src/lib/utils/abStoreFilter.js';

const base = '/Users/nithi/Desktop/Claude-Projects/TODC-Projects/RalphAI/sample_data/ahm-lake';
const promo = normalizeDdPromotion(parseCsv(readFileSync(`${base}/marketing_2025-01-01_2026-06-11_2FNL2_2026-06-12T12-46-47Z/MARKETING_PROMOTION_2025-01-01_2026-06-11_2FNL2_2026-06-12T12-46-47Z.csv`, 'utf8')));
const sponsored = normalizeDdSponsored(parseCsv(readFileSync(`${base}/marketing_2025-01-01_2026-06-11_2FNL2_2026-06-12T12-46-47Z/MARKETING_SPONSORED_LISTING_2025-01-01_2026-06-11_2FNL2_2026-06-12T12-46-47Z.csv`, 'utf8')));
const ddFinancial = normalizeDdFinancial(parseCsv(readFileSync(`${base}/financial_2025-01-01_2026-06-11_url3j_2026-06-12T12-44-43Z/FINANCIAL_DETAILED_TRANSACTIONS_2025-01-01_2026-06-11_url3j_2026-06-12T12-44-43Z.csv`, 'utf8')));

const config = {
  ddPreStart: new Date('2026-04-02'),
  ddPreEnd: new Date('2026-05-06'),
  ddPostStart: new Date('2026-05-07'),
  ddPostEnd: new Date('2026-06-10'),
  ddExcludedDates: [],
  storeTagMap: { 18968: 'A', 20276: 'A', 674684: 'A' },
  ddToUeStoreMap: {},
};
const scope = buildAnalysisScope(config);
const resolve = buildMarketingStoreResolver(ddFinancial);
const tables = buildCorpVsTodcBySource(promo, sponsored, {
  preStart: config.ddPreStart,
  preEnd: config.ddPreEnd,
  postStart: config.ddPostStart,
  postEnd: config.ddPostEnd,
  excludedDates: [],
}, scope, resolve);

console.log('DD stores:', buildDdStoreCatalog(ddFinancial).map((s) => `${s.id} (merchant ${s.merchantStoreId}, dd ${s.ddStoreId})`).join('; '));

const allTables = buildCorpVsTodcBySource(promo, sponsored, {
  preStart: config.ddPreStart,
  preEnd: config.ddPreEnd,
  postStart: config.ddPostStart,
  postEnd: config.ddPostEnd,
  excludedDates: [],
}, null, null);
console.log('\nAll stores (no scope) POST:');
for (const r of buildCorpTodcImpactRows(allTables.combined, 'post')) {
  console.log(`${r.group}: sales=${r.sales} orders=${r.orders}`);
}

for (const period of ['post', 'pre']) {
  console.log(`\n=== ${period.toUpperCase()} ===`);
  const rows = buildCorpTodcImpactRows(tables.combined, period);
  for (const r of rows) {
    console.log(`${r.group}: sales=${r.sales} orders=${r.orders} spend=${r.spend}`);
  }
  const corp = rows.find((r) => r.group === 'Corporate');
  const todc = rows.find((r) => r.group === 'TODC');
  const total = rows.find((r) => r.group === 'Total');
  const sumSales = (corp?.sales || 0) + (todc?.sales || 0);
  console.log(`Corporate+TODC sales=${sumSales}, Total=${total?.sales}, match=${Math.abs(sumSales - (total?.sales || 0)) < 0.01}`);
}
