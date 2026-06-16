import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { parseCsv } from '../src/lib/parsers/zipHandler.js';
import { normalizeDdSalesByOrder } from '../src/lib/parsers/ddSalesByOrder.js';
import { normalizeDdFinancial } from '../src/lib/parsers/ddFinancial.js';
import { buildSlotAnalysis } from '../src/lib/engine/slots.js';
import { filterByDateRange } from '../src/lib/engine/aggregator.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '../../../..');
const sales = normalizeDdSalesByOrder(
  parseCsv(readFileSync(join(root, 'sample_data/bican-sample-data/SALES_BY_ORDER_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.csv'), 'utf8')),
);
const fin = normalizeDdFinancial(
  parseCsv(readFileSync(join(root, 'sample_data/bican-sample-data/financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z/FINANCIAL_SIMPLIFIED_TRANSACTIONS_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv'), 'utf8')),
);

const cfg = {
  preStart: new Date('2026-04-01T00:00:00'),
  preEnd: new Date('2026-04-30T23:59:59.999'),
  postStart: new Date('2026-05-01T00:00:00'),
  postEnd: new Date('2026-05-31T23:59:59.999'),
  excludedDates: [],
  platform: 'dd',
  salesOrders: sales,
};

const slots = buildSlotAnalysis(fin, cfg);
const lunch = slots.salesPrePost.find((r) => r.slot === 'Lunch');
console.log('Lunch PvP:', { pre: lunch.pre, post: lunch.post, lyPrevspost: lunch.lyPrevspost, lyGrowthPct: lunch.lyGrowthPct });
const yoy = slots.salesYoY.find((r) => r.slot === 'Lunch');
console.log('Lunch YoY:', yoy);

for (const [label, start, end] of [
  ['Apr25', new Date('2025-04-01'), new Date('2025-04-30T23:59:59.999')],
  ['May25', new Date('2025-05-01'), new Date('2025-05-31T23:59:59.999')],
  ['Apr26', new Date('2026-04-01'), new Date('2026-04-30T23:59:59.999')],
  ['May26', new Date('2026-05-01'), new Date('2026-05-31T23:59:59.999')],
]) {
  const rows = filterByDateRange(sales, 'date', start, end);
  const sum = rows.reduce((s, o) => s + (o.subtotal || 0), 0);
  console.log(label, rows.length, 'orders', sum.toFixed(2), 'sales');
}
