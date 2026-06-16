import { subYears, parse, format, getDay, differenceInCalendarDays } from 'date-fns';

/** Excel 1900 date system serial -> local calendar date (e.g. 45748 -> 2025-04-01). */
export function parseExcelSerialDate(serial) {
  const n = typeof serial === 'number' ? serial : Number(String(serial).trim());
  if (!Number.isFinite(n)) return null;
  const days = Math.floor(n);
  // ~1950–2060 in Excel serial space; avoids mistaking small IDs as dates.
  if (days < 18000 || days > 65000) return null;
  const epoch = new Date(1899, 11, 30);
  const d = new Date(epoch.getTime() + days * 86400000);
  return isNaN(d.getTime()) ? null : d;
}

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
  d = parseExcelSerialDate(trimmed);
  if (d) return d;
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

/** Compact range when start/end share month or year (e.g. Mar 1–31, 2026). */
export function formatCompactDateRange(start, end) {
  if (!start) return '';
  if (!end || start.getTime() === end.getTime()) return formatDateShort(start);
  const sameYear = start.getFullYear() === end.getFullYear();
  const sameMonth = sameYear && start.getMonth() === end.getMonth();
  if (sameMonth) {
    return `${format(start, 'MMM d')}–${format(end, 'd, yyyy')}`;
  }
  if (sameYear) {
    return `${format(start, 'MMM d')}–${format(end, 'MMM d, yyyy')}`;
  }
  return `${formatDateShort(start)} – ${formatDateShort(end)}`;
}

/** Pre/Post windows for the topbar date chip. */
export function formatPeriodComparisonLabel(preStart, preEnd, postStart, postEnd) {
  const pre = formatCompactDateRange(preStart, preEnd);
  const post = formatCompactDateRange(postStart, postEnd);
  if (!pre && !post) return null;
  if (pre === post) return pre;
  return `Pre ${pre} · Post ${post}`;
}

/** Top 10% count rounded up (minimum 1 when total > 0). */
export function percentSpotlightCount(total, pct = 0.1) {
  if (!total || total <= 0) return 0;
  return Math.max(1, Math.ceil(total * pct));
}

/** Spotlight day count for a calendar window (inclusive). */
export function daySpotlightCount(start, end, pct = 0.1) {
  if (!start || !end) return 0;
  const days = differenceInCalendarDays(end, start) + 1;
  return percentSpotlightCount(days, pct);
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
