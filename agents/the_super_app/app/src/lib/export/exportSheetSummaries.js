import { formatCompactDateRange } from '../utils/dateUtils';

/** Display labels for A/B store tags in exports and UI. */
export const STORE_TAG_LABELS = {
  A: 'TODC',
  B: 'Non-TODC',
};

export function formatStoreTagLabel(tag) {
  const t = String(tag ?? '').trim();
  if (!t) return '';
  return STORE_TAG_LABELS[t] || t;
}

export function hasExportTags(config = {}) {
  const tagMap = config.storeTagMap || {};
  return Object.values(tagMap).some((t) => String(t ?? '').trim());
}

/** e.g. "8 TODC, 6 Non-TODC" */
export function describeExportTagCounts(config = {}) {
  if (!hasExportTags(config)) return '';
  const counts = {};
  for (const t of Object.values(config.storeTagMap || {})) {
    const key = String(t ?? '').trim();
    if (!key) continue;
    counts[key] = (counts[key] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([tag, n]) => `${n} ${formatStoreTagLabel(tag)}`)
    .join(', ');
}

/** Returns "which are TODC" or "" when no tags. */
export function tagScopeClause(config = {}) {
  const filter = config.abGroupFilter;
  if (filter === 'A' || filter === 'B') {
    return `which are ${formatStoreTagLabel(filter)}`;
  }
  const counts = describeExportTagCounts(config);
  if (!counts) return '';
  return `which are tagged ${counts}`;
}

export function combinedStoreCount(data) {
  return (data?.storeTables?.combined || []).length;
}

function periodLine(config) {
  const pre = formatCompactDateRange(config.ddPreStart || config.uePreStart, config.ddPreEnd || config.uePreEnd);
  const post = formatCompactDateRange(config.ddPostStart || config.uePostStart, config.ddPostEnd || config.uePostEnd);
  const parts = [];
  if (pre) parts.push(`Pre: ${pre}`);
  if (post) parts.push(`Post: ${post}`);
  return parts.length ? parts.join(' · ') : '';
}

function storeScopePhrase(data, config) {
  const n = combinedStoreCount(data);
  const tagClause = tagScopeClause(config);
  return tagClause ? `${n} stores ${tagClause}` : `${n} stores`;
}

/** @returns {string[]} 2–3 summary lines for a sheet */
export function getSheetSummaryLines(sheetName, data, config) {
  const operator = String(config.operatorName || 'the operator').trim();
  const periods = periodLine(config);
  const stores = storeScopePhrase(data, config);
  const tagClause = tagScopeClause(config);
  const ddCount = (data?.storeTables?.dd || []).length;
  const ueCount = (data?.storeTables?.ue || []).length;

  switch (sheetName) {
    case 'Summary Tables':
      return [
        `Portfolio-level Pre vs Post and Year-over-Year metrics for ${stores}.`,
        'Includes sales, payouts, orders, new customers, profitability, and average check across Combined, DoorDash, and UberEats.',
        periods,
      ].filter(Boolean);

    case 'Store-Level Tables':
      return [
        `Store-level sales comparison for ${stores}.`,
        'Pre vs Post and YoY tables for Combined, DoorDash, and UberEats — aligned rows; NA where a platform has no mapped store.',
        periods,
      ].filter(Boolean);

    case 'Corporate vs TODC':
      return [
        'DoorDash marketing split between Corporate and TODC campaigns (promotion and sponsored listing).',
        tagClause
          ? `Post-period performance for ${stores}.`
          : `Post-period performance across ${combinedStoreCount(data)} mapped stores.`,
        periods,
      ].filter(Boolean);

    case 'DD-slotWise':
      return [
        `DoorDash day-part (slot) analysis for ${ddCount} stores${tagClause ? ` ${tagClause}` : ''}.`,
        'Sales and payouts — Pre vs Post and Year-over-Year by slot.',
        periods,
      ].filter(Boolean);

    case 'UE-slotWise':
      return [
        `UberEats day-part (slot) analysis for ${ueCount} stores${tagClause ? ` ${tagClause}` : ''}.`,
        'Sales and payouts — Pre vs Post and Year-over-Year by slot.',
        periods,
      ].filter(Boolean);

    case 'DD Financial-Aggregate':
      return [
        `Combined DoorDash + UberEats financial summary (aggregate) for ${stores}.`,
        'Line-item Pre vs Post, last-year comparison, and YoY across the mapped portfolio.',
        periods,
      ].filter(Boolean);

    case 'DD Financial Breakdown':
      return [
        `Per-store financial breakdown for ${stores}.`,
        'Same financial metrics as the aggregate sheet, repeated for each combined store.',
        periods,
      ].filter(Boolean);

    case 'Insights':
      return [
        `Automated gain/loss highlights for ${operator} — ${stores}.`,
        'Largest Pre vs Post moves by metric, store, slot, and platform.',
        periods,
      ].filter(Boolean);

    case 'Extended Summary':
      return [
        `Extended metric summary (all platforms) for ${stores}.`,
        'Detailed Pre vs Post and YoY tables plus growth headline rows.',
        periods,
      ].filter(Boolean);

    case 'Full':
      return [
        `Full analysis export for ${operator} — ${stores}.`,
        'Overview, diagnostics, marketing, slots, buckets, and store detail in one workbook tab.',
        periods,
      ].filter(Boolean);

    case 'Date':
      return [
        `Daily sales spotlight for ${stores}.`,
        'Best and worst days in Pre and Post windows.',
        periods,
      ].filter(Boolean);

    case 'Marketing':
      return [
        `DoorDash marketing performance — Corporate vs TODC and campaign-level detail${tagClause ? ` for stores ${tagClause}` : ''}.`,
        'Promo and ads campaigns with ROAS, spend, and cost per order.',
        periods,
      ].filter(Boolean);

    case 'Slot':
      return [
        `Extended slot / day-part tables (financial + order mix) for ${stores}.`,
        'DoorDash and UberEats slot metrics beyond the legacy slot-wise sheets.',
        periods,
      ].filter(Boolean);

    case 'Bucket':
      return [
        `Ticket-size bucket and order-origin mix for ${stores}.`,
        'Pre vs Post share shifts and order volume by bucket.',
        periods,
      ].filter(Boolean);

    case 'Stores':
      return [
        `Store-level performance export for ${stores}.`,
        'Sales, payouts, orders, AOV, marketing spend, and profitability — Pre vs Post and YoY per store.',
        periods,
      ].filter(Boolean);

    case 'Operations':
      return [
        `Operations quality data (downtime, cancellations, etc.) where uploaded for ${operator}.`,
        tagClause ? `Scoped to mapped stores ${tagClause}.` : `Across ${combinedStoreCount(data)} mapped stores.`,
      ].filter(Boolean);

    case 'Product Mix':
      return [
        `Product mix and error-charge analysis for ${operator}${tagClause ? ` (${tagClause})` : ''}.`,
        'Top products, AOV, growth movers, and error charges when PMIX data is available.',
        periods,
      ].filter(Boolean);

    case 'DD Register':
      return [
        `DoorDash register — store × weekday × slot averages for ${ddCount} stores${tagClause ? ` ${tagClause}` : ''}.`,
        'Weekday-normalized sales, payouts, orders, and fee lines.',
        periods,
      ].filter(Boolean);

    case 'UE Register':
      return [
        `UberEats register — store × weekday × slot averages for ${ueCount} stores${tagClause ? ` ${tagClause}` : ''}.`,
        'Weekday-normalized sales, payouts, orders, and fee lines.',
        periods,
      ].filter(Boolean);

    default:
      if (sheetName.endsWith(' — A/B Analysis') || sheetName.includes(' vs ')) {
        return [
          `A/B comparison export — growth rates and cohort context${tagClause ? ` for stores ${tagClause}` : ''}.`,
          'Cross-group comparisons use growth % only; within-group tables include absolute Pre/Post values.',
          periods,
        ].filter(Boolean);
      }
      return [
        `Export data for ${operator}.`,
        periods,
      ].filter(Boolean);
  }
}

/** Prepend 2–3 summary lines and a blank row before sheet content. */
export function prependSheetSummary(rows, summaryLines) {
  const lines = (summaryLines || []).filter(Boolean);
  if (!lines.length) return rows || [];
  return [...lines.map((line) => [line]), [''], ...(rows || [])];
}

export function withSheetSummary(sheetName, rows, data, config) {
  return prependSheetSummary(rows, getSheetSummaryLines(sheetName, data, config));
}
