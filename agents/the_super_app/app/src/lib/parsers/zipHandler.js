import JSZip from 'jszip';
import Papa from 'papaparse';

/** V8/Chrome cannot build strings much above ~512MB; leave headroom for parsing. */
const MAX_CSV_UNCOMPRESSED_BYTES = 450 * 1024 * 1024;

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function csvTooLargeMessage(filename, uncompressedBytes) {
  return (
    `${filename} is too large to parse in the browser (${formatBytes(uncompressedBytes)} uncompressed; ` +
    `limit ~${formatBytes(MAX_CSV_UNCOMPRESSED_BYTES)}). ` +
    'Export a shorter date range from DoorDash (e.g. 3 months at a time), or use a smaller operator export.'
  );
}

function entryUncompressedSize(entry) {
  if (typeof entry.uncompressedSize === 'number') return entry.uncompressedSize;
  return entry?._data?.uncompressedSize ?? 0;
}

/** Skip AppleDouble / resource-fork junk that macOS adds inside ZIPs. */
function shouldSkipZipEntry(filename) {
  const lower = String(filename || '').toLowerCase().replace(/\\/g, '/');
  return lower.includes('__macosx/') || lower.includes('/._') || lower.startsWith('._');
}

export function detectFileType(filename) {
  const lower = filename.toLowerCase();
  if (lower.startsWith('financial_') && lower.endsWith('.zip')) return 'dd_financial';
  if (lower.startsWith('marketing_') && lower.endsWith('.zip')) return 'dd_marketing';
  if (lower.startsWith('product_mix_') && lower.endsWith('.zip')) return 'dd_product_mix';
  if (lower.startsWith('sales_') && lower.endsWith('.zip')) return 'dd_sales';
  if (lower.includes('operations_quality_viewbyorder') && lower.endsWith('.zip')) return 'dd_ops_order';
  if (lower.includes('operations_quality_viewbystore') && lower.endsWith('.zip')) return 'dd_ops_store';
  if (lower.includes('operations_quality_viewbytime') && lower.endsWith('.zip')) return 'dd_ops_time';
  if (lower.endsWith('.csv')) return 'ue_financial';
  return 'unknown';
}

export async function extractZip(file) {
  const zip = await JSZip.loadAsync(file);
  const csvFiles = {};
  for (const [name, entry] of Object.entries(zip.files)) {
    if (!entry.dir && name.toLowerCase().endsWith('.csv')) {
      csvFiles[name] = await entry.async('string');
    }
  }
  return csvFiles;
}

export function parseCsv(csvString) {
  const result = Papa.parse(csvString, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
    transformHeader: (header) => String(header ?? '').trim(),
    transform: (value) => (typeof value === 'string' ? value.trim() : value),
  });
  const rows = Array.isArray(result.data) ? result.data : [];
  return { data: rows, columns: Object.keys(rows[0] || {}) };
}

