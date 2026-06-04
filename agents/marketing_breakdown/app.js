const folderInput = document.getElementById('folderInput');
const analyzeButton = document.getElementById('analyzeButton');
const sourceLabel = document.getElementById('sourceLabel');
const statusBox = document.getElementById('statusBox');

const financialSummaryGrid = document.getElementById('summaryGrid');
const financialStoreFilter = document.getElementById('storeFilter');
const financialMeta = document.getElementById('financialMeta');

const marketingSummaryGrid = document.getElementById('marketingSummaryGrid');
const campaignFilter = document.getElementById('campaignFilter');
const marketingStoreFilter = document.getElementById('marketingStoreFilter');
const selfServeFilter = document.getElementById('selfServeFilter');
const marketingMeta = document.getElementById('marketingMeta');

const salesSummaryGrid = document.getElementById('salesSummaryGrid');
const salesStoreFilter = document.getElementById('salesStoreFilter');
const salesMeta = document.getElementById('salesMeta');
const combinedMeta = document.getElementById('combinedMeta');
const combinedPivotBody = document.getElementById('combinedPivotBody');

const filePrefixes = {
  financialDetailed: 'FINANCIAL_DETAILED',
  marketingPromotion: 'MARKETING_PROMO',
  salesByTimeProductPerformance: 'SALES_viewByTime_byStoreProductPerformance',
};

const financialColumns = {
  date: 'Timestamp local date',
  orderId: 'DoorDash order ID',
  storeId: 'Merchant store ID',
  subtotal: 'Subtotal',
  marketingFees: 'Marketing fees | (including any applicable taxes)',
  customerDiscounts: 'Customer discounts from marketing | (funded by you)',
};

const marketingColumns = {
  date: 'Date',
  selfServe: 'Is self serve campaign',
  campaignId: 'Campaign ID',
  storeId: 'Store ID',
  orders: 'Orders',
  sales: 'Sales',
  marketingFees: 'Marketing fees | (including any applicable taxes)',
  customerDiscounts: 'Customer discounts from marketing | (Funded by you)',
};

