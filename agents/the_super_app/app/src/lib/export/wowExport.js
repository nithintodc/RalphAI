import * as XLSX from 'xlsx';
import { xf } from '../utils/formatters';
import { buildExportFilename } from './exportFilename.js';
import { withSheetSummary, formatStoreTagLabel } from './exportSheetSummaries.js';
import { formatCompactDateRange } from '../utils/dateUtils';
import { resolveWeekStartsOn, getWeekDefinitionById } from '../utils/weekDefinition';
import {
  buildWowAnalysisRangeTable,
  buildWowGroupSalesTables,
} from '../engine/wowWeeklySales';
import { WOW_TABLE_METRICS } from '../engine/wowMetrics';

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

function formatExportValue(value, kind) {
  if (value == null || !Number.isFinite(value)) return '';
  if (kind === 'int') return xf.int(value);
  if (kind === 'usd2') return xf.usd2(value);
  return xf.usd(value);
}

function weeklyBreakdownHeaders() {
  const headers = ['Week', 'Date range'];
  for (const metric of WOW_TABLE_METRICS) {
    headers.push(
      metric.label,
      `${metric.label} WoW Δ`,
      `${metric.label} WoW %`,
      `${metric.label} LY`,
      `${metric.label} YoY Δ`,
      `${metric.label} YoY %`,
    );
  }
  return headers;
}

function weeklyBreakdownRows(table) {
  return (table?.rows || []).map((row) => {
    const out = [row.label, row.rangeLabel];
    for (const metric of WOW_TABLE_METRICS) {
      const m = row.metrics?.[metric.key] || {};
      out.push(
        formatExportValue(m.value, metric.kind),
        formatExportValue(m.delta, metric.kind),
        m.growthPct != null ? xf.deltaPct(m.growthPct) : '',
        formatExportValue(m.ly, metric.kind),
        formatExportValue(m.yoyDelta, metric.kind),
        m.yoyPct != null ? xf.deltaPct(m.yoyPct) : '',
      );
    }
    return out;
  });
}

function groupTableHeaders(weekColumns, metricLabel) {
  return [
    'Store',
    ...weekColumns.map((col) => `${col.label} (${col.rangeLabel})`),
    `${metricLabel} Total`,
    `${metricLabel} Average`,
  ];
}

function groupTableRows(group, metricKind) {
  if (!group?.rows?.length) return [];
  const cols = group.weekColumns || [];
  const dataRows = group.rows.map((row) => {
    const weekVals = cols.map((col) => formatExportValue(row.weeks[col.key], metricKind));
    const total = cols.reduce((sum, col) => sum + (row.weeks[col.key] || 0), 0);
    const avg = cols.length ? total / cols.length : 0;
    return [row.label, ...weekVals, formatExportValue(total, metricKind), formatExportValue(avg, metricKind)];
  });

  const totalRow = ['Total'];
  for (const col of cols) {
    totalRow.push(formatExportValue(group.totals?.[col.key], metricKind));
  }
  const grandTotal = cols.reduce((sum, col) => sum + (group.totals?.[col.key] || 0), 0);
  totalRow.push(formatExportValue(grandTotal, metricKind), '');

  const avgRow = ['Average'];
  for (const col of cols) {
    avgRow.push(formatExportValue(group.averages?.[col.key], metricKind));
  }
  avgRow.push('', '');

  return [...dataRows, totalRow, avgRow];
}

function buildFullGroupRows(shared, groupTag, weekLabel, rangeLabel) {
  const rows = [
    [`Group ${groupTag} · ${formatStoreTagLabel(groupTag) || groupTag}`],
    ['Combined DoorDash + Uber Eats', weekLabel, rangeLabel],
  ];
  for (const metric of WOW_TABLE_METRICS) {
    const tables = buildWowGroupSalesTables({
      ...shared,
      metricKey: metric.key,
    });
    const group = groupTag === 'A' ? tables.groupA : tables.groupB;
    addSection(
      rows,
      metric.label,
      groupTableHeaders(group.weekColumns, metric.label),
      groupTableRows(group, metric.kind),
    );
  }
  return rows;
}

/**
 * Export WoW analysis tables (weekly breakdown + Group A/B) to Excel.
 */
export function exportWowReport(data, config) {
  const rangeStart = config.ddPostStart || config.uePostStart;
  const rangeEnd = config.ddPostEnd || config.uePostEnd;
  if (!rangeStart || !rangeEnd) {
    throw new Error('Set an analysis date range in Config before exporting WoW.');
  }

  const weekStartsOn = resolveWeekStartsOn(config.weekDefinitionId);
  const weekLabel = getWeekDefinitionById(config.weekDefinitionId).label;
  const rangeLabel = formatCompactDateRange(rangeStart, rangeEnd);

  const shared = {
    ddFinancial: data.ddFinancial,
    ueFinancial: data.ueFinancial,
    ddMarketing: data.ddMarketing,
    config,
    platform: 'combined',
    storeScope: 'total',
    weekStartsOn,
    rangeStart,
    rangeEnd,
    storeTables: data.storeTables,
  };

  const breakdown = buildWowAnalysisRangeTable(shared);
  const breakdownData = weeklyBreakdownRows(breakdown);
  const breakdownRows = [
    ['WoW weekly breakdown', weekLabel, rangeLabel],
    [],
    ...(breakdownData.length
      ? [weeklyBreakdownHeaders(), ...breakdownData]
      : [['No weeks in analysis range']]),
  ];

  const groupARows = buildFullGroupRows(shared, 'A', weekLabel, rangeLabel);
  const groupBRows = buildFullGroupRows(shared, 'B', weekLabel, rangeLabel);

  const wb = XLSX.utils.book_new();

  const wsBreakdown = XLSX.utils.aoa_to_sheet(
    withSheetSummary('WoW Weekly Breakdown', breakdownRows, data, config),
  );
  wsBreakdown['!cols'] = estimateColumnWidths(breakdownRows);
  XLSX.utils.book_append_sheet(wb, wsBreakdown, cleanSheetName('WoW Breakdown'));

  const wsA = XLSX.utils.aoa_to_sheet(withSheetSummary('Group A WoW', groupARows, data, config));
  wsA['!cols'] = estimateColumnWidths(groupARows);
  XLSX.utils.book_append_sheet(wb, wsA, cleanSheetName('Group A'));

  const wsB = XLSX.utils.aoa_to_sheet(withSheetSummary('Group B WoW', groupBRows, data, config));
  wsB['!cols'] = estimateColumnWidths(groupBRows);
  XLSX.utils.book_append_sheet(wb, wsB, cleanSheetName('Group B'));

  const filename = buildExportFilename(config, 'wow_excel', { ext: 'xlsx' });
  XLSX.writeFile(wb, filename);
  return { filename };
}
