/** A/B store-group comparison (tagged stores from config.storeTagMap). */

export const AB_METRICS = [
  { key: 'sales', label: 'Sales', kind: 'usd', precision: 0 },
  { key: 'payouts', label: 'Payouts', kind: 'usd', precision: 0 },
  { key: 'orders', label: 'Orders', kind: 'int', precision: 0 },
  { key: 'mktSpend', label: 'Marketing Spend', kind: 'usd', precision: 0 },
  { key: 'aov', label: 'AOV', kind: 'usd2', precision: 2 },
  { key: 'avg_payout', label: 'Avg Payout / Order', kind: 'usd2', precision: 2 },
  { key: 'profitability', label: 'Profitability %', kind: 'pct', precision: 2 },
];

/** Store-level growth % field mapping (combined store rows). */
export const STORE_GROWTH_SPECS = [
  { key: 'sales', label: 'Sales', pvp: 'sales_growth_pct', lyPvp: 'sales_ly_growth_pct', yoy: 'sales_yoy_pct' },
  { key: 'payouts', label: 'Payouts', pvp: 'payouts_growth_pct', lyPvp: 'payouts_ly_growth_pct', yoy: 'payouts_yoy_pct' },
  { key: 'orders', label: 'Orders', pvp: 'orders_growth_pct', lyPvp: 'orders_ly_growth_pct', yoy: 'orders_yoy_pct' },
  { key: 'aov', label: 'AOV', pvp: 'aov_growth_pct', lyPvp: 'aov_ly_growth_pct', yoy: 'aov_yoy_pct', postKey: 'post_aov', postLyKey: 'postLY_aov' },
  { key: 'avg_payout', label: 'Avg Payout / Order', pvp: 'avg_payout_growth_pct', lyPvp: 'avg_payout_ly_growth_pct', yoy: 'avg_payout_yoy_pct', postKey: 'post_avg_payout', postLyKey: 'postLY_avg_payout' },
  { key: 'profitability', label: 'Profitability %', pvp: 'prof_growth_pct', lyPvp: 'prof_ly_growth_pct', yoy: 'prof_yoy_pct', postKey: 'post_profitability', postLyKey: 'postLY_profitability' },
];

const GROWTH_VIEWS = [
  { key: 'pvp', label: 'Pre vs Post', leftKey: 'leftPvpPct', rightKey: 'rightPvpPct', gapKey: 'pvpGap' },
  { key: 'yoy', label: 'YoY', leftKey: 'leftYoyPct', rightKey: 'rightYoyPct', gapKey: 'yoyGap' },
  { key: 'lyPvp', label: 'LY Pre vs Post', leftKey: 'leftLyPvpPct', rightKey: 'rightLyPvpPct', gapKey: 'lyPvpGap' },
];

function roundTo(v, precision = 0) {
  const n = Number(v || 0);
  if (!Number.isFinite(n)) return 0;
  const factor = 10 ** precision;
  return Math.round(n * factor) / factor;
}

export function getUniqueStoreTags(tagMap = {}) {
  return [...new Set(Object.values(tagMap).map((t) => String(t || '').trim()).filter(Boolean))].sort();
}

