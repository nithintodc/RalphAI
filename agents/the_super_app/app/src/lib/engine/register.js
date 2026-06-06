/**
 * Layer-1 register: store × weekday × slot with averaged metrics across calendar dates.
 */
import { format } from 'date-fns';
import { filterByDateRange, filterExcludedDates, filterExcludedStores } from './aggregator';
import { assignBucket, classifyDdOrder, sumDdOrderMarketingSignals } from './buckets';
import { getSlot, getSlotTimeRange, SLOT_NAMES, DAY_NAMES } from './slots';
import { safeDivide, round } from '../utils/safeMath';
import { exportByKind } from '../utils/formatters';
import { normalizeDdSalesByOrder } from '../parsers/ddSalesByOrder';
import { buildDdStoreIdToMerchantMap } from '../utils/storeCatalog';

function dayOfWeekLabel(date) {
  if (!date) return '';
  return DAY_NAMES[(date.getDay() + 6) % 7] ?? '';
}

function dateStr(date) {
  if (!date) return '';
  return format(date, 'yyyy-MM-dd');
}

function emptyAgg(storeId, date, slot) {
  return {
    storeId,
    date: dateStr(date),
    dayOfWeek: dayOfWeekLabel(date),
    slot,
    orders: 0,
    sales: 0,
    payouts: 0,
    mktSpend: 0,
    adsSpend: 0,
    discounts: 0,
    organicOrders: 0,
    promoOrders: 0,
    adsOrders: 0,
    bothOrders: 0,
    commission: 0,
    errorCharges: 0,
    adjustments: 0,
    ddMarketingCredit: 0,
    thirdPartyContribution: 0,
    paymentProcessingFee: 0,
    customerDiscountsYou: 0,
    customerDiscountsDoorDash: 0,
    customerDiscountsThirdParty: 0,
    newCustomerOrders: 0,
    repeatCustomerOrders: 0,
    unknownCustomerOrders: 0,
    dashPassOrders: 0,
    nonDashPassOrders: 0,
    totalItems: 0,
    marketplaceFee: 0,
    offers: 0,
    orderErrorAdjustments: 0,
    newCustomersFinancial: 0,
  };
}

function finalizeRow(row) {
  const orders = row.orders;
  const sales = row.sales;
  row.aov = round(safeDivide(sales, orders), 2);
  row.avgPayout = round(safeDivide(row.payouts, orders), 2);
  row.profitabilityPct = round(safeDivide(row.payouts, sales) * 100, 1);
  const errorBase = (row.errorCharges || 0) + (row.orderErrorAdjustments || 0);
  row.errorRatePct = round(safeDivide(errorBase, sales) * 100, 2);
  row.mktDrivenOrders = row.promoOrders + row.bothOrders;
  row.adsDrivenOrders = row.adsOrders + row.bothOrders;
  row.dashPassPct = round(safeDivide(row.dashPassOrders, orders) * 100, 1);
  row.avgItemsPerOrder = round(safeDivide(row.totalItems, orders), 2);
  return row;
}

function registerKey(storeId, date, slot) {
  return `${storeId}|${dateStr(date)}|${slot}`;
}

function registerWeekdayKey(storeId, dayOfWeek, slot) {
  return `${storeId}|${dayOfWeek}|${slot}`;
}

function registerStoreIds(financial, excludedStores) {
  const scoped = filterExcludedStores(financial || [], 'storeId', excludedStores);
  return [...new Set(scoped.map((r) => String(r.storeId || '').trim()).filter(Boolean))].sort(
    (a, b) => a.localeCompare(b, undefined, { numeric: true }),
  );
}

function normalizeOrderId(id) {
  return String(id || '').trim().toUpperCase();
}

function buildErrorExtrasByOrderId(ddFinancialError) {
  const map = new Map();
  for (const r of ddFinancialError || []) {
    const oid = normalizeOrderId(r.orderId);
    if (!oid) continue;
    const cur = map.get(oid) || { errorCharges: 0, adjustments: 0 };
    cur.errorCharges += r.errorCharges || 0;
    cur.adjustments += r.adjustments || 0;
    map.set(oid, cur);
  }
  return map;
}

