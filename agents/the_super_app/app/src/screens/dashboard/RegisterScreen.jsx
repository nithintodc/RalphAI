import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import PlatformLogo from '../../components/ui/PlatformLogo';
import { fmt } from '../../lib/utils/formatters';
import { exportDdRegister, exportUeRegister } from '../../lib/export/exportWorkbook';
import {
  buildDdRegister,
  buildUeRegister,
  DD_REGISTER_COLUMNS,
  UE_REGISTER_COLUMNS,
} from '../../lib/engine/register';
import { coerceDdSalesByOrderParsed } from '../../lib/parsers/ddSalesByOrder';

function hasDdSalesByOrderUpload(byOrder) {
  const { data } = coerceDdSalesByOrderParsed(byOrder);
  return data.length > 0;
}

function renderCell(kind, v) {
  if (v == null || v === '') return '—';
  if (kind === 'pct') return fmt.pct(v);
  if (kind === 'int') return fmt.int(v);
  if (kind === 'usd') return fmt.usd(v);
  if (kind === 'usd2' || kind === 'num2') return fmt.usd2(v);
  return String(v);
}

function buildTableColumns(specs) {
  return specs.map((c) => ({
    key: c.key,
    label: c.label,
    align: c.kind === 'text' ? 'left' : 'right',
    sortable: true,
    labelCol: c.kind === 'text',
    shrink: c.kind !== 'text',
    render: (v) => {
      if (c.key === 'storeId' || c.key === 'dayOfWeek' || c.key === 'slot') {
        return <span className="font-medium">{renderCell(c.kind, v)}</span>;
      }
      return renderCell(c.kind, v);
    },
  }));
}

function RegisterPanel({ platform, label, rows, columnSpecs, onExport, isExporting }) {
  const columns = useMemo(() => buildTableColumns(columnSpecs), [columnSpecs]);

  if (!rows.length) {
    return (
      <div className="card py-10 text-center">
        <div className="flex justify-center mb-3 opacity-60">
          <PlatformLogo platform={platform} size={24} />
        </div>
        <p className="text-sm text-[var(--text-muted)]">{label} register not available.</p>
        <p className="text-xs text-[var(--text-subtle)] mt-1">
          Upload {label} financial data to build the store × day × slot register.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <PlatformLogo platform={platform} size={18} />
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)]">{label} Register</h3>
            <p className="text-xs text-[var(--text-subtle)]">
              {rows.length.toLocaleString()} rows · store × day × 6 slots · weekday average (zeros included)
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onExport}
          disabled={isExporting}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] text-xs font-medium text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer shrink-0 disabled:opacity-50"
        >
          <Download size={13} />
          {isExporting ? 'Exporting…' : `Export ${label}`}
        </button>
      </div>
      <DataTable
        columns={columns}
        data={rows}
        maxHeight="min(65vh, 640px)"
        dense
        allowHorizontalScroll
      />
    </section>
  );
}

export default function RegisterScreen() {
  const data = useDataStore();
  const config = useConfigStore();
  const [tab, setTab] = useState('dd');
  const [exporting, setExporting] = useState(null);

  const ddRegister = useMemo(() => buildDdRegister(data, config), [data, config]);
  const ueRegister = useMemo(() => buildUeRegister(data, config), [data, config]);

  const handleExport = async (platform) => {
    if (exporting) return;
    setExporting(platform);
    try {
      const snapshot = useDataStore.getState();
      const cfg = useConfigStore.getState();
      if (platform === 'dd') await exportDdRegister(snapshot, cfg);
      else await exportUeRegister(snapshot, cfg);
    } catch (err) {
      console.error('Register export failed:', err);
      window.alert(err.message || 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  const tabs = [
    { id: 'dd', label: 'DD Register', count: ddRegister.length },
    { id: 'ue', label: 'UE Register', count: ueRegister.length },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-[var(--text)]">Register</h2>
        <p className="text-xs text-[var(--text-subtle)] mt-1 max-w-3xl leading-relaxed">
          Layer-1 intermediate data: every metric we can derive at{' '}
          <strong>store × day × slot</strong> grain, averaged across calendar dates for each weekday.
          DoorDash customer type, DashPass, and item counts come from the{' '}
          <strong>SALES_BY_ORDER</strong> export (order placed time for slots).
        </p>
        {tab === 'dd' && !hasDdSalesByOrderUpload(data.ddSales?.byOrder) && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            Upload the DoorDash <strong>sales</strong> ZIP (SALES_BY_ORDER) so New / Repeat / DashPass columns populate.
          </p>
        )}
        {tab === 'dd' && hasDdSalesByOrderUpload(data.ddSales?.byOrder) && (
          <p className="text-xs text-[var(--text-subtle)] mt-2">
            SALES_BY_ORDER loaded ({coerceDdSalesByOrderParsed(data.ddSales?.byOrder).data.length.toLocaleString()} rows).
          </p>
        )}
      </div>

      <div className="flex gap-1 border-b border-[var(--border)]">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors cursor-pointer
              ${tab === t.id
                ? 'border-[var(--accent)] text-[var(--text)]'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]'}`}
          >
            {t.label}
            {t.count > 0 && (
              <span className="ml-1.5 text-[10px] font-normal text-[var(--text-subtle)]">
                ({t.count.toLocaleString()})
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === 'dd' ? (
        <RegisterPanel
          platform="dd"
          label="DoorDash"
          rows={ddRegister}
          columnSpecs={DD_REGISTER_COLUMNS}
          onExport={() => handleExport('dd')}
          isExporting={exporting === 'dd'}
        />
      ) : (
        <RegisterPanel
          platform="ue"
          label="Uber Eats"
          rows={ueRegister}
          columnSpecs={UE_REGISTER_COLUMNS}
          onExport={() => handleExport('ue')}
          isExporting={exporting === 'ue'}
        />
      )}
    </div>
  );
}
