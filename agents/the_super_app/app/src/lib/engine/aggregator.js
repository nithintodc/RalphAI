import { endOfDay, startOfDay } from 'date-fns';
import { dateToKey } from '../utils/dateUtils';

function asCalendarDate(value) {
  if (!value) return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function groupBy(data, keyField) {
  const map = new Map();
  for (const row of data) {
    const key = String(row[keyField] || '');
    if (!key) continue;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(row);
  }
  return map;
}

export function aggregate(data, keyField, sumFields, uniqueCountFields = []) {
  const groups = groupBy(data, keyField);
  const result = [];

  for (const [key, rows] of groups) {
    const agg = { [keyField]: key };
    for (const field of sumFields) {
      agg[field] = rows.reduce((s, r) => s + (Number(r[field]) || 0), 0);
    }
    for (const field of uniqueCountFields) {
      agg[field] = new Set(rows.map(r => r[field]).filter(Boolean)).size;
    }
    result.push(agg);
  }
  return result;
}

export function filterByDateRange(data, dateField, start, end) {
  if (!start || !end) return data;
  const rangeStart = startOfDay(asCalendarDate(start));
  const rangeEnd = endOfDay(asCalendarDate(end));
  if (!rangeStart || !rangeEnd) return data;
  return data.filter((r) => {
    const d = asCalendarDate(r[dateField]);
    return d && d >= rangeStart && d <= rangeEnd;
  });
}

export function filterExcludedDates(data, dateField, excludedDates) {
  if (!excludedDates?.length) return data;
  const excluded = new Set(
    excludedDates
      .map((d) => {
        const parsed = asCalendarDate(d);
        return parsed ? dateToKey(parsed) : null;
      })
      .filter(Boolean),
  );
  return data.filter((r) => {
    const d = asCalendarDate(r[dateField]);
    if (!d) return false;
    return !excluded.has(dateToKey(d));
  });
}

export function filterExcludedStores(data, storeField, excludedStores) {
  if (!excludedStores || !excludedStores.length) return data;
  const excluded = new Set(excludedStores);
  return data.filter(r => !excluded.has(String(r[storeField] || '')));
}

export function uniqueValues(data, field) {
  return [...new Set(data.map(r => r[field]).filter(v => v != null && v !== ''))].sort();
}

export function sumField(data, field) {
  return data.reduce((acc, r) => acc + (Number(r[field]) || 0), 0);
}

export function countUnique(data, field) {
  return new Set(data.map(r => r[field]).filter(Boolean)).size;
}