export function aggregateTaggedGroup(rows) {
  const totals = {
    pre_sales: 0, post_sales: 0, preLY_sales: 0, postLY_sales: 0,
    pre_payouts: 0, post_payouts: 0, preLY_payouts: 0, postLY_payouts: 0,
    pre_orders: 0, post_orders: 0, preLY_orders: 0, postLY_orders: 0,
    pre_mktSpend: 0, post_mktSpend: 0, preLY_mktSpend: 0, postLY_mktSpend: 0,
  };
  for (const r of rows) {
    totals.pre_sales += r.pre_sales || 0;
    totals.post_sales += r.post_sales || 0;
    totals.preLY_sales += r.preLY_sales || 0;
    totals.postLY_sales += r.postLY_sales || 0;
    totals.pre_payouts += r.pre_payouts || 0;
    totals.post_payouts += r.post_payouts || 0;
    totals.preLY_payouts += r.preLY_payouts || 0;
    totals.postLY_payouts += r.postLY_payouts || 0;
    totals.pre_orders += r.pre_orders || 0;
    totals.post_orders += r.post_orders || 0;
    totals.preLY_orders += r.preLY_orders || 0;
    totals.postLY_orders += r.postLY_orders || 0;
    totals.pre_mktSpend += r.pre_mktSpend || 0;
    totals.post_mktSpend += r.post_mktSpend || 0;
    totals.preLY_mktSpend += r.preLY_mktSpend || 0;
    totals.postLY_mktSpend += r.postLY_mktSpend || 0;
  }
  const preOrders = totals.pre_orders || 0;
  const postOrders = totals.post_orders || 0;
  const preLyOrders = totals.preLY_orders || 0;
  const postLyOrders = totals.postLY_orders || 0;
  const preSales = totals.pre_sales || 0;
  const postSales = totals.post_sales || 0;
  const preLySales = totals.preLY_sales || 0;
  const postLySales = totals.postLY_sales || 0;
  const prePayouts = totals.pre_payouts || 0;
  const postPayouts = totals.post_payouts || 0;
  const preLyPayouts = totals.preLY_payouts || 0;
  const postLyPayouts = totals.postLY_payouts || 0;
  return {
    sales: { pre: totals.pre_sales, post: totals.post_sales, preLY: totals.preLY_sales, postLY: totals.postLY_sales },
    payouts: { pre: totals.pre_payouts, post: totals.post_payouts, preLY: totals.preLY_payouts, postLY: totals.postLY_payouts },
    orders: { pre: totals.pre_orders, post: totals.post_orders, preLY: totals.preLY_orders, postLY: totals.postLY_orders },
    mktSpend: { pre: totals.pre_mktSpend, post: totals.post_mktSpend, preLY: totals.preLY_mktSpend, postLY: totals.postLY_mktSpend },
    aov: {
      pre: preOrders ? preSales / preOrders : 0,
      post: postOrders ? postSales / postOrders : 0,
      preLY: preLyOrders ? preLySales / preLyOrders : 0,
      postLY: postLyOrders ? postLySales / postLyOrders : 0,
    },
    avg_payout: {
      pre: preOrders ? prePayouts / preOrders : 0,
      post: postOrders ? postPayouts / postOrders : 0,
      preLY: preLyOrders ? preLyPayouts / preLyOrders : 0,
      postLY: postLyOrders ? postLyPayouts / postLyOrders : 0,
    },
    profitability: {
      pre: preSales ? (prePayouts / preSales) * 100 : 0,
      post: postSales ? (postPayouts / postSales) * 100 : 0,
      preLY: preLySales ? (preLyPayouts / preLySales) * 100 : 0,
      postLY: postLySales ? (postLyPayouts / postLySales) * 100 : 0,
    },
  };
}

function pct(a, b) {
  return a ? ((b - a) / a) * 100 : 0;
}

function taggedStoreRows(combined, tagMap) {
  return (combined || [])
    .map((r) => ({ ...r, _tag: String(tagMap[r.storeId] || '').trim() }))
    .filter((r) => r._tag);
}

function storePctValue(row, spec, viewKey) {
  const field = viewKey === 'pvp' ? spec.pvp : viewKey === 'lyPvp' ? spec.lyPvp : spec.yoy;
  if (field && row[field] != null && Number.isFinite(row[field])) return row[field];
  if (viewKey === 'yoy' && spec.postKey && spec.postLyKey) {
    return pct(row[spec.postLyKey] || 0, row[spec.postKey] || 0);
  }
  return 0;
}

function distributionStats(values) {
  const nums = values.filter((v) => Number.isFinite(v));
  if (!nums.length) return { median: 0, avg: 0, positiveRate: 0, count: 0 };
  const sorted = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  const avg = nums.reduce((s, v) => s + v, 0) / nums.length;
  const positiveRate = (nums.filter((v) => v > 0).length / nums.length) * 100;
  return {
    median: roundTo(median, 1),
    avg: roundTo(avg, 1),
    positiveRate: roundTo(positiveRate, 1),
    count: nums.length,
  };
}

function buildPrePostRows(agg) {
  return AB_METRICS.map((m) => {
    const v = agg[m.key] || { pre: 0, post: 0, preLY: 0, postLY: 0 };
    const prevspost = (v.post || 0) - (v.pre || 0);
    const lyPrevspost = (v.postLY || 0) - (v.preLY || 0);
    return {
      metric: m.label,
      metricKey: m.key,
      kind: m.kind,
      precision: m.precision,
      pre: roundTo(v.pre, m.precision),
      post: roundTo(v.post, m.precision),
      prevspost: roundTo(prevspost, m.precision),
      lyPrevspost: roundTo(lyPrevspost, m.precision),
      growthPct: roundTo(pct(v.pre, v.post), 1),
      lyGrowthPct: roundTo(pct(v.preLY, v.postLY), 1),
    };
  });
}

