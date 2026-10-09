import "@/App.css";
import "@/r50.css";
import "@/r51.css";
import "@/r52.css";
import "@/r52-pages.css";
import "@/r52-extra.css";
import "@/r52-polish.css";
import "@/r55.css";
import "@/r56.css";
import "@/r61.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { InventoryProvider } from "@/lib/InventoryContext";
import { AuthProvider, useAuth } from "@/lib/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppLayout from "@/components/AppLayout";
import DashboardPage from "@/pages/DashboardPage";
import CalendarPage from "@/pages/CalendarPage";
import InventarioPage from "@/pages/InventarioPage";
import EliosTechOrdiniPage from "@/pages/EliosTechOrdiniPage";
import TrasferimentiPage from "@/pages/TrasferimentiPage";
import ArriviPage from "@/pages/ArriviPage";
import MovimentiPage from "@/pages/MovimentiPage";
import AnomaliePage from "@/pages/AnomaliePage";
import ChecklistPage from "@/pages/ChecklistPage";
import AIAssistantPage from "@/pages/AIAssistantPage";
import CommessePage from "@/pages/CommessePage";
import CommesseInsightsPage from "@/pages/CommesseInsightsPage";
import ReportsPage from "@/pages/ReportsPage";
import AdminPage from "@/pages/AdminPage";
import NotionMigrationPage from "@/pages/NotionMigrationPage";
import { FeaturesProvider } from "@/lib/FeaturesContext";
import AdminUsersPage from "@/pages/AdminUsersPage";
import LoginPage from "@/pages/LoginPage";
import ResetPasswordPage from "@/pages/ResetPasswordPage";
import ForceChangePasswordPage from "@/pages/ForceChangePasswordPage";
import { Navigate as Nav } from "react-router-dom";
import { SopralluoghiPage, InstallazioniPage, AssistenzaPage } from "@/pages/BusinessPages";
import PreventiviPage from "@/pages/PreventiviPage";
import AppConfirmProvider from "@/components/AppConfirmProvider";
import AppErrorBoundary from "@/components/AppErrorBoundary";
import CustomModulePage from "@/pages/CustomModulePage";
import ModuleBuilderPage from "@/pages/ModuleBuilderPage";

function LandingRedirect() {
  const { hasPermission } = useAuth();
  const targets = [
    ["dashboard", "/dashboard"], ["calendar", "/calendario"], ["ordini_clienti", "/clienti-ordini"],
    ["commesse", "/commesse"], ["inventario", "/inventario"], ["arrivi", "/arrivi"],
    ["spedizioni", "/spedizioni"], ["sopralluoghi", "/sopralluoghi"], ["preventivi", "/preventivi"],
    ["installazioni", "/installazioni"], ["assistenza", "/assistenza"],
  ];
  const found = targets.find(([module]) => hasPermission(module, "view"));
  return <Navigate to={found ? found[1] : "/login"} replace />;
}

function PasswordGate({ children }) {
  const { isAuthenticated, mustChangePassword } = useAuth();
  if (isAuthenticated && mustChangePassword) return <Nav to="/force-change-password" replace />;
  return children;
}

