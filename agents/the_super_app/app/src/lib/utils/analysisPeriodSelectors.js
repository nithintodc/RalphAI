/**
 * Builds Pre/Post date options from uploaded financial bounds:
 * calendar quarters, months, and Mon–Sun weeks (Week 0 = last complete week vs anchor).
 */
import {
  addDays,
  addWeeks,
  eachMonthOfInterval,
  eachQuarterOfInterval,
  endOfDay,
  endOfMonth,
  endOfQuarter,
  format,
  max,
  min,
  startOfDay,
  startOfMonth,
  startOfQuarter,
  subDays,
} from 'date-fns';
import { getDateRange as getDdDateRange } from '../parsers/ddFinancial';
import { getDateRange as getUeDateRange } from '../parsers/ueFinancial';

/** Merge DD + UE financial row date ranges. */
export function mergeUploadedDataBounds(ddFinancial, ueFinancial) {
  const ranges = [];
  if (ddFinancial?.length) {
    const r = getDdDateRange(ddFinancial);
    if (r.min && r.max) ranges.push({ min: r.min, max: r.max });
  }
  if (ueFinancial?.length) {
    const r = getUeDateRange(ueFinancial);
    if (r.min && r.max) ranges.push({ min: r.min, max: r.max });
  }
  if (!ranges.length) return { min: null, max: null };
  const minT = Math.min(...ranges.map((r) => startOfDay(r.min).getTime()));
  const maxT = Math.max(...ranges.map((r) => endOfDay(r.max).getTime()));
  return { min: new Date(minT), max: new Date(maxT) };
}

/** Sunday 00:00:00 on or before `d` (local). */
export function getSundayOnOrBefore(d) {
  const x = startOfDay(d);
  const dow = x.getDay();
  return subDays(x, dow);
}

/**
 * Anchor for WoW labels: today, capped to end of uploaded data (no future weeks).
 */
export function getWowAnchorDate(bounds) {
  const today = startOfDay(new Date());
  if (!bounds?.max) return today;
  return min([today, startOfDay(bounds.max)]);
}

/**
 * Week k: Monday..Sunday where k=0 is the week whose Sunday is the most recent Sunday on or before anchor.
 * k=-1 is the previous Mon–Sun, etc.
 */
export function getWowWeekRange(anchorDate, weekIndex) {
  const anchor = startOfDay(anchorDate);
  const sun0 = getSundayOnOrBefore(anchor);
  const mon0 = addDays(sun0, -6);
  const mon = addWeeks(mon0, weekIndex);
  const sun = addDays(mon, 6);
  return { monday: mon, sunday: sun, start: startOfDay(mon), end: endOfDay(sun) };
}

/**
 * @param {{ min: Date, max: Date }} bounds
 * @param {number} maxBack number of past weeks (Week 0, -1, …)
 */
export function listWowWeekOptions(bounds, maxBack = 52) {
  if (!bounds?.min || !bounds?.max) return [];
  const minB = startOfDay(bounds.min);
  const maxB = endOfDay(bounds.max);
  if (minB.getTime() > maxB.getTime()) return [];
  const anchor = getWowAnchorDate(bounds);

  const out = [];
  for (let k = 0; k >= -maxBack; k--) {
    const { start: wStart, end: wEnd, monday, sunday } = getWowWeekRange(anchor, k);
    const start = max([minB, wStart]);
    const end = min([maxB, wEnd]);
    if (start > end) continue;
    const label =
      k === 0
        ? `Week 0: ${format(monday, 'M/d/yyyy')} – ${format(sunday, 'M/d/yyyy')} (last Mon–Sun)`
        : `Week ${k}: ${format(monday, 'M/d/yyyy')} – ${format(sunday, 'M/d/yyyy')}`;
    out.push({ id: `wow-${k}`, weekIndex: k, label, start, end });
  }
  return out;
}

export function listQuarterOptions(bounds) {
  if (!bounds?.min || !bounds?.max) return [];
  const minB = startOfDay(bounds.min);
  const maxB = endOfDay(bounds.max);
  if (minB.getTime() > maxB.getTime()) return [];
  const intervalStart = startOfQuarter(minB);
  const intervalEnd = endOfQuarter(maxB);
  if (intervalStart.getTime() > intervalEnd.getTime()) return [];
  const starts = eachQuarterOfInterval({ start: intervalStart, end: intervalEnd });
  return starts.map((qStart) => {
    const qEnd = endOfQuarter(qStart);
    const y = qStart.getFullYear();
    const q = Math.floor(qStart.getMonth() / 3) + 1;
    const start = max([minB, startOfDay(qStart)]);
    const end = min([maxB, endOfDay(qEnd)]);
    return {
      id: `${y}-Q${q}`,
      label: `Q${q} ${y} (${format(start, 'M/d/yyyy')}–${format(end, 'M/d/yyyy')})`,
      start,
      end,
    };
  }).filter((o) => o.start <= o.end);
}

export function listMonthOptions(bounds) {
  if (!bounds?.min || !bounds?.max) return [];
  const minB = startOfDay(bounds.min);
  const maxB = endOfDay(bounds.max);
  if (minB.getTime() > maxB.getTime()) return [];
  const months = eachMonthOfInterval({ start: startOfMonth(minB), end: endOfMonth(maxB) });
  return months.map((mStart) => {
    const mEnd = endOfMonth(mStart);
    const start = max([minB, startOfDay(mStart)]);
    const end = min([maxB, endOfDay(mEnd)]);
    return {
      id: format(mStart, 'yyyy-MM'),
      label: format(mStart, 'MMM yyyy'),
      start,
      end,
    };
  }).filter((o) => o.start <= o.end);
}

export function listYearOptions(bounds) {
  if (!bounds?.min || !bounds?.max) return [];
  const minB = startOfDay(bounds.min);
  const maxB = endOfDay(bounds.max);
  if (minB.getTime() > maxB.getTime()) return [];
  const minYear = minB.getFullYear();
  const maxYear = maxB.getFullYear();
  const out = [];
  for (let y = minYear; y <= maxYear; y++) {
    const yStart = startOfDay(new Date(y, 0, 1));
    const yEnd = endOfDay(new Date(y, 11, 31));
    const start = max([minB, yStart]);
    const end = min([maxB, yEnd]);
    if (start > end) continue;
    out.push({
      id: String(y),
      label: `${y} (${format(start, 'M/d/yyyy')}–${format(end, 'M/d/yyyy')})`,
      start,
      end,
    });
  }
  return out;
}
