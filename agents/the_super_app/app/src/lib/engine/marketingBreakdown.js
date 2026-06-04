/**
 * DoorDash export breakdown pivots (financial, marketing promotion, sales-by-time, combined).
 * Financial (by date), Marketing Promotion (by date), Sales by Time (by granularity), combined merge.
 */

import { formatDateStr } from '../utils/dateUtils';

export const FINANCIAL_COLUMNS = {
  date: 'Timestamp local date',
  orderId: 'DoorDash order ID',
  storeId: 'Merchant store ID',
  subtotal: 'Subtotal',
  marketingFees: 'Marketing fees | (including any applicable taxes)',
  customerDiscounts: 'Customer discounts from marketing | (funded by you)',
};

export const MARKETING_COLUMNS = {
  date: 'Date',
  selfServe: 'Is self serve campaign',
  campaignId: 'Campaign ID',
  storeId: 'Store ID',
  orders: 'Orders',
  sales: 'Sales',
  marketingFees: 'Marketing fees | (including any applicable taxes)',
  customerDiscounts: 'Customer discounts from marketing | (Funded by you)',
};

export const SALES_COLUMNS = {
  granularity: 'Granularity',
  storeName: 'Store Name',
  grossSales: 'Gross Sales',
  totalOrders: 'Total Orders Including Cancelled Orders',
  aov: 'AOV',
  totalPromotionFees: 'Total Promotion Fees | (for historical reference only)',
  totalPromotionSales: 'Total Promotion Sales | (for historical reference only)',
  totalAdFees: 'Total Ad Fees | (for historical reference only)',
  totalAdSales: 'Total Ad Sales | (for historical reference only)',
};

export const COMBINED_COLUMNS = [
  { key: 'label', label: 'Date / Granularity' },
  { key: 'finSubtotal', label: 'Financial Subtotal' },
  { key: 'finMktFees', label: 'Financial Marketing Fees' },
  { key: 'finCustDisc', label: 'Financial Customer Discounts' },
  { key: 'finOrders', label: 'Financial Unique Orders' },
  { key: 'mktSales', label: 'Marketing Sales' },
  { key: 'mktOrders', label: 'Marketing Orders' },
  { key: 'salesGross', label: 'Sales Gross Sales' },
  { key: 'salesOrders', label: 'Sales Orders Incl. Cancelled' },
  { key: 'salesAov', label: 'Sales AOV' },
  { key: 'salesPromoFees', label: 'Sales Promotion Fees' },
  { key: 'salesPromoSales', label: 'Sales Promotion Sales' },
  { key: 'salesAdFees', label: 'Sales Ad Fees' },
  { key: 'salesAdSales', label: 'Sales Ad Sales' },
];

