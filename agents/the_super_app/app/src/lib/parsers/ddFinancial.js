import { parseDate, minMaxDates } from '../utils/dateUtils';
import { toNum } from '../utils/safeMath';

const DATE_COLS = ['Timestamp local date', 'Timestamp Local Date', 'timestamp local date', 'Date', 'date', 'Timestamp'];
const TIME_COLS = ['Timestamp local time', 'Timestamp Local Time', 'timestamp local time', 'Order received local time', 'Order Received Local Time'];
const MERCHANT_STORE_COLS = ['Merchant store ID', 'Merchant Store ID'];
const DD_STORE_ID_COLS = ['Store ID', 'store ID', 'DoorDash store ID', 'Doordash store ID'];
const STORE_COLS = [...MERCHANT_STORE_COLS, ...DD_STORE_ID_COLS];
const STORE_NAME_COLS = ['Store name', 'Store Name'];
const BUSINESS_NAME_COLS = ['Business name', 'Business Name'];
const ORDER_ID_COLS = ['DoorDash order ID', 'DoorDash Order ID', 'Doordash order ID'];
const SUBTOTAL_COLS = ['Subtotal', 'subtotal'];
const NET_TOTAL_COLS = ['Net total', 'Net total (for historical reference only)'];
const MKT_FEE_COLS = ['Marketing fees | (including any applicable taxes)', 'Marketing fees'];
const CUST_DISC_COLS = ['Customer discounts from marketing | (funded by you)', 'Customer discounts from marketing | (Funded by you)', 'Customer discounts from marketing'];
const CUST_DISC_DD_COLS = ['Customer discounts from marketing | (funded by DoorDash)', 'Customer discounts from marketing | (Funded by DoorDash)'];
const CUST_DISC_THIRD_PARTY_COLS = ['Customer discounts from marketing | (funded by a third-party)', 'Customer discounts from marketing | (Funded by a third-party)', 'Customer discounts from marketing | (funded by a third party)'];
const COMMISSION_COLS = ['Commission', 'commission'];
const ERROR_COLS = ['Error charges', 'error charges'];
const ADJ_COLS = ['Adjustments', 'adjustments'];
const DD_MKT_CREDIT_COLS = ['DoorDash marketing credit'];
const THIRD_PARTY_COLS = ['Third-party contribution', 'Third party contribution'];
const PAYMENT_PROCESSING_COLS = ['Payment processing fee', 'Payment Processing Fee'];
const TXN_TYPE_COLS = ['Transaction type', 'Transaction Type'];

