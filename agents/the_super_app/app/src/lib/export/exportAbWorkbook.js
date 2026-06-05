import * as XLSX from 'xlsx';
import { xf } from '../utils/formatters';
import { buildAbComparison, buildSingleTagComparison } from '../engine/abComparison';
import { buildExportFilename } from './exportFilename.js';
import { formatStoreTagLabel, withSheetSummary } from './exportSheetSummaries.js';

function cleanSheetName(name) {
  return name.replace(/[\][:\\/?*]/g, '').slice(0, 31);
}

function addSection(rows, title, headers, dataRows) {
  if (!Array.isArray(dataRows) || !dataRows.length) return;
  if (rows.length) rows.push([]);
  rows.push([title]);
  rows.push(headers);
  rows.push(...dataRows);
}

function addBlock(rows, title, dataRows) {
  if (!Array.isArray(dataRows) || !dataRows.length) return;
  if (rows.length) rows.push([]);
  rows.push([title]);
  rows.push(...dataRows);
}

function estimateColumnWidths(rows) {
  const widths = [];
  for (const row of rows) {
    row.forEach((value, index) => {
      const len = String(value ?? '').length;
      widths[index] = Math.min(Math.max(widths[index] || 10, len + 2), 42);
    });
  }
  return widths.map((wch) => ({ wch }));
}

function appendPrePostSection(rows, title, prePostRows) {
  addSection(
    rows,
    title,
    ['Metric', 'Pre', 'Post', 'Pre vs Post', 'LY Pre vs Post', 'Growth%', 'LY Growth%'],
    (prePostRows || []).map((r) => [
      r.metric,
      r.kind === 'pct' ? xf.pct(r.pre) : r.kind === 'int' ? xf.int(r.pre) : r.kind === 'usd2' ? xf.usd2(r.pre) : xf.usd(r.pre),
      r.kind === 'pct' ? xf.pct(r.post) : r.kind === 'int' ? xf.int(r.post) : r.kind === 'usd2' ? xf.usd2(r.post) : xf.usd(r.post),
      r.kind === 'pct' ? xf.pct(r.prevspost) : r.kind === 'int' ? xf.int(r.prevspost) : r.kind === 'usd2' ? xf.usd2(r.prevspost) : xf.usd(r.prevspost),
      r.kind === 'pct' ? xf.pct(r.lyPrevspost) : r.kind === 'int' ? xf.int(r.lyPrevspost) : r.kind === 'usd2' ? xf.usd2(r.lyPrevspost) : xf.usd(r.lyPrevspost),
      xf.deltaPct(r.growthPct),
      xf.deltaPct(r.lyGrowthPct),
    ]),
  );
}

function appendYoySection(rows, title, yoyRows) {
  addSection(
    rows,
    title,
    ['Metric', 'LY Post', 'Post', 'YoY', 'YoY%'],
    (yoyRows || []).map((r) => [
      r.metric,
      r.kind === 'pct' ? xf.pct(r.postLY) : r.kind === 'int' ? xf.int(r.postLY) : r.kind === 'usd2' ? xf.usd2(r.postLY) : xf.usd(r.postLY),
      r.kind === 'pct' ? xf.pct(r.post) : r.kind === 'int' ? xf.int(r.post) : r.kind === 'usd2' ? xf.usd2(r.post) : xf.usd(r.post),
      r.kind === 'pct' ? xf.pct(r.yoy) : r.kind === 'int' ? xf.int(r.yoy) : r.kind === 'usd2' ? xf.usd2(r.yoy) : xf.usd(r.yoy),
      xf.deltaPct(r.yoyPct),
    ]),
  );
}

function appendGrowthProfileSection(rows, title, profileRows) {
  addSection(
    rows,
    title,
    ['Metric', 'PvP%', 'LY PvP%', 'YoY%'],
    (profileRows || []).map((r) => [r.metric, xf.deltaPct(r.pvpPct), xf.deltaPct(r.lyPvpPct), xf.deltaPct(r.yoyPct)]),
  );
}

function appendFocusedGrowthSection(rows, title, leftTag, rightTag, focusedRows) {
  addSection(
    rows,
    title,
    ['Metric', `${leftTag} %`, `${rightTag} %`, 'Gap (pp)'],
    (focusedRows || []).map((r) => [r.metric, xf.deltaPct(r.leftPct), xf.deltaPct(r.rightPct), xf.deltaPct(r.gap)]),
  );
}

