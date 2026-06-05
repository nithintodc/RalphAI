import { filterByDateRange, filterExcludedDates, filterExcludedStores, aggregate } from './aggregator';
import { getLastYearDates } from '../utils/dateUtils';
import { buildStoreMetaLookup } from '../utils/storeMeta';

export function buildFourWindowAggregation(rawData, config) {
  const {
    preStart, preEnd, postStart, postEnd,
    excludedDates = [], excludedStores = [],
    dateField, storeField, sumFields, uniqueFields = [],
  } = config;

  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);

  const windows = {
    pre: { start: preStart, end: preEnd },
    post: { start: postStart, end: postEnd },
    preLY: lyPre,
    postLY: lyPost,
  };

  const result = {};
  for (const [name, { start, end }] of Object.entries(windows)) {
    let filtered = filterByDateRange(rawData, dateField, start, end);
    filtered = filterExcludedDates(filtered, dateField, excludedDates);
    filtered = filterExcludedStores(filtered, storeField, excludedStores);
    result[name] = aggregate(filtered, storeField, sumFields, uniqueFields);
  }
  return result;
}

export function mergeFourWindows(windows, storeField, metricFields, storeMetaLookup = null) {
  const allStores = new Set();
  for (const win of Object.values(windows)) {
    for (const row of win) {
      allStores.add(String(row[storeField]));
    }
  }

  const lookup = {};
  for (const [winName, rows] of Object.entries(windows)) {
    lookup[winName] = {};
    for (const row of rows) {
      lookup[winName][String(row[storeField])] = row;
    }
  }

  const merged = [];
  for (const store of allStores) {
    const meta = storeMetaLookup?.get(store);
    const row = {
      storeId: store,
      storeName: meta?.storeName || '',
      ddStoreId: meta?.ddStoreId || '',
    };
    for (const metric of metricFields) {
      for (const win of ['pre', 'post', 'preLY', 'postLY']) {
        row[`${win}_${metric}`] = lookup[win]?.[store]?.[metric] || 0;
      }
    }
    merged.push(row);
  }
  return merged;
}

export function buildDdPlatformData(ddFinancial, config) {
  if (!ddFinancial || !ddFinancial.length) return [];
  const windows = buildFourWindowAggregation(ddFinancial, {
    ...config,
    dateField: 'date',
    storeField: 'storeId',
    sumFields: ['subtotal', 'netTotal', 'marketingFees', 'customerDiscounts', 'customerDiscountsDoorDash', 'customerDiscountsThirdParty', 'commission', 'errorCharges', 'adjustments', 'ddMarketingCredit', 'thirdPartyContribution', 'paymentProcessingFee'],
    uniqueFields: ['orderId'],
  });

  const metricMap = {
    subtotal: 'sales',
    netTotal: 'payouts',
    orderId: 'orders',
    marketingFees: 'marketingFees',
    customerDiscounts: 'customerDiscounts',
    customerDiscountsDoorDash: 'customerDiscountsDoorDash',
    customerDiscountsThirdParty: 'customerDiscountsThirdParty',
    commission: 'commission',
    errorCharges: 'errorCharges',
    adjustments: 'adjustments',
    ddMarketingCredit: 'ddMarketingCredit',
    thirdPartyContribution: 'thirdPartyContribution',
    paymentProcessingFee: 'paymentProcessingFee',
  };

  const renamed = {};
  for (const [winName, rows] of Object.entries(windows)) {
    renamed[winName] = rows.map(r => {
      const out = { storeId: r.storeId };
      for (const [from, to] of Object.entries(metricMap)) {
        out[to] = r[from] || 0;
      }
      return out;
    });
  }

  return mergeFourWindows(renamed, 'storeId', Object.values(metricMap), buildStoreMetaLookup(ddFinancial));
}

export function buildUePlatformData(ueFinancial, config) {
  if (!ueFinancial || !ueFinancial.length) return [];
  const windows = buildFourWindowAggregation(ueFinancial, {
    ...config,
    dateField: 'date',
    storeField: 'storeId',
    sumFields: ['sales', 'totalPayout', 'marketplaceFee', 'offers', 'orderErrorAdjustments'],
    uniqueFields: ['orderId'],
  });

  const metricMap = {
    sales: 'sales',
    totalPayout: 'payouts',
    orderId: 'orders',
    marketplaceFee: 'marketplaceFee',
    offers: 'offers',
  };

  const renamed = {};
  for (const [winName, rows] of Object.entries(windows)) {
    renamed[winName] = rows.map(r => {
      const out = { storeId: r.storeId };
      for (const [from, to] of Object.entries(metricMap)) {
        out[to] = r[from] || 0;
      }
      return out;
    });
  }

  return mergeFourWindows(renamed, 'storeId', Object.values(metricMap), buildStoreMetaLookup(ueFinancial));
}