function safeTrim(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function parseNumber(value) {
  const raw = safeTrim(value);
  if (!raw) return 0;
  return Number(raw.replaceAll(',', '')) || 0;
}

function collectUnique(rows, key) {
  return [...new Set(rows.map((row) => row[key]).filter(Boolean))].sort();
}

function minValue(rows, key) {
  return rows.reduce((current, row) => (!current || row[key] < current ? row[key] : current), '');
}

function maxValue(rows, key) {
  return rows.reduce((current, row) => (!current || row[key] > current ? row[key] : current), '');
}

export function normalizeSelfServe(value) {
  const normalized = safeTrim(String(value || '')).toLowerCase();
  if (!normalized) return '';
  return normalized === 'true' ? 'true' : 'false';
}

export function normalizedGranularityKey(value) {
  const trimmed = safeTrim(value);
  if (trimmed.startsWith('Day of ')) return trimmed.slice(7);
  return trimmed;
}

function weightedAverage(total, weight) {
  if (!weight) return 0;
  return total / weight;
}

export function buildFinancialDataset(rows, fileLabel, sourceKind = 'upload') {
  const normalizedRows = rows
    .map((row) => ({
      date: safeTrim(row[FINANCIAL_COLUMNS.date]),
      orderId: safeTrim(row[FINANCIAL_COLUMNS.orderId]),
      storeId: safeTrim(row[FINANCIAL_COLUMNS.storeId]),
      subtotal: parseNumber(row[FINANCIAL_COLUMNS.subtotal]),
      marketingFees: parseNumber(row[FINANCIAL_COLUMNS.marketingFees]),
      customerDiscounts: parseNumber(row[FINANCIAL_COLUMNS.customerDiscounts]),
    }))
    .filter((row) => row.date);

  if (!normalizedRows.length) {
    throw new Error('The financial detailed file does not contain usable rows.');
  }

  return {
    type: 'financialDetailed',
    fileLabel,
    sourceKind,
    rows: normalizedRows,
    storeIds: collectUnique(normalizedRows, 'storeId'),
    minDate: minValue(normalizedRows, 'date'),
    maxDate: maxValue(normalizedRows, 'date'),
  };
}

export function buildFinancialDatasetFromDdFinancial(ddFinancial, fileLabel = 'DoorDash Financial (detailed)') {
  const normalizedRows = (ddFinancial || [])
    .map((row) => ({
      date: formatDateStr(row.date),
      orderId: safeTrim(row.orderId),
      storeId: safeTrim(row.storeId),
      subtotal: row.subtotal ?? 0,
      marketingFees: row.marketingFees ?? 0,
      customerDiscounts: row.customerDiscounts ?? 0,
    }))
    .filter((row) => row.date);

  if (!normalizedRows.length) {
    throw new Error('Financial data does not contain usable rows for breakdown.');
  }

  return {
    type: 'financialDetailed',
    fileLabel,
    sourceKind: 'superapp',
    rows: normalizedRows,
    storeIds: collectUnique(normalizedRows, 'storeId'),
    minDate: minValue(normalizedRows, 'date'),
    maxDate: maxValue(normalizedRows, 'date'),
  };
}

export function buildMarketingDataset(rows, fileLabel, sourceKind = 'upload') {
  const normalizedRows = rows
    .map((row) => ({
      date: safeTrim(row[MARKETING_COLUMNS.date]),
      campaignId: safeTrim(row[MARKETING_COLUMNS.campaignId]),
      storeId: safeTrim(row[MARKETING_COLUMNS.storeId]),
      selfServe: normalizeSelfServe(row[MARKETING_COLUMNS.selfServe]),
      orders: parseNumber(row[MARKETING_COLUMNS.orders]),
      sales: parseNumber(row[MARKETING_COLUMNS.sales]),
      marketingFees: parseNumber(row[MARKETING_COLUMNS.marketingFees]),
      customerDiscounts: parseNumber(row[MARKETING_COLUMNS.customerDiscounts]),
    }))
    .filter((row) => row.date);

  if (!normalizedRows.length) {
    throw new Error('The marketing promotion file does not contain usable rows.');
  }

  return {
    type: 'marketingPromotion',
    fileLabel,
    sourceKind,
    rows: normalizedRows,
    campaignIds: collectUnique(normalizedRows, 'campaignId'),
    storeIds: collectUnique(normalizedRows, 'storeId'),
    selfServeValues: collectUnique(normalizedRows, 'selfServe'),
    minDate: minValue(normalizedRows, 'date'),
    maxDate: maxValue(normalizedRows, 'date'),
  };
}

export function buildSalesDataset(rows, fileLabel, sourceKind = 'upload') {
  const normalizedRows = rows
    .map((row) => ({
      granularity: safeTrim(row[SALES_COLUMNS.granularity]),
      storeName: safeTrim(row[SALES_COLUMNS.storeName]),
      grossSales: parseNumber(row[SALES_COLUMNS.grossSales]),
      totalOrders: parseNumber(row[SALES_COLUMNS.totalOrders]),
      aov: parseNumber(row[SALES_COLUMNS.aov]),
      totalPromotionFees: parseNumber(row[SALES_COLUMNS.totalPromotionFees]),
      totalPromotionSales: parseNumber(row[SALES_COLUMNS.totalPromotionSales]),
      totalAdFees: parseNumber(row[SALES_COLUMNS.totalAdFees]),
      totalAdSales: parseNumber(row[SALES_COLUMNS.totalAdSales]),
    }))
    .filter((row) => row.granularity);

  if (!normalizedRows.length) {
    throw new Error('The sales by time product performance file does not contain usable rows.');
  }

  return {
    type: 'salesByTimeProductPerformance',
    fileLabel,
    sourceKind,
    rows: normalizedRows,
    storeNames: collectUnique(normalizedRows, 'storeName'),
    granularityCount: collectUnique(normalizedRows, 'granularity').length,
  };
}

export function computeFinancialScope(dataset, storeId = 'ALL') {
  const rows =
    storeId === 'ALL'
      ? dataset.rows
      : dataset.rows.filter((row) => row.storeId === storeId);

  const uniqueOrders = new Set();
  let subtotal = 0;
  let marketingFees = 0;
  let customerDiscounts = 0;

  for (const row of rows) {
    subtotal += row.subtotal;
    marketingFees += row.marketingFees;
    customerDiscounts += row.customerDiscounts;
    if (row.orderId) uniqueOrders.add(row.orderId);
  }

  const summary = [
    { label: 'Date range', value: `${dataset.minDate} to ${dataset.maxDate}` },
    { label: 'Store filter', value: storeId === 'ALL' ? 'All stores' : storeId },
    { label: 'Subtotal', value: subtotal, kind: 'usd' },
    { label: 'Marketing fees', value: marketingFees, kind: 'usd' },
    { label: 'Customer discounts', value: customerDiscounts, kind: 'usd' },
    { label: 'Unique orders', value: uniqueOrders.size, kind: 'int' },
  ];

  const pivotMap = new Map();
  for (const row of rows) {
    if (!pivotMap.has(row.date)) {
      pivotMap.set(row.date, {
        date: row.date,
        subtotal: 0,
        marketingFees: 0,
        customerDiscounts: 0,
        orderIds: new Set(),
      });
    }
    const bucket = pivotMap.get(row.date);
    bucket.subtotal += row.subtotal;
    bucket.marketingFees += row.marketingFees;
    bucket.customerDiscounts += row.customerDiscounts;
    if (row.orderId) bucket.orderIds.add(row.orderId);
  }

  const pivot = [...pivotMap.values()].sort((a, b) => a.date.localeCompare(b.date));
  return { summary, pivot, fileLabel: dataset.fileLabel };
}

export function computeMarketingScope(dataset, filters = {}) {
  const selectedCampaign = filters.campaignId || 'ALL';
  const selectedStore = filters.storeId || 'ALL';
  const selectedSelfServe = filters.selfServe || 'ALL';

  const rows = dataset.rows.filter((row) => {
    if (selectedCampaign !== 'ALL' && row.campaignId !== selectedCampaign) return false;
    if (selectedStore !== 'ALL' && row.storeId !== selectedStore) return false;
    if (selectedSelfServe !== 'ALL' && row.selfServe !== selectedSelfServe) return false;
    return true;
  });

  let sales = 0;
  let orders = 0;

  for (const row of rows) {
    sales += row.sales;
    orders += row.orders;
  }

  const summary = [
    { label: 'Date range', value: `${dataset.minDate} to ${dataset.maxDate}` },
    { label: 'Campaign filter', value: selectedCampaign === 'ALL' ? 'All campaigns' : selectedCampaign },
    { label: 'Store filter', value: selectedStore === 'ALL' ? 'All stores' : selectedStore },
    { label: 'Self serve filter', value: selectedSelfServe === 'ALL' ? 'All' : selectedSelfServe },
    { label: 'Sales', value: sales, kind: 'usd' },
    { label: 'Orders', value: orders, kind: 'int' },
  ];

  const pivotMap = new Map();
  for (const row of rows) {
    if (!pivotMap.has(row.date)) {
      pivotMap.set(row.date, {
        date: row.date,
        sales: 0,
        orders: 0,
        marketingFees: 0,
        customerDiscounts: 0,
      });
    }
    const bucket = pivotMap.get(row.date);
    bucket.sales += row.sales;
    bucket.orders += row.orders;
    bucket.marketingFees += row.marketingFees;
    bucket.customerDiscounts += row.customerDiscounts;
  }

  const pivot = [...pivotMap.values()].sort((a, b) => a.date.localeCompare(b.date));
  return { summary, pivot, fileLabel: dataset.fileLabel };
}

export function computeSalesScope(dataset, storeName = 'ALL') {
  const rows =
    storeName === 'ALL'
      ? dataset.rows
      : dataset.rows.filter((row) => row.storeName === storeName);

  let grossSales = 0;
  let totalOrders = 0;
  let totalPromotionFees = 0;
  let totalPromotionSales = 0;
  let totalAdFees = 0;
  let totalAdSales = 0;

  for (const row of rows) {
    grossSales += row.grossSales;
    totalOrders += row.totalOrders;
    totalPromotionFees += row.totalPromotionFees;
    totalPromotionSales += row.totalPromotionSales;
    totalAdFees += row.totalAdFees;
    totalAdSales += row.totalAdSales;
  }

  const summary = [
    { label: 'Store filter', value: storeName === 'ALL' ? 'All stores' : storeName },
    { label: 'Granularity rows', value: dataset.granularityCount, kind: 'int' },
    { label: 'Gross sales', value: grossSales, kind: 'usd' },
    { label: 'Orders incl. cancelled', value: totalOrders, kind: 'int' },
    { label: 'Promotion fees', value: totalPromotionFees, kind: 'usd' },
    { label: 'Promotion sales', value: totalPromotionSales, kind: 'usd' },
    { label: 'Ad fees', value: totalAdFees, kind: 'usd' },
    { label: 'Ad sales', value: totalAdSales, kind: 'usd' },
  ];

  const pivotMap = new Map();
  for (const row of rows) {
    if (!pivotMap.has(row.granularity)) {
      pivotMap.set(row.granularity, {
        granularity: row.granularity,
        grossSales: 0,
        totalOrders: 0,
        aovWeightedSales: 0,
        aovWeightedOrders: 0,
        totalPromotionFees: 0,
        totalPromotionSales: 0,
        totalAdFees: 0,
        totalAdSales: 0,
      });
    }
    const bucket = pivotMap.get(row.granularity);
    bucket.grossSales += row.grossSales;
    bucket.totalOrders += row.totalOrders;
    bucket.aovWeightedSales += row.aov * row.totalOrders;
    bucket.aovWeightedOrders += row.totalOrders;
    bucket.totalPromotionFees += row.totalPromotionFees;
    bucket.totalPromotionSales += row.totalPromotionSales;
    bucket.totalAdFees += row.totalAdFees;
    bucket.totalAdSales += row.totalAdSales;
  }

  const pivot = [...pivotMap.values()].sort((a, b) =>
    normalizedGranularityKey(a.granularity).localeCompare(normalizedGranularityKey(b.granularity)),
  );

  return { summary, pivot, fileLabel: dataset.fileLabel };
}

export function buildCombinedRows(financialPivot, marketingPivot, salesPivot) {
  const rowsByKey = new Map();

  for (const row of financialPivot) {
    rowsByKey.set(row.date, {
      key: row.date,
      label: row.date,
      financial: row,
      marketing: null,
      sales: null,
    });
  }

  for (const row of marketingPivot) {
    const existing = rowsByKey.get(row.date) || {
      key: row.date,
      label: row.date,
      financial: null,
      marketing: null,
      sales: null,
    };
    existing.marketing = row;
    rowsByKey.set(row.date, existing);
  }

  for (const row of salesPivot) {
    const key = normalizedGranularityKey(row.granularity);
    const existing = rowsByKey.get(key) || {
      key,
      label: row.granularity,
      financial: null,
      marketing: null,
      sales: null,
    };
    existing.sales = row;
    if (!existing.label || existing.label === key) existing.label = row.granularity;
    rowsByKey.set(key, existing);
  }

  return [...rowsByKey.values()]
    .sort((a, b) => a.key.localeCompare(b.key))
    .map((row) => {
      const fin = row.financial;
      const mkt = row.marketing;
      const sales = row.sales;
      const aov = sales
        ? weightedAverage(sales.aovWeightedSales, sales.aovWeightedOrders)
        : null;
      return {
        label: row.label,
        finSubtotal: fin?.subtotal ?? null,
        finMktFees: fin?.marketingFees ?? null,
        finCustDisc: fin?.customerDiscounts ?? null,
        finOrders: fin?.orderIds?.size ?? null,
        mktSales: mkt?.sales ?? null,
        mktOrders: mkt?.orders ?? null,
        salesGross: sales?.grossSales ?? null,
        salesOrders: sales?.totalOrders ?? null,
        salesAov: aov,
        salesPromoFees: sales?.totalPromotionFees ?? null,
        salesPromoSales: sales?.totalPromotionSales ?? null,
        salesAdFees: sales?.totalAdFees ?? null,
        salesAdSales: sales?.totalAdSales ?? null,
      };
    });
}

export function buildMarketingBreakdownAnalysis({ financial, marketing, sales }) {
  const parts = [];
  if (financial) parts.push(`Financial: ${financial.fileLabel}`);
  if (marketing) parts.push(`Marketing: ${marketing.fileLabel}`);
  if (sales) parts.push(`Sales: ${sales.fileLabel}`);
  return {
    financial,
    marketing,
    sales,
    statusMessage: parts.join(' · ') || 'No datasets loaded',
  };
}

export async function fetchDefaultBreakdownDatasets() {
  const response = await fetch('/api/default-dataset', { cache: 'no-store' });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || 'Failed to load default datasets.');
  }
  const financial = payload.financialDetailed?.csvText
    ? buildFinancialDataset(
        parseCsvToRows(payload.financialDetailed.csvText),
        payload.financialDetailed.relativePath || 'financial (root)',
        'root',
      )
    : null;
  const marketing = payload.marketingPromotion?.csvText
    ? buildMarketingDataset(
        parseCsvToRows(payload.marketingPromotion.csvText),
        payload.marketingPromotion.relativePath || 'marketing (root)',
        'root',
      )
    : null;
  const sales = payload.salesByTimeProductPerformance?.csvText
    ? buildSalesDataset(
        parseCsvToRows(payload.salesByTimeProductPerformance.csvText),
        payload.salesByTimeProductPerformance.relativePath || 'sales (root)',
        'root',
      )
    : null;
  return { financial, marketing, sales };
}

/** RFC-style CSV parse for DoorDash export files. */
export function parseCsvToRows(text) {
  const rows = [];
  let currentRow = [];
  let currentCell = '';
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const nextChar = text[index + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        currentCell += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === ',' && !inQuotes) {
      currentRow.push(currentCell);
      currentCell = '';
      continue;
    }

    if ((char === '\n' || char === '\r') && !inQuotes) {
      if (char === '\r' && nextChar === '\n') index += 1;
      currentRow.push(currentCell);
      currentCell = '';
      if (currentRow.some((cell) => cell.length > 0)) rows.push(currentRow);
      currentRow = [];
      continue;
    }

    currentCell += char;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    currentRow.push(currentCell);
    if (currentRow.some((cell) => cell.length > 0)) rows.push(currentRow);
  }

  if (!rows.length) return [];
  const [headers, ...records] = rows;
  return records.map((record) => {
    const rowObject = {};
    headers.forEach((header, i) => {
      rowObject[header] = record[i] || '';
    });
    return rowObject;
  });
}