function App() {
  return (
    <AppErrorBoundary>
      <div className="App">
        <BrowserRouter>
          <AuthProvider>
            <InventoryProvider>
              <FeaturesProvider>
                <AppConfirmProvider>
                  <Routes>
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/reset-password" element={<ResetPasswordPage />} />
                    <Route path="/force-change-password" element={<ProtectedRoute><ForceChangePasswordPage /></ProtectedRoute>} />
                    <Route element={<ProtectedRoute><PasswordGate><AppLayout /></PasswordGate></ProtectedRoute>}>
                      <Route path="/" element={<LandingRedirect />} />
                      <Route path="/dashboard" element={<ProtectedRoute permission="dashboard"><DashboardPage /></ProtectedRoute>} />
                      <Route path="/calendario" element={<ProtectedRoute permission="calendar"><CalendarPage /></ProtectedRoute>} />
                      <Route path="/inventario" element={<ProtectedRoute permission="inventario"><InventarioPage warehouseId="elios-tech" warehouseName="Magazzino Elios Tech" /></ProtectedRoute>} />
                      <Route path="/magazzino-verona" element={<ProtectedRoute permission="inventario"><InventarioPage warehouseId="verona" warehouseName="Magazzino Verona" /></ProtectedRoute>} />
                      <Route path="/trasferimenti" element={<ProtectedRoute permission="movimenti"><TrasferimentiPage /></ProtectedRoute>} />
                      <Route path="/arrivi" element={<ProtectedRoute permission="arrivi"><ArriviPage /></ProtectedRoute>} />
                      <Route path="/spedizioni" element={<ProtectedRoute permission="spedizioni"><ChecklistPage /></ProtectedRoute>} />
                      <Route path="/movimenti" element={<ProtectedRoute permission="movimenti"><MovimentiPage /></ProtectedRoute>} />
                      <Route path="/anomalie" element={<ProtectedRoute permission="anomalie"><AnomaliePage /></ProtectedRoute>} />
                      <Route path="/assistente-ai" element={<ProtectedRoute permission="ai"><AIAssistantPage /></ProtectedRoute>} />
                      <Route path="/moduli/:slug" element={<CustomModulePage />} />
                      <Route path="/admin/moduli" element={<ProtectedRoute requireAdmin><ModuleBuilderPage /></ProtectedRoute>} />
                      <Route path="/admin/migrazione-notion" element={<ProtectedRoute requireAdmin><NotionMigrationPage /></ProtectedRoute>} />
                      <Route path="/commesse" element={<ProtectedRoute permission="commesse"><CommessePage /></ProtectedRoute>} />
                      <Route path="/fatturato" element={<ProtectedRoute permission="commesse"><CommesseInsightsPage mode="fatturato" /></ProtectedRoute>} />
                      <Route path="/wallbox" element={<ProtectedRoute permission="commesse"><CommesseInsightsPage mode="wallbox" /></ProtectedRoute>} />
                      <Route path="/report" element={<ProtectedRoute permission="commesse"><ReportsPage /></ProtectedRoute>} />
                      <Route path="/clienti-ordini" element={<ProtectedRoute permission="ordini_clienti"><EliosTechOrdiniPage /></ProtectedRoute>} />
                      <Route path="/elios-tech-ordini" element={<Navigate to="/clienti-ordini" replace />} />
                      <Route path="/clienti" element={<Navigate to="/clienti-ordini" replace />} />
                      <Route path="/contatti" element={<Navigate to="/clienti-ordini" replace />} />
                      <Route path="/sedi" element={<Navigate to="/clienti-ordini" replace />} />
                      <Route path="/sopralluoghi" element={<ProtectedRoute permission="sopralluoghi"><SopralluoghiPage /></ProtectedRoute>} />
                      <Route path="/preventivi" element={<ProtectedRoute permission="preventivi"><PreventiviPage /></ProtectedRoute>} />
                      <Route path="/ordini-clienti" element={<Navigate to="/clienti-ordini" replace />} />
                      <Route path="/installazioni" element={<ProtectedRoute permission="installazioni"><InstallazioniPage /></ProtectedRoute>} />
                      <Route path="/assistenza" element={<ProtectedRoute permission="assistenza"><AssistenzaPage /></ProtectedRoute>} />
                      <Route path="/admin" element={<ProtectedRoute requireAdmin><AdminPage /></ProtectedRoute>} />
                      <Route path="/admin/utenti" element={<ProtectedRoute requireAdmin><AdminUsersPage /></ProtectedRoute>} />
                    </Route>
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </AppConfirmProvider>
              </FeaturesProvider>
            </InventoryProvider>
          </AuthProvider>
        </BrowserRouter>
        <Toaster position="top-center" richColors closeButton toastOptions={{ duration: 4000 }} />
      </div>
    </AppErrorBoundary>
  );
}

export default App;