function appendHeadlineGrowthSection(rows, title, leftTag, rightTag, growthRows) {
  addSection(
    rows,
    title,
    [
      'Metric',
      `${leftTag} PvP%`,
      `${rightTag} PvP%`,
      'PvP Gap',
      `${leftTag} YoY%`,
      `${rightTag} YoY%`,
      'YoY Gap',
      `${leftTag} LY PvP%`,
      `${rightTag} LY PvP%`,
      'LY PvP Gap',
    ],
    (growthRows || []).map((r) => [
      r.metric,
      xf.deltaPct(r.leftPvpPct),
      xf.deltaPct(r.rightPvpPct),
      xf.deltaPct(r.pvpGap),
      xf.deltaPct(r.leftYoyPct),
      xf.deltaPct(r.rightYoyPct),
      xf.deltaPct(r.yoyGap),
      xf.deltaPct(r.leftLyPvpPct),
      xf.deltaPct(r.rightLyPvpPct),
      xf.deltaPct(r.lyPvpGap),
    ]),
  );
}

function appendDistributionSection(rows, title, leftTag, rightTag, distributionRows) {
  addSection(
    rows,
    title,
    [
      'Metric',
      'Growth type',
      `${leftTag} median%`,
      `${rightTag} median%`,
      'Median gap',
      `${leftTag} avg%`,
      `${rightTag} avg%`,
      'Avg gap',
      `${leftTag} % stores positive`,
      `${rightTag} % stores positive`,
      'Positive rate gap',
      `${leftTag} n`,
      `${rightTag} n`,
    ],
    (distributionRows || []).map((r) => [
      r.metric,
      r.growthType,
      xf.deltaPct(r.leftMedian),
      xf.deltaPct(r.rightMedian),
      xf.deltaPct(r.medianGap),
      xf.deltaPct(r.leftAvg),
      xf.deltaPct(r.rightAvg),
      xf.deltaPct(r.avgGap),
      xf.deltaPct(r.leftPositiveRate),
      xf.deltaPct(r.rightPositiveRate),
      xf.deltaPct(r.positiveRateGap),
      xf.int(r.leftCount),
      xf.int(r.rightCount),
    ]),
  );
}

function appendOutperformanceSection(rows, title, outperformanceRows) {
  addSection(
    rows,
    title,
    ['Metric', 'Growth type', 'Median winner', 'Avg winner', '% positive winner', 'Median gap', 'Avg gap', 'Positive rate gap'],
    (outperformanceRows || []).map((r) => [
      r.metric,
      r.growthType,
      r.medianWinner,
      r.avgWinner,
      r.positiveWinner,
      xf.deltaPct(r.medianGap),
      xf.deltaPct(r.avgGap),
      xf.deltaPct(r.positiveRateGap),
    ]),
  );
}

function appendStorePctSection(rows, title, storeRows) {
  addSection(
    rows,
    title,
    [
      'Tag',
      'Store',
      'Sales PvP%',
      'Sales LY PvP%',
      'Sales YoY%',
      'Payouts PvP%',
      'Payouts YoY%',
      'Orders PvP%',
      'Orders YoY%',
      'AOV PvP%',
      'AOV YoY%',
      'Avg Payout PvP%',
      'Profitability PvP%',
    ],
    (storeRows || []).map((r) => [
      r.tag,
      r.storeId,
      xf.deltaPct(r.sales_pvp),
      xf.deltaPct(r.sales_lypvp),
      xf.deltaPct(r.sales_yoy),
      xf.deltaPct(r.payouts_pvp),
      xf.deltaPct(r.payouts_yoy),
      xf.deltaPct(r.orders_pvp),
      xf.deltaPct(r.orders_yoy),
      xf.deltaPct(r.aov_pvp),
      xf.deltaPct(r.aov_yoy),
      xf.deltaPct(r.avg_payout_pvp),
      xf.deltaPct(r.profitability_pvp),
    ]),
  );
}

