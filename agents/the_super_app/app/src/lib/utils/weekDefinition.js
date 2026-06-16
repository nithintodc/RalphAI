/** Business-week options — `weekStartsOn` matches date-fns (0 = Sun … 6 = Sat). */
export const WEEK_DEFINITION_OPTIONS = [
  { id: 'mon-sun', label: 'Mon – Sun', weekStartsOn: 1 },
  { id: 'sun-sat', label: 'Sun – Sat', weekStartsOn: 0 },
  { id: 'tue-mon', label: 'Tue – Mon', weekStartsOn: 2 },
  { id: 'wed-tue', label: 'Wed – Tue', weekStartsOn: 3 },
  { id: 'thu-wed', label: 'Thu – Wed', weekStartsOn: 4 },
  { id: 'fri-thu', label: 'Fri – Thu', weekStartsOn: 5 },
  { id: 'sat-fri', label: 'Sat – Fri', weekStartsOn: 6 },
];

export const DEFAULT_WEEK_DEFINITION_ID = 'mon-sun';

export function getWeekDefinitionById(id) {
  return WEEK_DEFINITION_OPTIONS.find((o) => o.id === id) || WEEK_DEFINITION_OPTIONS[0];
}

export function resolveWeekStartsOn(weekDefinitionId, fallback = 1) {
  const hit = getWeekDefinitionById(weekDefinitionId || DEFAULT_WEEK_DEFINITION_ID);
  return hit?.weekStartsOn ?? fallback;
}
