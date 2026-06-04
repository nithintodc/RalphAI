/**
 * Column detection + pivots for DoorDash Operations / Product Mix CSV exports
 * (dynamic headers — we match by keyword patterns.)
 */

const STORE_ID_ORDER = [
  /^store\s*id$/i,
  /^merchant\s*store\s*id$/i,
  /^merchant\s*id$/i,
  /^external\s*store\s*id/i,
];

const STORE_ORDER = [
  ...STORE_ID_ORDER,
  /^external\s*store/i,
  /^store$/i,
  /store\s*id/i,
  /store\s*name/i,
  /business\s*name/i,
  /merchant\s*name/i,
];

const PRODUCT_ORDER = [
  /^item\s*name$/i,
  /^menu\s*item/i,
  /^product\s*name$/i,
  /^item$/i,
  /item\s*name/i,
  /item\s*description/i,
  /product\s*description/i,
  /^sku$/i,
  /menu\s*item\s*name/i,
];

const METRIC_PATTERNS = [
  [/item\s*sales/i, 5],
  [/sales/i, 4],
  [/revenue/i, 4],
  [/net\s*sales/i, 4],
  [/quantity/i, 3],
  [/qty/i, 3],
  [/units?\s*sold/i, 3],
  [/orders/i, 2],
  [/count/i, 1],
];

/** First column matching the first matching regex (order = priority). */
export function pickColumnByRegexOrder(columns, regexList) {
  if (!columns?.length) return null;
  for (const re of regexList) {
    for (const col of columns) {
      if (re.test(String(col || '').trim())) return col;
    }
  }
  return null;
}

export function pickStoreColumn(columns) {
  return pickColumnByRegexOrder(columns, STORE_ORDER);
}

export function pickProductColumn(columns) {
  return pickColumnByRegexOrder(columns, PRODUCT_ORDER);
}

const CATEGORY_ORDER = [
  /downtime\s*category/i,
  /downtime\s*type/i,
  /down\s*time\s*category/i,
  /category/i,
  /subcategory/i,
  /issue\s*type/i,
  /error\s*type/i,
  /cancellation\s*category/i,
  /reason\s*category/i,
  /^type$/i,
  /reason/i,
  /bucket/i,
  /segment/i,
  /channel/i,
];

/** Columns that look like duration / downtime metrics (excluding one column e.g. store). */
export function pickDowntimeValueColumns(columns, excludeCol) {
  const ex = new Set(excludeCol != null && excludeCol !== '' ? [excludeCol] : []);
  return pickDowntimeValueColumnsEx(columns, ex);
}

/** Duration-like columns excluding any in `excludeSet`. */
export function pickDowntimeValueColumnsEx(columns, excludeSet) {
  if (!columns?.length) return [];
  const ex = excludeSet instanceof Set ? excludeSet : new Set(excludeSet || []);
  const dur = /downtime|duration|offline|outage|time\s*down|down\s*time|minutes?\s*down|hours?\s*down/i;
  return columns.filter((c) => !ex.has(c) && dur.test(String(c)));
}

export function pickCategoryColumn(columns, exclude = []) {
  const ex = new Set(exclude);
  for (const re of CATEGORY_ORDER) {
    for (const col of columns) {
      if (ex.has(col)) continue;
      if (re.test(String(col || '').trim())) return col;
    }
  }
  return null;
}

/** Heuristic categorical columns for pivots (not IDs, bounded cardinality). */
export function inferCategoricalColumns(rows, columns, { exclude = [], maxUniq = 90, minUniq = 2, sample = 800 } = {}) {
  const ex = new Set(exclude);
  const idLike = /(^id$|_id$|id\s|uuid|^order\s*id|workflow|external)/i;
  const out = [];
  const slice = rows.slice(0, sample);
  for (const col of columns) {
    if (ex.has(col) || idLike.test(String(col))) continue;
    const vals = new Set();
    let n = 0;
    for (const row of slice) {
      const v = row[col];
      if (v == null || v === '') continue;
      n += 1;
      vals.add(String(v).trim());
    }
    if (n < 8) continue;
    const u = vals.size;
    if (u < minUniq || u > maxUniq) continue;
    if (u / slice.length > 0.55) continue;
    out.push({ col, unique: u, nonNull: n });
  }
  out.sort((a, b) => a.unique - b.unique || b.nonNull - a.nonNull);
  return out;
}

