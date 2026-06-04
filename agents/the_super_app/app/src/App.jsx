import { useState, useMemo, useRef, useEffect } from 'react';
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
import RegisterScreen from './screens/dashboard/RegisterScreen';
import MapScreen from './screens/dashboard/MapScreen';
import BreakdownScreen from './screens/dashboard/BreakdownScreen';
import { formatPeriodComparisonLabel } from './lib/utils/dateUtils';
import { exportAllReports } from './lib/export/exportWorkbook';
import { exportPartnershipReport, openReportForPdf } from './lib/export/reportDocument';
import { notifySlackExport } from './lib/export/notifySlackExport';

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
  register: RegisterScreen,
  map: MapScreen,
  breakdown: BreakdownScreen,
};

export default function App() {
  useEffect(() => {
    if (typeof window !== 'undefined' && window.self !== window.top) {
      document.documentElement.classList.add('in-iframe');
    }
  }, []);

  useEffect(() => {
    const tab = new URLSearchParams(window.location.search).get('tab');
    if (tab && DASHBOARD_SCREENS[tab]) {
      useUiStore.getState().setActiveTab(tab);
    }
  }, []);

  const [isExporting, setIsExporting] = useState(false);
  const [exportModal, setExportModal] = useState(null);
  const reportSnapshot = useRef(null);
  const { screen, activeTab, setActiveTab } = useUiStore();
  const config = useConfigStore();

  const periodLabel = useMemo(
    () => formatPeriodComparisonLabel(
      config.ddPreStart,
      config.ddPreEnd,
      config.ddPostStart,
      config.ddPostEnd,
    ),
    [config.ddPreStart, config.ddPreEnd, config.ddPostStart, config.ddPostEnd],
  );

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

      const spreadsheetUrl = result.spreadsheetUrl ?? null;
      const docUrl = report.docUrl ?? null;

      // Notify Slack whenever local export succeeded (links may be null if Google push failed).
      notifySlackExport(config, { docUrl, spreadsheetUrl });

      setExportModal({
        kind: 'result',
        filename: result.filename,
        spreadsheetUrl,
        googleSheets: result.googleSheets,
        docFilename: report.docFilename ?? null,
        docUrl,
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

  const handleOpenPdf = async () => {
    if (!reportSnapshot.current) return;
    await openReportForPdf(reportSnapshot.current.data, reportSnapshot.current.config);
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
        {activeTab === 'map' ? (
          <DashboardScreen />
        ) : (
          <div className="max-w-full min-w-0 overflow-x-hidden">
            <DashboardScreen />
          </div>
        )}
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
