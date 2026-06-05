import { safeDivide, round, cleanInfinity } from '../utils/safeMath';
import { getDominantStorePlatform } from '../utils/storeMeta';

function windowMktSpend(row, window) {
  if (row[`${window}_marketplaceFee`] !== undefined || row[`${window}_offers`] !== undefined) {
    return round(
      Math.abs(row[`${window}_marketplaceFee`] || 0) + Math.abs(row[`${window}_offers`] || 0),
    );
  }
  return round(
    Math.abs(row[`${window}_marketingFees`] || 0)
      + Math.abs(row[`${window}_customerDiscounts`] || 0)
      + Math.abs(row[`${window}_customerDiscountsDoorDash`] || 0)
      + Math.abs(row[`${window}_customerDiscountsThirdParty`] || 0),
  );
}

export function addDerivedMetrics(storeData) {
  return storeData.map(store => {
    const r = { ...store };

    for (const metric of ['sales', 'payouts', 'orders']) {
      const pre = r[`pre_${metric}`] || 0;
      const post = r[`post_${metric}`] || 0;
      const preLY = r[`preLY_${metric}`] || 0;
      const postLY = r[`postLY_${metric}`] || 0;

      r[`${metric}_prevspost`] = round(post - pre);
      r[`${metric}_ly_prevspost`] = round(postLY - preLY);
      r[`${metric}_yoy`] = round(post - postLY);
      r[`${metric}_growth_pct`] = round(cleanInfinity(safeDivide(post - pre, pre) * 100));
      r[`${metric}_ly_growth_pct`] = round(cleanInfinity(safeDivide(postLY - preLY, preLY) * 100));
      r[`${metric}_yoy_pct`] = round(cleanInfinity(safeDivide(post - postLY, postLY) * 100));
    }

    for (const w of ['pre', 'post', 'preLY', 'postLY']) {
      r[`${w}_aov`] = round(safeDivide(r[`${w}_sales`], r[`${w}_orders`]), 2);
      r[`${w}_avg_payout`] = round(safeDivide(r[`${w}_payouts`], r[`${w}_orders`]), 2);
      r[`${w}_mktSpend`] = windowMktSpend(r, w);
      r[`${w}_profitability`] = round(safeDivide(r[`${w}_payouts`], r[`${w}_sales`]) * 100);
    }

    r.aov_prevspost = round(r.post_aov - r.pre_aov, 2);
    r.aov_ly_prevspost = round(r.postLY_aov - r.preLY_aov, 2);
    r.aov_growth_pct = round(cleanInfinity(safeDivide(r.aov_prevspost, r.pre_aov) * 100));
    r.aov_ly_growth_pct = round(cleanInfinity(safeDivide(r.aov_ly_prevspost, r.preLY_aov) * 100));
    r.aov_yoy = round(r.post_aov - r.postLY_aov, 2);
    r.aov_yoy_pct = round(cleanInfinity(safeDivide(r.aov_yoy, r.postLY_aov) * 100));

    r.avg_payout_prevspost = round(r.post_avg_payout - r.pre_avg_payout, 2);
    r.avg_payout_ly_prevspost = round(r.postLY_avg_payout - r.preLY_avg_payout, 2);
    r.avg_payout_growth_pct = round(cleanInfinity(safeDivide(r.avg_payout_prevspost, r.pre_avg_payout) * 100));
    r.avg_payout_ly_growth_pct = round(cleanInfinity(safeDivide(r.avg_payout_ly_prevspost, r.preLY_avg_payout) * 100));
    r.avg_payout_yoy = round(r.post_avg_payout - r.postLY_avg_payout, 2);
    r.avg_payout_yoy_pct = round(cleanInfinity(safeDivide(r.avg_payout_yoy, r.postLY_avg_payout) * 100));

    r.prof_prevspost = round(r.post_profitability - r.pre_profitability);
    r.prof_ly_prevspost = round(r.postLY_profitability - r.preLY_profitability);
    r.prof_growth_pct = round(cleanInfinity(safeDivide(r.prof_prevspost, r.pre_profitability) * 100));
    r.prof_ly_growth_pct = round(cleanInfinity(safeDivide(r.prof_ly_prevspost, r.preLY_profitability) * 100));
    r.prof_yoy = round(r.post_profitability - r.postLY_profitability);
    r.prof_yoy_pct = round(cleanInfinity(safeDivide(r.prof_yoy, r.postLY_profitability) * 100));

    return r;
  });
}

