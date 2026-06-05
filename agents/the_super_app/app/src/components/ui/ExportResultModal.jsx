import { useEffect, useState } from 'react';
import {
  X,
  ExternalLink,
  Copy,
  Check,
  FileSpreadsheet,
  FileText,
  Printer,
  Loader2,
  CheckCircle2,
} from 'lucide-react';

function useCopyLink() {
  const [copied, setCopied] = useState(false);
  const copy = async (text) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  return { copied, copy };
}

function ExportCard({ icon: Icon, title, hint, href, linkLabel, onCopy, copied, children }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface)] border border-[var(--border)] text-[var(--accent)]">
          <Icon size={18} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-[var(--text)]">{title}</p>
          {hint ? <p className="text-[11px] text-[var(--text-muted)] mt-0.5">{hint}</p> : null}
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)]"
              >
                <ExternalLink size={13} />
                {linkLabel}
              </a>
            ) : null}
            {children}
            {href && onCopy ? (
              <button
                type="button"
                onClick={onCopy}
                className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-[11px] text-[var(--text-muted)] hover:bg-[var(--surface)] hover:text-[var(--text)] cursor-pointer"
                title="Copy link"
              >
                {copied ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
                {copied ? 'Copied' : 'Copy link'}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function Alert({ tone, title, children }) {
  const styles =
    tone === 'error'
      ? 'border-red-500/25 bg-red-500/8 text-red-200'
      : 'border-amber-500/25 bg-amber-500/8 text-amber-100';
  return (
    <div className={`rounded-lg border px-3 py-2 text-[11px] leading-relaxed ${styles}`}>
      {title ? <p className="font-medium mb-0.5">{title}</p> : null}
      <p className="text-[var(--text-muted)]">{children}</p>
    </div>
  );
}

export default function ExportResultModal({ open, payload, onClose, onOpenPdf }) {
  const docCopy = useCopyLink();
  const sheetCopy = useCopyLink();

  const handleClose = () => onClose();

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

  const shell = (children) => (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xl">
        {children}
      </div>
    </div>
  );

  if (payload.kind === 'loading') {
    return shell(
      <div className="p-5">
        <div className="flex items-center gap-3">
          <Loader2 size={20} className="animate-spin text-[var(--accent)]" />
          <div>
            <h2 id="export-modal-title" className="text-sm font-semibold text-[var(--text)]">
              Generating export…
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Building your report and workbook. This usually takes a few seconds.
            </p>
          </div>
        </div>
      </div>,
    );
  }

  if (payload.kind === 'error') {
    return shell(
      <>
        <div className="flex items-start justify-between gap-3 p-5 pb-0">
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
        <p className="px-5 pt-2 pb-5 text-xs text-[var(--text-muted)] leading-relaxed">{payload.message}</p>
        <div className="px-5 pb-5 flex justify-end border-t border-[var(--border)] pt-4">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer"
          >
            Close
          </button>
        </div>
      </>,
      'Export failed',
    );
  }

  const {
    filename,
    docFilename,
    pdfFilename,
    spreadsheetUrl,
    googleSheets,
    docUrl,
    googleDoc,
    canOpenPdf,
  } = payload;
  const hasReport = !!(docUrl || canOpenPdf || googleDoc);
  const hasWorkbook = !!(spreadsheetUrl || filename);
  const sheetsFailed = !googleSheets?.skipped && googleSheets?.error;
  const sheetsSkipped = googleSheets?.skipped;
  const docFailed = googleDoc?.error;

  return shell(
    <>
      <div className="flex items-start justify-between gap-3 p-5 pb-4">
        <div className="flex items-center gap-2.5">
          <CheckCircle2 size={20} className="text-[var(--accent)] shrink-0" />
          <div>
            <h2 id="export-modal-title" className="text-sm font-semibold text-[var(--text)]">
              Export complete
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">Open your report and data below.</p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleClose}
          className="p-1 rounded-lg hover:bg-[var(--surface-2)] text-[var(--text-muted)] cursor-pointer"
          aria-label="Close"
        >
          <X size={16} />
        </button>
      </div>

      <div className="px-5 pb-4 space-y-3">
        {docFailed ? (
          <Alert tone="error" title="Google Doc unavailable">
            {googleDoc.error}. Use Save as PDF if the local file downloaded.
          </Alert>
        ) : null}
        {sheetsFailed ? (
          <Alert tone="error" title="Google Sheets unavailable">
            {googleSheets.error}. Your Excel file was still saved locally.
          </Alert>
        ) : null}
        {sheetsSkipped ? (
          <Alert tone="warn" title="Google Sheets not configured">
            {googleSheets.reason || 'Only the local Excel download is available.'}
          </Alert>
        ) : null}

        {hasReport ? (
          <ExportCard
            icon={FileText}
            title="Partnership report"
            hint="Google Doc with KPIs, platforms, and store insights"
            href={docUrl || undefined}
            linkLabel="Open report"
            onCopy={docUrl ? () => docCopy.copy(docUrl) : undefined}
            copied={docCopy.copied}
          >
            {canOpenPdf ? (
              <button
                type="button"
                onClick={onOpenPdf}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text)] hover:bg-[var(--surface)] cursor-pointer"
              >
                <Printer size={13} />
                Save as PDF
              </button>
            ) : null}
          </ExportCard>
        ) : null}

        {hasWorkbook ? (
          <ExportCard
            icon={FileSpreadsheet}
            title="Data workbook"
            hint="Full analysis tabs — Marketing, Stores, Slots, and more"
            href={spreadsheetUrl || undefined}
            linkLabel="Open spreadsheet"
            onCopy={spreadsheetUrl ? () => sheetCopy.copy(spreadsheetUrl) : undefined}
            copied={sheetCopy.copied}
          />
        ) : null}

        {(filename || docFilename) ? (
          <div className="text-[10px] text-[var(--text-subtle)] text-center space-y-1">
            {docFilename ? (
              <p>
                Report saved as{' '}
                <span className="font-mono text-[var(--text-muted)]">{docFilename}</span>
              </p>
            ) : null}
            {filename ? (
              <p>
                Workbook saved as{' '}
                <span className="font-mono text-[var(--text-muted)]">{filename}</span>
              </p>
            ) : null}
            {pdfFilename && canOpenPdf ? (
              <p>
                PDF save-as name:{' '}
                <span className="font-mono text-[var(--text-muted)]">{pdfFilename}</span>
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="px-5 pb-5 flex justify-end border-t border-[var(--border)] pt-4">
        <button
          type="button"
          onClick={handleClose}
          className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer"
        >
          Done
        </button>
      </div>
    </>,
  );
}
