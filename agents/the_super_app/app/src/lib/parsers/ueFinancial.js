import { parseDate, minMaxDates } from '../utils/dateUtils';
import { toNum } from '../utils/safeMath';
import { sanitizeStoreId } from './ddFinancial';

const STORE_NAME_COLS = ['Store Name', 'Restaurant Name', 'Restaurant name', 'Merchant Name', 'Store name'];
/** Location-level IDs first; chain-level Store ID / Shop ID are fallbacks only. */
const STORE_ID_COLS = [
  'External store ID as per Uber Eats manager',
  'External Store ID as per Uber Eats manager',
  'External store ID',
  'Merchant Store ID',
  'Store ID as per Uber Eats manager',
  'Store ID',
  'Shop ID',
];

export function sanitizeUeStoreId(raw) {
  const s = sanitizeStoreId(raw);
  if (!s) return '';
  if (/^\d+\.0+$/.test(s)) return s.replace(/\.0+$/, '');
  return s;
}

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

function isStoreNameLikeColumn(col) {
  const cl = normalizeColHeader(col);
  return cl.includes('store') && cl.includes('name');
}

function scoreStoreIdColumn(data, col, storeNameCol) {
  const ids = new Set();
  const names = new Set();
  let numeric = 0;
  for (const row of data || []) {
    const id = sanitizeUeStoreId(row[col]);
    const name = storeNameCol ? String(row[storeNameCol] || '').trim() : '';
    if (id) {
      ids.add(id);
      if (/^\d+$/.test(id)) numeric += 1;
    }
    if (name) names.add(name);
  }
  if (!ids.size) return -1;

  let overlapsName = 0;
  for (const id of ids) {
    if (names.has(id)) overlapsName += 1;
  }

  const numericRatio = numeric / ids.size;
  return ids.size * 100 + numericRatio * 50 - overlapsName * 200;
}

function findStoreIdCol(columns, data, storeNameCol) {
  const candidates = [];
  const seen = new Set();
  const addCandidate = (col) => {
    if (!col || seen.has(col) || isStoreNameLikeColumn(col)) return;
    seen.add(col);
    candidates.push(col);
  };

  for (const v of STORE_ID_COLS) addCandidate(findCol(columns, [v]));

  for (const c of columns) {
    const cl = normalizeColHeader(c);
    if (!cl.includes('store') || !cl.includes('id')) continue;
    if (cl.includes('order') || cl.includes('unique id') || cl.includes('name')) continue;
    addCandidate(c);
  }

  let best = null;
  let bestScore = -1;
  for (const col of candidates) {
    const score = scoreStoreIdColumn(data, col, storeNameCol);
    if (score > bestScore) {
      bestScore = score;
      best = col;
    }
  }
  return best;
}

function findTimeCol(columns) {
  return findCol(columns, [
    'Order Accept Time',
    'Order accept time',
    'Order Accepted Time',
    'Local timestamp for when order was accepted by the merchant',
  ]);
}

function _isUeAdSpendDescription(desc) {
  const d = String(desc ?? '').trim().toLowerCase();
  return d === 'ad spend' || d.includes('ad spend');
}

/** UE ads spend: Other payments where description is Ad Spend (absolute $). */
function _ueAdSpendFromRow(row, otherPaymentsCol, otherPaymentsDescCol) {
  if (!otherPaymentsCol || !otherPaymentsDescCol) return 0;
  const desc = String(row[otherPaymentsDescCol] ?? '').trim();
  if (!_isUeAdSpendDescription(desc)) return 0;
  return Math.abs(toNum(row[otherPaymentsCol]));
}

export function normalizeUeFinancial(parsed) {
  const { data, columns } = parsed;

  const dateCol = findCol(columns, [
    'Order date',
    'Order Date',
  ]);
  const timeCol = findTimeCol(columns);
  const storeNameCol = findStoreNameCol(columns);
  const storeIdCol = findStoreIdCol(columns, data, storeNameCol);
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
    'Offers on items (incl. tax)',
    'Offers on items',
    'Offers',
    'Merchant promotions applied to the order',
  ]);
  const deliveryOffersCol = findCol(columns, [
    'Delivery Offer Redemptions (incl. tax)',
    'Delivery Offer Redemptions',
    'Delivery offer redemptions (incl. tax)',
  ]);
  const otherPaymentsCol = findCol(columns, [
    'Other payments',
    'All miscellaneous payments',
  ]);
  const otherPaymentsDescCol = findCol(columns, [
    'Other payments description',
    'Description of adhoc one-time payments or charges from Uber',
    'Description of adhoc one-time payments or charges from Uber Eats',
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

  return data
    .map((row) => {
      const date = dateCol ? parseDate(row[dateCol]) : null;
      const storeName = storeNameCol ? String(row[storeNameCol] || '').trim() : '';
      const rawStoreId = storeIdCol ? sanitizeUeStoreId(row[storeIdCol]) : '';
      const storeId = rawStoreId || storeName;
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
        deliveryOffers: deliveryOffersCol ? toNum(row[deliveryOffersCol]) : 0,
        adSpend: _ueAdSpendFromRow(row, otherPaymentsCol, otherPaymentsDescCol),
        marketingAdjustment: marketingAdjCol ? toNum(row[marketingAdjCol]) : 0,
        orderErrorAdjustments: errorAdjCol ? Math.abs(toNum(row[errorAdjCol])) : 0,
        newCustomers: newCustCol ? toNum(row[newCustCol]) : 0,
        diningMode: diningCol ? row[diningCol] : null,
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

/** Row counts by calendar year — used to verify LY coverage after upload. */
export function summarizeUeFinancialYears(data) {
  const years = {};
  for (const r of data || []) {
    if (!r?.date) continue;
    const y = r.date.getFullYear();
    years[y] = (years[y] || 0) + 1;
  }
  const sorted = Object.keys(years).map(Number).sort((a, b) => a - b);
  return { years, sortedYears: sorted };
}
