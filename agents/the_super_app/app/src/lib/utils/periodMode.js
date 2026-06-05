/** True when analysis uses one date window (no Pre vs Post comparison). */
export function isSinglePeriodMode(dateAnalysisMode) {
  const m = String(dateAnalysisMode || '');
  return m === 'singleRange'
    || m === 'singleWeek'
    || m === 'singleMonth'
    || m === 'singleQuarter'
    || m === 'singleYear';
}
