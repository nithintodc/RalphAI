import { parseDate, minMaxDates } from '../utils/dateUtils';
import { toNum } from '../utils/safeMath';

const STORE_NAME_COLS = ['Store Name', 'Restaurant Name', 'Restaurant name', 'Merchant Name', 'Store name'];
const STORE_ID_COLS = [
  'Store ID',
  'Shop ID',
  'External store ID as per Uber Eats manager',
  'External Store ID as per Uber Eats manager',
  'External store ID',
  'Merchant Store ID',
];

function normalizeColHeader(col) {
  return String(col ?? '')
    .replace(/\uFEFF/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

function findCol(columns, variations) {
  const normCols = columns.map((c) => ({ raw: c, norm: normalizeColHeader(c) }));
  for (const v of variations) {
    const vn = normalizeColHeader(v);
    const hit = normCols.find(({ norm }) => norm === vn);
    if (hit) return hit.raw;
  }
  for (const v of variations) {
    const vn = normalizeColHeader(v);
    const hit = normCols.find(({ norm }) => norm.includes(vn) || vn.includes(norm));
    if (hit) return hit.raw;
  }
  return null;
}

function findStoreNameCol(columns) {
  const found = findCol(columns, STORE_NAME_COLS);
  if (found) return found;
  return columns.find((c) => {
    const cl = normalizeColHeader(c);
    return cl.includes('store') && cl.includes('name') && !cl.includes('order');
  }) || null;
}

function findStoreIdCol(columns) {
  const found = findCol(columns, STORE_ID_COLS);
  if (found) return found;
  const external = columns.find((c) => {
    const cl = normalizeColHeader(c);
    return cl.includes('external') && cl.includes('store') && cl.includes('id');
  });
  if (external) return external;
  return columns.find((c) => {
    const cl = normalizeColHeader(c);
    if (!cl.includes('store') || !cl.includes('id')) return false;
    if (cl.includes('order')) return false;
    if (cl.includes('unique id')) return false;
    return true;
  }) || null;
}

function findTimeCol(columns, dateColIndex) {
  const explicit = findCol(columns, [
    'Order Accept Time',
    'Order accept time',
    'Order Accepted Time',
    'Local timestamp for when order was accepted by the merchant',
  ]);
  if (explicit) return explicit;
  const nextIdx = dateColIndex >= 0 ? dateColIndex + 1 : -1;
  if (nextIdx >= 0 && nextIdx < columns.length) {
    const next = columns[nextIdx];
    const cl = normalizeColHeader(next);
    if (cl.includes('time') || cl.includes('accept')) return next;
  }
  return columns.find((c) => {
    const cl = normalizeColHeader(c);
    return cl.includes('accept') && cl.includes('time');
  }) || null;
}

function uniqueCount(rows, accessor) {
  const seen = new Set();
  for (const row of rows || []) {
    const v = accessor(row);
    if (v) seen.add(v);
  }
  return seen.size;
}

export function normalizeUeFinancial(parsed) {
  const { data, columns } = parsed;

  const dateCol = findCol(columns, [
    'Order date',
    'Order Date',
    'Local date the order was placed',
    'Date',
    'date',
  ]) || columns[8] || null;
  const dateColIndex = dateCol ? columns.indexOf(dateCol) : 8;
  const timeCol =
    findCol(columns, [
      'Order placed time',
      'Order Placed Time',
      'Local timestamp for when order was placed',
    ])
    || findTimeCol(columns, dateColIndex);
  const storeNameCol = findStoreNameCol(columns);
  const storeIdCol = findStoreIdCol(columns);
  const orderIdCol = findCol(columns, [
    'Order ID as per Uber Eats manager',
    'Order ID',
    'Workflow ID',
    'Unique ID to identify the order',
  ]);
  const salesCol = findCol(columns, [
    'Sales (excl. tax)',
    'Sales (excl tax)',
    'Total item sales excl tax',
    'Total item sales excl. tax',
  ]);
  const payoutCol = findCol(columns, [
    'Total payout',
    'Total Payout',
    'Total payout associated with this order',
  ]);
  const marketplaceCol = findCol(columns, [
    'Marketplace Fee',
    'Marketplace fee',
    'Marketplace fee charged to merchant',
  ]);
  const offersCol = findCol(columns, [
    'Offers on items',
    'Offers on items (incl. tax)',
    'Offers',
    'Merchant promotions applied to the order',
  ]);
  const marketingAdjCol = findCol(columns, [
    'Marketing Adjustment',
    'Marketing adjustment',
  ]);
  const errorAdjCol = findCol(columns, [
    'Order Error Adjustments',
    'Order error adjustments',
    'Amount merchants are responsible for refunding customers when they report order errors (excl tax)',
  ]);
  const newCustCol = findCol(columns, ['New customers', 'New Customers']);
  const diningCol = findCol(columns, ['Dining Mode', 'Dining mode']);

  const storeIdCount = uniqueCount(data, (row) => (storeIdCol ? String(row[storeIdCol] || '').trim() : ''));
  const storeNameCount = uniqueCount(data, (row) => (storeNameCol ? String(row[storeNameCol] || '').trim() : ''));
  const primaryStoreKey = storeNameCount > storeIdCount ? 'storeName' : 'storeId';

  return data
    .map((row) => {
      const date = dateCol ? parseDate(row[dateCol]) : null;
      const storeName = storeNameCol ? String(row[storeNameCol] || '').trim() : '';
      const rawStoreId = storeIdCol ? String(row[storeIdCol] || '').trim() : '';
      const primaryStoreValue = primaryStoreKey === 'storeName' ? storeName : rawStoreId;
      const storeId = primaryStoreValue || rawStoreId || storeName;
      if (!date || !storeId) return null;
      return {
        date,
        time: timeCol ? row[timeCol] : null,
        storeId,
        storeName,
        rawStoreId,
        orderId: orderIdCol ? String(row[orderIdCol] || '').trim() : null,
        sales: salesCol ? toNum(row[salesCol]) : 0,
        totalPayout: payoutCol ? toNum(row[payoutCol]) : 0,
        marketplaceFee: marketplaceCol ? toNum(row[marketplaceCol]) : 0,
        offers: offersCol ? toNum(row[offersCol]) : 0,
        marketingAdjustment: marketingAdjCol ? toNum(row[marketingAdjCol]) : 0,
        orderErrorAdjustments: errorAdjCol ? Math.abs(toNum(row[errorAdjCol])) : 0,
        newCustomers: newCustCol ? toNum(row[newCustCol]) : 0,
        diningMode: diningCol ? row[diningCol] : null,
        primaryStoreKey,
      };
    })
    .filter(Boolean);
}

export function getUniqueStores(data) {
  return [...new Set(data.map((r) => r.storeId).filter(Boolean))].sort();
}

export function getDateRange(data) {
  return minMaxDates(data.map((r) => r.date).filter(Boolean));
}
