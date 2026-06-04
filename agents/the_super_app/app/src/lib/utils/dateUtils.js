import { subYears, parse, format, getDay } from 'date-fns';

export function parseDate(str) {
  if (!str) return null;
  if (str instanceof Date) return isNaN(str) ? null : str;
  const trimmed = String(str).trim();
  let d = parse(trimmed, 'MM/dd/yyyy', new Date());
  if (!isNaN(d)) return d;
  d = parse(trimmed, 'yyyy-MM-dd', new Date());
  if (!isNaN(d)) return d;
  d = parse(trimmed, 'M/d/yyyy', new Date());
  if (!isNaN(d)) return d;
  d = new Date(trimmed);
  return isNaN(d) ? null : d;
}

export function getLastYearDates(start, end) {
  return { start: subYears(start, 1), end: subYears(end, 1) };
}

export function isInRange(date, start, end) {
  if (!date || !start || !end) return false;
  return date >= start && date <= end;
}

export function formatDateStr(d) {
  if (!d) return '';
  return format(d, 'MM/dd/yyyy');
}

/**
 * Parses a single-line period like "1/1/2026-1/31/2026" or "01/01/2026-01/31/2026"
 * (month/day/year on each side, separated by a hyphen).
 */
export function parseSlashDateRange(str) {
  const trimmed = String(str).trim();
  if (!trimmed) return null;
  const m = trimmed.match(/^(\d{1,2}\/\d{1,2}\/\d{4})\s*-\s*(\d{1,2}\/\d{1,2}\/\d{4})$/);
  if (!m) return null;
  const start = parseDate(m[1]);
  const end = parseDate(m[2]);
  if (!start || !end) return null;
  if (start > end) return null;
  return { start, end };
}

export function formatSlashDateRange(start, end) {
  if (!start || !end) return '';
  return `${formatDateStr(start)}-${formatDateStr(end)}`;
}

export function formatDateShort(d) {
  if (!d) return '';
  return format(d, 'MMM d, yyyy');
}

export function getFourWindows(preStart, preEnd, postStart, postEnd) {
  const lyPre = getLastYearDates(preStart, preEnd);
  const lyPost = getLastYearDates(postStart, postEnd);
  return {
    pre: { start: preStart, end: preEnd },
    post: { start: postStart, end: postEnd },
    preLY: lyPre,
    postLY: lyPost,
  };
}

export function getDayName(date) {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  return days[getDay(date)];
}

export function dateToKey(d) {
  return format(d, 'yyyy-MM-dd');
}

/** Min/max dates without spread (safe for 100k+ rows). */
export function minMaxDates(dates) {
  let minT = Infinity;
  let maxT = -Infinity;
  for (const d of dates) {
    if (!d) continue;
    const t = d instanceof Date ? d.getTime() : new Date(d).getTime();
    if (!Number.isFinite(t)) continue;
    if (t < minT) minT = t;
    if (t > maxT) maxT = t;
  }
  if (!Number.isFinite(minT)) return { min: null, max: null };
  return { min: new Date(minT), max: new Date(maxT) };
}