function normalizeUeHeaderCell(cell) {
  return String(cell ?? '')
    .replace(/\uFEFF/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

/** True when row is UE short header row (row 2 in standard exports). */
export function isUeFinancialHeaderRow(fields) {
  if (!fields?.length) return false;
  const norms = fields.map(normalizeUeHeaderCell);
  const storeName = norms[0] || '';
  if (storeName !== 'store name') return false;
  return norms.includes('order date') && norms.some((n) => n.includes('sales') && n.includes('excl'));
}

/**
 * UberEats financial CSV: row 1 = long descriptions, row 2 = column names, row 3+ = data.
 * Also skips optional banner rows (e.g. "[N more lines]") before the header row.
 */
export function parseUeFinancialCsv(csvString) {
  const parsed = Papa.parse(csvString, {
    header: false,
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  const matrix = Array.isArray(parsed.data) ? parsed.data : [];
  let headerIdx = matrix.findIndex((row) => isUeFinancialHeaderRow(row));
  if (headerIdx < 0 && matrix.length >= 2) {
    headerIdx = 1;
  }
  if (headerIdx < 0 || headerIdx >= matrix.length) {
    return { data: [], columns: [] };
  }

  const columns = matrix[headerIdx].map((h) => String(h ?? '').trim());
  const data = [];
  for (let i = headerIdx + 1; i < matrix.length; i += 1) {
    const fields = matrix[i];
    if (!fields?.length) continue;
    const row = {};
    for (let j = 0; j < columns.length; j += 1) {
      const key = columns[j];
      if (!key) continue;
      const v = fields[j];
      row[key] = typeof v === 'string' ? v.trim() : v ?? '';
    }
    data.push(row);
  }
  return { data, columns };
}

/** DD financial detailed signature — works for renamed / re-saved CSVs inside arbitrary zips. */
function looksLikeDdFinancialColumns(columns) {
  const norms = new Set((columns || []).map((c) => String(c ?? '').replace(/\uFEFF/g, '').trim().toLowerCase()));
  return (
    norms.has('transaction type')
    && norms.has('doordash order id')
    && norms.has('subtotal')
    && (norms.has('timestamp local date') || norms.has('timestamp local time'))
  );
}

export async function processUploadedFile(file) {
  let type = detectFileType(file.name);
  // Zips with non-standard names (e.g. edited exports re-zipped by hand): treat as a
  // DD financial candidate and confirm below by CSV header signature.
  const isHeaderSniffedZip = type === 'unknown' && file.name.toLowerCase().endsWith('.zip');
  if (isHeaderSniffedZip) type = 'dd_financial';
  if (type === 'unknown') return { type, error: 'Unrecognized file format' };

  if (type === 'ue_financial') {
    const text = await file.text();
    const parsed = parseUeFinancialCsv(text);
    return { type, data: parsed };
  }

  const zip = await JSZip.loadAsync(file);
  const results = {};
  const unmatchedCsvs = [];
  for (const [filename, entry] of Object.entries(zip.files)) {
    if (entry.dir || !filename.toLowerCase().endsWith('.csv')) continue;
    if (shouldSkipZipEntry(filename)) continue;
    const lower = filename.toLowerCase();
    const uncompressed = entryUncompressedSize(entry);
    if (uncompressed > MAX_CSV_UNCOMPRESSED_BYTES) {
      return { type, error: csvTooLargeMessage(filename, uncompressed) };
    }
    let content;
    try {
      content = await entry.async('string');
    } catch (err) {
      const msg = String(err?.message || err || '');
      if (msg.includes('Invalid string length')) {
        return {
          type,
          error: csvTooLargeMessage(filename, uncompressed || file.size * 4),
        };
      }
      throw err;
    }
    const parsed = parseCsv(content);

    if (type === 'dd_financial') {
      if (lower.includes('financial_detailed')) results.detailed = parsed;
      else if (lower.includes('financial_simplified')) results.simplified = parsed;
      else if (lower.includes('error_charges')) results.errorCharges = parsed;
      else if (lower.includes('payout_summary')) results.payoutSummary = parsed;
      else unmatchedCsvs.push(parsed);
    } else if (type === 'dd_marketing') {
      if (lower.includes('promotion')) results.promotion = parsed;
      if (lower.includes('sponsored')) results.sponsored = parsed;
    } else if (type === 'dd_product_mix') {
      if (lower.includes('product_mix')) results.productMix = parsed;
    } else if (type === 'dd_sales') {
      if (lower.includes('sales_by_order')) results.byOrder = parsed;
      else if (lower.includes('sales_by_time')) results.byTime = parsed;
      else if (lower.includes('sales_by_store')) results.byStore = parsed;
    } else if (type === 'dd_ops_order') {
      if (lower.includes('avoidable_wait')) results.avoidableWait = parsed;
      if (lower.includes('cancelled')) results.cancelled = parsed;
      if (lower.includes('missing_incorrect')) results.missingIncorrect = parsed;
    } else if (type === 'dd_ops_store') {
      if (lower.includes('cancellation')) results.cancellations = parsed;
      if (lower.includes('downtime')) results.downtime = parsed;
      if (lower.includes('missingandincorrect')) results.missingIncorrect = parsed;
    } else if (type === 'dd_ops_time') {
      if (lower.includes('productmix')) results.productMix = parsed;
      if (lower.includes('bystore')) results.byStore = parsed;
      if (lower.includes('aggregate')) results.aggregate = parsed;
    }
  }

  if (type === 'dd_sales') {
    if (results.byOrder) return { type: 'dd_sales_by_order', data: results.byOrder };
    if (results.byTime) return { type: 'dd_sales_by_time', data: results.byTime };
    if (results.byStore) return { type: 'dd_sales_by_store', data: results.byStore };
  }

  if (type === 'dd_financial' && !results.detailed?.data?.length) {
    if (results.simplified?.data?.length) {
      results.detailed = results.simplified;
    } else {
      // Renamed CSV inside the zip — accept it when the header matches DD financial.
      const fallback = unmatchedCsvs.find((p) => p?.data?.length && looksLikeDdFinancialColumns(p.columns));
      if (fallback) {
        results.detailed = fallback;
      } else if (isHeaderSniffedZip) {
        return { type: 'unknown', error: 'Unrecognized file format' };
      } else {
        return {
          type,
          error: 'No FINANCIAL_DETAILED or FINANCIAL_SIMPLIFIED transactions found in ZIP (check export or re-download without macOS resource forks).',
        };
      }
    }
  }

  return { type, data: results };
}

export function getFileTypeLabel(type) {
  const labels = {
    dd_financial: 'DoorDash Financial',
    dd_marketing: 'DoorDash Marketing',
    dd_product_mix: 'DoorDash Product Mix',
    dd_sales: 'DoorDash Sales',
    dd_sales_by_order: 'DoorDash Sales (by Order)',
    dd_sales_by_time: 'DoorDash Sales (by Time)',
    dd_sales_by_store: 'DoorDash Sales (by Store)',
    dd_ops_order: 'DoorDash Ops (by Order)',
    dd_ops_store: 'DoorDash Ops (by Store)',
    dd_ops_time: 'DoorDash Ops (by Time)',
    ue_financial: 'UberEats Financial',
  };
  return labels[type] || type;
}

export function getFileCategory(type) {
  if (type.startsWith('dd_financial') || type === 'ue_financial') return 'Financials';
  if (type.startsWith('dd_marketing')) return 'Marketing';
  if (type.startsWith('dd_ops')) return 'Operations';
  if (type.startsWith('dd_product')) return 'Product Mix';
  if (type.startsWith('dd_sales')) return 'Sales';
  return 'Other';
}

export const ALL_FILE_TYPES = [
  { key: 'dd_financial', label: 'Financial', platform: 'dd', category: 'Financials' },
  { key: 'dd_marketing', label: 'Marketing', platform: 'dd', category: 'Marketing' },
  { key: 'dd_product_mix', label: 'Product Mix', platform: 'dd', category: 'Product Mix' },
  { key: 'dd_sales_by_order', label: 'Sales (by Order)', platform: 'dd', category: 'Sales' },
  { key: 'dd_sales_by_time', label: 'Sales (by Time)', platform: 'dd', category: 'Sales' },
  { key: 'dd_sales_by_store', label: 'Sales (by Store)', platform: 'dd', category: 'Sales' },
  { key: 'dd_ops_order', label: 'Ops (by Order)', platform: 'dd', category: 'Operations' },
  { key: 'dd_ops_store', label: 'Ops (by Store)', platform: 'dd', category: 'Operations' },
  { key: 'dd_ops_time', label: 'Ops (by Time)', platform: 'dd', category: 'Operations' },
  { key: 'ue_financial', label: 'Financial Export', platform: 'ue', category: 'Financials' },
];
