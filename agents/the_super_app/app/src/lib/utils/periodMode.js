/** True when analysis uses one date window (no Pre vs Post comparison). */
export function isSinglePeriodMode(dateAnalysisMode) {
  const m = String(dateAnalysisMode || '');
  return m === 'singleRange'
    || m === 'singleWeek'
    || m === 'singleMonth'
    || m === 'singleQuarter'
    || m === 'singleYear';
}

/** WoW / MoM / QoQ: one analysis range, periods derived inside it (no Pre vs Post inputs). */
export const PRESET_RANGE_MODES = ['wow', 'mom', 'qoq'];

export function isPresetRangeMode(dateAnalysisMode) {
  return PRESET_RANGE_MODES.includes(String(dateAnalysisMode || ''));
}

/** Custom Pre vs Post (manual dates or YoY preset pairs). */
export function isCustomCompareMode(dateAnalysisMode) {
  const m = String(dateAnalysisMode || '');
  if (isSinglePeriodMode(m) || isPresetRangeMode(m)) return false;
  return m === 'pvp' || m === 'yoy' || !m;
}
