import { safeDivide, round, growthPct } from '../utils/safeMath';
import { filterByDateRange, filterExcludedDates, groupBy } from './aggregator';
import { classifyOrder, sumPromoDiscountsFromRows } from './buckets';

export function decomposeSalesChange(preOrders, postOrders, preAov, postAov) {
  const ordersEffect = (postOrders - preOrders) * preAov;
  const aovEffect = (postAov - preAov) * postOrders;
  return { ordersEffect: round(ordersEffect), aovEffect: round(aovEffect) };
}

export function decomposePayoutChange(preSales, postSales, preMargin, postMargin) {
  const salesEffect = (postSales - preSales) * preMargin;
  const marginEffect = (postMargin - preMargin) * postSales;
  return { salesEffect: round(salesEffect), marginEffect: round(marginEffect) };
}

export function detectExceptions(summary) {
  const exceptions = [];
  const pre = summary.find(r => r.metric === 'sales');
  const postSales = pre?.post || 0;
  const preSales = pre?.pre || 0;
  const payRow = summary.find(r => r.metric === 'payouts');
  const ordRow = summary.find(r => r.metric === 'orders');
  const aovRow = summary.find(r => r.metric === 'aov');

  if (postSales < preSales && pre?.prevspost < 0) {
    exceptions.push({ type: 'warning', metric: 'Sales', message: 'Sales declined Pre vs Post' });
  }
  if (postSales > preSales && payRow && payRow.post < payRow.pre) {
    exceptions.push({ type: 'warning', metric: 'Payouts', message: 'Sales up but payouts down — margin compression' });
  }
  if (ordRow && ordRow.post > ordRow.pre && aovRow && aovRow.post < aovRow.pre) {
    exceptions.push({ type: 'info', metric: 'AOV', message: 'Orders up but AOV down — ticket dilution' });
  }
  return exceptions;
}

export function buildSalesWaterfall(summary) {
  const salesRow = summary.find(r => r.metric === 'sales');
  const ordersRow = summary.find(r => r.metric === 'orders');
  const aovRow = summary.find(r => r.metric === 'aov');
  if (!salesRow || !ordersRow || !aovRow) return [];

  const { ordersEffect, aovEffect } = decomposeSalesChange(
    ordersRow.pre, ordersRow.post, aovRow.pre, aovRow.post
  );

  return [
    { label: 'Pre Sales', value: salesRow.pre, type: 'start' },
    { label: 'Order Volume', value: ordersEffect, type: ordersEffect >= 0 ? 'pos' : 'neg' },
    { label: 'AOV Change', value: aovEffect, type: aovEffect >= 0 ? 'pos' : 'neg' },
    { label: 'Post Sales', value: salesRow.post, type: 'end' },
  ];
}

export function buildRevenueGrowthDrivers(summary) {
  const salesRow = summary.find(r => r.metric === 'sales');
  const ordersRow = summary.find(r => r.metric === 'orders');
  const aovRow = summary.find(r => r.metric === 'aov');
  if (!salesRow || !ordersRow || !aovRow) return [];

  const preSales = salesRow.pre || 0;
  const postSales = salesRow.post || 0;
  const change = postSales - preSales;
  const orderEffect = (ordersRow.post - ordersRow.pre) * aovRow.pre;
  const aovEffect = ordersRow.post * (aovRow.post - aovRow.pre);

  return [
    {
      driver: 'Order volume effect',
      formula: '(Post Orders - Pre Orders) × Pre AOV',
      value: round(orderEffect),
      contributionPct: round(safeDivide(orderEffect, change) * 100),
    },
    {
      driver: 'AOV / basket effect',
      formula: 'Post Orders × (Post AOV - Pre AOV)',
      value: round(aovEffect),
      contributionPct: round(safeDivide(aovEffect, change) * 100),
    },
    {
      driver: 'Total sales change',
      formula: 'Post Sales - Pre Sales',
      value: round(change),
      contributionPct: 100,
    },
  ];
}

function buildDdOrderLevel(ddFinancial, start, end, excludedDates = []) {
  let rows = filterByDateRange(ddFinancial || [], 'date', start, end);
  rows = filterExcludedDates(rows, 'date', excludedDates);
  rows = rows.filter(r => !r.transactionType || r.transactionType === 'Order');

  const orderGroups = groupBy(rows, 'orderId');
  const orders = [];
  for (const [orderId, orderRows] of orderGroups) {
    if (!orderId) continue;
    const subtotal = orderRows.reduce((s, r) => s + (r.subtotal || 0), 0);
    const netTotal = orderRows.reduce((s, r) => s + (r.netTotal || 0), 0);
    const marketingFees = orderRows.reduce((s, r) => s + Math.abs(r.marketingFees || 0), 0);
    const customerDiscounts = sumPromoDiscountsFromRows(orderRows);
    orders.push({
      orderId,
      storeId: orderRows[0]?.storeId,
      subtotal,
      netTotal,
      marketingFees,
      customerDiscounts,
      orderType: classifyOrder(marketingFees, customerDiscounts),
    });
  }
  return orders;
}

