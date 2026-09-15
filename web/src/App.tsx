import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { BomExplorerPage } from "./components/BomExplorerPage";
import { KingdeeSyncPage } from "./modules/kingdee/KingdeeSyncPage";
import { OrdersPage } from "./modules/orders/OrdersPage";
import ScheduleWorkspace from "./modules/schedule/ScheduleWorkspace";
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
