import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { BomExplorerPage } from "./components/BomExplorerPage";
import { KingdeeSyncPage } from "./modules/kingdee/KingdeeSyncPage";
import { OrdersPage } from "./modules/orders/OrdersPage";
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
import { HrAttendancePage, HrRosterPage } from "./modules/hr/HrPages";
import { HrLaborCostPage, ProductionTimeReportPage } from "./modules/labor/LaborPages";
import { OrderChangesPage } from "./modules/flow/OrderChangesPage";
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
            <Route path="/modules/finance" element={<ModuleSummaryPage module="finance" />} />
            <Route path="/modules/project" element={<ModuleSummaryPage module="project" />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/kingdee" element={<KingdeeSyncPage />} />
            <Route path="/schedule" element={<ScheduleWorkspace />} />
            <Route path="/stock" element={<StockCenterPage planAllocations={[]} />} />
            <Route path="/bom" element={<BomExplorerPage />} />
            <Route path="/" element={<Navigate to="/portal" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
