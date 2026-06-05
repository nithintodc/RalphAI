import { Loader2 } from 'lucide-react';

export default function ProcessingOverlay({ open, message = 'Updating analysis…' }) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-busy="true"
      aria-live="polite"
      aria-label={message}
    >
      <div className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xl p-5">
        <div className="flex items-center gap-3">
          <Loader2 size={20} className="animate-spin text-[var(--accent)] shrink-0" />
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">{message}</h2>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Recalculating metrics for the selected view.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
