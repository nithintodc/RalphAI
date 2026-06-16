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
  startOfWeek,
  endOfWeek,
  subDays,
  subYears,
} from 'date-fns';
import { dateToKey } from './dateUtils';
import { mergeAllUploadedBounds } from './uploadedDataBounds';

/** True when two inclusive date ranges match by calendar day. */
export function rangesEqual(aStart, aEnd, bStart, bEnd) {
  if (!aStart || !aEnd || !bStart || !bEnd) return false;
  return dateToKey(aStart) === dateToKey(bStart) && dateToKey(aEnd) === dateToKey(bEnd);
}

/** Merge DD + UE date ranges (financial and/or DoorDash sales exports). */
export function mergeUploadedDataBounds(ddFinancial, ueFinancial, ddSales = null) {
  return mergeAllUploadedBounds(ddFinancial, ueFinancial, ddSales);
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
 * Week k relative to anchor: k=0 is the week containing anchor, k=-1 previous, etc.
 */
export function getWowWeekRange(anchorDate, weekIndex, weekStartsOn = 1) {
  const anchor = startOfDay(anchorDate);
  const currentWeekStart = startOfWeek(anchor, { weekStartsOn });
  const weekStart = addWeeks(currentWeekStart, weekIndex);
  const weekEnd = endOfWeek(weekStart, { weekStartsOn });
  return {
    monday: weekStart,
    sunday: weekEnd,
    start: startOfDay(weekStart),
    end: endOfDay(weekEnd),
  };
}

/**
 * @param {{ min: Date, max: Date }} bounds
 * @param {number} maxBack number of past weeks (Week 0, -1, …)
 */
export function listWowWeekOptions(bounds, maxBack = 52, weekStartsOn = 1) {
  if (!bounds?.min || !bounds?.max) return [];
  const minB = startOfDay(bounds.min);
  const maxB = endOfDay(bounds.max);
  if (minB.getTime() > maxB.getTime()) return [];
  const anchor = getWowAnchorDate(bounds);

  const out = [];
  for (let k = 0; k >= -maxBack; k--) {
    const { start: wStart, end: wEnd, monday, sunday } = getWowWeekRange(anchor, k, weekStartsOn);
    const start = max([minB, wStart]);
    const end = min([maxB, wEnd]);
    if (start > end) continue;
    const label =
      k === 0
        ? `Week 0: ${format(monday, 'M/d/yyyy')} – ${format(sunday, 'M/d/yyyy')} (current week)`
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

function takeRecentPresets(presets, max = 12) {
  if (!presets?.length) return [];
  return presets.slice(-max).reverse();
}

function buildAdjacentComparePresets(items, mode, labelFn, idFn, isAdjacent) {
  const out = [];
  for (let i = 1; i < items.length; i++) {
    const pre = items[i - 1];
    const post = items[i];
    if (isAdjacent && !isAdjacent(pre, post)) continue;
    out.push({
      id: idFn(pre, post),
      mode,
      label: labelFn(pre, post),
      preStart: pre.start,
      preEnd: pre.end,
      postStart: post.start,
      postEnd: post.end,
    });
  }
  return out;
}

/**
 * Pre/Post preset pairs derived from uploaded data bounds (MoM, WoW, QoQ, YoY).
 * Each group is ordered most-recent first.
 */
export function buildComparePeriodPresetGroups(bounds, { maxPresetsPerGroup = 12, weekStartsOn = 1 } = {}) {
  if (!bounds?.min || !bounds?.max) {
    return { mom: [], wow: [], qoq: [], yoy: [] };
  }

  const monthOpts = listMonthOptions(bounds);
  const quarterOpts = listQuarterOptions(bounds);
  const weekOpts = [...listWowWeekOptions(bounds, 52, weekStartsOn)].sort((a, b) => a.weekIndex - b.weekIndex);

  const momAll = buildAdjacentComparePresets(
    monthOpts,
    'mom',
    (pre, post) => `${pre.label} vs ${post.label}`,
    (pre, post) => `mom-${pre.id}-${post.id}`,
  );

  const qoqAll = buildAdjacentComparePresets(
    quarterOpts,
    'qoq',
    (pre, post) => `${pre.label.split(' (')[0]} vs ${post.label.split(' (')[0]}`,
    (pre, post) => `qoq-${pre.id}-${post.id}`,
  );

  const wowAll = buildAdjacentComparePresets(
    weekOpts,
    'wow',
    (pre, post) => `Week ${pre.weekIndex} vs Week ${post.weekIndex}`,
    (pre, post) => `wow-${pre.id}-${post.id}`,
    (pre, post) => post.weekIndex === pre.weekIndex + 1,
  );

  const monthById = new Map(monthOpts.map((m) => [m.id, m]));
  const yoyMonthAll = [];
  for (const post of monthOpts) {
    const lyId = format(subYears(post.start, 1), 'yyyy-MM');
    const pre = monthById.get(lyId);
    if (!pre) continue;
    yoyMonthAll.push({
      id: `yoy-m-${post.id}`,
      mode: 'pvp',
      label: `${pre.label} vs ${post.label}`,
      preStart: pre.start,
      preEnd: pre.end,
      postStart: post.start,
      postEnd: post.end,
    });
  }

  const quarterById = new Map(quarterOpts.map((q) => [q.id, q]));
  const yoyQuarterAll = [];
  for (const post of quarterOpts) {
    const y = post.start.getFullYear() - 1;
    const q = Math.floor(post.start.getMonth() / 3) + 1;
    const lyId = `${y}-Q${q}`;
    const pre = quarterById.get(lyId);
    if (!pre) continue;
    yoyQuarterAll.push({
      id: `yoy-q-${post.id}`,
      mode: 'pvp',
      label: `${pre.label.split(' (')[0]} vs ${post.label.split(' (')[0]}`,
      preStart: pre.start,
      preEnd: pre.end,
      postStart: post.start,
      postEnd: post.end,
    });
  }

  return {
    mom: takeRecentPresets(momAll, maxPresetsPerGroup),
    wow: takeRecentPresets(wowAll, maxPresetsPerGroup),
    qoq: takeRecentPresets(qoqAll, maxPresetsPerGroup),
    yoy: takeRecentPresets([...yoyMonthAll, ...yoyQuarterAll], maxPresetsPerGroup),
  };
}

/** Single-period presets (week / month / quarter / year) from uploaded bounds. */
export function buildSinglePeriodPresetGroups(bounds, { maxPresetsPerGroup = 8 } = {}) {
  if (!bounds?.min || !bounds?.max) {
    return { week: [], month: [], quarter: [], year: [] };
  }

  const weekOpts = listWowWeekOptions(bounds, 52);
  const monthOpts = listMonthOptions(bounds);
  const quarterOpts = listQuarterOptions(bounds);
  const yearOpts = listYearOptions(bounds);

  const toSingle = (items, mode, labelKey = 'label') =>
    takeRecentPresets(
      items.map((item) => ({
        id: `single-${mode}-${item.id}`,
        mode: mode === 'week' ? 'singleWeek' : mode === 'month' ? 'singleMonth' : mode === 'quarter' ? 'singleQuarter' : 'singleYear',
        label: item[labelKey],
        start: item.start,
        end: item.end,
      })),
      maxPresetsPerGroup,
    );

  return {
    week: toSingle(weekOpts, 'week'),
    month: toSingle(monthOpts, 'month'),
    quarter: toSingle(quarterOpts, 'quarter'),
    year: toSingle(yearOpts, 'year'),
  };
}

/** Find a compare preset matching current Pre/Post dates, if any. */
export function findMatchingComparePreset(groups, preStart, preEnd, postStart, postEnd) {
  if (!groups) return null;
  for (const [groupKey, presets] of Object.entries(groups)) {
    for (const preset of presets) {
      if (
        rangesEqual(preStart, preEnd, preset.preStart, preset.preEnd)
        && rangesEqual(postStart, postEnd, preset.postStart, preset.postEnd)
      ) {
        return { groupKey, preset };
      }
    }
  }
  return null;
}

export function findMatchingSinglePreset(groups, start, end) {
  if (!groups || !start || !end) return null;
  for (const [groupKey, presets] of Object.entries(groups)) {
    for (const preset of presets) {
      if (rangesEqual(start, end, preset.start, preset.end)) {
        return { groupKey, preset };
      }
    }
  }
  return null;
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

function clipToUserRange(itemStart, itemEnd, rangeStart, rangeEnd) {
  const rs = startOfDay(rangeStart);
  const re = endOfDay(rangeEnd);
  if (itemEnd < rs || itemStart > re) return null;
  return {
    start: max([itemStart, rs]),
    end: min([itemEnd, re]),
  };
}

/** Business weeks overlapping an inclusive analysis range (clipped to uploaded bounds). */
export function listWeeksInRange(rangeStart, rangeEnd, bounds, weekStartsOn = 1) {
  if (!rangeStart || !rangeEnd || !bounds?.min || !bounds?.max) return [];
  const minB = startOfDay(bounds.min);
  const maxB = endOfDay(bounds.max);
  const rangeMin = max([minB, startOfDay(rangeStart)]);
  const rangeMax = min([maxB, endOfDay(rangeEnd)]);
  if (rangeMin.getTime() > rangeMax.getTime()) return [];

  let weekStart = startOfWeek(rangeMin, { weekStartsOn });
  const lastWeekStart = startOfWeek(rangeMax, { weekStartsOn });
  const out = [];
  let index = 0;

  while (weekStart.getTime() <= lastWeekStart.getTime()) {
    const weekEnd = endOfWeek(weekStart, { weekStartsOn });
    const clipped = clipToUserRange(startOfDay(weekStart), endOfDay(weekEnd), rangeMin, rangeMax);
    if (clipped) {
      out.push({
        id: `week-${dateToKey(weekStart)}`,
        label: `${format(weekStart, 'M/d')} – ${format(weekEnd, 'M/d/yyyy')}`,
        weekStart: startOfDay(weekStart),
        weekEnd: endOfDay(weekEnd),
        start: max([minB, clipped.start]),
        end: min([maxB, clipped.end]),
        index,
      });
      index += 1;
    }
    weekStart = addWeeks(weekStart, 1);
  }
  return out;
}

/** Calendar months overlapping an inclusive analysis range. */
export function listMonthsInRange(rangeStart, rangeEnd, bounds) {
  if (!rangeStart || !rangeEnd || !bounds?.min || !bounds?.max) return [];
  return listMonthOptions(bounds).flatMap((month) => {
    const clipped = clipToUserRange(month.start, month.end, rangeStart, rangeEnd);
    if (!clipped) return [];
    return [{
      ...month,
      start: max([startOfDay(bounds.min), clipped.start]),
      end: min([endOfDay(bounds.max), clipped.end]),
    }];
  });
}

/** Calendar quarters overlapping an inclusive analysis range. */
export function listQuartersInRange(rangeStart, rangeEnd, bounds) {
  if (!rangeStart || !rangeEnd || !bounds?.min || !bounds?.max) return [];
  return listQuarterOptions(bounds).flatMap((quarter) => {
    const clipped = clipToUserRange(quarter.start, quarter.end, rangeStart, rangeEnd);
    if (!clipped) return [];
    return [{
      ...quarter,
      start: max([startOfDay(bounds.min), clipped.start]),
      end: min([endOfDay(bounds.max), clipped.end]),
    }];
  });
}

/**
 * Periods inside a user analysis range, each with optional prior period for delta / growth.
 * @param {'wow'|'mom'|'qoq'} mode
 */
export function buildPeriodsInAnalysisRange(mode, rangeStart, rangeEnd, bounds, weekStartsOn = 1) {
  if (!rangeStart || !rangeEnd) return [];

  let items = [];
  if (mode === 'wow') {
    items = listWeeksInRange(rangeStart, rangeEnd, bounds, weekStartsOn);
  } else if (mode === 'mom') {
    items = listMonthsInRange(rangeStart, rangeEnd, bounds);
  } else if (mode === 'qoq') {
    items = listQuartersInRange(rangeStart, rangeEnd, bounds);
  }

  return items.map((item, i) => {
    const prior = i > 0 ? items[i - 1] : null;
    let priorStart = prior?.start ?? null;
    let priorEnd = prior?.end ?? null;

    if (mode === 'wow' && !prior && item.weekStart) {
      const prevWeekStart = addWeeks(item.weekStart, -1);
      const prevWeekEnd = endOfWeek(prevWeekStart, { weekStartsOn });
      const minB = startOfDay(bounds.min);
      const maxB = endOfDay(bounds.max);
      priorStart = max([minB, startOfDay(prevWeekStart)]);
      priorEnd = min([maxB, endOfDay(prevWeekEnd)]);
    }

    return {
      ...item,
      priorStart,
      priorEnd,
      priorLabel: prior?.label ?? null,
    };
  });
}
