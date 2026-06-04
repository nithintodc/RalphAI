import { useEffect, useState } from 'react';
import { X, ExternalLink, Copy, Check, FileText, Printer, Loader2 } from 'lucide-react';

export default function ExportResultModal({ open, payload, onClose, onOpenPdf }) {
  const [copied, setCopied] = useState(false);
  const [docCopied, setDocCopied] = useState(false);

  const handleClose = () => {
    setCopied(false);
    setDocCopied(false);
    onClose();
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open || !payload) return null;

  if (payload.kind === 'loading') {
    return (
      <div
        className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-modal-title"
      >
        <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <Loader2 size={18} className="animate-spin text-[var(--accent)]" />
            <h2 id="export-modal-title" className="text-sm font-semibold text-[var(--text)]">
              Generating export…
            </h2>
          </div>
          <p className="text-xs text-[var(--text-muted)] leading-relaxed">
            Building the Partnership Report and data workbook, then pushing to Google Drive. This takes a few seconds.
          </p>
        </div>
      </div>
    );
  }

  if (payload.kind === 'error') {
    return (
      <div
        className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40"
        role="dialog"
        aria-modal="true"
        aria-labelledby="export-modal-title"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) handleClose();
        }}
      >
        <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xl p-5">
          <div className="flex items-start justify-between gap-3 mb-3">
            <h2 id="export-modal-title" className="text-sm font-semibold text-[var(--text)]">
              Export failed
            </h2>
            <button
              type="button"
              onClick={handleClose}
              className="p-1 rounded-lg hover:bg-[var(--surface-2)] text-[var(--text-muted)] cursor-pointer"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
          <p className="text-xs text-[var(--text-muted)] leading-relaxed">{payload.message}</p>
          <div className="mt-5 flex justify-end">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { filename, spreadsheetUrl, googleSheets, docFilename, docUrl, googleDoc, canOpenPdf } = payload;
  const sheetsMessage =
    googleSheets && typeof googleSheets.message === 'string' && googleSheets.message.trim()
      ? googleSheets.message.trim()
      : null;

  const copyToClipboard = async (text, setFlag) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setFlag(true);
      window.setTimeout(() => setFlag(false), 2000);
    } catch {
      setFlag(false);
    }
  };

  const handleCopy = () => copyToClipboard(spreadsheetUrl, setCopied);
  const handleDocCopy = () => copyToClipboard(docUrl, setDocCopied);

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div className="w-full max-w-lg max-h-[88vh] overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xl p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <h2 id="export-modal-title" className="text-sm font-semibold text-[var(--text)]">
            Export complete
          </h2>
          <button
            type="button"
            onClick={handleClose}
            className="p-1 rounded-lg hover:bg-[var(--surface-2)] text-[var(--text-muted)] cursor-pointer"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* ── Partnership Performance Report (document) ── */}
        {docFilename || docUrl || googleDoc ? (
          <div className="rounded-lg border border-[var(--accent-border)] bg-[var(--accent-soft)] px-3 py-3 mb-4">
            <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--accent-text)] mb-1">
              Partnership Performance Report
            </p>
            <p className="text-[11px] text-[var(--text-muted)] leading-relaxed mb-3">
              Branded report (cover, KPIs, Pre/Post &amp; YoY, DoorDash / Uber Eats, store-level, day-part) populated
              with your current data.
            </p>

            <div className="flex flex-col sm:flex-row gap-2 mb-2">
              {canOpenPdf ? (
                <button
                  type="button"
                  onClick={onOpenPdf}
                  className="inline-flex items-center justify-center gap-1.5 flex-1 px-3 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer"
                >
                  <Printer size={14} />
                  Open &amp; save as PDF
                </button>
              ) : null}
              {docFilename ? (
                <span className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)]">
                  <FileText size={14} />
                  {docFilename} downloaded
                </span>
              ) : null}
            </div>

            {docUrl ? (
              <div className="mt-1">
                <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)] mb-1.5">
                  Google Doc
                </p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <a
                    href={docUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 flex-1 px-3 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer"
                  >
                    <ExternalLink size={14} />
                    Open Google Doc
                  </a>
                  <button
                    type="button"
                    onClick={handleDocCopy}
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text)] hover:bg-[var(--surface-2)] cursor-pointer"
                  >
                    {docCopied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                    {docCopied ? 'Copied' : 'Copy link'}
                  </button>
                </div>
                <p className="mt-2 text-[10px] text-[var(--text-subtle)] break-all">{docUrl}</p>
              </div>
            ) : googleDoc?.error ? (
              <p className="text-[11px] text-red-300 leading-relaxed">
                Google Doc push failed: {googleDoc.error}. The .doc file was still downloaded.
              </p>
            ) : (
              <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
                The .doc was downloaded. Start the export API (port 8765) to also push a Google Doc.
              </p>
            )}
          </div>
        ) : null}

        <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-4">
          A full data workbook was also generated (Excel tabs: Full, Date, Marketing, Slot, Bucket, Operations,
          Product Mix, App2 AITF) and sent to Google Sheets when push is enabled.
        </p>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5 mb-4">
          <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)] mb-1">
            Downloaded workbook
          </p>
          <p className="text-xs font-mono text-[var(--text)] break-all">{filename}</p>
        </div>

        {googleSheets?.skipped ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 mb-4">
            <p className="text-xs font-medium text-amber-200 mb-1">Google Sheets not configured</p>
            <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">
              {googleSheets.reason ||
                'Set VITE_GOOGLE_SHEETS_EXPORT_URL to push this workbook to a spreadsheet automatically.'}
            </p>
          </div>
        ) : null}

        {!googleSheets?.skipped && googleSheets?.error ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 mb-4">
            <p className="text-xs font-medium text-red-200 mb-1">Google Sheets push failed</p>
            <p className="text-[11px] text-[var(--text-muted)] leading-relaxed">{googleSheets.error}</p>
            <p className="text-[10px] text-[var(--text-subtle)] mt-2">The Excel file was still saved.</p>
          </div>
        ) : null}

        {spreadsheetUrl ? (
          <div className="mb-4">
            <p className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-subtle)] mb-2">
              Google Sheets
            </p>
            <div className="flex flex-col sm:flex-row gap-2">
              <a
                href={spreadsheetUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-1.5 flex-1 px-3 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer"
              >
                <ExternalLink size={14} />
                Open spreadsheet
              </a>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text)] hover:bg-[var(--surface-2)] cursor-pointer"
              >
                {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                {copied ? 'Copied' : 'Copy link'}
              </button>
            </div>
            <p className="mt-2 text-[10px] text-[var(--text-subtle)] break-all">{spreadsheetUrl}</p>
          </div>
        ) : null}

        {!googleSheets?.skipped && !googleSheets?.error && !spreadsheetUrl && sheetsMessage ? (
          <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-4">{sheetsMessage}</p>
        ) : null}

        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] text-xs font-medium text-[var(--text)] hover:bg-[var(--surface)] cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
