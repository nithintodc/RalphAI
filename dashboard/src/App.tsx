import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AgentsPage } from "./pages/AgentsPage";
import { RunsPage } from "./pages/RunsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { LogsPage } from "./pages/LogsPage";
import { MonthlyReporterPage } from "./pages/MonthlyReporterPage";
import { MarketingRecoPage } from "./pages/MarketingRecoPage";
import { OffersPage } from "./pages/OffersPage";
import { AdsPage } from "./pages/AdsPage";
import { CampaignReviewPage } from "./pages/CampaignReviewPage";
import { DataRunPage } from "./pages/DataRunPage";
import { StrategistPage } from "./pages/StrategistPage";
import { CampaignKillerPage } from "./pages/CampaignKillerPage";
import { HealthCheckPage } from "./pages/HealthCheckPage";
import { JobsPage } from "./pages/JobsPage";
import { AgentIframePage } from "./pages/AgentIframePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/embed" element={<AgentIframePage />} />
        <Route path="/agents/monthly-reporter" element={<MonthlyReporterPage />} />
        <Route path="/agents/marketingreco" element={<MarketingRecoPage />} />
        <Route path="/agents/campaign-review" element={<CampaignReviewPage />} />
        <Route path="/agents/offers" element={<OffersPage />} />
        <Route path="/agents/ads" element={<AdsPage />} />
        <Route path="/agents/data-run" element={<DataRunPage />} />
        <Route path="/agents/strategist" element={<StrategistPage />} />
        <Route path="/agents/health-check" element={<HealthCheckPage />} />
        <Route path="/agents/campaign-killer" element={<CampaignKillerPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
