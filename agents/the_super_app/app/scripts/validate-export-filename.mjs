import assert from 'node:assert/strict';
import {
  buildExportFilename,
  sanitizeOperatorForFilename,
} from '../src/lib/export/exportFilename.js';

assert.equal(sanitizeOperatorForFilename('Bican Family Restaurants Inc'), 'Bican_Family_Restaurants_Inc');
assert.equal(sanitizeOperatorForFilename(''), 'operator');

const name = buildExportFilename(
  { operatorName: 'Bican Family Restaurants Inc' },
  'excel',
  { ext: 'xlsx', ts: '20260605_194052' },
);
assert.equal(name, 'Bican_Family_Restaurants_Inc_20260605_194052_excel.xlsx');

const doc = buildExportFilename(
  { operatorName: 'Bican Family Restaurants Inc' },
  'doc',
  { ext: 'doc', ts: '20260605_194109' },
);
assert.equal(doc, 'Bican_Family_Restaurants_Inc_20260605_194109_doc.doc');

console.log('export filename validation OK');