function applyOrphanErrorCharges(rows, ddFinancialError, orders) {
  const orderIds = new Set(orders.map((o) => normalizeOrderId(o.orderId)).filter(Boolean));
  const byKey = new Map(rows.map((r) => [registerKey(r.storeId, parseDateFromStr(r.date), r.slot), r]));

  for (const e of ddFinancialError || []) {
    const oid = normalizeOrderId(e.orderId);
    if (oid && orderIds.has(oid)) continue;
    const slot = getSlot(e.time, 'dd');
    if (!SLOT_NAMES.includes(slot)) continue;
    const key = registerKey(e.storeId, e.date, slot);
    const row = byKey.get(key);
    if (!row) continue;
    row.errorCharges += Math.abs(e.errorCharges || 0);
    row.adjustments += e.adjustments || 0;
    finalizeRow(row);
  }
  return rows;
}

function parseDateFromStr(s) {
  if (!s) return null;
  const [y, m, d] = String(s).split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function resolveDdSalesStoreId(rawStoreId, ddStoreIdToMerchant) {
  const id = String(rawStoreId || '').trim();
  if (!id) return '';
  for (const key of [id, String(Number(id))]) {
    if (key && ddStoreIdToMerchant.has(key)) return ddStoreIdToMerchant.get(key);
  }
  return ddStoreIdToMerchant.get(id) || id;
}

function emptySalesMetrics() {
  return {
    newCustomerOrders: 0,
    repeatCustomerOrders: 0,
    unknownCustomerOrders: 0,
    dashPassOrders: 0,
    nonDashPassOrders: 0,
    totalItems: 0,
    salesErrorCharges: 0,
  };
}

function addSalesOrderToBucket(bucket, o) {
  if (o.customerType === 'new') bucket.newCustomerOrders += 1;
  else if (o.customerType === 'repeat') bucket.repeatCustomerOrders += 1;
  else bucket.unknownCustomerOrders += 1;
  if (o.isDashPass === true) bucket.dashPassOrders += 1;
  else if (o.isDashPass === false) bucket.nonDashPassOrders += 1;
  bucket.totalItems += o.itemCount || 0;
  bucket.salesErrorCharges += o.errorCharge || 0;
}

/** SALES_BY_ORDER → store × weekday × slot (same grain as collapsed register). */
function aggregateDdSalesByWeekdaySlot(salesOrders, ddStoreIdToMerchant) {
  const groups = new Map();
  for (const o of salesOrders || []) {
    if (!o.date || !o.slot || !SLOT_NAMES.includes(o.slot)) continue;
    const storeId = resolveDdSalesStoreId(o.storeId, ddStoreIdToMerchant);
    if (!storeId) continue;
    const dayOfWeek = dayOfWeekLabel(o.date);
    if (!dayOfWeek) continue;
    const key = `${storeId}|${dayOfWeek}|${o.slot}`;
    let group = groups.get(key);
    if (!group) {
      group = { dates: new Set(), ...emptySalesMetrics() };
      groups.set(key, group);
    }
    group.dates.add(dateStr(o.date));
    addSalesOrderToBucket(group, o);
  }

  const out = new Map();
  for (const [key, group] of groups) {
    const n = group.dates.size || 1;
    out.set(key, {
      newCustomerOrders: Math.round(group.newCustomerOrders / n),
      repeatCustomerOrders: Math.round(group.repeatCustomerOrders / n),
      unknownCustomerOrders: Math.round(group.unknownCustomerOrders / n),
      dashPassOrders: Math.round(group.dashPassOrders / n),
      nonDashPassOrders: Math.round(group.nonDashPassOrders / n),
      totalItems: Math.round(group.totalItems / n),
      salesErrorCharges: round(group.salesErrorCharges / n, 2),
    });
  }
  return out;
}

function mergeSalesWeekdayIntoRegister(rows, salesByWeekday) {
  if (!salesByWeekday?.size) return rows;
  for (const row of rows) {
    const key = `${row.storeId}|${row.dayOfWeek}|${row.slot}`;
    const s = salesByWeekday.get(key);
    if (!s) continue;
    row.newCustomerOrders = s.newCustomerOrders;
    row.repeatCustomerOrders = s.repeatCustomerOrders;
    row.unknownCustomerOrders = s.unknownCustomerOrders;
    row.dashPassOrders = s.dashPassOrders;
    row.nonDashPassOrders = s.nonDashPassOrders;
    row.totalItems = s.totalItems;
    row.errorCharges += s.salesErrorCharges || 0;
    finalizeRow(row);
  }
  return rows;
}

function buildDdOrderRecords(ddFinancial, errorByOrderId) {
  const rows = ddFinancial;
  const byOrder = new Map();
  for (const r of rows) {
    const oid = normalizeOrderId(r.orderId);
    if (!oid) continue;
    if (!byOrder.has(oid)) byOrder.set(oid, []);
    byOrder.get(oid).push(r);
  }

  const out = [];
  for (const [rawOrderId, rs] of byOrder) {
    const orderId = normalizeOrderId(rawOrderId);
    const head = rs[0];
    const slot = getSlot(head.time, 'dd');
    if (!SLOT_NAMES.includes(slot)) continue;

    const sales = rs.reduce((s, r) => s + (r.subtotal || 0), 0);
    const payouts = rs.reduce((s, r) => s + (r.netTotal || 0), 0);
    const marketingFees = rs.reduce((s, r) => s + (r.marketingFees || 0), 0);
    const cdYou = rs.reduce((s, r) => s + (r.customerDiscounts || 0), 0);
    const cdDd = rs.reduce((s, r) => s + (r.customerDiscountsDoorDash || 0), 0);
    const cd3p = rs.reduce((s, r) => s + (r.customerDiscountsThirdParty || 0), 0);
    const mktSignals = sumDdOrderMarketingSignals(rs);
    const orderType = classifyDdOrder(mktSignals);

    const errExtra = errorByOrderId.get(orderId) || {};

    out.push({
      storeId: head.storeId,
      date: head.date,
      slot,
      sales,
      payouts,
      marketingFees,
      cdYou,
      cdDd,
      cd3p,
      discounts: Math.abs(cdYou) + Math.abs(cdDd) + Math.abs(cd3p),
      mktSpend: Math.abs(marketingFees) + Math.abs(cdYou) + Math.abs(cdDd) + Math.abs(cd3p),
      adsSpend: marketingFees,
      commission: rs.reduce((s, r) => s + (r.commission || 0), 0),
      errorCharges:
        Math.abs(rs.reduce((s, r) => s + (r.errorCharges || 0), 0))
        + Math.abs(errExtra.errorCharges || 0),
      adjustments: rs.reduce((s, r) => s + (r.adjustments || 0), 0) + (errExtra.adjustments || 0),
      ddMarketingCredit: rs.reduce((s, r) => s + (r.ddMarketingCredit || 0), 0),
      thirdPartyContribution: rs.reduce((s, r) => s + (r.thirdPartyContribution || 0), 0),
      paymentProcessingFee: rs.reduce((s, r) => s + (r.paymentProcessingFee || 0), 0),
      orderType,
      bucket: assignBucket(sales),
      orderId,
    });
  }
  return out;
}

const UE_OFFER_EPSILON = 0.01;

/** UE register: promo when |offers| > 0; no ads bucket (UE financial has no ad spend). */
function classifyUeRegisterOrder(offers) {
  return Math.abs(offers || 0) >= UE_OFFER_EPSILON ? 'promo' : 'organic';
}

function buildUeOrderRecords(ueFinancial) {
  const byOrder = new Map();
  for (const r of ueFinancial) {
    const oid = r.orderId;
    if (!oid) continue;
    if (!byOrder.has(oid)) byOrder.set(oid, []);
    byOrder.get(oid).push(r);
  }

  const out = [];
  for (const [, rs] of byOrder) {
    const head = rs[0];
    const slot = getSlot(head.time, 'ue');
    if (!SLOT_NAMES.includes(slot)) continue;

    const sales = rs.reduce((s, r) => s + (r.sales || 0), 0);
    const payouts = rs.reduce((s, r) => s + (r.totalPayout || 0), 0);
    const marketplaceFee = rs.reduce((s, r) => s + (r.marketplaceFee || 0), 0);
    const offers = rs.reduce((s, r) => s + Math.abs(r.offers || 0), 0);
    const orderType = classifyUeRegisterOrder(offers);

    out.push({
      storeId: head.storeId,
      date: head.date,
      slot,
      sales,
      payouts,
      marketplaceFee,
      offers,
      discounts: offers,
      orderErrorAdjustments: rs.reduce((s, r) => s + (r.orderErrorAdjustments || 0), 0),
      orderType,
    });
  }
  return out;
}

function aggregateOrders(orders) {
  const map = new Map();
  for (const o of orders) {
    const key = registerKey(o.storeId, o.date, o.slot);
    let row = map.get(key);
    if (!row) {
      row = emptyAgg(o.storeId, o.date, o.slot);
      map.set(key, row);
    }
    row.orders += 1;
    row.sales += o.sales || 0;
    row.payouts += o.payouts || 0;
    row.mktSpend += o.mktSpend || 0;
    row.adsSpend += o.adsSpend || 0;
    row.discounts += o.discounts || 0;

    if (o.orderType === 'organic') row.organicOrders += 1;
    else if (o.orderType === 'promo') row.promoOrders += 1;
    else if (o.orderType === 'ads') row.adsOrders += 1;
    else if (o.orderType === 'promo_ads') row.bothOrders += 1;

    if (o.commission != null) row.commission += o.commission;
    if (o.errorCharges != null) row.errorCharges += o.errorCharges;
    if (o.adjustments != null) row.adjustments += o.adjustments;
    if (o.ddMarketingCredit != null) row.ddMarketingCredit += o.ddMarketingCredit;
    if (o.thirdPartyContribution != null) row.thirdPartyContribution += o.thirdPartyContribution;
    if (o.paymentProcessingFee != null) row.paymentProcessingFee += o.paymentProcessingFee;
    if (o.cdYou != null) row.customerDiscountsYou += Math.abs(o.cdYou);
    if (o.cdDd != null) row.customerDiscountsDoorDash += Math.abs(o.cdDd);
    if (o.cd3p != null) row.customerDiscountsThirdParty += Math.abs(o.cd3p);

    if (o.customerType === 'new') row.newCustomerOrders += 1;
    else if (o.customerType === 'repeat') row.repeatCustomerOrders += 1;
    else row.unknownCustomerOrders += 1;

    if (o.isDashPass === true) row.dashPassOrders += 1;
    else if (o.isDashPass === false) row.nonDashPassOrders += 1;

    row.totalItems += o.itemCount || 0;

    if (o.marketplaceFee != null) row.marketplaceFee += o.marketplaceFee;
    if (o.offers != null) row.offers += Math.abs(o.offers);
    if (o.orderErrorAdjustments != null) row.orderErrorAdjustments += o.orderErrorAdjustments;
    row.newCustomersFinancial += o.newCustomersFinancial || 0;
  }

  return [...map.values()].map(finalizeRow);
}

function sortRegister(rows) {
  return rows.sort((a, b) => {
    if (a.storeId !== b.storeId) return a.storeId.localeCompare(b.storeId);
    const dowA = DAY_NAMES.indexOf(a.dayOfWeek);
    const dowB = DAY_NAMES.indexOf(b.dayOfWeek);
    if (dowA !== dowB) return dowA - dowB;
    return SLOT_NAMES.indexOf(a.slot) - SLOT_NAMES.indexOf(b.slot);
  });
}

const REGISTER_SUM_KEYS = [
  'orders', 'sales', 'payouts', 'mktSpend', 'adsSpend', 'discounts',
  'organicOrders', 'promoOrders', 'adsOrders', 'bothOrders',
  'commission', 'errorCharges', 'adjustments', 'ddMarketingCredit',
  'thirdPartyContribution', 'paymentProcessingFee',
  'customerDiscountsYou', 'customerDiscountsDoorDash', 'customerDiscountsThirdParty',
  'newCustomerOrders', 'repeatCustomerOrders', 'unknownCustomerOrders',
  'dashPassOrders', 'nonDashPassOrders', 'totalItems',
  'marketplaceFee', 'offers', 'orderErrorAdjustments', 'newCustomersFinancial',
];

/** Count metrics averaged across calendar dates → nearest whole number (typical weekday GC). */
const REGISTER_COUNT_KEYS = new Set([
  'orders', 'organicOrders', 'promoOrders', 'adsOrders', 'bothOrders',
  'newCustomerOrders', 'repeatCustomerOrders', 'unknownCustomerOrders',
  'dashPassOrders', 'nonDashPassOrders', 'totalItems', 'newCustomersFinancial',
]);

function averageRegisterMetric(key, sum, dayCount) {
  const n = dayCount || 1;
  const avg = sum / n;
  return REGISTER_COUNT_KEYS.has(key) ? Math.round(avg) : round(avg, 2);
}

function emptyWeekdaySlotRow(storeId, dayOfWeek, slot) {
  const row = { storeId, dayOfWeek, slot };
  for (const k of REGISTER_SUM_KEYS) row[k] = 0;
  return finalizeRow(row);
}

/** Ensure every store × weekday × slot exists (zeros when no orders in period). */
function fillRegisterWeekdayGrid(rows, storeIds) {
  const byKey = new Map(
    rows.map((r) => [registerWeekdayKey(r.storeId, r.dayOfWeek, r.slot), r]),
  );
  const stores = storeIds?.length
    ? storeIds
    : [...new Set(rows.map((r) => r.storeId).filter(Boolean))].sort((a, b) =>
      String(a).localeCompare(String(b), undefined, { numeric: true }),
    );

  const out = [];
  for (const storeId of stores) {
    for (const dayOfWeek of DAY_NAMES) {
      for (const slot of SLOT_NAMES) {
        const key = registerWeekdayKey(storeId, dayOfWeek, slot);
        out.push(byKey.get(key) || emptyWeekdaySlotRow(storeId, dayOfWeek, slot));
      }
    }
  }
  return out;
}

/** Average calendar-day rows into store × weekday × slot (typical day). */
function collapseRegisterByWeekday(rows) {
  const groups = new Map();

  for (const row of rows) {
    const key = `${row.storeId}|${row.dayOfWeek}|${row.slot}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        storeId: row.storeId,
        dayOfWeek: row.dayOfWeek,
        slot: row.slot,
        dates: new Set(),
        sums: Object.fromEntries(REGISTER_SUM_KEYS.map((k) => [k, 0])),
      };
      groups.set(key, group);
    }

    group.dates.add(row.date);
    for (const k of REGISTER_SUM_KEYS) {
      group.sums[k] += row[k] || 0;
    }
  }

  const out = [];
  for (const group of groups.values()) {
    const n = group.dates.size || 1;
    const row = {
      storeId: group.storeId,
      dayOfWeek: group.dayOfWeek,
      slot: group.slot,
    };
    for (const k of REGISTER_SUM_KEYS) {
      row[k] = averageRegisterMetric(k, group.sums[k], n);
    }
    out.push(finalizeRow(row));
  }
  return out;
}

export const DD_REGISTER_COLUMNS = [
  { key: 'storeId', label: 'Store ID', kind: 'text' },
  { key: 'dayOfWeek', label: 'Day', kind: 'text' },
  { key: 'slot', label: 'Slot', kind: 'text' },
  { key: 'slotTime', label: 'Slot time', kind: 'text' },
  { key: 'orders', label: 'Orders (GC)', kind: 'int' },
  { key: 'sales', label: 'Sales', kind: 'usd' },
  { key: 'payouts', label: 'Payouts', kind: 'usd' },
  { key: 'aov', label: 'AOV', kind: 'usd2' },
  { key: 'avgPayout', label: 'Avg Payout', kind: 'usd2' },
  { key: 'profitabilityPct', label: 'Profitability %', kind: 'pct' },
  { key: 'mktSpend', label: 'Mkt Spend', kind: 'usd' },
  { key: 'adsSpend', label: 'Ads Spend', kind: 'usd' },
  { key: 'discounts', label: 'Discounts', kind: 'usd' },
  { key: 'organicOrders', label: 'Organic Orders', kind: 'int' },
  { key: 'promoOrders', label: 'Promo Orders', kind: 'int' },
  { key: 'adsOrders', label: 'Ads Orders', kind: 'int' },
  { key: 'bothOrders', label: 'Promo + Ads Orders', kind: 'int' },
  { key: 'mktDrivenOrders', label: 'Mkt Driven Orders', kind: 'int' },
  { key: 'adsDrivenOrders', label: 'Ads Driven Orders', kind: 'int' },
  { key: 'commission', label: 'Commission', kind: 'usd' },
  { key: 'errorCharges', label: 'Error Charges', kind: 'usd' },
  { key: 'errorRatePct', label: 'Error Rate %', kind: 'pct' },
  { key: 'ddMarketingCredit', label: 'DD Mkt Credit', kind: 'usd' },
  { key: 'thirdPartyContribution', label: '3P Contribution', kind: 'usd' },
  { key: 'paymentProcessingFee', label: 'Payment Processing', kind: 'usd' },
  { key: 'customerDiscountsYou', label: 'Discounts (You)', kind: 'usd' },
  { key: 'customerDiscountsDoorDash', label: 'Discounts (DD)', kind: 'usd' },
  { key: 'customerDiscountsThirdParty', label: 'Discounts (3P)', kind: 'usd' },
  { key: 'newCustomerOrders', label: 'New Customer Orders', kind: 'int' },
  { key: 'repeatCustomerOrders', label: 'Repeat Customer Orders', kind: 'int' },
  { key: 'unknownCustomerOrders', label: 'Unknown Customer Orders', kind: 'int' },
  { key: 'dashPassOrders', label: 'DashPass Orders', kind: 'int' },
  { key: 'nonDashPassOrders', label: 'Non-DashPass Orders', kind: 'int' },
  { key: 'dashPassPct', label: 'DashPass %', kind: 'pct' },
  { key: 'totalItems', label: 'Total Items', kind: 'int' },
  { key: 'avgItemsPerOrder', label: 'Avg Items / Order', kind: 'num2' },
];

export const UE_REGISTER_COLUMNS = [
  { key: 'storeId', label: 'Store ID', kind: 'text' },
  { key: 'dayOfWeek', label: 'Day', kind: 'text' },
  { key: 'slot', label: 'Slot', kind: 'text' },
  { key: 'slotTime', label: 'Slot time', kind: 'text' },
  { key: 'orders', label: 'Orders (GC)', kind: 'int' },
  { key: 'sales', label: 'Sales', kind: 'usd' },
  { key: 'payouts', label: 'Payouts', kind: 'usd' },
  { key: 'aov', label: 'AOV', kind: 'usd2' },
  { key: 'avgPayout', label: 'Avg Payout', kind: 'usd2' },
  { key: 'profitabilityPct', label: 'Profitability %', kind: 'pct' },
  { key: 'marketplaceFee', label: 'Marketplace Fee', kind: 'usd' },
  { key: 'discounts', label: 'Discounts (Offers)', kind: 'usd' },
  { key: 'organicOrders', label: 'Organic Orders', kind: 'int' },
  { key: 'promoOrders', label: 'Promo Orders', kind: 'int' },
  { key: 'orderErrorAdjustments', label: 'Order Error Adjustments', kind: 'usd' },
  { key: 'errorRatePct', label: 'Error Rate %', kind: 'pct' },
];

function applyExcludedDates(orders, excludedDates) {
  if (!excludedDates?.length) return orders;
  return filterExcludedDates(orders, 'date', excludedDates);
}

function applyPostPeriod(rows, start, end) {
  if (!start || !end || !rows?.length) return rows;
  return filterByDateRange(rows, 'date', start, end);
}

export function buildDdRegister(data, config = {}) {
  const { ddFinancial, ddSales, ddFinancialError } = data;
  if (!ddFinancial?.length) return [];

  const storeIds = registerStoreIds(ddFinancial, config.ddExcludedStores);
  if (!storeIds.length) return [];

  let ddFin = filterExcludedStores(ddFinancial, 'storeId', config.ddExcludedStores);
  ddFin = applyPostPeriod(ddFin, config.ddPostStart, config.ddPostEnd);
  let ddErr = ddFinancialError?.length
    ? filterExcludedStores(ddFinancialError, 'storeId', config.ddExcludedStores)
    : ddFinancialError;
  ddErr = applyPostPeriod(ddErr, config.ddPostStart, config.ddPostEnd);

  const ddStoreIdToMerchant = buildDdStoreIdToMerchantMap(ddFin);
  const errorByOrderId = buildErrorExtrasByOrderId(ddErr);

  let salesOrders = normalizeDdSalesByOrder(ddSales?.byOrder);
  salesOrders = applyPostPeriod(salesOrders, config.ddPostStart, config.ddPostEnd);
  salesOrders = applyExcludedDates(salesOrders, config.ddExcludedDates);
  const salesByWeekday = aggregateDdSalesByWeekdaySlot(salesOrders, ddStoreIdToMerchant);

  let orders = buildDdOrderRecords(ddFin, errorByOrderId);
  orders = applyExcludedDates(orders, config.ddExcludedDates);

  let rows = aggregateOrders(orders);
  rows = applyOrphanErrorCharges(rows, ddErr, orders);
  rows = collapseRegisterByWeekday(rows);
  rows = fillRegisterWeekdayGrid(rows, storeIds);
  rows = mergeSalesWeekdayIntoRegister(rows, salesByWeekday);
  return sortRegister(rows);
}

export function buildUeRegister(data, config = {}) {
  const { ueFinancial } = data;
  if (!ueFinancial?.length) return [];

  const storeIds = registerStoreIds(ueFinancial, config.ueExcludedStores);
  if (!storeIds.length) return [];

  let ueFin = filterExcludedStores(ueFinancial, 'storeId', config.ueExcludedStores);
  ueFin = applyPostPeriod(ueFin, config.uePostStart, config.uePostEnd);

  let orders = buildUeOrderRecords(ueFin);
  orders = applyExcludedDates(orders, config.ueExcludedDates);

  let rows = collapseRegisterByWeekday(aggregateOrders(orders));
  rows = fillRegisterWeekdayGrid(rows, storeIds);
  return sortRegister(rows);
}

export { compareRegisterWeekSlots, REGISTER_WOW_METRICS } from './registerWow.js';

export function registerRowToExport(row, columns) {
  return columns.map((c) => {
    if (c.key === 'slotTime') return getSlotTimeRange(row.slot);
    const v = row[c.key];
    if (v == null || v === '') return '';
    if (c.kind === 'text' || c.kind === 'date') return v;
    const exportKind = c.kind === 'num2' ? 'usd2' : c.kind;
    return exportByKind(exportKind, v);
  });
}