const salesColumns = {
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

let uploadedFiles = [];
let activeAnalysis = null;
let currentPivots = {
  financial: [],
  marketing: [],
  sales: [],
};

folderInput.addEventListener('change', () => {
  uploadedFiles = Array.from(folderInput.files || []);
  const financialMatch = findUploadedFile(uploadedFiles, filePrefixes.financialDetailed);
  const marketingMatch = findUploadedFile(uploadedFiles, filePrefixes.marketingPromotion);
  const salesMatch = findUploadedFile(
    uploadedFiles,
    filePrefixes.salesByTimeProductPerformance
  );

  if (financialMatch && marketingMatch && salesMatch) {
    sourceLabel.textContent =
      `Upload ready: ${financialMatch.webkitRelativePath || financialMatch.name}, ${marketingMatch.webkitRelativePath || marketingMatch.name}, and ${salesMatch.webkitRelativePath || salesMatch.name}`;
    setStatus('Upload detected. Click Analyze to use the uploaded folder.', 'info');
    return;
  }

  sourceLabel.textContent =
    'Upload is missing one or more required files. Root scan will be used for anything not found.';
  setStatus(
    'The selected upload is missing one or more required files: FINANCIAL_DETAILED*, MARKETING_PROMO*, or SALES_viewByTime_byStoreProductPerformance*. The app will fall back to the root scan for missing inputs.',
    'warn'
  );
});

analyzeButton.addEventListener('click', async () => {
  analyzeButton.disabled = true;
  setStatus('Loading data sources...', 'info');

  try {
    activeAnalysis = await loadAnalysis();

    populateSelect(financialStoreFilter, activeAnalysis.financial.storeIds, 'All stores');
    financialStoreFilter.disabled = false;

    populateSelect(campaignFilter, activeAnalysis.marketing.campaignIds, 'All campaigns');
    populateSelect(marketingStoreFilter, activeAnalysis.marketing.storeIds, 'All stores');
    populateSelect(selfServeFilter, activeAnalysis.marketing.selfServeValues, 'All');
    campaignFilter.disabled = false;
    marketingStoreFilter.disabled = false;
    selfServeFilter.disabled = false;

    populateSelect(salesStoreFilter, activeAnalysis.sales.storeNames, 'All stores');
    salesStoreFilter.disabled = false;

    financialStoreFilter.value = 'ALL';
    campaignFilter.value = 'ALL';
    marketingStoreFilter.value = 'ALL';
    selfServeFilter.value = 'ALL';
    salesStoreFilter.value = 'ALL';

    renderFinancial();
    renderMarketing();
    renderSales();
    renderCombinedTable();
    setStatus(activeAnalysis.statusMessage, 'info');
  } catch (error) {
    activeAnalysis = null;
    clearAllResults();
    setStatus(error.message || 'Analysis failed.', 'error');
  } finally {
    analyzeButton.disabled = false;
  }
});

financialStoreFilter.addEventListener('change', () => {
  if (activeAnalysis) {
    renderFinancial();
    renderCombinedTable();
  }
});

campaignFilter.addEventListener('change', () => {
  if (activeAnalysis) {
    renderMarketing();
    renderCombinedTable();
  }
});

marketingStoreFilter.addEventListener('change', () => {
  if (activeAnalysis) {
    renderMarketing();
    renderCombinedTable();
  }
});

selfServeFilter.addEventListener('change', () => {
  if (activeAnalysis) {
    renderMarketing();
    renderCombinedTable();
  }
});

salesStoreFilter.addEventListener('change', () => {
  if (activeAnalysis) {
    renderSales();
    renderCombinedTable();
  }
});

function findUploadedFile(files, prefix) {
  return files.find((file) => file.name.startsWith(prefix) && file.name.endsWith('.csv'));
}

async function loadAnalysis() {
  const uploadedFinancial = findUploadedFile(uploadedFiles, filePrefixes.financialDetailed);
  const uploadedMarketing = findUploadedFile(uploadedFiles, filePrefixes.marketingPromotion);
  const uploadedSales = findUploadedFile(
    uploadedFiles,
    filePrefixes.salesByTimeProductPerformance
  );

  let defaultPayload = null;

  if (!uploadedFinancial || !uploadedMarketing || !uploadedSales) {
    const response = await fetch('/api/default-dataset', { cache: 'no-store' });
    defaultPayload = await response.json();

    if (!response.ok) {
      throw new Error(defaultPayload.error || 'Failed to load the default datasets.');
    }
  }

  const financialDataset = await readDataset(
    uploadedFinancial,
    defaultPayload && defaultPayload.financialDetailed,
    'financialDetailed'
  );
  const marketingDataset = await readDataset(
    uploadedMarketing,
    defaultPayload && defaultPayload.marketingPromotion,
    'marketingPromotion'
  );
  const salesDataset = await readDataset(
    uploadedSales,
    defaultPayload && defaultPayload.salesByTimeProductPerformance,
    'salesByTimeProductPerformance'
  );

  return {
    financial: financialDataset,
    marketing: marketingDataset,
    sales: salesDataset,
    statusMessage:
      `Financial source: ${financialDataset.fileLabel} | Marketing source: ${marketingDataset.fileLabel} | Sales source: ${salesDataset.fileLabel}`,
  };
}

async function readDataset(uploadedFile, fallbackPayload, type) {
  if (uploadedFile) {
    const csvText = await uploadedFile.text();
    return buildDataset(type, csvText, uploadedFile.webkitRelativePath || uploadedFile.name, 'upload');
  }

  if (!fallbackPayload || fallbackPayload.error) {
    throw new Error(
      fallbackPayload && fallbackPayload.error
        ? fallbackPayload.error
        : `Missing ${type} dataset.`
    );
  }

  return buildDataset(type, fallbackPayload.csvText, fallbackPayload.relativePath, 'root');
}

function buildDataset(type, csvText, fileLabel, sourceKind) {
  const rows = parseCSV(csvText);

  if (type === 'financialDetailed') {
    return buildFinancialDataset(rows, fileLabel, sourceKind);
  }

  if (type === 'marketingPromotion') {
    return buildMarketingDataset(rows, fileLabel, sourceKind);
  }

  if (type === 'salesByTimeProductPerformance') {
    return buildSalesDataset(rows, fileLabel, sourceKind);
  }

  throw new Error(`Unsupported dataset type: ${type}`);
}

function buildFinancialDataset(rows, fileLabel, sourceKind) {
  const normalizedRows = rows
    .map((row) => ({
      date: safeTrim(row[financialColumns.date]),
      orderId: safeTrim(row[financialColumns.orderId]),
      storeId: safeTrim(row[financialColumns.storeId]),
      subtotal: parseNumber(row[financialColumns.subtotal]),
      marketingFees: parseNumber(row[financialColumns.marketingFees]),
      customerDiscounts: parseNumber(row[financialColumns.customerDiscounts]),
    }))
    .filter((row) => row.date);

  if (normalizedRows.length === 0) {
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

function buildMarketingDataset(rows, fileLabel, sourceKind) {
  const normalizedRows = rows
    .map((row) => ({
      date: safeTrim(row[marketingColumns.date]),
      campaignId: safeTrim(row[marketingColumns.campaignId]),
      storeId: safeTrim(row[marketingColumns.storeId]),
      selfServe: normalizeSelfServe(row[marketingColumns.selfServe]),
      orders: parseNumber(row[marketingColumns.orders]),
      sales: parseNumber(row[marketingColumns.sales]),
      marketingFees: parseNumber(row[marketingColumns.marketingFees]),
      customerDiscounts: parseNumber(row[marketingColumns.customerDiscounts]),
    }))
    .filter((row) => row.date);

  if (normalizedRows.length === 0) {
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

function buildSalesDataset(rows, fileLabel, sourceKind) {
  const normalizedRows = rows
    .map((row) => ({
      granularity: safeTrim(row[salesColumns.granularity]),
      storeName: safeTrim(row[salesColumns.storeName]),
      grossSales: parseNumber(row[salesColumns.grossSales]),
      totalOrders: parseNumber(row[salesColumns.totalOrders]),
      aov: parseNumber(row[salesColumns.aov]),
      totalPromotionFees: parseNumber(row[salesColumns.totalPromotionFees]),
      totalPromotionSales: parseNumber(row[salesColumns.totalPromotionSales]),
      totalAdFees: parseNumber(row[salesColumns.totalAdFees]),
      totalAdSales: parseNumber(row[salesColumns.totalAdSales]),
    }))
    .filter((row) => row.granularity);

  if (normalizedRows.length === 0) {
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

function renderFinancial() {
  const storeId = financialStoreFilter.value || 'ALL';
  const rows =
    storeId === 'ALL'
      ? activeAnalysis.financial.rows
      : activeAnalysis.financial.rows.filter((row) => row.storeId === storeId);

  financialMeta.textContent = `Source: ${activeAnalysis.financial.fileLabel}`;

  const uniqueOrders = new Set();
  let subtotal = 0;
  let marketingFees = 0;
  let customerDiscounts = 0;

  for (const row of rows) {
    subtotal += row.subtotal;
    marketingFees += row.marketingFees;
    customerDiscounts += row.customerDiscounts;
    if (row.orderId) {
      uniqueOrders.add(row.orderId);
    }
  }

  renderSummaryCards(financialSummaryGrid, [
    ['Date range', `${activeAnalysis.financial.minDate} to ${activeAnalysis.financial.maxDate}`],
    ['Store filter', storeId === 'ALL' ? 'All stores' : storeId],
    ['Subtotal', formatCurrency(subtotal)],
    ['Marketing fees', formatCurrency(marketingFees)],
    ['Customer discounts', formatCurrency(customerDiscounts)],
    ['Unique orders', formatInteger(uniqueOrders.size)],
  ]);

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
    if (row.orderId) {
      bucket.orderIds.add(row.orderId);
    }
  }

  currentPivots.financial = [...pivotMap.values()].sort((left, right) =>
    left.date.localeCompare(right.date)
  );
}

function renderMarketing() {
  const selectedCampaign = campaignFilter.value || 'ALL';
  const selectedStore = marketingStoreFilter.value || 'ALL';
  const selectedSelfServe = selfServeFilter.value || 'ALL';

  const rows = activeAnalysis.marketing.rows.filter((row) => {
    if (selectedCampaign !== 'ALL' && row.campaignId !== selectedCampaign) {
      return false;
    }
    if (selectedStore !== 'ALL' && row.storeId !== selectedStore) {
      return false;
    }
    if (selectedSelfServe !== 'ALL' && row.selfServe !== selectedSelfServe) {
      return false;
    }
    return true;
  });

  marketingMeta.textContent = `Source: ${activeAnalysis.marketing.fileLabel}`;

  let sales = 0;
  let orders = 0;
  let marketingFees = 0;
  let customerDiscounts = 0;

  for (const row of rows) {
    sales += row.sales;
    orders += row.orders;
    marketingFees += row.marketingFees;
    customerDiscounts += row.customerDiscounts;
  }

  renderSummaryCards(marketingSummaryGrid, [
    ['Date range', `${activeAnalysis.marketing.minDate} to ${activeAnalysis.marketing.maxDate}`],
    ['Campaign filter', selectedCampaign === 'ALL' ? 'All campaigns' : selectedCampaign],
    ['Store filter', selectedStore === 'ALL' ? 'All stores' : selectedStore],
    ['Self serve filter', selectedSelfServe === 'ALL' ? 'All' : selectedSelfServe],
    ['Sales', formatCurrency(sales)],
    ['Orders', formatInteger(orders)],
    ['Marketing fees', formatCurrency(marketingFees)],
    ['Customer discounts', formatCurrency(customerDiscounts)],
  ]);

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

  currentPivots.marketing = [...pivotMap.values()].sort((left, right) =>
    left.date.localeCompare(right.date)
  );
}

function renderSales() {
  const selectedStore = salesStoreFilter.value || 'ALL';
  const rows =
    selectedStore === 'ALL'
      ? activeAnalysis.sales.rows
      : activeAnalysis.sales.rows.filter((row) => row.storeName === selectedStore);

  salesMeta.textContent = `Source: ${activeAnalysis.sales.fileLabel}`;

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

  renderSummaryCards(salesSummaryGrid, [
    ['Store filter', selectedStore === 'ALL' ? 'All stores' : selectedStore],
    ['Granularity rows', formatInteger(activeAnalysis.sales.granularityCount)],
    ['Gross sales', formatCurrency(grossSales)],
    ['Orders incl. cancelled', formatInteger(totalOrders)],
    ['Promotion fees', formatCurrency(totalPromotionFees)],
    ['Promotion sales', formatCurrency(totalPromotionSales)],
    ['Ad fees', formatCurrency(totalAdFees)],
    ['Ad sales', formatCurrency(totalAdSales)],
  ]);

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

  currentPivots.sales = [...pivotMap.values()].sort((left, right) =>
    normalizedGranularityKey(left.granularity).localeCompare(
      normalizedGranularityKey(right.granularity)
    )
  );
}

function renderSummaryCards(target, cards) {
  target.innerHTML = cards
    .map(
      ([label, value]) =>
        `<article class="summary-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(
          value
        )}</strong></article>`
    )
    .join('');
}

function renderTable(target, rows, renderRow, emptyColspan = 5) {
  if (rows.length === 0) {
    target.innerHTML =
      `<tr><td colspan="${emptyColspan}" class="empty-state">No rows matched the selected filters.</td></tr>`;
    return;
  }

  target.innerHTML = rows.map(renderRow).join('');
}

function renderCombinedTable() {
  const rowsByKey = new Map();

  for (const row of currentPivots.financial) {
    rowsByKey.set(row.date, {
      key: row.date,
      label: row.date,
      financial: row,
      marketing: null,
      sales: null,
    });
  }

  for (const row of currentPivots.marketing) {
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

  for (const row of currentPivots.sales) {
    const key = normalizedGranularityKey(row.granularity);
    const existing = rowsByKey.get(key) || {
      key,
      label: row.granularity,
      financial: null,
      marketing: null,
      sales: null,
    };
    existing.sales = row;
    if (!existing.label || existing.label === key) {
      existing.label = row.granularity;
    }
    rowsByKey.set(key, existing);
  }

  const combinedRows = [...rowsByKey.values()].sort((left, right) =>
    left.key.localeCompare(right.key)
  );

  combinedMeta.textContent =
    'Rows are merged by date. Sales granularity values are mapped into the same timeline where possible.';

  renderTable(
    combinedPivotBody,
    combinedRows,
    (row) => `
      <tr>
        <td>${escapeHtml(row.label)}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.financial && row.financial.subtotal))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.financial && row.financial.marketingFees))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.financial && row.financial.customerDiscounts))}</td>
        <td class="numeric">${escapeHtml(formatNullableInteger(row.financial && row.financial.orderIds && row.financial.orderIds.size))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.marketing && row.marketing.sales))}</td>
        <td class="numeric">${escapeHtml(formatNullableInteger(row.marketing && row.marketing.orders))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.marketing && row.marketing.marketingFees))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.marketing && row.marketing.customerDiscounts))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.sales && row.sales.grossSales))}</td>
        <td class="numeric">${escapeHtml(formatNullableInteger(row.sales && row.sales.totalOrders))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.sales ? weightedAverage(row.sales.aovWeightedSales, row.sales.aovWeightedOrders) : null))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.sales && row.sales.totalPromotionFees))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.sales && row.sales.totalPromotionSales))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.sales && row.sales.totalAdFees))}</td>
        <td class="numeric">${escapeHtml(formatNullableCurrency(row.sales && row.sales.totalAdSales))}</td>
      </tr>
    `,
    16
  );
}

function populateSelect(select, values, allLabel) {
  select.innerHTML = ['<option value="ALL">', escapeHtml(allLabel), '</option>']
    .join('');

  const options = [`<option value="ALL">${escapeHtml(allLabel)}</option>`]
    .concat(
      values.map(
        (value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`
      )
    )
    .join('');

  select.innerHTML = options;
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

function normalizeSelfServe(value) {
  const normalized = safeTrim(String(value || '')).toLowerCase();
  if (!normalized) {
    return '';
  }
  return normalized === 'true' ? 'true' : 'false';
}

function clearAllResults() {
  financialSummaryGrid.innerHTML = '';
  marketingSummaryGrid.innerHTML = '';
  salesSummaryGrid.innerHTML = '';
  financialMeta.textContent = 'Waiting for analysis.';
  marketingMeta.textContent = 'Waiting for analysis.';
  salesMeta.textContent = 'Waiting for analysis.';
  combinedMeta.textContent =
    'Financial, marketing, and sales rows will be merged here after analysis.';
  currentPivots = { financial: [], marketing: [], sales: [] };
  combinedPivotBody.innerHTML =
    '<tr><td colspan="16" class="empty-state">No analysis yet.</td></tr>';

  disableFilter(financialStoreFilter, 'All stores');
  disableFilter(campaignFilter, 'All campaigns');
  disableFilter(marketingStoreFilter, 'All stores');
  disableFilter(selfServeFilter, 'All');
  disableFilter(salesStoreFilter, 'All stores');
}

function disableFilter(select, allLabel) {
  select.disabled = true;
  select.innerHTML = `<option value="ALL">${escapeHtml(allLabel)}</option>`;
}

function weightedAverage(total, weight) {
  if (!weight) {
    return 0;
  }
  return total / weight;
}

function normalizedGranularityKey(value) {
  const trimmed = safeTrim(value);
  if (trimmed.startsWith('Day of ')) {
    return trimmed.slice(7);
  }
  return trimmed;
}

function formatNullableCurrency(value) {
  return typeof value === 'number' && Number.isFinite(value) ? formatCurrency(value) : '—';
}

function formatNullableInteger(value) {
  return typeof value === 'number' && Number.isFinite(value) ? formatInteger(value) : '—';
}

function setStatus(message, tone) {
  statusBox.textContent = message;
  statusBox.className = `status-box status-${tone}`;
}

function parseNumber(value) {
  const raw = safeTrim(value);
  if (!raw) {
    return 0;
  }
  return Number(raw.replaceAll(',', '')) || 0;
}

function safeTrim(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function formatCurrency(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value);
}

function formatInteger(value) {
  return new Intl.NumberFormat('en-US').format(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function parseCSV(text) {
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
      if (char === '\r' && nextChar === '\n') {
        index += 1;
      }

      currentRow.push(currentCell);
      currentCell = '';

      if (currentRow.some((cell) => cell.length > 0)) {
        rows.push(currentRow);
      }

      currentRow = [];
      continue;
    }

    currentCell += char;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    currentRow.push(currentCell);
    if (currentRow.some((cell) => cell.length > 0)) {
      rows.push(currentRow);
    }
  }

  if (rows.length === 0) {
    return [];
  }

  const [headers, ...records] = rows;

  return records.map((record) => {
    const rowObject = {};
    headers.forEach((header, index) => {
      rowObject[header] = record[index] || '';
    });
    return rowObject;
  });
}
