import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { BomExplorerPage } from "./components/BomExplorerPage";
import { KingdeeSyncPage } from "./modules/kingdee/KingdeeSyncPage";
import { OrdersPage } from "./modules/orders/OrdersPage";
import { QuotesPage } from "./modules/orders/QuotesPage";
import ScheduleWorkspace from "./modules/schedule/ScheduleWorkspace";
import { CockpitPage, ModuleSummaryPage } from "./modules/cockpit/CockpitPage";
import { ProjectBoardPage } from "./modules/project/ProjectBoardPage";
import {
  CrmOpportunitiesPage,
  CrmReportsPage,
  CrmSamplesPage,
  CtpPage,
} from "./modules/crm/CrmPages";
import {
  CheckinPage,
  FollowsPage,
  MyCustomersPage,
  OpportunitiesListPage,
  SeaCustomersPage,
} from "./modules/crm/CrmExtendedPages";
import { VisitPage } from "./modules/crm/VisitPage";
import { ContractedProgressPage } from "./modules/crm/ContractedProgressPage";
import { LeadPoolPage, LeadPoolRulesPage, MyLeadsPage } from "./modules/crm/LeadsPages";
import { GoalsPage } from "./modules/crm/GoalsPage";
import { ScopeNotePage } from "./modules/crm/ScopeNotePage";
import { PaymentsPage } from "./modules/crm/PaymentsPage";
import { LeadReportPage } from "./modules/crm/LeadReportPage";
import { SettingsPage } from "./modules/settings/SettingsPage";
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
import { KbPage } from "./modules/kb/KbPage";
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
            <Route path="/kb" element={<KbPage />} />
            <Route path="/demo" element={<DemoConsolePage />} />
            <Route path="/demo/story/schedule" element={<ScheduleStoryPage />} />
            <Route path="/demo/story/cost" element={<CostStoryPage />} />
            <Route path="/todos" element={<TodoCenterPage />} />
            <Route path="/cockpit" element={<CockpitPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/crm/visit" element={<VisitPage />} />
            <Route path="/crm/customers" element={<MyCustomersPage />} />
            <Route path="/crm/customers/:code" element={<MyCustomersPage />} />
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
            <Route path="/modules/project" element={<ProjectBoardPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/quotes" element={<QuotesPage />} />
            <Route path="/crm/leads/mine" element={<MyLeadsPage />} />
            <Route path="/crm/leads/pool" element={<LeadPoolPage />} />
            <Route path="/crm/leads/rules" element={<LeadPoolRulesPage />} />
            <Route path="/crm/leads/report" element={<LeadReportPage />} />
            <Route path="/crm/goals" element={<GoalsPage />} />
            <Route path="/crm/sea" element={<SeaCustomersPage />} />
            <Route path="/crm/follows" element={<FollowsPage />} />
            <Route path="/crm/checkin" element={<CheckinPage />} />
            <Route path="/crm/opportunities-list" element={<OpportunitiesListPage />} />
            <Route path="/crm/progress" element={<ContractedProgressPage />} />
            <Route path="/crm/payments" element={<PaymentsPage />} />
            <Route path="/crm/contacts" element={<ScopeNotePage kind="contacts" />} />
            <Route path="/crm/returns" element={<ScopeNotePage kind="returns" />} />
            <Route path="/crm/shipments" element={<ScopeNotePage kind="ship" />} />
            <Route path="/crm/reconcile" element={<ScopeNotePage kind="recon" />} />
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
