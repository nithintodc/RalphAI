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
  Financials: { desc: 'Sales, Payouts, Orders, AOV, Profitability, Bucketing, Slots', screens: ['Overview', 'Pre vs Post', 'Stores', 'Slots', 'Buckets'] },
  Marketing: { desc: 'Export breakdown pivots, Corp vs TODC, ROAS, campaigns', screens: ['Marketing'] },
  Operations: { desc: 'Cancellations, Downtime, Missing/Incorrect orders', screens: ['Operations'] },
  'Product Mix': { desc: 'Item-level performance and mix analysis', screens: ['Product Mix'] },
  Sales: { desc: 'Order-level, time-based, and store-level sales views', screens: ['Slots', 'Diagnostics'] },
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

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6 sm:p-8">
      <div className="w-full max-w-3xl mx-auto space-y-6 pb-12">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2.5 mb-4">
            <div className="w-10 h-10 rounded-xl bg-[var(--accent)] text-white flex items-center justify-center font-bold text-lg">R</div>
            <h1 className="text-2xl font-bold text-[var(--text)]">Ralph <span className="font-normal text-[var(--text-muted)]">Analyse</span></h1>
          </div>
          <p className="text-[var(--text-muted)]">Upload your platform data files to begin analysis</p>
        </div>

        {/* Drop Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-xl p-10 text-center transition-all
            ${dragActive ? 'border-[var(--accent)] bg-[var(--accent-soft)]' : 'border-[var(--border-strong)] bg-[var(--surface)]'}
            ${isProcessing ? 'opacity-60 pointer-events-none' : ''}`}
        >
          <Upload size={36} className="mx-auto mb-3 text-[var(--text-subtle)]" />
          <p className="text-sm font-medium text-[var(--text)]">
            {isProcessing ? 'Processing files...' : 'Drop your files here, or click to browse'}
          </p>
          <p className="text-xs text-[var(--text-subtle)] mt-1">
            9 DoorDash ZIPs + 1 UberEats CSV — upload all or just what you have
          </p>
          <input
            type="file"
            multiple
            accept=".zip,.csv"
            onChange={handleInput}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />
        </div>

        {/* Error Messages */}
        {errors.length > 0 && (
          <div className="card border-[var(--negative)] bg-red-50 p-4 space-y-1">
            {errors.map((e, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-[var(--negative)]">
                <AlertCircle size={14} className="mt-0.5 shrink-0" />
                {e}
              </div>
            ))}
          </div>
        )}

        {/* Upload Progress */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--text)]">DoorDash Files</h3>
            <span className="text-xs font-medium text-[var(--text-muted)] tnum">
              {Object.keys(uploadedFiles).filter(k => k.startsWith('dd_')).length}/9 uploaded
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {ALL_FILE_TYPES.filter(f => f.platform === 'dd').map(f => {
              const uploaded = !!uploadedFiles[f.key];
              return (
                <div key={f.key} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs
                  ${uploaded ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]' : 'bg-[var(--surface-2)] text-[var(--text-muted)]'}`}>
                  {uploaded ? <CheckCircle2 size={14} /> : <Circle size={14} className="opacity-30" />}
                  <FileArchive size={13} />
                  {f.label}
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between mt-6 mb-3">
            <h3 className="font-semibold text-[var(--text)]">UberEats File</h3>
            <span className="text-xs font-medium text-[var(--text-muted)] tnum">
              {uploadedFiles['ue_financial'] ? '1/1' : '0/1'} uploaded
            </span>
          </div>
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs
            ${uploadedFiles['ue_financial'] ? 'bg-[var(--accent-soft)] text-[var(--accent-text)]' : 'bg-[var(--surface-2)] text-[var(--text-muted)]'}`}>
            {uploadedFiles['ue_financial'] ? <CheckCircle2 size={14} /> : <Circle size={14} className="opacity-30" />}
            <FileSpreadsheet size={13} />
            Financial Export (CSV)
          </div>

          {/* Progress Bar */}
          {uploadCount > 0 && (
            <div className="mt-4">
              <div className="w-full h-1.5 bg-[var(--surface-3)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[var(--accent)] rounded-full transition-all duration-500"
                  style={{ width: `${(uploadCount / totalFiles) * 100}%` }}
                />
              </div>
              <p className="text-xs text-[var(--text-subtle)] mt-1 tnum">{uploadCount}/{totalFiles} files uploaded</p>
            </div>
          )}
        </div>

        {/* Available Analysis */}
        {uploadCount > 0 && (
          <div className="card">
            <h3 className="font-semibold text-[var(--text)] mb-3">Available Analysis</h3>
            <div className="grid grid-cols-2 gap-2">
              {categories.map(([cat, info]) => {
                const available =
                  (cat === 'Financials' && analysis.financials) ||
                  (cat === 'Marketing' && analysis.marketing) ||
                  (cat === 'Operations' && analysis.operations) ||
                  (cat === 'Product Mix' && analysis.productMix) ||
                  (cat === 'Sales' && analysis.salesViews);
                return (
                  <div key={cat} className={`px-3 py-2.5 rounded-lg border text-xs
                    ${available ? 'border-[var(--accent-border)] bg-[var(--accent-soft)]' : 'border-[var(--border)] bg-[var(--surface-2)] opacity-50'}`}>
                    <div className="flex items-center gap-2">
                      {available ? <CheckCircle2 size={14} className="text-[var(--accent)]" /> : <Circle size={14} className="text-[var(--text-subtle)]" />}
                      <span className="font-medium text-[var(--text)]">{cat}</span>
                    </div>
                    <p className="text-[var(--text-muted)] mt-0.5 ml-[22px]">{info.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Continue Button */}
        <div className="flex justify-end">
          <button
            disabled={!canContinue}
            onClick={() => setScreen('config')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg font-medium text-sm transition-all
              ${canContinue
                ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] cursor-pointer'
                : 'bg-[var(--surface-3)] text-[var(--text-subtle)] cursor-not-allowed'}`}
          >
            Continue
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