/**
 * Parse a cell value to minutes. Handles numbers, "1d 2h 30m", H:MM, H:MM:SS, Excel day fractions.
 */
export function parseDurationToMinutes(raw) {
  if (raw == null || raw === '') return 0;
  if (typeof raw === 'number' && !Number.isNaN(raw)) {
    if (raw > 0 && raw < 1) return Math.round(raw * 24 * 60);
    return Math.abs(raw);
  }
  const s0 = String(raw).trim();
  if (!s0 || s0 === '-' || s0.toLowerCase() === 'n/a') return 0;

  const plain = Number(s0.replace(/,/g, ''));
  if (!Number.isNaN(plain) && /^[\d.,\s]+$/.test(s0.replace(/,/g, ''))) {
    return Math.abs(plain);
  }

  const s = s0.toLowerCase();
  let mins = 0;
  const d = s.match(/(\d+(?:\.\d+)?)\s*d(?:ay|ays)?\b/);
  if (d) mins += parseFloat(d[1]) * 1440;
  const h = s.match(/(\d+(?:\.\d+)?)\s*h(?:our|ours|rs?)?\b/);
  if (h) mins += parseFloat(h[1]) * 60;
  const m = s.match(/(\d+(?:\.\d+)?)\s*m(?:in|ins|inute|inutes)?\b/);
  if (m) mins += parseFloat(m[1]);

  if (mins > 0) return mins;

  const timeMatch = s0.match(/^(\d+):(\d{2})(?::(\d{2}))?$/);
  if (timeMatch) {
    const p1 = parseInt(timeMatch[1], 10);
    const p2 = parseInt(timeMatch[2], 10);
    const p3 = timeMatch[3] != null ? parseInt(timeMatch[3], 10) : null;
    if (p3 != null) return p1 * 60 + p2 + p3 / 60;
    return p1 * 60 + p2;
  }

  return 0;
}

export function minutesToDayHourMinute(totalMinutes) {
  const t = Math.max(0, Math.round(Number(totalMinutes) || 0));
  const days = Math.floor(t / 1440);
  const hours = Math.floor((t % 1440) / 60);
  const minutes = t % 60;
  return { days, hours, minutes, totalMinutes: t };
}

const KEY_SEP = '\x1e';

export function pivotDowntimeByStore(rows, columns) {
  const storeCol = pickStoreColumn(columns);
  if (!storeCol) return { storeCol: null, downtimeCols: [], rows: [] };
  const agg = pivotDowntimeByDimension(rows, columns, storeCol);
  return {
    storeCol,
    downtimeCols: agg.downtimeCols,
    rows: agg.rows.map((r) => ({ store: r.label, days: r.days, hours: r.hours, minutes: r.minutes, totalMinutes: r.totalMinutes, lineCount: r.lineCount })),
  };
}

/** Sum downtime minutes by any categorical dimension (store, category, date bucket, …). */
export function pivotDowntimeByDimension(rows, columns, dimCol) {
  if (!rows?.length || !dimCol) return { dimCol: null, downtimeCols: [], rows: [] };
  const downtimeCols = resolveDowntimeSumColumns(rows, columns, new Set([dimCol]));
  if (!downtimeCols.length) return { dimCol, downtimeCols: [], rows: [] };
  const map = new Map();
  for (const row of rows) {
    const label = String(row[dimCol] || '').trim() || '—';
    const mins = downtimeCols.reduce((s, c) => s + parseDurationToMinutes(row[c]), 0);
    if (!map.has(label)) map.set(label, { totalMinutes: 0, lineCount: 0 });
    const agg = map.get(label);
    agg.totalMinutes += mins;
    agg.lineCount += 1;
  }
  const rowsOut = [...map.entries()].map(([label, { totalMinutes, lineCount }]) => {
    const { days, hours, minutes } = minutesToDayHourMinute(totalMinutes);
    return { label, days, hours, minutes, totalMinutes, lineCount };
  });
  rowsOut.sort((a, b) => b.totalMinutes - a.totalMinutes);
  return { dimCol, downtimeCols, rows: rowsOut };
}

