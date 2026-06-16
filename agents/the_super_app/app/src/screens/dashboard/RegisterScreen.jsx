import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import DataTable from '../../components/ui/DataTable';
import PlatformLogo from '../../components/ui/PlatformLogo';
import { formatByKind } from '../../lib/utils/formatters';
import { exportDdRegister, exportUeRegister } from '../../lib/export/exportWorkbook';
import {
  buildDdRegister,
  buildUeRegister,
  DD_REGISTER_COLUMNS,
  UE_REGISTER_COLUMNS,
} from '../../lib/engine/register';
import { buildPeriodExcludedStores, mergeExcludedStores } from '../../lib/utils/storePeriodAlignment';
import { getUniqueStores as getDdStores } from '../../lib/parsers/ddFinancial';
import { getUniqueStores as getUeStores } from '../../lib/parsers/ueFinancial';
import { ddMerchantStoreIdFromKey } from '../../lib/utils/storeDisplay';
import { isSinglePeriodMode } from '../../lib/utils/periodMode';
import GroupedBarChart from '../../components/charts/GroupedBarChart';
import { SLOT_NAMES } from '../../lib/engine/slots';
import { fmt } from '../../lib/utils/formatters';
import { SERIES } from '../../components/charts/chartTheme';

/** Roll the store × day × slot register up to a 6-slot daypart summary. */
function RegisterDaypartCharts({ rows }) {
  const bySlot = SLOT_NAMES.map((slot) => {
    const rs = rows.filter((r) => r.slot === slot);
    return {
      slot,
      sales: rs.reduce((s, r) => s + (Number(r.sales) || 0), 0),
      orders: rs.reduce((s, r) => s + (Number(r.orders) || 0), 0),
    };
  });
  if (!bySlot.some((s) => s.sales || s.orders)) return null;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      <GroupedBarChart
        title="Sales by day-part"
        subtitle="Total register sales rolled up across stores & weekdays."
        data={bySlot}
        xKey="slot"
        height={240}
        valueFormatter={fmt.usdK}
        series={[{ key: 'sales', name: 'Sales', color: SERIES.post }]}
        legend={false}
      />
      <GroupedBarChart
        title="Orders by day-part"
        subtitle="Total order count by day-part slot."
        data={bySlot}
        xKey="slot"
        height={240}
        valueFormatter={fmt.int}
        series={[{ key: 'orders', name: 'Orders', color: SERIES.pre }]}
        legend={false}
      />
    </div>
  );
}

function hasDdSalesByOrderUpload(byOrder) {
  const { data } = coerceDdSalesByOrderParsed(byOrder);
  return data.length > 0;
}

function renderCell(kind, v) {
  return formatByKind(kind, v);
}

function buildTableColumns(specs, platform, ddFinancial) {
  return specs.map((c) => ({
    key: c.key,
    label: c.label,
    align: c.kind === 'text' ? 'left' : 'right',
    sortable: true,
    labelCol: c.kind === 'text',
    shrink: c.kind !== 'text',
    render: (v) => {
      if (c.key === 'storeId' && platform === 'dd') {
        return <span className="font-medium">{ddMerchantStoreIdFromKey(v, ddFinancial) || v}</span>;
      }
      if (c.key === 'storeId' || c.key === 'dayOfWeek' || c.key === 'slot' || c.key === 'slotTime') {
        return <span className="font-medium">{renderCell(c.kind, v)}</span>;
      }
      return renderCell(c.kind, v);
    },
  }));
}

function RegisterPanel({ platform, label, rows, columnSpecs, onExport, isExporting, ddFinancial }) {
  const columns = useMemo(
    () => buildTableColumns(columnSpecs, platform, ddFinancial),
    [columnSpecs, platform, ddFinancial],
  );

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
      <RegisterDaypartCharts rows={rows} />
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

  const registerConfig = useMemo(() => {
    if (isSinglePeriodMode(config.dateAnalysisMode)) return config;
    const ddStores = data.ddFinancial ? getDdStores(data.ddFinancial) : [];
    const ueStores = data.ueFinancial ? getUeStores(data.ueFinancial) : [];
    return {
      ...config,
      ddExcludedStores: mergeExcludedStores(
        config.ddExcludedStores,
        buildPeriodExcludedStores(ddStores, data.storePeriodAlignment?.dd),
      ),
      ueExcludedStores: mergeExcludedStores(
        config.ueExcludedStores,
        buildPeriodExcludedStores(ueStores, data.storePeriodAlignment?.ue),
      ),
    };
  }, [config, data.ddFinancial, data.ueFinancial, data.storePeriodAlignment]);

  const ddRegister = useMemo(() => buildDdRegister(data, registerConfig), [data, registerConfig]);
  const ueRegister = useMemo(() => buildUeRegister(data, registerConfig), [data, registerConfig]);

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
        {tab === 'ue' && (
          <p className="text-xs text-[var(--text-subtle)] mt-2">
            Uber Eats: <strong>Marketplace Fee</strong> is platform commission (not ads).
            Promo = offers + delivery offers; Ads = ad spend from Other payments (per UE financial export).
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
          ddFinancial={data.ddFinancial}
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