function normalizeColHeader(col) {
  return String(col ?? '')
    .replace(/\uFEFF/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

/** Treat spreadsheet NULL / empty as missing store IDs. */
export function sanitizeStoreId(raw) {
  if (raw == null || raw === undefined) return '';
  const s = String(raw).trim();
  if (!s || /^null$/i.test(s) || /^n\/?a$/i.test(s) || /^undefined$/i.test(s) || s === '—') return '';
  return s;
}

function findCol(columns, variations, { exclude = [] } = {}) {
  const excludeNorm = new Set(exclude.map(normalizeColHeader));
  const normCols = columns.map((c) => ({ raw: c, norm: normalizeColHeader(c) }));

  for (const v of variations) {
    const vn = normalizeColHeader(v);
    const hit = normCols.find(({ norm }) => norm === vn && !excludeNorm.has(norm));
    if (hit) return hit.raw;
  }
  return null;
}

/** Match DD marketing discount columns when exact header text varies slightly. */
function findDiscCol(columns, variations, fundingPhrase) {
  const exact = findCol(columns, variations);
  if (exact) return exact;
  const phrase = normalizeColHeader(fundingPhrase);
  const hit = columns.find((c) => {
    const norm = normalizeColHeader(c);
    return norm.includes('customer discounts from marketing') && norm.includes(phrase);
  });
  return hit ?? null;
}

function uniqueCount(rows, accessor) {
  const seen = new Set();
  for (const row of rows || []) {
    const v = accessor(row);
    if (v) seen.add(v);
  }
  return seen.size;
}

export function normalizeDdFinancial(parsed) {
  const { data, columns } = parsed;
  const dateCol = findCol(columns, DATE_COLS);
  const timeCol = findCol(columns, TIME_COLS);
  const merchantStoreCol = findCol(columns, MERCHANT_STORE_COLS);
  const ddStoreIdCol = findCol(columns, DD_STORE_ID_COLS, {
    exclude: ['merchant store id'],
  });
  const storeCol = merchantStoreCol || ddStoreIdCol || findCol(columns, STORE_COLS);
  const storeNameCol = findCol(columns, STORE_NAME_COLS);
  const businessNameCol = findCol(columns, BUSINESS_NAME_COLS);
  const orderCol = findCol(columns, ORDER_ID_COLS);
  const subtotalCol = findCol(columns, SUBTOTAL_COLS);
  const netTotalCol = findCol(columns, NET_TOTAL_COLS);
  const mktFeeCol = findCol(columns, MKT_FEE_COLS);
  const custDiscCol = findDiscCol(columns, CUST_DISC_COLS, 'funded by you');
  const custDiscDdCol = findDiscCol(columns, CUST_DISC_DD_COLS, 'funded by doordash');
  const custDiscThirdPartyCol = findDiscCol(columns, CUST_DISC_THIRD_PARTY_COLS, 'third-party');
  const commissionCol = findCol(columns, COMMISSION_COLS);
  const errorCol = findCol(columns, ERROR_COLS);
  const adjCol = findCol(columns, ADJ_COLS);
  const ddMktCreditCol = findCol(columns, DD_MKT_CREDIT_COLS);
  const thirdPartyCol = findCol(columns, THIRD_PARTY_COLS);
  const paymentProcessingCol = findCol(columns, PAYMENT_PROCESSING_COLS);
  const txnTypeCol = findCol(columns, TXN_TYPE_COLS);

  const merchantCount = uniqueCount(data, (row) => (merchantStoreCol ? sanitizeStoreId(row[merchantStoreCol]) : ''));
  const ddStoreCount = uniqueCount(data, (row) => (ddStoreIdCol ? sanitizeStoreId(row[ddStoreIdCol]) : ''));
  const storeNameCount = uniqueCount(data, (row) => {
    const name = storeNameCol
      ? String(row[storeNameCol] || '').trim()
      : businessNameCol
        ? String(row[businessNameCol] || '').trim()
        : '';
    return name && !/^null$/i.test(name) ? name : '';
  });

  const candidates = [
    { key: 'merchantStoreId', count: merchantCount, rank: 3 },
    { key: 'ddStoreId', count: ddStoreCount, rank: 2 },
    { key: 'storeName', count: storeNameCount, rank: 1 },
  ];
  candidates.sort((a, b) => (b.count - a.count) || (b.rank - a.rank));
  const primaryStoreKey = candidates[0]?.key || 'merchantStoreId';

  return data
    .map(row => {
      const date = dateCol ? parseDate(row[dateCol]) : null;
      const merchantStoreId = merchantStoreCol ? sanitizeStoreId(row[merchantStoreCol]) : '';
      const ddStoreId = ddStoreIdCol ? sanitizeStoreId(row[ddStoreIdCol]) : '';
      const storeName = storeNameCol
        ? String(row[storeNameCol] || '').trim()
        : businessNameCol
          ? String(row[businessNameCol] || '').trim()
          : '';
      const primaryStoreValue = (
        primaryStoreKey === 'merchantStoreId'
          ? merchantStoreId
          : primaryStoreKey === 'ddStoreId'
            ? ddStoreId
            : storeName
      ) || '';
      const storeId = primaryStoreValue || merchantStoreId || ddStoreId || (storeCol ? sanitizeStoreId(row[storeCol]) : null) || storeName;
      if (!date || !storeId) return null;
      return {
        date,
        time: timeCol ? row[timeCol] : null,
        storeId,
        merchantStoreId,
        ddStoreId,
        storeName,
        orderId: orderCol ? String(row[orderCol] || '') : null,
        subtotal: subtotalCol ? toNum(row[subtotalCol]) : 0,
        netTotal: netTotalCol ? toNum(row[netTotalCol]) : 0,
        marketingFees: mktFeeCol ? toNum(row[mktFeeCol]) : 0,
        customerDiscounts: custDiscCol ? toNum(row[custDiscCol]) : 0,
        customerDiscountsDoorDash: custDiscDdCol ? toNum(row[custDiscDdCol]) : 0,
        customerDiscountsThirdParty: custDiscThirdPartyCol ? toNum(row[custDiscThirdPartyCol]) : 0,
        commission: commissionCol ? toNum(row[commissionCol]) : 0,
        errorCharges: errorCol ? toNum(row[errorCol]) : 0,
        adjustments: adjCol ? toNum(row[adjCol]) : 0,
        ddMarketingCredit: ddMktCreditCol ? toNum(row[ddMktCreditCol]) : 0,
        thirdPartyContribution: thirdPartyCol ? toNum(row[thirdPartyCol]) : 0,
        paymentProcessingFee: paymentProcessingCol ? toNum(row[paymentProcessingCol]) : 0,
        transactionType: txnTypeCol ? row[txnTypeCol] : null,
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