export function resolveDowntimeSumColumns(rows, columns, excludeSet) {
  const ex = excludeSet instanceof Set ? excludeSet : new Set(excludeSet || []);
  let dow = pickDowntimeValueColumnsEx(columns, ex);
  if (!dow.length) {
    dow = columns.filter((c) => {
      if (ex.has(c)) return false;
      if (!/downtime|duration|offline|outage|minute|hour|time\s*down|down\s*time/i.test(String(c))) return false;
      const sample = rows.slice(0, 25).reduce((s, r) => s + parseDurationToMinutes(r[c]), 0);
      return sample > 0;
    });
  }
  return dow;
}

function numericRatio(rows, col, sample = 400) {
  const slice = rows.slice(0, sample);
  let ok = 0;
  let n = 0;
  for (const row of slice) {
    const v = row[col];
    if (v == null || v === '') continue;
    n += 1;
    const num = Number(String(v).replace(/[$,%\s,]/g, ''));
    if (!Number.isNaN(num)) ok += 1;
  }
  return n ? ok / n : 0;
}

export function pickMetricColumn(rows, columns, exclude) {
  const ex = new Set(exclude || []);
  let best = null;
  let bestScore = -1;
  for (const col of columns) {
    if (ex.has(col)) continue;
    let score = numericRatio(rows, col) * 20;
    if (score < 4) continue;
    const name = String(col);
    for (const [re, w] of METRIC_PATTERNS) {
      if (re.test(name)) score += w;
    }
    if (score > bestScore) {
      bestScore = score;
      best = col;
    }
  }
  if (!best) {
    for (const col of columns) {
      if (ex.has(col)) continue;
      const r = numericRatio(rows, col) * 20;
      if (r > bestScore) {
        bestScore = r;
        best = col;
      }
    }
  }
  if (!best || numericRatio(rows, best) < 0.08) return null;
  return best;
}

