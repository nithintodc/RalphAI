import { format } from 'date-fns';

/** Filesystem-safe operator slug for export names. */
export function sanitizeOperatorForFilename(operatorName) {
  let safe = String(operatorName || '').trim();
  if (!safe) return 'operator';
  safe = safe.replace(/[@./\\,;:'"&]+/g, '_');
  safe = safe.replace(/\s+/g, '_');
  safe = safe.replace(/[^a-zA-Z0-9_-]+/g, '_');
  while (safe.includes('__')) safe = safe.replaceAll('__', '_');
  safe = safe.replace(/^_|_$/g, '');
  return safe.slice(0, 80) || 'operator';
}

export function exportTimestamp(date = new Date()) {
  return format(date, 'yyyyMMdd_HHmmss');
}

/**
 * Build export name: `<OPERATORNAME>_<TIMESTAMP>_<FILETYPE>[.ext]`
 * @param {object} config — expects operatorName
 * @param {string} fileType — e.g. excel, doc, pdf, register_dd_excel
 */
export function buildExportFilename(config, fileType, opts = {}) {
  const op = sanitizeOperatorForFilename(config?.operatorName);
  const ts = opts.ts || exportTimestamp(opts.date);
  const type = String(fileType || 'export').replace(/[^a-zA-Z0-9_-]/g, '_');
  const base = `${op}_${ts}_${type}`;
  if (opts.ext) {
    const ext = opts.ext.startsWith('.') ? opts.ext : `.${opts.ext}`;
    return `${base}${ext}`;
  }
  return base;
}
