import assert from 'node:assert/strict';
import { pickProductMixQtyColumn } from '../src/lib/utils/opsProductPivot.js';

const columns = [
  'Start date', 'End date', 'Store ID', 'Item name', 'Gross sales', 'Discounts', 'Total sold',
];

assert.equal(pickProductMixQtyColumn(columns), 'Total sold');
assert.notEqual(pickProductMixQtyColumn(columns), 'Discounts');

const sales = 114328;
const qty = 10427;
const aov = Math.round((sales / qty) * 100) / 100;
assert.ok(aov > 10 && aov < 12, `expected ~$11 AOV, got ${aov}`);

console.log('pmix AOV column detection OK');
