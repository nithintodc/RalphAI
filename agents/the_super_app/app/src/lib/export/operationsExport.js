import {
  pivotDowntimeByStore,
  pivotDowntimeByDimension,
  pivotCountByStore,
  pivotStoreByDatePeriod,
  pivotStoreReasonMatrix,
  pivotTopDatesPerStore,
  pickCategoryColumn,
  pickStoreColumn,
  inferCategoricalColumns,
  formatDurationDHM,
} from '../utils/opsProductPivot';
import { xf } from '../utils/formatters';

function objectColumns(rows) {
  return rows?.[0] ? Object.keys(rows[0]) : [];
}

function matrixToRows(rowHeaderLabel, rowKeys, colKeys, matrix) {
  if (!rowKeys?.length || !colKeys?.length || !matrix?.length) return [];
  const headers = [rowHeaderLabel, ...colKeys, 'Total'];
  const body = rowKeys.map((rk, i) => {
    const vals = matrix[i] || [];
    const total = vals.reduce((s, v) => s + Number(v || 0), 0);
    return [rk, ...vals, total];
  });
  return [headers, ...body];
}

function formatMatrixCell(valueKind, v) {
  if (v == null || v === 0) return '';
  if (valueKind === 'duration') return formatDurationDHM(v);
  if (valueKind === 'count') return xf.int(v);
  return String(v);
}

function topDateExportRows(pivot, valueKind) {
  return (pivot?.rows || []).map((r) => [
    r.store,
    r.date,
    formatMatrixCell(valueKind, r.total),
  ]);
}

/**
 * Flat sections for Excel / doc export — mirrors Operations screen tables.
 * `addSection(title, headers, rows)` callback matches exportWorkbook.addSection shape.
 */
