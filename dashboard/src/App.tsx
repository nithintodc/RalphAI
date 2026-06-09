import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AgentsPage } from "./pages/AgentsPage";
import { RunsPage } from "./pages/RunsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { LogsPage } from "./pages/LogsPage";
import { OffersPage } from "./pages/OffersPage";
import { AdsPage } from "./pages/AdsPage";
import { DataRunPage } from "./pages/DataRunPage";
import { StrategistPage } from "./pages/StrategistPage";
import { HealthCheckPage } from "./pages/HealthCheckPage";
import { JobsPage } from "./pages/JobsPage";
import { InternalAppPage } from "./pages/InternalAppPage";
import { StoreMapPage } from "./pages/StoreMapPage";
import { ReportingBrowserUsePage } from "./pages/ReportingBrowserUsePage";
import { OperatorProfileMappingPage } from "./pages/OperatorProfileMappingPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/store-map" element={<StoreMapPage />} />
        <Route path="/agents/the-super-app" element={<InternalAppPage />} />
        <Route path="/agents/markup-app" element={<InternalAppPage />} />
        <Route path="/agents/embed" element={<Navigate to="/agents" replace />} />
        <Route
          path="/agents/monthly-reporter"
          element={<Navigate to="/agents/the-super-app" replace />}
        />
        <Route path="/agents/marketingreco" element={<Navigate to="/agents/strategist" replace />} />
        <Route path="/agents/campaign-review" element={<Navigate to="/agents/health-check" replace />} />
        <Route path="/agents/offers" element={<OffersPage />} />
        <Route path="/agents/ads" element={<AdsPage />} />
        <Route path="/agents/data-run" element={<DataRunPage />} />
        <Route path="/agents/strategist" element={<StrategistPage />} />
        <Route path="/agents/health-check" element={<HealthCheckPage />} />
        <Route
          path="/agents/reporting-browser-use/:forkId"
          element={<ReportingBrowserUsePage />}
        />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/settings/operator-mapping" element={<OperatorProfileMappingPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
