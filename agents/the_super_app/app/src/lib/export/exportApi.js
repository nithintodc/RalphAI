/**
 * Resolve Google export API URLs for local dev, Cloud Run (same-origin), or legacy Apps Script.
 * Production Docker builds must not bake placeholder.invalid — use same-origin /api/* instead.
 */

const PLACEHOLDER_RE = /placeholder\.invalid/i;

function isUsableExportUrl(url) {
  const u = String(url || '').trim();
  return u.length > 0 && !PLACEHOLDER_RE.test(u);
}

/** @param {string | undefined} envUrl Vite env override */
/** @param {() => string | null} sameOriginFallback */
export function resolveSheetsExportUrl(envUrl, sameOriginFallback) {
  if (isUsableExportUrl(envUrl)) return envUrl.trim();
  return sameOriginFallback?.() ?? null;
}

/** @param {string | undefined} envDocUrl */
/** @param {string | undefined} envSheetsUrl */
/** @param {() => string | null} sameOriginFallback */
export function resolveDocExportUrl(envDocUrl, envSheetsUrl, sameOriginFallback) {
  if (isUsableExportUrl(envDocUrl)) return envDocUrl.trim();
  const sheets = String(envSheetsUrl || '').trim();
  if (isUsableExportUrl(sheets)) {
    return sheets.replace(/\/export\/?$/i, '/export-doc');
  }
  return sameOriginFallback?.() ?? null;
}