export function appendOperationsExportSections(addSection, addBlock, data) {
  const downtimeRows = data.ddOps?.byStore?.downtime?.data || [];
  const downtimeCols = objectColumns(downtimeRows);
  const downtimePivot = pivotDowntimeByStore(downtimeRows, downtimeCols);
  addSection(
    'Downtime by store',
    ['Store', 'Days', 'Hours', 'Minutes', 'Total (min)', 'Rows'],
    (downtimePivot.rows || []).map((r) => [r.store, r.days, r.hours, r.minutes, r.totalMinutes, r.lineCount]),
  );

  const storeColEarly = pickStoreColumn(downtimeCols);
  const categoryCol =
    pickCategoryColumn(downtimeCols, [storeColEarly].filter(Boolean))
    || inferCategoricalColumns(downtimeRows, downtimeCols, { exclude: [storeColEarly].filter(Boolean), maxUniq: 90 })[0]?.col
    || null;
  const downtimeByCategory = categoryCol
    ? pivotDowntimeByDimension(downtimeRows, downtimeCols, categoryCol)
    : null;
  addSection(
    `Downtime by category${categoryCol ? ` (${categoryCol})` : ''}`,
    ['Bucket', 'Days', 'Hours', 'Minutes', 'Total (min)', 'Rows'],
    (downtimeByCategory?.rows || []).map((r) => [r.label, r.days, r.hours, r.minutes, r.totalMinutes, r.lineCount]),
  );

  const downtimeStoreReason = pivotStoreReasonMatrix(downtimeRows, downtimeCols, { valueKind: 'duration', maxReasonCols: 10 });
  if (downtimeStoreReason?.rowKeys?.length) {
    addBlock(
      `Downtime by store × reason (${downtimeStoreReason.reasonCol})`,
      matrixToRows('Store', downtimeStoreReason.rowKeys, downtimeStoreReason.colKeys, downtimeStoreReason.matrix),
    );
  }

  const downtimeTopDates = pivotTopDatesPerStore(downtimeRows, downtimeCols, { topPerStore: 5, valueKind: 'duration' });
  addSection(
    'Top downtime dates by store',
    ['Store', 'Date', 'Downtime'],
    topDateExportRows(downtimeTopDates, 'duration'),
  );

  const cancelRows = data.ddOps?.byStore?.cancellations?.data || [];
  const cancelCols = objectColumns(cancelRows);
  const cancelPivot = pivotCountByStore(cancelRows, cancelCols);
  addSection(
    'Cancellations by store',
    ['Store', 'Count'],
    (cancelPivot.rows || []).map((r) => [r.store, r.rowCount]),
  );

  const cancelStoreReason = pivotStoreReasonMatrix(cancelRows, cancelCols, { valueKind: 'count', maxReasonCols: 10 });
  if (cancelStoreReason?.rowKeys?.length) {
    addBlock(
      `Cancellations by store × reason (${cancelStoreReason.reasonCol})`,
      matrixToRows('Store', cancelStoreReason.rowKeys, cancelStoreReason.colKeys, cancelStoreReason.matrix),
    );
  }

  const cancelTopDates = pivotTopDatesPerStore(cancelRows, cancelCols, { topPerStore: 5, valueKind: 'count' });
  addSection(
    'Top cancellation dates by store',
    ['Store', 'Date', 'Count'],
    topDateExportRows(cancelTopDates, 'count'),
  );

  const missRows = data.ddOps?.byStore?.missingIncorrect?.data || [];
  const missCols = objectColumns(missRows);
  const missPivot = pivotCountByStore(missRows, missCols);
  addSection(
    'Missing / incorrect by store',
    ['Store', 'Count'],
    (missPivot.rows || []).map((r) => [r.store, r.rowCount]),
  );

  const missStoreReason = pivotStoreReasonMatrix(missRows, missCols, { valueKind: 'count', maxReasonCols: 10 });
  if (missStoreReason?.rowKeys?.length) {
    addBlock(
      `Missing / incorrect by store × reason (${missStoreReason.reasonCol})`,
      matrixToRows('Store', missStoreReason.rowKeys, missStoreReason.colKeys, missStoreReason.matrix),
    );
  }

  const missTopDates = pivotTopDatesPerStore(missRows, missCols, { topPerStore: 5, valueKind: 'count' });
  addSection(
    'Top missing / incorrect dates by store',
    ['Store', 'Date', 'Count'],
    topDateExportRows(missTopDates, 'count'),
  );

  const timeAggRows = data.ddOps?.byTime?.aggregate?.data || [];
  const timeTopDates = pivotTopDatesPerStore(timeAggRows, objectColumns(timeAggRows), { topPerStore: 5, valueKind: 'metric' });
  addSection(
    'Operations quality — top dates (aggregate)',
    ['Store', 'Date', timeTopDates.valueCol || 'Value'],
    topDateExportRows(timeTopDates, 'metric'),
  );

  const timeByStoreRows = data.ddOps?.byTime?.byStore?.data || [];
  const timeByStoreTopDates = pivotTopDatesPerStore(timeByStoreRows, objectColumns(timeByStoreRows), { topPerStore: 5, valueKind: 'metric' });
  addSection(
    'Operations quality — top dates (by store export)',
    ['Store', 'Date', timeByStoreTopDates.valueCol || 'Value'],
    topDateExportRows(timeByStoreTopDates, 'metric'),
  );

  const timeAggPivot = pivotStoreByDatePeriod(timeAggRows, objectColumns(timeAggRows), { maxCols: 36 });
  addBlock('Operations quality over time (pivot)', matrixToRows('Store', timeAggPivot.rowStores, timeAggPivot.colProducts, timeAggPivot.matrix));

  const timeByStorePivot = pivotStoreByDatePeriod(timeByStoreRows, objectColumns(timeByStoreRows), { maxCols: 28 });
  addBlock('By store (time export) — pivot', matrixToRows('Store', timeByStorePivot.rowStores, timeByStorePivot.colProducts, timeByStorePivot.matrix));

  const bo = data.ddOps?.byOrder;
  const orderSheets = [
    ['Avoidable wait', bo?.avoidableWait?.data || []],
    ['Cancelled orders', bo?.cancelled?.data || []],
    ['Missing / incorrect', bo?.missingIncorrect?.data || []],
  ];
  for (const [label, blockRows] of orderSheets) {
    const cols = objectColumns(blockRows);
    const p = pivotCountByStore(blockRows, cols);
    addSection(`${label} — by store`, ['Store', 'Count'], (p.rows || []).map((r) => [r.store, r.rowCount]));

    const storeReason = pivotStoreReasonMatrix(blockRows, cols, { valueKind: 'count', maxReasonCols: 10 });
    if (storeReason?.rowKeys?.length) {
      addBlock(
        `${label} — store × reason (${storeReason.reasonCol})`,
        matrixToRows('Store', storeReason.rowKeys, storeReason.colKeys, storeReason.matrix),
      );
    }

    const topDates = pivotTopDatesPerStore(blockRows, cols, { topPerStore: 5, valueKind: 'count' });
    addSection(
      `${label} — top dates by store`,
      ['Store', 'Date', 'Count'],
      topDateExportRows(topDates, 'count'),
    );
  }
}

/** Collect flat export sections for Word/PDF rendering. */
export function collectOperationsExportSections(data) {
  const sections = [];
  appendOperationsExportSections(
    (title, headers, rows) => {
      if (rows?.length) sections.push({ type: 'table', title, headers, rows });
    },
    (title, blockRows) => {
      if (blockRows?.length) sections.push({ type: 'block', title, blockRows });
    },
    data,
  );
  return sections;
}