export function buildSummaryRow(storeData, metricName) {
  const totals = {};
  for (const w of ['pre', 'post', 'preLY', 'postLY']) {
    totals[w] = storeData.reduce((s, r) => s + (r[`${w}_${metricName}`] || 0), 0);
  }
  const prevspost = totals.post - totals.pre;
  const lyPrevspost = totals.postLY - totals.preLY;
  const yoy = totals.post - totals.postLY;
  return {
    metric: metricName,
    pre: round(totals.pre),
    post: round(totals.post),
    preLY: round(totals.preLY),
    postLY: round(totals.postLY),
    prevspost: round(prevspost),
    lyPrevspost: round(lyPrevspost),
    yoy: round(yoy),
    growthPct: round(cleanInfinity(safeDivide(prevspost, totals.pre) * 100)),
    lyGrowthPct: round(cleanInfinity(safeDivide(lyPrevspost, totals.preLY) * 100)),
    yoyPct: round(cleanInfinity(safeDivide(yoy, totals.postLY) * 100)),
  };
}

function buildDerivedSummaryRow(storeData, type) {
  const sales = buildSummaryRow(storeData, 'sales');
  const payouts = buildSummaryRow(storeData, 'payouts');
  const orders = buildSummaryRow(storeData, 'orders');
  return buildDerivedFromRows(sales, payouts, orders, type);
}

function buildDerivedFromRows(sales, payouts, orders, type) {
  if (type === 'profitability') {
    const calc = (p, s) => round(safeDivide(p, s) * 100);
    const pre = calc(payouts.pre, sales.pre);
    const post = calc(payouts.post, sales.post);
    const preLY = calc(payouts.preLY, sales.preLY);
    const postLY = calc(payouts.postLY, sales.postLY);
    const prevspost = round(post - pre);
    const lyPrevspost = round(postLY - preLY);
    const yoy = round(post - postLY);
    return {
      metric: 'profitability', pre, post, preLY, postLY,
      prevspost, lyPrevspost, yoy,
      growthPct: round(cleanInfinity(safeDivide(prevspost, pre) * 100)),
      lyGrowthPct: round(cleanInfinity(safeDivide(lyPrevspost, preLY) * 100)),
      yoyPct: round(cleanInfinity(safeDivide(yoy, postLY) * 100)),
    };
  }
  if (type === 'aov') {
    const calc = (s, o) => round(safeDivide(s, o), 2);
    const pre = calc(sales.pre, orders.pre);
    const post = calc(sales.post, orders.post);
    const preLY = calc(sales.preLY, orders.preLY);
    const postLY = calc(sales.postLY, orders.postLY);
    const prevspost = round(post - pre, 2);
    const lyPrevspost = round(postLY - preLY, 2);
    const yoy = round(post - postLY, 2);
    return {
      metric: 'aov', pre, post, preLY, postLY,
      prevspost, lyPrevspost, yoy,
      growthPct: round(cleanInfinity(safeDivide(prevspost, pre) * 100)),
      lyGrowthPct: round(cleanInfinity(safeDivide(lyPrevspost, preLY) * 100)),
      yoyPct: round(cleanInfinity(safeDivide(yoy, postLY) * 100)),
    };
  }
  return null;
}

function combineSummaryRows(dd, ue, metric) {
  const row = { metric };
  for (const key of ['pre', 'post', 'preLY', 'postLY']) {
    row[key] = (dd[key] || 0) + (ue[key] || 0);
  }
  row.prevspost = row.post - row.pre;
  row.lyPrevspost = row.postLY - row.preLY;
  row.yoy = row.post - row.postLY;
  row.growthPct = round(cleanInfinity(safeDivide(row.prevspost, row.pre) * 100));
  row.lyGrowthPct = round(cleanInfinity(safeDivide(row.lyPrevspost, row.preLY) * 100));
  row.yoyPct = round(cleanInfinity(safeDivide(row.yoy, row.postLY) * 100));
  return row;
}