function buildYoyRows(agg) {
  return AB_METRICS.map((m) => {
    const v = agg[m.key] || { pre: 0, post: 0, preLY: 0, postLY: 0 };
    const yoy = (v.post || 0) - (v.postLY || 0);
    return {
      metric: m.label,
      metricKey: m.key,
      kind: m.kind,
      precision: m.precision,
      postLY: roundTo(v.postLY, m.precision),
      post: roundTo(v.post, m.precision),
      yoy: roundTo(yoy, m.precision),
      yoyPct: roundTo(pct(v.postLY, v.post), 1),
    };
  });
}

/** Within-group growth profile — % only (no absolutes). */
function buildGroupGrowthProfileRows(agg) {
  const prePost = buildPrePostRows(agg);
  const yoy = buildYoyRows(agg);
  return AB_METRICS.map((m, i) => ({
    metric: m.label,
    metricKey: m.key,
    pvpPct: prePost[i].growthPct,
    lyPvpPct: prePost[i].lyGrowthPct,
    yoyPct: yoy[i].yoyPct,
  }));
}

function buildGrowthComparisonRows(leftAgg, rightAgg) {
  return AB_METRICS.map((m) => {
    const left = leftAgg[m.key] || { pre: 0, post: 0, postLY: 0, preLY: 0 };
    const right = rightAgg[m.key] || { pre: 0, post: 0, postLY: 0, preLY: 0 };
    const leftPvpPct = pct(left.pre, left.post);
    const rightPvpPct = pct(right.pre, right.post);
    const leftYoyPct = pct(left.postLY, left.post);
    const rightYoyPct = pct(right.postLY, right.post);
    const leftLyPvpPct = pct(left.preLY, left.postLY);
    const rightLyPvpPct = pct(right.preLY, right.postLY);
    return {
      metric: m.label,
      metricKey: m.key,
      leftPvpPct: roundTo(leftPvpPct, 1),
      rightPvpPct: roundTo(rightPvpPct, 1),
      pvpGap: roundTo(leftPvpPct - rightPvpPct, 1),
      leftYoyPct: roundTo(leftYoyPct, 1),
      rightYoyPct: roundTo(rightYoyPct, 1),
      yoyGap: roundTo(leftYoyPct - rightYoyPct, 1),
      leftLyPvpPct: roundTo(leftLyPvpPct, 1),
      rightLyPvpPct: roundTo(rightLyPvpPct, 1),
      lyPvpGap: roundTo(leftLyPvpPct - rightLyPvpPct, 1),
    };
  });
}

function buildFocusedGrowthRows(growthRows, viewKey) {
  const view = GROWTH_VIEWS.find((v) => v.key === viewKey);
  if (!view) return [];
  return growthRows.map((r) => ({
    metric: r.metric,
    metricKey: r.metricKey,
    leftPct: r[view.leftKey],
    rightPct: r[view.rightKey],
    gap: r[view.gapKey],
  }));
}

function buildDistributionComparisonRows(leftRows, rightRows, leftTag, rightTag) {
  const out = [];
  for (const spec of STORE_GROWTH_SPECS) {
    for (const view of [
      { key: 'pvp', label: 'PvP%' },
      { key: 'lyPvp', label: 'LY PvP%' },
      { key: 'yoy', label: 'YoY%' },
    ]) {
      const leftVals = leftRows.map((r) => storePctValue(r, spec, view.key));
      const rightVals = rightRows.map((r) => storePctValue(r, spec, view.key));
      const left = distributionStats(leftVals);
      const right = distributionStats(rightVals);
      out.push({
        metric: spec.label,
        growthType: view.label,
        leftMedian: left.median,
        rightMedian: right.median,
        medianGap: roundTo(left.median - right.median, 1),
        leftAvg: left.avg,
        rightAvg: right.avg,
        avgGap: roundTo(left.avg - right.avg, 1),
        leftPositiveRate: left.positiveRate,
        rightPositiveRate: right.positiveRate,
        positiveRateGap: roundTo(left.positiveRate - right.positiveRate, 1),
        leftCount: left.count,
        rightCount: right.count,
        leftTag,
        rightTag,
      });
    }
  }
  return out;
}

function buildOutperformanceRows(distributionRows, leftTag, rightTag) {
  return distributionRows.map((r) => {
    const medianWinner = r.medianGap > 0 ? leftTag : r.medianGap < 0 ? rightTag : 'Tie';
    const avgWinner = r.avgGap > 0 ? leftTag : r.avgGap < 0 ? rightTag : 'Tie';
    const positiveWinner = r.positiveRateGap > 0 ? leftTag : r.positiveRateGap < 0 ? rightTag : 'Tie';
    return {
      metric: r.metric,
      growthType: r.growthType,
      medianWinner,
      avgWinner,
      positiveWinner,
      medianGap: r.medianGap,
      avgGap: r.avgGap,
      positiveRateGap: r.positiveRateGap,
    };
  });
}