const COUNT_SUM_PATTERNS = [
  /\b#?\s*of\s*cancellations?\b/i,
  /\bcancellations?\s*(count|#)?\b/i,
  /\btotal\s*cancellations?\b/i,
  /\btotal\s*missing\b/i,
  /\bnumber\s+of\b/i,
  /\bcount\b/i,
  /\bqty\b/i,
  /\bquantity\b/i,
  /\bevents?\b/i,
];

/**
 * Optional numeric column to sum per store (aggregated exports).
 * Excludes obvious id/time columns even if name contains "order".
 */
export function pickCountSumColumn(rows, columns, excludeCol) {
  if (!rows?.length || !columns?.length) return null;
  const ex = new Set([excludeCol].filter(Boolean));
  let best = null;
  let bestScore = -1;
  for (const col of columns) {
    if (ex.has(col)) continue;
    const name = String(col || '').trim();
    const lower = name.toLowerCase();
    if (/order\s*id|workflow|uuid|timestamp|local\s*date|store\s*id|merchant\s*id/i.test(lower)) continue;
    if (!COUNT_SUM_PATTERNS.some((re) => re.test(lower))) continue;
    const ratio = numericRatio(rows, col);
    if (ratio < 0.35) continue;
    let score = ratio * 12;
    if (/\bpercent|ratio|%\b/.test(lower)) score -= 6;
    if (score > bestScore) {
      bestScore = score;
      best = col;
    }
  }
  return best;
}

/**
 * Store → event totals: Σ numeric “count” column when present, else row count per store.
 * Output uses `rowCount` to avoid clashing with CSV fields named `Count`.
 */
export function pivotCountByStore(rows, columns) {
  const storeCol = pickStoreColumn(columns);
  if (!storeCol) return { storeCol: null, sumCol: null, rows: [] };
  const sumCol = pickCountSumColumn(rows, columns, storeCol);
  const map = new Map();
  if (sumCol) {
    for (const row of rows) {
      const store = String(row[storeCol] || '').trim() || '—';
      const raw = row[sumCol];
      const n = Number(String(raw ?? '').replace(/[$,%\s,]/g, ''));
      const add = Number.isFinite(n) ? n : 0;
      map.set(store, (map.get(store) || 0) + add);
    }
  } else {
    for (const row of rows) {
      const store = String(row[storeCol] || '').trim() || '—';
      map.set(store, (map.get(store) || 0) + 1);
    }
  }
  const out = [...map.entries()].map(([store, rowCount]) => ({ store, rowCount }));
  out.sort((a, b) => b.rowCount - a.rowCount);
  return { storeCol, sumCol, rows: out };
}

const DATE_ORDER = [/week\s*ending/i, /reporting\s*week/i, /^week$/i, /\bweek\b/i, /\bdate\b/i, /^day$/i, /\bperiod\b/i];

export function pickDateColumn(columns, exclude = []) {
  const ex = new Set(exclude);
  for (const re of DATE_ORDER) {
    for (const col of columns) {
      if (ex.has(col)) continue;
      if (re.test(String(col || '').trim())) return col;
    }
  }
  return null;
}

function chronoSortKeys(keys) {
  return [...keys].sort((a, b) => {
    const da = Date.parse(a);
    const db = Date.parse(b);
    if (!Number.isNaN(da) && !Number.isNaN(db)) return da - db;
    return String(a).localeCompare(String(b));
  });
}

/**
 * @param {'volume'|'chrono'} colMode - volume: top columns by total value; chrono: last maxCols periods in time order
 */
export function pivotRowColValue(rows, rowKey, colKey, valueKey, { maxCols = 28, colMode = 'volume' } = {}) {
  const empty = {
    rowDim: rowKey,
    colDim: colKey,
    valueCol: valueKey,
    rowKeys: [],
    colKeys: [],
    matrix: [],
  };
  if (!rows?.length || !rowKey || !colKey || !valueKey) return empty;

  const pairTotals = new Map();
  const colTotals = new Map();
  const rowSet = new Set();

  for (const row of rows) {
    const rk = String(row[rowKey] || '').trim() || '—';
    const ck = String(row[colKey] || '').trim() || '—';
    const v = Number(String(row[valueKey]).replace(/[$,%\s,]/g, '')) || 0;
    rowSet.add(rk);
    const k = rk + KEY_SEP + ck;
    pairTotals.set(k, (pairTotals.get(k) || 0) + v);
    colTotals.set(ck, (colTotals.get(ck) || 0) + v);
  }

  let colKeys;
  if (colMode === 'chrono') {
    const ordered = chronoSortKeys([...colTotals.keys()]);
    colKeys = ordered.slice(-maxCols);
  } else {
    colKeys = [...colTotals.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxCols)
      .map(([c]) => c);
  }
  const colSet = new Set(colKeys);

  const rowKeys = [...rowSet].sort((a, b) => a.localeCompare(b));

  const matrix = rowKeys.map((rk) => {
    const cells = colKeys.map((ck) => pairTotals.get(rk + KEY_SEP + ck) || 0);
    let other = 0;
    for (const [k, val] of pairTotals) {
      const i = k.indexOf(KEY_SEP);
      const r = k.slice(0, i);
      const c = k.slice(i + KEY_SEP.length);
      if (r !== rk) continue;
      if (!colSet.has(c)) other += val;
    }
    return colMode === 'volume' ? [...cells, other] : cells;
  });

  const outColKeys = colMode === 'volume' ? [...colKeys, 'Other'] : colKeys;

  return {
    rowDim: rowKey,
    colDim: colKey,
    valueCol: valueKey,
    rowKeys,
    colKeys: outColKeys,
    matrix,
  };
}

/** Store × product (or item) matrix; top products by volume as columns + Other. */
export function pivotStoreByProduct(rows, columns, { maxProductCols = 28 } = {}) {
  const storeCol = pickStoreColumn(columns);
  const productCol = pickProductColumn(columns);
  if (!storeCol || !productCol) {
    return { storeCol, productCol, valueCol: null, rowStores: [], colProducts: [], matrix: [] };
  }
  const valueCol = pickMetricColumn(rows, columns, [storeCol, productCol]);
  if (!valueCol) {
    return { storeCol, productCol, valueCol: null, rowStores: [], colProducts: [], matrix: [] };
  }
  const p = pivotRowColValue(rows, storeCol, productCol, valueCol, { maxCols: maxProductCols, colMode: 'volume' });
  return {
    storeCol,
    productCol,
    valueCol,
    rowStores: p.rowKeys,
    colProducts: p.colKeys,
    matrix: p.matrix,
  };
}

/** Product × store matrix: products as rows, top stores by volume as columns + Other. */
export function pivotProductByStore(rows, columns, { maxStoreCols = 28 } = {}) {
  const storeCol = pickStoreColumn(columns);
  const productCol = pickProductColumn(columns);
  if (!storeCol || !productCol) {
    return { storeCol, productCol, valueCol: null, rowProducts: [], colStores: [], matrix: [] };
  }
  const valueCol = pickMetricColumn(rows, columns, [storeCol, productCol]);
  if (!valueCol) {
    return { storeCol, productCol, valueCol: null, rowProducts: [], colStores: [], matrix: [] };
  }
  const p = pivotRowColValue(rows, productCol, storeCol, valueCol, { maxCols: maxStoreCols, colMode: 'volume' });
  return {
    storeCol,
    productCol,
    valueCol,
    rowProducts: p.rowKeys,
    colStores: p.colKeys,
    matrix: p.matrix,
  };
}

/** One-way rollup: sum metric by a single dimension (store or product totals). */
export function pivotOneWaySum(rows, dimCol, valueCol) {
  if (!rows?.length || !dimCol || !valueCol) {
    return { dimCol, valueCol, keys: [], values: [], total: 0 };
  }
  const map = new Map();
  for (const row of rows) {
    const key = String(row[dimCol] || '').trim() || '—';
    const v = Number(String(row[valueCol]).replace(/[$,%\s,]/g, '')) || 0;
    map.set(key, (map.get(key) || 0) + v);
  }
  const entries = [...map.entries()].sort((a, b) => b[1] - a[1]);
  return {
    dimCol,
    valueCol,
    keys: entries.map(([k]) => k),
    values: entries.map(([, v]) => v),
    total: entries.reduce((s, [, v]) => s + v, 0),
  };
}

function isStoreLikeColumn(col) {
  return /store|merchant|business\s*name|restaurant\s*name/i.test(String(col || ''));
}

function isRedundantStorePair(rowDim, colDim) {
  return isStoreLikeColumn(rowDim) && isStoreLikeColumn(colDim) && rowDim !== colDim;
}

/** Sort pivot rows by label or row total. */
export function sortPivotRows({ rowKeys, colKeys, matrix }, { by = 'total', dir = 'desc' } = {}) {
  if (!rowKeys?.length) return { rowKeys: [], colKeys: colKeys || [], matrix: [] };
  const indices = rowKeys.map((_, i) => i);
  indices.sort((a, b) => {
    if (by === 'name') {
      const cmp = String(rowKeys[a]).localeCompare(String(rowKeys[b]), undefined, { numeric: true });
      return dir === 'asc' ? cmp : -cmp;
    }
    const sumA = (matrix[a] || []).reduce((s, v) => s + (Number(v) || 0), 0);
    const sumB = (matrix[b] || []).reduce((s, v) => s + (Number(v) || 0), 0);
    return dir === 'asc' ? sumA - sumB : sumB - sumA;
  });
  return {
    rowKeys: indices.map((i) => rowKeys[i]),
    colKeys,
    matrix: indices.map((i) => matrix[i]),
  };
}

/** Store × time period (recent columns, chronological). */
export function pivotStoreByDatePeriod(rows, columns, { maxCols = 32 } = {}) {
  const storeCol = pickStoreColumn(columns);
  const dateCol = pickDateColumn(columns, [storeCol]);
  if (!storeCol || !dateCol) {
    return { storeCol, dateCol: null, valueCol: null, rowStores: [], colProducts: [], matrix: [] };
  }
  const valueCol = pickMetricColumn(rows, columns, [storeCol, dateCol]);
  if (!valueCol) {
    return { storeCol, dateCol, valueCol: null, rowStores: [], colProducts: [], matrix: [] };
  }
  const p = pivotRowColValue(rows, storeCol, dateCol, valueCol, { maxCols, colMode: 'chrono' });
  return {
    storeCol,
    dateCol,
    valueCol,
    rowStores: p.rowKeys,
    colProducts: p.colKeys,
    matrix: p.matrix,
  };
}

/** Σ downtime minutes per (rowKey × colKey). `colMode` `chrono` sorts time columns on col axis. */
export function pivotRowColDuration(rows, rowKey, colKey, downtimeCols, { maxCols = 22, colMode = 'volume' } = {}) {
  if (!rows?.length || !rowKey || !colKey || !downtimeCols?.length) {
    return { rowDim: rowKey, colDim: colKey, valueCol: '__minutes__', rowKeys: [], colKeys: [], matrix: [] };
  }

  const pairTotals = new Map();
  const colTotals = new Map();
  const rowSet = new Set();

  for (const row of rows) {
    const rk = String(row[rowKey] || '').trim() || '—';
    const ck = String(row[colKey] || '').trim() || '—';
    const mins = downtimeCols.reduce((s, c) => s + parseDurationToMinutes(row[c]), 0);
    rowSet.add(rk);
    const k = rk + KEY_SEP + ck;
    pairTotals.set(k, (pairTotals.get(k) || 0) + mins);
    colTotals.set(ck, (colTotals.get(ck) || 0) + mins);
  }

  let colKeys;
  if (colMode === 'chrono') {
    const ordered = chronoSortKeys([...colTotals.keys()]);
    colKeys = ordered.slice(-maxCols);
  } else {
    colKeys = [...colTotals.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxCols)
      .map(([c]) => c);
  }
  const colSet = new Set(colKeys);
  const rowKeys = [...rowSet].sort((a, b) => a.localeCompare(b));

  const matrix = rowKeys.map((rk) => {
    const cells = colKeys.map((ck) => pairTotals.get(rk + KEY_SEP + ck) || 0);
    let other = 0;
    for (const [k, val] of pairTotals) {
      const i = k.indexOf(KEY_SEP);
      const r = k.slice(0, i);
      const c = k.slice(i + KEY_SEP.length);
      if (r !== rk) continue;
      if (!colSet.has(c)) other += val;
    }
    return colMode === 'volume' ? [...cells, other] : cells;
  });

  const outColKeys = colMode === 'volume' ? [...colKeys, 'Other'] : colKeys;

  return {
    rowDim: rowKey,
    colDim: colKey,
    valueCol: '__minutes__',
    rowKeys,
    colKeys: outColKeys,
    matrix,
  };
}

/** Count rows per (rowKey × colKey) — for cancellation-style pivots. */
export function pivotRowColCount(rows, rowKey, colKey, { maxCols = 22, colMode = 'volume' } = {}) {
  if (!rows?.length || !rowKey || !colKey) {
    return { rowDim: rowKey, colDim: colKey, valueCol: '__count__', rowKeys: [], colKeys: [], matrix: [] };
  }

  const pairTotals = new Map();
  const colTotals = new Map();
  const rowSet = new Set();

  for (const row of rows) {
    const rk = String(row[rowKey] || '').trim() || '—';
    const ck = String(row[colKey] || '').trim() || '—';
    rowSet.add(rk);
    const k = rk + KEY_SEP + ck;
    pairTotals.set(k, (pairTotals.get(k) || 0) + 1);
    colTotals.set(ck, (colTotals.get(ck) || 0) + 1);
  }

  let colKeys;
  if (colMode === 'chrono') {
    const ordered = chronoSortKeys([...colTotals.keys()]);
    colKeys = ordered.slice(-maxCols);
  } else {
    colKeys = [...colTotals.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxCols)
      .map(([c]) => c);
  }
  const colSet = new Set(colKeys);
  const rowKeys = [...rowSet].sort((a, b) => a.localeCompare(b));

  const matrix = rowKeys.map((rk) => {
    const cells = colKeys.map((ck) => pairTotals.get(rk + KEY_SEP + ck) || 0);
    let other = 0;
    for (const [k, val] of pairTotals) {
      const i = k.indexOf(KEY_SEP);
      const r = k.slice(0, i);
      const c = k.slice(i + KEY_SEP.length);
      if (r !== rk) continue;
      if (!colSet.has(c)) other += val;
    }
    return colMode === 'volume' ? [...cells, other] : cells;
  });

  const outColKeys = colMode === 'volume' ? [...colKeys, 'Other'] : colKeys;

  return {
    rowDim: rowKey,
    colDim: colKey,
    valueCol: '__count__',
    rowKeys,
    colKeys: outColKeys,
    matrix,
  };
}

/**
 * Discover dimensions + all useful downtime pivots (1-way tables + 2-way minute matrices).
 */
export function discoverDowntimePivotCatalog(rows, columns, { maxMatrixCols = 20, maxMatrices = 14 } = {}) {
  const catalogLines = [];
  const oneWay = [];
  const matrices = [];

  if (!rows?.length || !columns?.length) {
    return { downtimeCols: [], dimensions: [], catalogLines, oneWay, matrices };
  }

  const storeCol = pickStoreColumn(columns);
  let categoryCol = pickCategoryColumn(columns, [storeCol].filter(Boolean));
  if (!categoryCol && storeCol) {
    const inferred = inferCategoricalColumns(rows, columns, { exclude: [storeCol], maxUniq: 90 });
    categoryCol = inferred.find((x) => x.col !== storeCol)?.col ?? null;
  }

  const dateCol = pickDateColumn(columns, [storeCol, categoryCol].filter(Boolean));
  const excludeForDuration = new Set([storeCol, categoryCol, dateCol].filter(Boolean));
  const downtimeCols = resolveDowntimeSumColumns(rows, columns, excludeForDuration);

  if (!downtimeCols.length) {
    catalogLines.push('No duration/downtime columns detected — cannot build downtime pivots.');
    return { downtimeCols: [], dimensions: [], catalogLines, oneWay, matrices };
  }

  catalogLines.push(`Duration fields summed: ${downtimeCols.join(', ')}.`);

  const dimensions = [];
  if (storeCol) dimensions.push({ col: storeCol, label: 'Store' });
  if (categoryCol && categoryCol !== storeCol) dimensions.push({ col: categoryCol, label: 'Category' });
  if (dateCol) dimensions.push({ col: dateCol, label: 'Period' });

  const inferMore = inferCategoricalColumns(rows, columns, {
    exclude: dimensions.map((d) => d.col),
    maxUniq: 72,
  });
  for (const inf of inferMore) {
    if (dimensions.some((d) => d.col === inf.col)) continue;
    if (storeCol && isStoreLikeColumn(inf.col) && isStoreLikeColumn(storeCol)) continue;
    if (dimensions.length >= 6) break;
    dimensions.push({ col: inf.col, label: inf.col });
  }

  for (const d of dimensions) {
    const agg = pivotDowntimeByDimension(rows, columns, d.col);
    if (!agg.rows.length) continue;
    oneWay.push({
      title: `Downtime by ${d.label}`,
      dimCol: d.col,
      downtimeCols: agg.downtimeCols,
      rows: agg.rows,
    });
    catalogLines.push(`1-way: Σ minutes (→ days / hours / minutes) by «${d.col}» — ${agg.rows.length} values.`);
  }

  const pairSeen = new Set();
  for (let i = 0; i < dimensions.length && matrices.length < maxMatrices; i++) {
    for (let j = i + 1; j < dimensions.length && matrices.length < maxMatrices; j++) {
      let rowDim = dimensions[i].col;
      let colDim = dimensions[j].col;
      let colMode = 'volume';
      if (dateCol) {
        if (colDim === dateCol) colMode = 'chrono';
        else if (rowDim === dateCol) {
          const t = rowDim;
          rowDim = colDim;
          colDim = t;
          colMode = 'chrono';
        }
      }
      const pk = rowDim <= colDim ? `${rowDim}|${colDim}` : `${colDim}|${rowDim}`;
      if (pairSeen.has(pk)) continue;
      if (isRedundantStorePair(rowDim, colDim)) continue;
      pairSeen.add(pk);

      const m = pivotRowColDuration(rows, rowDim, colDim, downtimeCols, {
        maxCols: colMode === 'chrono' ? 34 : maxMatrixCols,
        colMode,
      });
      if (!m.rowKeys.length || !m.colKeys.length) continue;

      const rowLab = dimensions.find((d) => d.col === rowDim)?.label ?? rowDim;
      const colLab = dimensions.find((d) => d.col === colDim)?.label ?? colDim;
      matrices.push({
        title: `${rowLab} × ${colLab} (Σ minutes)`,
        rowDim,
        colDim,
        colMode,
        rowKeys: m.rowKeys,
        colKeys: m.colKeys,
        matrix: m.matrix,
      });
      catalogLines.push(
        `2-way: «${rowDim}» × «${colDim}» — summed downtime minutes (${colMode === 'chrono' ? 'time-ordered columns' : 'top columns + Other'}).`,
      );
    }
  }

  return {
    downtimeCols,
    dimensions,
    catalogLines,
    oneWay,
    matrices,
  };
}

/** Count-based pivot catalog for sheets without duration columns (e.g. cancellations). */
export function discoverCountPivotCatalog(rows, columns, { maxMatrices = 8, maxMatrixCols = 18 } = {}) {
  const lines = [];
  const matrices = [];
  if (!rows?.length || !columns?.length) return { catalogLines: lines, matrices };

  const storeCol = pickStoreColumn(columns);
  const dims = [];
  if (storeCol) dims.push({ col: storeCol, label: 'Store' });
  const inferred = inferCategoricalColumns(rows, columns, { exclude: [storeCol].filter(Boolean), maxUniq: 65 });
  for (const inf of inferred) {
    if (dims.some((d) => d.col === inf.col)) continue;
    if (dims.length >= 5) break;
    dims.push({ col: inf.col, label: inf.col });
  }
  const dateCol = pickDateColumn(columns, dims.map((d) => d.col));

  if (dateCol && !dims.some((d) => d.col === dateCol)) dims.push({ col: dateCol, label: 'Period' });

  for (const d of dims) {
    lines.push(`1-way: row count by «${d.col}».`);
  }

  const pairSeen = new Set();
  for (let i = 0; i < dims.length && matrices.length < maxMatrices; i++) {
    for (let j = i + 1; j < dims.length && matrices.length < maxMatrices; j++) {
      let rowDim = dims[i].col;
      let colDim = dims[j].col;
      let colMode = 'volume';
      if (dateCol) {
        if (colDim === dateCol) colMode = 'chrono';
        else if (rowDim === dateCol) {
          const t = rowDim;
          rowDim = colDim;
          colDim = t;
          colMode = 'chrono';
        }
      }
      const pk = rowDim <= colDim ? `${rowDim}|${colDim}` : `${colDim}|${rowDim}`;
      if (pairSeen.has(pk)) continue;
      pairSeen.add(pk);

      const m = pivotRowColCount(rows, rowDim, colDim, { maxCols: maxMatrixCols, colMode });
      if (m.rowKeys.length < 2 || m.colKeys.length < 2) continue;
      const rowLab = dims.find((d) => d.col === rowDim)?.label ?? rowDim;
      const colLab = dims.find((d) => d.col === colDim)?.label ?? colDim;
      matrices.push({
        title: `${rowLab} × ${colLab} (row counts)`,
        rowDim,
        colDim,
        colMode,
        rowKeys: m.rowKeys,
        colKeys: m.colKeys,
        matrix: m.matrix,
      });
      lines.push(`2-way counts: «${rowDim}» × «${colDim}».`);
    }
  }

  return { catalogLines: lines, matrices };
}
