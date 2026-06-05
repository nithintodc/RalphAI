import assert from 'node:assert/strict';
import { UE_REGISTER_COLUMNS } from '../src/lib/engine/register.js';

const keys = UE_REGISTER_COLUMNS.map((c) => c.key);
assert.ok(!keys.includes('mktSpend'), 'UE register should not include mktSpend');
assert.ok(!keys.includes('adsSpend'), 'UE register should not include adsSpend');
assert.ok(!keys.includes('adsOrders'), 'UE register should not include adsOrders');
assert.ok(!keys.includes('bothOrders'), 'UE register should not include bothOrders');
assert.ok(!keys.includes('mktDrivenOrders'), 'UE register should not include mktDrivenOrders');
assert.ok(!keys.includes('adsDrivenOrders'), 'UE register should not include adsDrivenOrders');
assert.ok(keys.includes('marketplaceFee'), 'UE register keeps marketplaceFee (commission)');
assert.ok(keys.includes('promoOrders') && keys.includes('organicOrders'));

console.log('UE register columns OK');