function buildStoreLevelPctRows(taggedRows, tags) {
  const tagSet = new Set(tags);
  return taggedRows
    .filter((r) => tagSet.has(r._tag))
    .map((r) => {
      const row = { tag: r._tag, storeId: r.storeId };
      for (const spec of STORE_GROWTH_SPECS) {
        row[`${spec.key}_pvp`] = roundTo(storePctValue(r, spec, 'pvp'), 1);
        row[`${spec.key}_lypvp`] = roundTo(storePctValue(r, spec, 'lyPvp'), 1);
        row[`${spec.key}_yoy`] = roundTo(storePctValue(r, spec, 'yoy'), 1);
      }
      return row;
    });
}

/** Build comparison tables for one tag pair (matches A/B Comparison screen). */
export function buildAbComparison(combined, tagMap, leftTag, rightTag) {
  const taggedRows = taggedStoreRows(combined, tagMap);
  const leftRows = taggedRows.filter((r) => r._tag === leftTag);
  const rightRows = taggedRows.filter((r) => r._tag === rightTag);
  const leftAgg = aggregateTaggedGroup(leftRows);
  const rightAgg = aggregateTaggedGroup(rightRows);
  const growthComparisonRows = buildGrowthComparisonRows(leftAgg, rightAgg);
  const distributionRows = buildDistributionComparisonRows(leftRows, rightRows, leftTag, rightTag);

  return {
    leftTag,
    rightTag,
    leftStoreCount: leftRows.length,
    rightStoreCount: rightRows.length,
    leftPrePostRows: buildPrePostRows(leftAgg),
    rightPrePostRows: buildPrePostRows(rightAgg),
    leftYoyRows: buildYoyRows(leftAgg),
    rightYoyRows: buildYoyRows(rightAgg),
    leftGrowthProfileRows: buildGroupGrowthProfileRows(leftAgg),
    rightGrowthProfileRows: buildGroupGrowthProfileRows(rightAgg),
    growthComparisonRows,
    pvpComparisonRows: buildFocusedGrowthRows(growthComparisonRows, 'pvp'),
    yoyComparisonRows: buildFocusedGrowthRows(growthComparisonRows, 'yoy'),
    lyPvpComparisonRows: buildFocusedGrowthRows(growthComparisonRows, 'lyPvp'),
    distributionRows,
    outperformanceRows: buildOutperformanceRows(distributionRows, leftTag, rightTag),
    storeLevelPctRows: buildStoreLevelPctRows(taggedRows, [leftTag, rightTag]),
    storeLevelRows: buildStoreLevelPctRows(taggedRows, [leftTag, rightTag]),
    comparisonRows: growthComparisonRows,
  };
}

export function buildSingleTagComparison(combined, tagMap, tag) {
  const taggedRows = taggedStoreRows(combined, tagMap).filter((r) => r._tag === tag);
  const agg = aggregateTaggedGroup(taggedRows);
  return {
    tag,
    storeCount: taggedRows.length,
    prePostRows: buildPrePostRows(agg),
    yoyRows: buildYoyRows(agg),
    growthProfileRows: buildGroupGrowthProfileRows(agg),
    storeLevelPctRows: buildStoreLevelPctRows(taggedRows, [tag]),
    storeLevelRows: buildStoreLevelPctRows(taggedRows, [tag]),
  };
}

/** Ordered tag pairs to export: A vs B first when present, then remaining pairs. */
export function listAbComparisonPairs(tagMap = {}) {
  const tags = getUniqueStoreTags(tagMap);
  if (tags.length < 2) return [];

  const pairs = [];
  const seen = new Set();
  const addPair = (left, right) => {
    const key = `${left}\0${right}`;
    if (seen.has(key)) return;
    seen.add(key);
    pairs.push([left, right]);
  };

  if (tags.includes('A') && tags.includes('B')) addPair('A', 'B');
  for (let i = 0; i < tags.length; i += 1) {
    for (let j = i + 1; j < tags.length; j += 1) {
      addPair(tags[i], tags[j]);
    }
  }
  return pairs;
}

export function buildAllAbComparisons(combined, tagMap) {
  return listAbComparisonPairs(tagMap).map(([leftTag, rightTag]) =>
    buildAbComparison(combined, tagMap, leftTag, rightTag));
}
