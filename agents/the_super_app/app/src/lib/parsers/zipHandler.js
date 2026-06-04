import JSZip from 'jszip';
import Papa from 'papaparse';

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

export async function processUploadedFile(file) {
  const type = detectFileType(file.name);
  if (type === 'unknown') return { type, error: 'Unrecognized file format' };

  if (type === 'ue_financial') {
    const text = await file.text();
    const firstNl = text.indexOf('\n');
    const cleaned = firstNl >= 0 ? text.slice(firstNl + 1) : text;
    const parsed = parseCsv(cleaned);
    return { type, data: parsed };
  }

  const zip = await JSZip.loadAsync(file);
  const results = {};
  for (const [filename, entry] of Object.entries(zip.files)) {
    if (entry.dir || !filename.toLowerCase().endsWith('.csv')) continue;
    const lower = filename.toLowerCase();
    if (type === 'dd_financial' && !lower.includes('financial_detailed')) {
      continue;
    }
    const content = await entry.async('string');
    const parsed = parseCsv(content);

    if (type === 'dd_financial') {
      if (lower.includes('financial_detailed')) results.detailed = parsed;
      else if (lower.includes('financial_simplified')) results.simplified = parsed;
      else if (lower.includes('error_charges')) results.errorCharges = parsed;
      else if (lower.includes('payout_summary')) results.payoutSummary = parsed;
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
