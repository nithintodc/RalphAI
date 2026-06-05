import { useState, useCallback } from 'react';
import { Upload, CheckCircle2, Circle, FileArchive, FileSpreadsheet, ChevronRight, AlertCircle } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useUiStore } from '../../stores/uiStore';
import { processUploadedFile, ALL_FILE_TYPES } from '../../lib/parsers/zipHandler';
import { normalizeDdFinancial, normalizeDdErrorCharges } from '../../lib/parsers/ddFinancial';
import { normalizeUeFinancial } from '../../lib/parsers/ueFinancial';
import { normalizeDdPromotion, normalizeDdSponsored } from '../../lib/parsers/ddMarketing';
import { applyDdOrderPlacedTiming } from '../../lib/parsers/ddOrderTiming';

function syncDdPlacedTiming() {
  const s = useDataStore.getState();
  const sales = s.ddSales?.byOrder;
  if (s.ddFinancial?.length) {
    s.setDdFinancial(applyDdOrderPlacedTiming(s.ddFinancial, sales));
  }
  if (s.ddFinancialError?.length) {
    s.setDdFinancialError(applyDdOrderPlacedTiming(s.ddFinancialError, sales));
  }
}

const CATEGORY_INFO = {
  Financials: { desc: 'Sales, Payouts, Orders, AOV, Profitability', screens: ['Overview', 'Pre vs Post', 'Stores', 'Slots', 'Days', 'Day-Slot', 'Buckets'] },
  Marketing: { desc: 'Corp vs TODC, ROAS, campaigns', screens: ['Marketing'] },
  Operations: { desc: 'Cancellations, Downtime, Missing orders', screens: ['Operations'] },
  'Product Mix': { desc: 'Item-level performance and mix', screens: ['Product Mix'] },
  Sales: { desc: 'Order, time, and store sales views', screens: ['Slots', 'Days', 'Day-Slot', 'Diagnostics'] },
};

