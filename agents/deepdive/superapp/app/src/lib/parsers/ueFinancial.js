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

function findCol(columns, variations) {
  for (const v of variations) {
    if (columns.includes(v)) return v;
  }
  for (const c of columns) {
    const cl = c.toLowerCase();
    for (const v of variations) {
      if (cl === v.toLowerCase()) return c;
    }
  }
  return null;
}

function findStoreNameCol(columns) {
  const found = findCol(columns, STORE_NAME_COLS);
  if (found) return found;
  return columns.find(c => c.toLowerCase().includes('store') && c.toLowerCase().includes('name')) || null;
}

/** Resolves Uber Eats merchant/store id column (not order id). */
function findStoreIdCol(columns) {
  const found = findCol(columns, STORE_ID_COLS);
  if (found) return found;
  const external = columns.find(c => {
    const cl = c.toLowerCase();
    return cl.includes('external') && cl.includes('store') && cl.includes('id');
  });
  if (external) return external;
  return (
    columns.find(c => {
      const cl = c.toLowerCase();
      if (!cl.includes('store') || !cl.includes('id')) return false;
      if (cl.includes('order')) return false;
      if (cl.includes('unique id')) return false;
      if (cl.includes('store name')) return false;
      return true;
    }) || null
  );
}

function findTimeCol(columns, dateColIndex) {
  const nextIdx = dateColIndex + 1;
  if (nextIdx < columns.length) {
    const next = columns[nextIdx];
    if (next.toLowerCase().includes('time') || next.toLowerCase().includes('accept')) return next;
  }
  return columns.find(c => c.toLowerCase().includes('accept') && c.toLowerCase().includes('time')) || null;
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

  const dateCol = columns[8] || findCol(columns, ['Date', 'date']);
  const timeCol = findTimeCol(columns, 8);
  const storeNameCol = findStoreNameCol(columns);
  const storeIdCol = findStoreIdCol(columns);
  const orderIdCol = findCol(columns, ['Order ID', 'Workflow ID']);
  const salesCol = findCol(columns, ['Sales (excl. tax)', 'Sales (excl tax)']);
  const payoutCol = findCol(columns, ['Total payout', 'Total Payout']);
  const marketplaceCol = findCol(columns, ['Marketplace Fee', 'Marketplace fee']);
  const offersCol = findCol(columns, ['Offers on items', 'Offers']);
  const errorAdjCol = findCol(columns, ['Order Error Adjustments', 'Order error adjustments']);
  const newCustCol = findCol(columns, ['New customers', 'New Customers']);
  const diningCol = findCol(columns, ['Dining Mode', 'Dining mode']);

  const storeIdCount = uniqueCount(data, (row) => (storeIdCol ? String(row[storeIdCol] || '').trim() : ''));
  const storeNameCount = uniqueCount(data, (row) => (storeNameCol ? String(row[storeNameCol] || '').trim() : ''));
  const primaryStoreKey = storeNameCount > storeIdCount ? 'storeName' : 'storeId';

  return data
    .map(row => {
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
        orderId: orderIdCol ? String(row[orderIdCol] || '') : null,
        sales: salesCol ? toNum(row[salesCol]) : 0,
        totalPayout: payoutCol ? toNum(row[payoutCol]) : 0,
        marketplaceFee: marketplaceCol ? toNum(row[marketplaceCol]) : 0,
        offers: offersCol ? toNum(row[offersCol]) : 0,
        orderErrorAdjustments: errorAdjCol ? toNum(row[errorAdjCol]) : 0,
        newCustomers: newCustCol ? toNum(row[newCustCol]) : 0,
        diningMode: diningCol ? row[diningCol] : null,
        primaryStoreKey,
      };
    })
    .filter(Boolean);
}

export function getUniqueStores(data) {
  return [...new Set(data.map(r => r.storeId).filter(Boolean))].sort();
}

export function getDateRange(data) {
  return minMaxDates(data.map((r) => r.date).filter(Boolean));
}
