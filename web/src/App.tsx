import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { BomExplorerPage } from "./components/BomExplorerPage";
import { KingdeeSyncPage } from "./modules/kingdee/KingdeeSyncPage";
import { OrdersPage } from "./modules/orders/OrdersPage";
import { QuotesPage } from "./modules/orders/QuotesPage";
import ScheduleWorkspace from "./modules/schedule/ScheduleWorkspace";
import { CockpitPage, ModuleSummaryPage } from "./modules/cockpit/CockpitPage";
import {
  CrmCustomersPage,
  CrmOpportunitiesPage,
  CrmReportsPage,
  CrmSamplesPage,
  CtpPage,
} from "./modules/crm/CrmPages";
import { DemoConsolePage, TodoCenterPage } from "./modules/demo/DemoPages";
import { CostStoryPage, ScheduleStoryPage } from "./modules/demo/StoryPages";
import { HrAttendancePage, HrRosterPage } from "./modules/hr/HrPages";
import { HrLaborCostPage, ProductionTimeReportPage } from "./modules/labor/LaborPages";
import { Dept1StatsPage } from "./modules/production/ProdStatsPages";
import { OrderChangesPage } from "./modules/flow/OrderChangesPage";
import {
  QcAuditsPage,
  QcComplaintsPage,
  QcDailyDefectsPage,
  QcExceptionsPage,
  QcLabExternalPage,
  QcMasterPage,
  QcProductTestsPage,
  QcReceiptsPage,
  QcSwabTestsPage,
} from "./modules/qc/QcPages";
import { PortalPage } from "./pages/PortalPage";
import { StockCenterPage } from "./pages/StockCenterPage";
import { AuthProvider, RequireAuth } from "./shell/auth";
import { LoginPage } from "./shell/LoginPage";
import { ShellLayout } from "./shell/ShellLayout";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <ShellLayout />
              </RequireAuth>
            }
          >
            <Route path="/portal" element={<PortalPage />} />
            <Route path="/demo" element={<DemoConsolePage />} />
            <Route path="/demo/story/schedule" element={<ScheduleStoryPage />} />
            <Route path="/demo/story/cost" element={<CostStoryPage />} />
            <Route path="/todos" element={<TodoCenterPage />} />
            <Route path="/cockpit" element={<CockpitPage />} />
            <Route path="/crm/customers" element={<CrmCustomersPage />} />
            <Route path="/crm/customers/:code" element={<CrmCustomersPage />} />
            <Route path="/crm/opportunities" element={<CrmOpportunitiesPage />} />
            <Route path="/crm/opportunities/:id" element={<CrmOpportunitiesPage />} />
            <Route path="/crm/samples" element={<CrmSamplesPage />} />
            <Route path="/crm/samples/:code" element={<CrmSamplesPage />} />
            <Route path="/crm/reports" element={<CrmReportsPage />} />
            <Route path="/crm/ctp" element={<CtpPage />} />
            <Route path="/changes" element={<OrderChangesPage />} />
            <Route path="/modules/hr" element={<Navigate to="/modules/hr/roster" replace />} />
            <Route path="/modules/hr/roster" element={<HrRosterPage />} />
            <Route path="/modules/hr/roster/:empNo" element={<HrRosterPage />} />
            <Route path="/modules/hr/attendance" element={<HrAttendancePage />} />
            <Route path="/modules/hr/labor-cost" element={<HrLaborCostPage />} />
            <Route path="/modules/production" element={<ModuleSummaryPage module="production" />} />
            <Route path="/modules/production/time-report" element={<ProductionTimeReportPage />} />
            <Route path="/modules/production/stats/dept1" element={<Dept1StatsPage />} />
            <Route path="/modules/finance" element={<ModuleSummaryPage module="finance" />} />
            <Route path="/modules/project" element={<ModuleSummaryPage module="project" />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/quotes" element={<QuotesPage />} />
            <Route path="/kingdee" element={<KingdeeSyncPage />} />
            <Route path="/schedule" element={<ScheduleWorkspace />} />
            <Route path="/stock" element={<StockCenterPage planAllocations={[]} />} />
            <Route path="/bom" element={<BomExplorerPage />} />
            <Route path="/qc/receipts" element={<QcReceiptsPage />} />
            <Route path="/qc/exceptions" element={<QcExceptionsPage />} />
            <Route path="/qc/daily-defects" element={<QcDailyDefectsPage />} />
            <Route path="/qc/complaints" element={<QcComplaintsPage />} />
            <Route path="/qc/audits" element={<QcAuditsPage />} />
            <Route path="/qc/lab-external" element={<QcLabExternalPage />} />
            <Route path="/qc/swab-tests" element={<QcSwabTestsPage />} />
            <Route path="/qc/product-tests" element={<QcProductTestsPage />} />
            <Route path="/qc/master" element={<QcMasterPage />} />
            <Route path="/qc" element={<Navigate to="/qc/receipts" replace />} />
            <Route path="/" element={<Navigate to="/portal" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