export function buildSummaryTables(ddStoreData, ueStoreData) {
  const metrics = ['sales', 'payouts', 'orders'];

  const dd = [
    ...metrics.map(m => buildSummaryRow(ddStoreData || [], m)),
    buildDerivedSummaryRow(ddStoreData || [], 'profitability'),
    buildDerivedSummaryRow(ddStoreData || [], 'aov'),
  ].filter(Boolean);

  const ue = [
    ...metrics.map(m => buildSummaryRow(ueStoreData || [], m)),
    buildDerivedSummaryRow(ueStoreData || [], 'profitability'),
    buildDerivedSummaryRow(ueStoreData || [], 'aov'),
  ].filter(Boolean);

  const combined = metrics.map(m => {
    const ddRow = dd.find(r => r.metric === m) || { pre: 0, post: 0, preLY: 0, postLY: 0 };
    const ueRow = ue.find(r => r.metric === m) || { pre: 0, post: 0, preLY: 0, postLY: 0 };
    return combineSummaryRows(ddRow, ueRow, m);
  });

  const cSales = combined.find(r => r.metric === 'sales');
  const cPayouts = combined.find(r => r.metric === 'payouts');
  const cOrders = combined.find(r => r.metric === 'orders');
  if (cSales && cPayouts && cOrders) {
    const prof = buildDerivedFromRows(cSales, cPayouts, cOrders, 'profitability');
    const aov = buildDerivedFromRows(cSales, cPayouts, cOrders, 'aov');
    if (prof) combined.push(prof);
    if (aov) combined.push(aov);
  }

  return { dd, ue, combined };
}

function sumStoreMetricRows(rows) {
  if (!rows?.length) return null;
  const metrics = ['sales', 'payouts', 'orders'];
  const windows = ['pre', 'post', 'preLY', 'postLY'];
  const base = { storeId: rows[0].storeId };
  for (const w of windows) {
    for (const m of metrics) {
      const k = `${w}_${m}`;
      base[k] = rows.reduce((s, r) => s + (r[k] || 0), 0);
    }
  }
  return base;
}

function sumCombinedStoreMetrics(dd, ue, rowMeta) {
  const row = { ...rowMeta };
  const metrics = ['sales', 'payouts', 'orders'];
  for (const m of metrics) {
    for (const w of ['pre', 'post', 'preLY', 'postLY']) {
      row[`${w}_${m}`] = (dd?.[`${w}_${m}`] || 0) + (ue?.[`${w}_${m}`] || 0);
    }
  }

  for (const m of metrics) {
    row[`${m}_prevspost`] = round(row[`post_${m}`] - row[`pre_${m}`]);
    row[`${m}_ly_prevspost`] = round(row[`postLY_${m}`] - row[`preLY_${m}`]);
    row[`${m}_yoy`] = round(row[`post_${m}`] - row[`postLY_${m}`]);
    row[`${m}_growth_pct`] = round(cleanInfinity(safeDivide(row[`${m}_prevspost`], row[`pre_${m}`]) * 100));
    row[`${m}_ly_growth_pct`] = round(cleanInfinity(safeDivide(row[`${m}_ly_prevspost`], row[`preLY_${m}`]) * 100));
    row[`${m}_yoy_pct`] = round(cleanInfinity(safeDivide(row[`${m}_yoy`], row[`postLY_${m}`]) * 100));
  }

  for (const w of ['pre', 'post', 'preLY', 'postLY']) {
    row[`${w}_mktSpend`] = (dd?.[`${w}_mktSpend`] || 0) + (ue?.[`${w}_mktSpend`] || 0);
  }

  for (const w of ['pre', 'post', 'preLY', 'postLY']) {
    row[`${w}_aov`] = round(safeDivide(row[`${w}_sales`], row[`${w}_orders`]), 2);
    row[`${w}_avg_payout`] = round(safeDivide(row[`${w}_payouts`], row[`${w}_orders`]), 2);
    row[`${w}_profitability`] = round(safeDivide(row[`${w}_payouts`], row[`${w}_sales`]) * 100);
  }
  row.aov_prevspost = round(row.post_aov - row.pre_aov, 2);
  row.aov_ly_prevspost = round(row.postLY_aov - row.preLY_aov, 2);
  row.aov_growth_pct = round(cleanInfinity(safeDivide(row.aov_prevspost, row.pre_aov) * 100));
  row.aov_ly_growth_pct = round(cleanInfinity(safeDivide(row.aov_ly_prevspost, row.preLY_aov) * 100));
  row.avg_payout_prevspost = round(row.post_avg_payout - row.pre_avg_payout, 2);
  row.avg_payout_ly_prevspost = round(row.postLY_avg_payout - row.preLY_avg_payout, 2);
  row.avg_payout_growth_pct = round(cleanInfinity(safeDivide(row.avg_payout_prevspost, row.pre_avg_payout) * 100));
  row.avg_payout_ly_growth_pct = round(cleanInfinity(safeDivide(row.avg_payout_ly_prevspost, row.preLY_avg_payout) * 100));
  row.prof_prevspost = round(row.post_profitability - row.pre_profitability);
  row.prof_ly_prevspost = round(row.postLY_profitability - row.preLY_profitability);
  row.prof_growth_pct = round(cleanInfinity(safeDivide(row.prof_prevspost, row.pre_profitability) * 100));
  row.prof_ly_growth_pct = round(cleanInfinity(safeDivide(row.prof_ly_prevspost, row.preLY_profitability) * 100));

  return row;
}