export default function UploadScreen() {
  const [dragActive, setDragActive] = useState(false);
  const [errors, setErrors] = useState([]);
  const store = useDataStore();
  const { setScreen } = useUiStore();
  const uploadedFiles = store.uploadedFiles;
  const isProcessing = store.isProcessing;

  const handleFiles = useCallback(async (files) => {
    store.setProcessing(true);
    setErrors([]);
    const newErrors = [];

    for (const file of files) {
      try {
        const result = await processUploadedFile(file);
        if (result.error) {
          newErrors.push(`${file.name}: ${result.error}`);
          continue;
        }

        const { type, data } = result;

        if (type === 'dd_financial' && data.detailed) {
          const normalized = normalizeDdFinancial(data.detailed);
          store.setDdFinancial(normalized);
          if (data.errorCharges) {
            store.setDdFinancialError(normalizeDdErrorCharges(data.errorCharges));
          }
          store.setUploadedFile('dd_financial', { name: file.name, rows: normalized.length, status: 'done' });
          syncDdPlacedTiming();
        } else if (type === 'dd_marketing') {
          if (data.promotion) {
            store.setDdMarketingRaw('promotion', data.promotion, file.name);
            const promo = normalizeDdPromotion(data.promotion);
            store.setDdMarketing('promotion', promo);
          }
          if (data.sponsored) {
            store.setDdMarketingRaw('sponsored', data.sponsored, file.name);
            const sponsored = normalizeDdSponsored(data.sponsored);
            store.setDdMarketing('sponsored', sponsored);
          }
          store.setUploadedFile('dd_marketing', { name: file.name, status: 'done' });
        } else if (type === 'dd_product_mix' && data.productMix) {
          store.setDdProductMix(data.productMix.data);
          store.setUploadedFile('dd_product_mix', { name: file.name, status: 'done' });
        } else if (type === 'dd_sales_by_order') {
          store.setDdSales('byOrder', data);
          const rowCount = data?.data?.length ?? 0;
          store.setUploadedFile('dd_sales_by_order', { name: file.name, rows: rowCount, status: 'done' });
          syncDdPlacedTiming();
        } else if (type === 'dd_sales_by_time') {
          store.setDdSales('byTime', { ...data, fileLabel: file.name });
          store.setUploadedFile('dd_sales_by_time', { name: file.name, status: 'done' });
        } else if (type === 'dd_sales_by_store') {
          store.setDdSales('byStore', data);
          store.setUploadedFile('dd_sales_by_store', { name: file.name, status: 'done' });
        } else if (type === 'dd_ops_order') {
          store.setDdOps('byOrder', data);
          store.setUploadedFile('dd_ops_order', { name: file.name, status: 'done' });
        } else if (type === 'dd_ops_store') {
          store.setDdOps('byStore', data);
          store.setUploadedFile('dd_ops_store', { name: file.name, status: 'done' });
        } else if (type === 'dd_ops_time') {
          store.setDdOps('byTime', data);
          store.setUploadedFile('dd_ops_time', { name: file.name, status: 'done' });
        } else if (type === 'ue_financial') {
          const normalized = normalizeUeFinancial(data);
          store.setUeFinancial(normalized);
          store.setUploadedFile('ue_financial', { name: file.name, rows: normalized.length, status: 'done' });
        }
      } catch (err) {
        newErrors.push(`${file.name}: ${err.message}`);
      }
    }

    setErrors(newErrors);
    store.setProcessing(false);
  }, [store]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragActive(false);
    handleFiles(Array.from(e.dataTransfer.files));
  }, [handleFiles]);

  const handleInput = useCallback((e) => {
    handleFiles(Array.from(e.target.files));
  }, [handleFiles]);

  const uploadCount = Object.keys(uploadedFiles).length;
  const totalFiles = 10;
  const analysis = store.getAvailableAnalysis();
  const categories = Object.entries(CATEGORY_INFO);

  const canContinue = uploadCount > 0;

  const AnalysisButton = ({ className = '', fullWidth = false }) => (
    <button
      type="button"
      disabled={!canContinue}
      onClick={() => setScreen('config')}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all shrink-0
        ${fullWidth ? 'w-full' : ''} ${className}
        ${canContinue
          ? 'bg-[var(--accent)] text-white shadow-sm hover:bg-[var(--accent-hover)] cursor-pointer'
          : 'bg-[var(--surface-3)] text-[var(--text-subtle)] cursor-not-allowed'}`}
    >
      Continue to analysis
      <ChevronRight size={16} />
    </button>
  );

  const isCategoryAvailable = (cat) =>
    (cat === 'Financials' && analysis.financials) ||
    (cat === 'Marketing' && analysis.marketing) ||
    (cat === 'Operations' && analysis.operations) ||
    (cat === 'Product Mix' && analysis.productMix) ||
    (cat === 'Sales' && analysis.salesViews);

  return (
    <div className="standalone-screen upload-screen bg-[var(--bg)]">
      <div className="standalone-screen-body upload-screen-body p-3 sm:p-4">
        {/* Header */}
        <div className="mb-3 flex shrink-0 items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 shadow-sm">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)] text-base font-bold text-white">R</div>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold leading-tight text-[var(--text)]">
              Ralph <span className="font-normal text-[var(--text-muted)]">Analyse</span>
            </h1>
            <p className="truncate text-xs text-[var(--text-muted)]">Upload platform data to begin analysis</p>
          </div>
        </div>

        {/* Three columns: upload | files | analysis */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {/* Column 1: Drop zone */}
        <div className="flex min-h-0 flex-col gap-2">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            className={`relative flex min-h-[200px] flex-col items-center justify-center rounded-xl border-2 border-dashed p-4 text-center transition-all lg:min-h-[280px]
              ${dragActive ? 'border-[var(--accent)] bg-[var(--accent-soft)]' : 'border-[var(--border-strong)] bg-[var(--surface)]'}
              ${isProcessing ? 'pointer-events-none opacity-60' : ''}`}
          >
            <Upload size={28} className="mb-2 text-[var(--text-subtle)]" />
            <p className="text-xs font-medium text-[var(--text)]">
              {isProcessing ? 'Processing files...' : 'Drop files here or click to browse'}
            </p>
            <p className="mt-1 text-[10px] leading-snug text-[var(--text-subtle)]">
              9 DoorDash ZIPs + 1 UberEats CSV
            </p>
            <input
              type="file"
              multiple
              accept=".zip,.csv"
              onChange={handleInput}
              className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            />
          </div>

          {errors.length > 0 && (
            <div className="max-h-24 shrink-0 space-y-1 overflow-y-auto rounded-lg border border-[var(--negative)] bg-red-50 p-2">
              {errors.map((e, i) => (
                <div key={i} className="flex items-start gap-1.5 text-[11px] text-[var(--negative)]">
                  <AlertCircle size={12} className="mt-0.5 shrink-0" />
                  <span className="break-words">{e}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Column 2: File status */}
        <div className="card">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[var(--text)]">DoorDash</h3>
            <span className="tnum text-[10px] font-medium text-[var(--text-muted)]">
              {Object.keys(uploadedFiles).filter(k => k.startsWith('dd_')).length}/9
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-2">
              {ALL_FILE_TYPES.filter(f => f.platform === 'dd').map(f => {
                const uploaded = !!uploadedFiles[f.key];
                return (
                  <div
                    key={f.key}
                    className={`flex min-w-0 items-center gap-1.5 rounded-md px-2 py-1.5 text-[10px]
                      ${uploaded ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]' : 'bg-[var(--surface-2)] text-[var(--text-muted)]'}`}
                  >
                    {uploaded ? <CheckCircle2 size={12} className="shrink-0" /> : <Circle size={12} className="shrink-0 opacity-30" />}
                    <FileArchive size={11} className="shrink-0" />
                    <span className="truncate">{f.label}</span>
                  </div>
                );
              })}
          </div>

          <div className="mt-3 border-t border-[var(--border)] pt-2">
            <div className="mb-1.5 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[var(--text)]">UberEats</h3>
              <span className="tnum text-[10px] font-medium text-[var(--text-muted)]">
                {uploadedFiles['ue_financial'] ? '1/1' : '0/1'}
              </span>
            </div>
            <div
              className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[10px]
                ${uploadedFiles['ue_financial'] ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]' : 'bg-[var(--surface-2)] text-[var(--text-muted)]'}`}
            >
              {uploadedFiles['ue_financial'] ? <CheckCircle2 size={12} /> : <Circle size={12} className="opacity-30" />}
              <FileSpreadsheet size={11} />
              <span className="truncate">Financial Export (CSV)</span>
            </div>
          </div>

          {uploadCount > 0 && (
            <div className="mt-2 shrink-0">
              <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--surface-3)]">
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-all duration-500"
                  style={{ width: `${(uploadCount / totalFiles) * 100}%` }}
                />
              </div>
              <p className="tnum mt-0.5 text-[10px] text-[var(--text-subtle)]">{uploadCount}/{totalFiles} files uploaded</p>
            </div>
          )}
        </div>

        {/* Column 3: Available analysis */}
        <div className="card">
          <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">Available Analysis</h3>
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {categories.map(([cat, info]) => {
              const available = uploadCount > 0 && isCategoryAvailable(cat);
              return (
                <div
                  key={cat}
                  className={`rounded-md border px-2 py-1.5 text-[10px]
                    ${available ? 'border-[var(--accent-border)] bg-[var(--accent-soft)]' : 'border-[var(--border)] bg-[var(--surface-2)] opacity-60'}`}
                >
                  <div className="flex items-center gap-1.5">
                    {available ? (
                      <CheckCircle2 size={12} className="shrink-0 text-[var(--accent)]" />
                    ) : (
                      <Circle size={12} className="shrink-0 text-[var(--text-subtle)]" />
                    )}
                    <span className="font-medium text-[var(--text)]">{cat}</span>
                  </div>
                  <p className="mt-0.5 ml-[18px] leading-snug text-[var(--text-muted)]">{info.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
        </div>
      </div>

      {/* Always-visible analysis action (fixed footer inside iframe) */}
      <div className="standalone-screen-footer upload-screen-footer px-4 py-3">
        <AnalysisButton fullWidth className="py-3 text-base" />
        {!canContinue && (
          <p className="mt-1.5 text-center text-xs text-[var(--text-subtle)]">Upload at least one file to continue</p>
        )}
      </div>
    </div>
  );
}