function buildPairExportRows(cmp) {
  const {
    leftTag,
    rightTag,
    leftStoreCount,
    rightStoreCount,
    leftPrePostRows,
    rightPrePostRows,
    leftYoyRows,
    rightYoyRows,
    leftGrowthProfileRows,
    rightGrowthProfileRows,
    growthComparisonRows,
    pvpComparisonRows,
    yoyComparisonRows,
    lyPvpComparisonRows,
    distributionRows,
    outperformanceRows,
    storeLevelPctRows,
  } = cmp;

  const rows = [];
  addBlock(rows, `${leftTag} vs ${rightTag} — A/B Analysis`, [
    ['Note', 'Unequal store counts — cross-group comparison uses growth % only'],
    [`${leftTag} stores`, String(leftStoreCount)],
    [`${rightTag} stores`, String(rightStoreCount)],
  ]);

  appendGrowthProfileSection(rows, `Group ${leftTag} — Growth profile (%)`, leftGrowthProfileRows);
  appendGrowthProfileSection(rows, `Group ${rightTag} — Growth profile (%)`, rightGrowthProfileRows);
  appendPrePostSection(rows, `Group ${leftTag} — Pre vs Post (context)`, leftPrePostRows);
  appendPrePostSection(rows, `Group ${rightTag} — Pre vs Post (context)`, rightPrePostRows);
  appendYoySection(rows, `Group ${leftTag} — Year over Year (context)`, leftYoyRows);
  appendYoySection(rows, `Group ${rightTag} — Year over Year (context)`, rightYoyRows);

  appendHeadlineGrowthSection(rows, `${leftTag} vs ${rightTag} — Headline growth % comparison`, leftTag, rightTag, growthComparisonRows);
  appendFocusedGrowthSection(rows, `${leftTag} vs ${rightTag} — Pre vs Post growth %`, leftTag, rightTag, pvpComparisonRows);
  appendFocusedGrowthSection(rows, `${leftTag} vs ${rightTag} — YoY growth %`, leftTag, rightTag, yoyComparisonRows);
  appendFocusedGrowthSection(rows, `${leftTag} vs ${rightTag} — LY Pre vs Post growth %`, leftTag, rightTag, lyPvpComparisonRows);
  appendDistributionSection(rows, `${leftTag} vs ${rightTag} — Store-level distribution`, leftTag, rightTag, distributionRows);
  appendOutperformanceSection(rows, `${leftTag} vs ${rightTag} — Outperformance scorecard`, outperformanceRows);
  appendStorePctSection(rows, `${leftTag} vs ${rightTag} — Store-level growth rates (%)`, storeLevelPctRows);

  return rows;
}

function buildSingleGroupExportRows(single) {
  const rows = [];
  addBlock(rows, `Group ${single.tag} — A/B Analysis`, [
    ['Scope', `Group ${single.tag} only`],
    ['Stores', String(single.storeCount)],
  ]);
  appendGrowthProfileSection(rows, `Group ${single.tag} — Growth profile (%)`, single.growthProfileRows);
  appendPrePostSection(rows, `Group ${single.tag} — Pre vs Post`, single.prePostRows);
  appendYoySection(rows, `Group ${single.tag} — Year over Year`, single.yoyRows);
  appendStorePctSection(rows, `Group ${single.tag} — Store-level growth rates (%)`, single.storeLevelPctRows);
  return rows;
}

/**
 * Export dedicated A/B workbook for the selected comparison on screen.
 * @param {object} data — dataStore snapshot
 * @param {object} config — configStore snapshot
 * @param {{ leftTag?: string, rightTag?: string }} opts — pair shown on screen (when abGroupFilter is all)
 */
export function exportAbReport(data, config, opts = {}) {
  const combined = data.storeTables?.combined || [];
  const tagMap = config.storeTagMap || {};
  const abFilter = config.abGroupFilter || 'all';

  let exportRows;
  let sheetLabel = 'A/B';

  if (abFilter === 'A' || abFilter === 'B') {
    const single = buildSingleTagComparison(combined, tagMap, abFilter);
    if (!single.storeCount) throw new Error(`No stores tagged as ${formatStoreTagLabel(abFilter) || `Group ${abFilter}`}.`);
    exportRows = buildSingleGroupExportRows(single);
    sheetLabel = formatStoreTagLabel(abFilter) || `Group ${abFilter}`;
  } else {
    const leftTag = opts.leftTag || 'A';
    const rightTag = opts.rightTag || 'B';
    const cmp = buildAbComparison(combined, tagMap, leftTag, rightTag);
    if (!cmp.leftStoreCount && !cmp.rightStoreCount) {
      throw new Error('No tagged stores found for the selected groups.');
    }
    exportRows = buildPairExportRows(cmp);
    const leftLabel = formatStoreTagLabel(leftTag) || leftTag;
    const rightLabel = formatStoreTagLabel(rightTag) || rightTag;
    sheetLabel = `${leftLabel} vs ${rightLabel}`;
  }

  const summarySheetName = `${sheetLabel} — A/B Analysis`;
  exportRows = withSheetSummary(summarySheetName, exportRows, data, config);

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(exportRows);
  ws['!cols'] = estimateColumnWidths(exportRows);
  XLSX.utils.book_append_sheet(wb, ws, cleanSheetName(sheetLabel));

  const filename = buildExportFilename(config, 'ab_excel', { ext: 'xlsx' });
  XLSX.writeFile(wb, filename);
  return { filename, sheetLabel };
}
