import PlatformLogo from './PlatformLogo';
import { formatStoreComparisonNotes } from '../../lib/utils/storePeriodAlignment';

function buildComparisonSummary(alignment) {
  if (!alignment?.pvp) return null;
  const common = alignment.pvp.commonCount ?? 0;
  const excluded =
    (alignment.pvp.excludedFromLeft?.length || 0)
    + (alignment.pvp.excludedFromRight?.length || 0);
  if (!alignment.pvp.needsAlignment && !alignment.lyPvp?.needsAlignment && !alignment.yoy?.needsAlignment) {
    return `${common} store${common === 1 ? '' : 's'} active in both Pre and Post`;
  }
  if (excluded > 0) {
    return `${common} stores compared · ${excluded} excluded from one side`;
  }
  return `${common} stores compared · alignment notes apply`;
}

/**
 * Banner explaining which stores are included in Pre/Post and YoY comparisons.
 */
export default function StoreComparisonNotice({ platform, alignment, className = '', compact = false }) {
  const notes = formatStoreComparisonNotes(alignment);
  if (!notes.length) return null;

  const label = platform === 'dd' ? 'DoorDash' : platform === 'ue' ? 'Uber Eats' : null;
  const summary = buildComparisonSummary(alignment);

  if (compact && summary) {
    return (
      <details className={`group rounded-md border border-amber-200/80 bg-amber-50/80 ${className}`}>
        <summary className="cursor-pointer list-none px-2.5 py-1.5 text-[11px] text-amber-950 marker:content-none">
          <span className="flex items-center justify-between gap-2">
            <span className="font-medium truncate">{summary}</span>
            <span className="shrink-0 text-[10px] text-amber-800/80 group-open:hidden">Details</span>
          </span>
        </summary>
        <div className="border-t border-amber-200/80 px-2.5 py-2 space-y-1.5 text-[11px] text-amber-950">
          {notes.map((note) => (
            <p key={note} className="leading-relaxed">{note}</p>
          ))}
        </div>
      </details>
    );
  }

  return (
    <div className={`rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-950 space-y-1.5 ${className}`}>
      {label && (
        <div className="flex items-center gap-2 font-medium">
          <PlatformLogo platform={platform} size={14} />
          <span>{label} store comparison</span>
        </div>
      )}
      {notes.map((note) => (
        <p key={note} className="leading-relaxed">{note}</p>
      ))}
    </div>
  );
}