export function buildOrderOriginAov(ddFinancial, config) {
  if (!ddFinancial || !config?.ddPostStart || !config?.ddPostEnd) return [];
  const orders = buildDdOrderLevel(ddFinancial, config.ddPostStart, config.ddPostEnd, config.ddExcludedDates || []);
  const groups = {
    organic: { label: 'Organic', rows: [] },
    promo: { label: 'Promo Driven', rows: [] },
    ads: { label: 'Ads Driven', rows: [] },
    promo_ads: { label: 'Both Driven', rows: [] },
  };
  for (const order of orders) groups[order.orderType]?.rows.push(order);

  const totalOrders = orders.length || 1;
  const totalSales = orders.reduce((s, r) => s + r.subtotal, 0) || 1;

  return Object.entries(groups).map(([id, group]) => {
    const sales = group.rows.reduce((s, r) => s + r.subtotal, 0);
    const orderCount = group.rows.length;
    return {
      id,
      segment: group.label,
      orders: orderCount,
      orderSharePct: round(safeDivide(orderCount, totalOrders) * 100),
      sales: round(sales),
      salesSharePct: round(safeDivide(sales, totalSales) * 100),
      aov: round(safeDivide(sales, orderCount), 2),
    };
  });
}

const BRIDGE_COMPONENTS = [
  { step: 'Marketing fees', type: 'cost', ownership: 'Controllable - ads', field: 'marketingFees' },
  { step: 'Customer discounts funded by you', type: 'cost', ownership: 'Controllable - promo', field: 'merchantDiscounts' },
  { step: 'Customer discounts funded by third party', type: 'cost', ownership: 'External funding discount', field: 'thirdPartyDiscounts' },
  { step: 'Customer discounts funded by DoorDash', type: 'cost', ownership: 'Platform-funded discount', field: 'ddDiscounts' },
  { step: 'Third-party contribution', type: 'credit', ownership: 'External credit', field: 'thirdPartyContribution' },
  { step: 'DoorDash marketing credit', type: 'credit', ownership: 'Platform credit', field: 'ddMarketingCredit' },
  { step: 'Adjustments', type: 'credit', ownership: 'Operational adjustment', field: 'adjustments' },
  { step: 'Commission', type: 'cost', ownership: 'Platform fee', field: 'commission' },
  { step: 'Error charges', type: 'cost', ownership: 'Controllable - operations', field: 'errorCharges' },
  { step: 'Payment processing fee', type: 'cost', ownership: 'Processing fee', field: 'paymentProcessing' },
];

function bridgeEffectLabel(type) {
  if (type === 'start') return 'Start — gross sales (subtotal) before deductions.';
  if (type === 'cost') return 'Subtract — reduces running payout (fee or discount).';
  if (type === 'credit') return 'Add — increases running payout (credit or adjustment).';
  if (type === 'end') return 'Result — balance after all steps (calculated payout).';
  if (type === 'actual') return 'Check — net total as reported in the detailed export.';
  if (type === 'variance') return 'Gap — actual minus calculated (rounding / timing).';
  return '—';
}

/** Per-period summed inputs for the DoorDash payout walk (line-level financial rows). */
export function computePayoutBridgeSums(rows) {
  if (!rows?.length) return null;
  const sum = (field, absolute = true) => rows.reduce((s, r) => {
    const value = Number(r[field] || 0);
    return s + (absolute ? Math.abs(value) : value);
  }, 0);
  return {
    subtotal: sum('subtotal', false),
    marketingFees: sum('marketingFees'),
    merchantDiscounts: sum('customerDiscounts'),
    thirdPartyDiscounts: sum('customerDiscountsThirdParty'),
    ddDiscounts: sum('customerDiscountsDoorDash'),
    thirdPartyContribution: sum('thirdPartyContribution'),
    ddMarketingCredit: sum('ddMarketingCredit'),
    adjustments: sum('adjustments'),
    commission: sum('commission'),
    errorCharges: sum('errorCharges'),
    paymentProcessing: sum('paymentProcessingFee'),
    netTotal: sum('netTotal', false),
  };
}

function emptyPayoutSums() {
  return {
    subtotal: 0,
    marketingFees: 0,
    merchantDiscounts: 0,
    thirdPartyDiscounts: 0,
    ddDiscounts: 0,
    thirdPartyContribution: 0,
    ddMarketingCredit: 0,
    adjustments: 0,
    commission: 0,
    errorCharges: 0,
    paymentProcessing: 0,
    netTotal: 0,
  };
}

