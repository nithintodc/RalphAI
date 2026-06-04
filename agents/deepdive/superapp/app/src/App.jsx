import { useState, useMemo, useRef } from 'react';
import ExportResultModal from './components/ui/ExportResultModal';
import { useUiStore } from './stores/uiStore';
import { useDataStore } from './stores/dataStore';
import { useConfigStore } from './stores/configStore';
import Shell from './components/layout/Shell';
import UploadScreen from './screens/upload/UploadScreen';
import ConfigScreen from './screens/config/ConfigScreen';
import OverviewScreen from './screens/dashboard/OverviewScreen';
import CompareScreen from './screens/dashboard/CompareScreen';
import DiagnosticsScreen from './screens/dashboard/DiagnosticsScreen';
import StoresScreen from './screens/dashboard/StoresScreen';
import AbComparisonScreen from './screens/dashboard/AbComparisonScreen';
import StoreDetailScreen from './screens/dashboard/StoreDetailScreen';
import SlotsScreen from './screens/dashboard/SlotsScreen';
import BucketsScreen from './screens/dashboard/BucketsScreen';
import MarketingScreen from './screens/dashboard/MarketingScreen';
import OperationsScreen from './screens/dashboard/OperationsScreen';
import ProductMixScreen from './screens/dashboard/ProductMixScreen';
import App2DateWiseScreen from './screens/dashboard/App2DateWiseScreen';
import App2BucketingScreen from './screens/dashboard/App2BucketingScreen';
import MapScreen from './screens/dashboard/MapScreen';
import { formatDateShort } from './lib/utils/dateUtils';
import { exportAllReports } from './lib/export/exportWorkbook';
import { exportPartnershipReport, openReportForPdf } from './lib/export/reportDocument';

const DASHBOARD_SCREENS = {
  overview: OverviewScreen,
  compare: CompareScreen,
  diagnostics: DiagnosticsScreen,
  stores: StoresScreen,
  abComparison: AbComparisonScreen,
  storeDetail: StoreDetailScreen,
  slots: SlotsScreen,
  buckets: BucketsScreen,
  marketing: MarketingScreen,
  operations: OperationsScreen,
  productMix: ProductMixScreen,
  app2DateWise: App2DateWiseScreen,
  app2Bucketing: App2BucketingScreen,
  map: MapScreen,
};

export default function App() {
  const [isExporting, setIsExporting] = useState(false);
  const [exportModal, setExportModal] = useState(null);
  const reportSnapshot = useRef(null);
  const { screen, activeTab, setActiveTab } = useUiStore();
  const config = useConfigStore();

  const periodLabel = useMemo(() => {
    if (!config.ddPreStart || !config.ddPostStart) return null;
    const sameWindow =
      config.ddPreStart?.getTime?.() === config.ddPostStart?.getTime?.()
      && config.ddPreEnd?.getTime?.() === config.ddPostEnd?.getTime?.();
    if (sameWindow) {
      const start = formatDateShort(config.ddPostStart);
      const end = formatDateShort(config.ddPostEnd);
      return start === end ? start : `${start} – ${end}`;
    }
    return `${formatDateShort(config.ddPreStart)} vs ${formatDateShort(config.ddPostStart)}`;
  }, [config.ddPreStart, config.ddPreEnd, config.ddPostStart, config.ddPostEnd]);

  const handleExport = async () => {
    if (isExporting) return;
    setIsExporting(true);
    setExportModal({ kind: 'loading' });
    try {
      const data = useDataStore.getState();
      const config = useConfigStore.getState();
      reportSnapshot.current = { data, config };

      const result = await exportAllReports(data, config);
      if (result.googleSheets?.skipped) {
        console.info('Google Sheets export:', result.googleSheets.reason);
      }

      let report = {};
      try {
        report = await exportPartnershipReport(data, config);
      } catch (reportErr) {
        console.error('Report export failed:', reportErr);
        report = { googleDoc: { error: reportErr.message || String(reportErr) } };
      }

      setExportModal({
        kind: 'result',
        filename: result.filename,
        spreadsheetUrl: result.spreadsheetUrl ?? null,
        googleSheets: result.googleSheets,
        docFilename: report.docFilename ?? null,
        docUrl: report.docUrl ?? null,
        googleDoc: report.googleDoc ?? null,
        canOpenPdf: !!reportSnapshot.current,
      });
    } catch (err) {
      console.error('Export failed:', err);
      setExportModal({ kind: 'error', message: err.message || String(err) });
    } finally {
      setIsExporting(false);
    }
  };

  const handleOpenPdf = () => {
    if (!reportSnapshot.current) return;
    openReportForPdf(reportSnapshot.current.data, reportSnapshot.current.config);
  };

  if (screen === 'upload') return <UploadScreen />;
  if (screen === 'config') return <ConfigScreen />;

  const DashboardScreen = DASHBOARD_SCREENS[activeTab] || OverviewScreen;

  return (
    <>
      <Shell
        active={activeTab}
        setActive={setActiveTab}
        periodLabel={periodLabel}
        onExport={handleExport}
        isExporting={isExporting}
      >
        <DashboardScreen />
      </Shell>
      <ExportResultModal
        open={!!exportModal}
        payload={exportModal}
        onOpenPdf={handleOpenPdf}
        onClose={() => setExportModal(null)}
      />
    </>
  );
}