/**
 * Merge DD + UE store-level metrics. `ddToUeStoreMap`: DD Merchant store ID → UE Store ID (exact strings as in parsed data).
 * Combined rows use Store ID + Store Name from whichever platform has more stores (DD wins ties).
 * Multiple DD IDs may map to the same UE id — their metrics are summed before merging with UE.
 */
export function buildCombinedStoreTables(ddStoreData, ueStoreData, ddToUeStoreMap = {}) {
  const map = ddToUeStoreMap && typeof ddToUeStoreMap === 'object' && !Array.isArray(ddToUeStoreMap) ? ddToUeStoreMap : {};
  const ddList = ddStoreData || [];
  const ueList = ueStoreData || [];
  const ddPrimary = getDominantStorePlatform(ddList.length, ueList.length) === 'dd';

  const ddMap = new Map(ddList.map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));
  const ueMap = new Map(ueList.map((r) => [String(r.storeId ?? '').trim(), r]).filter(([k]) => k));

  const ueToDdIds = new Map();
  for (const [ddId, ueId] of Object.entries(map)) {
    const ueKey = String(ueId ?? '').trim();
    if (!ueKey) continue;
    if (!ueToDdIds.has(ueKey)) ueToDdIds.set(ueKey, []);
    ueToDdIds.get(ueKey).push(String(ddId).trim());
  }

  const combined = [];

  if (ddPrimary) {
    for (const ddRow of ddList) {
      const ddKey = String(ddRow.storeId ?? '').trim();
      if (!ddKey) continue;
      const ueKey = String(map[ddKey] ?? '').trim();
      const ueRow = ueKey ? ueMap.get(ueKey) : null;
      combined.push(sumCombinedStoreMetrics(ddRow, ueRow, {
        storeId: ddKey,
        storeName: ddRow.storeName || '',
        ddStoreId: ddRow.ddStoreId || '',
        _ddStoreKey: ddKey,
        _ueStoreKey: ueKey,
      }));
    }
  } else {
    for (const ueRow of ueList) {
      const ueKey = String(ueRow.storeId ?? '').trim();
      if (!ueKey) continue;
      const ddKeys = ueToDdIds.get(ueKey) || [];
      const ddRows = ddKeys.map((id) => ddMap.get(id)).filter(Boolean);
      const ddMerged = ddRows.length > 1 ? sumStoreMetricRows(ddRows) : (ddRows[0] || null);
      combined.push(sumCombinedStoreMetrics(ddMerged, ueRow, {
        storeId: ueKey,
        storeName: ueRow.storeName || '',
        ddStoreId: ddMerged?.ddStoreId || '',
        _ddStoreKey: ddKeys[0] || '',
        _ueStoreKey: ueKey,
      }));
    }
  }

  combined.sort((a, b) => (b.post_sales || 0) - (a.post_sales || 0));
  return combined;
}