/** One period: `value` = line magnitude; `running` = payout balance after applying that line (costs subtract, credits add). */
export function buildPayoutBridgeStepsFromSums(sums) {
  if (!sums) return [];
  const sales = sums.subtotal;
  const steps = [];
  steps.push({
    step: 'Subtotal / Sales',
    type: 'start',
    ownership: 'Revenue',
    value: round(sales),
    running: round(sales),
    effectLabel: bridgeEffectLabel('start'),
  });
  let running = sales;
  for (const c of BRIDGE_COMPONENTS) {
    const v = round(Math.abs(sums[c.field]));
    running += c.type === 'credit' ? v : -v;
    steps.push({
      step: c.step,
      type: c.type,
      ownership: c.ownership,
      value: v,
      running: round(running),
      effectLabel: bridgeEffectLabel(c.type),
    });
  }
  steps.push({
    step: 'Calculated Net Total / Payouts',
    type: 'end',
    ownership: 'Payout',
    value: round(running),
    running: round(running),
    effectLabel: bridgeEffectLabel('end'),
  });
  const actual = round(sums.netTotal);
  steps.push({
    step: 'Actual Net Total in file',
    type: 'actual',
    ownership: 'Validation',
    value: actual,
    running: actual,
    effectLabel: bridgeEffectLabel('actual'),
  });
  steps.push({
    step: 'Formula variance',
    type: 'variance',
    ownership: 'Validation',
    value: round(actual - running),
    running: round(actual - running),
    effectLabel: bridgeEffectLabel('variance'),
  });
  return steps;
}

/** Post-period funnel only (used where a single period is enough). */
export function buildPayoutBridge(ddFinancial, config) {
  if (!ddFinancial || !config?.ddPostStart || !config?.ddPostEnd) return [];
  let rows = filterByDateRange(ddFinancial, 'date', config.ddPostStart, config.ddPostEnd);
  rows = filterExcludedDates(rows, 'date', config.ddExcludedDates || []);
  const sums = computePayoutBridgeSums(rows);
  return sums ? buildPayoutBridgeStepsFromSums(sums) : [];
}

/**
 * Pre vs Post: Post columns stay `value` / `running`; add `valuePre`, `runningPre`, `valueDelta`, `valueDeltaPct`.
 * Costs use positive magnitudes and are subtracted from the running balance; credits are added.
 */
export function buildPayoutBridgePrePost(ddFinancial, config) {
  if (!ddFinancial || !config?.ddPostStart || !config?.ddPostEnd) {
    return { hasPre: false, rows: [] };
  }
  const ex = config.ddExcludedDates || [];
  let postRows = filterByDateRange(ddFinancial, 'date', config.ddPostStart, config.ddPostEnd);
  postRows = filterExcludedDates(postRows, 'date', ex);
  const postSums = computePayoutBridgeSums(postRows);
  if (!postSums) return { hasPre: false, rows: [] };

  const postSteps = buildPayoutBridgeStepsFromSums(postSums);

  const hasPreWindow = !!(config.ddPreStart && config.ddPreEnd);
  let preRows = [];
  if (hasPreWindow) {
    preRows = filterByDateRange(ddFinancial, 'date', config.ddPreStart, config.ddPreEnd);
    preRows = filterExcludedDates(preRows, 'date', ex);
  }
  const hasPreData = hasPreWindow && preRows.length > 0;

  if (!hasPreData) {
    return {
      hasPre: false,
      rows: postSteps.map((postRow) => ({
        ...postRow,
        valuePre: null,
        runningPre: null,
        valueDelta: null,
        valueDeltaPct: null,
      })),
    };
  }

  const preSums = computePayoutBridgeSums(preRows);
  const preSteps = preSums ? buildPayoutBridgeStepsFromSums(preSums) : buildPayoutBridgeStepsFromSums(emptyPayoutSums());
  const rows = preSteps.map((preRow, i) => {
    const postRow = postSteps[i];
    const pv = preRow.value;
    const pqv = postRow.value;
    const dv = round(pqv - pv);
    const dPctRaw = growthPct(pv, pqv);
    const dPct = Number.isFinite(dPctRaw) ? round(dPctRaw, 1) : null;
    return {
      ...postRow,
      valuePre: pv,
      runningPre: preRow.running,
      valueDelta: dv,
      valueDeltaPct: dPct,
    };
  });
  return { hasPre: true, rows };
}

export function computePercentileRanking(storeData, metricField) {
  const sorted = [...storeData].sort((a, b) => (a[metricField] || 0) - (b[metricField] || 0));
  const n = sorted.length;
  return sorted.map((store, i) => ({
    ...store,
    [`${metricField}_percentile`]: n > 1 ? round((i / (n - 1)) * 100) : 50,
  }));
}

export function getTopMovers(storeData, count = 5) {
  const sorted = [...storeData].sort((a, b) => (b.sales_growth_pct || 0) - (a.sales_growth_pct || 0));
  return {
    up: sorted.slice(0, count),
    down: sorted.slice(-count).reverse(),
  };
}
