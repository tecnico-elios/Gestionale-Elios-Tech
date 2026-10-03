import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";

/** Protegge autenticazione, ruolo Admin e permessi granulari. */
export default function ProtectedRoute({ children, requireAdmin = false, permission = null, action = "view" }) {
  const { isAuthenticated, isAdmin, isLoading, hasPermission } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500" data-testid="auth-loading">
        Caricamento…
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  if (requireAdmin && !isAdmin) return <Navigate to="/" replace />;
  if (permission && !hasPermission(permission, action)) return <Navigate to="/" replace />;
  return children;
}
