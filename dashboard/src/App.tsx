import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { AgentsPage } from "./pages/AgentsPage";
import { RunsPage } from "./pages/RunsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { LogsPage } from "./pages/LogsPage";
import { MonthlyReporterPage } from "./pages/MonthlyReporterPage";
import { DeepDivePage } from "./pages/DeepDivePage";
import { MarketingRecoPage } from "./pages/MarketingRecoPage";
import { OffersPage } from "./pages/OffersPage";
import { AdsPage } from "./pages/AdsPage";
import { CampaignReviewPage } from "./pages/CampaignReviewPage";
import { DataRunPage } from "./pages/DataRunPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/monthly-reporter" element={<MonthlyReporterPage />} />
        <Route path="/agents/deepdive" element={<DeepDivePage />} />
        <Route path="/agents/marketingreco" element={<MarketingRecoPage />} />
        <Route path="/agents/campaign-review" element={<CampaignReviewPage />} />
        <Route path="/agents/offers" element={<OffersPage />} />
        <Route path="/agents/ads" element={<AdsPage />} />
        <Route path="/agents/data-run" element={<DataRunPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
