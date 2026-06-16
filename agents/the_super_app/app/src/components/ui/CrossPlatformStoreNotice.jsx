import { formatCrossPlatformStoreNote } from '../../lib/engine/crossPlatformStoreAlign';

export default function CrossPlatformStoreNotice({ crossPlatform, className = '' }) {
  const note = formatCrossPlatformStoreNote(crossPlatform);
  if (!note) return null;

  return (
    <div className={`rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950 leading-relaxed ${className}`}>
      <div className="font-medium mb-1">DoorDash ↔ Uber Eats store alignment</div>
      <p>{note}</p>
    </div>
  );
}
