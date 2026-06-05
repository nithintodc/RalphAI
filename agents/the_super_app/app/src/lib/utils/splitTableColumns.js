const ANCHOR_KEY_HINTS = new Set([
  'label',
  'metric',
  'group',
  'store',
  'storeId',
  'slot',
  'slotTime',
  'step',
  'segment',
  'product',
  'key',
  'tag',
  'range',
  'campaign',
  'campaignName',
  'driver',
  'id',
]);

/** Keys that stay on every split chunk (row labels). */
export function getAnchorKeys(columns) {
  const explicit = columns.filter((c) => c.labelCol).map((c) => c.key);
  if (explicit.length) return [...new Set(explicit)];
  const firstKey = columns[0]?.key;
  if (firstKey && (ANCHOR_KEY_HINTS.has(firstKey) || columns[0].align !== 'right')) {
    return [firstKey];
  }
  const left = columns.find((c) => c.align !== 'right');
  return left ? [left.key] : firstKey ? [firstKey] : [];
}

/**
 * Split wide column sets into multiple table definitions that fit the viewport.
 * Anchor columns repeat in each chunk.
 */
export function splitTableColumns(columns, { maxDataCols = 5 } = {}) {
  if (!columns?.length) return [[]];
  const anchorKeys = new Set(getAnchorKeys(columns));
  const anchors = columns.filter((c) => anchorKeys.has(c.key));
  const rest = columns.filter((c) => !anchorKeys.has(c.key));
  if (rest.length <= maxDataCols) return [columns];
  const chunks = [];
  for (let i = 0; i < rest.length; i += maxDataCols) {
    chunks.push([...anchors, ...rest.slice(i, i + maxDataCols)]);
  }
  return chunks;
}

export function splitColKeys(colKeys, maxCols = 8) {
  if (!colKeys?.length || colKeys.length <= maxCols) return [colKeys];
  const chunks = [];
  for (let i = 0; i < colKeys.length; i += maxCols) {
    chunks.push(colKeys.slice(i, i + maxCols));
  }
  return chunks;
}
