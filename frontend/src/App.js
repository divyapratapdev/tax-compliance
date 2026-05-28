import React from "react";
import { BrowserRouter, Routes, Route, Outlet, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";
import { ClientProvider } from "@/components/ClientContext";
import { AuthProvider, useAuth } from "@/components/AuthContext";

import Dashboard from "@/pages/Dashboard";
import Clients from "@/pages/Clients";
import Documents from "@/pages/Documents";
import GSTReconciliation from "@/pages/GSTReconciliation";
import TDSAlerts from "@/pages/TDSAlerts";
import Compliance from "@/pages/Compliance";
import Settings from "@/pages/Settings";
import Login from "@/pages/Login";
import NotFound from "@/pages/NotFound";

import "@/App.css";

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex h-screen items-center justify-center text-slate-500">Loading TaxPilot...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <ClientProvider>{children}</ClientProvider>;
};

const Shell = () => {
  const { user } = useAuth();
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar firm={user} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar firm={user} />
        <main className="flex-1 overflow-auto p-8" data-testid="page-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <Toaster richColors position="top-right" />
      <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            <Route element={<ProtectedRoute><Shell /></ProtectedRoute>}>
              <Route path="/"                    element={<Dashboard />} />
              <Route path="/clients"             element={<Clients />} />
              <Route path="/documents"           element={<Documents />} />
              <Route path="/gst-reconciliation"  element={<GSTReconciliation />} />
              <Route path="/tds-alerts"          element={<TDSAlerts />} />
              <Route path="/compliance"          element={<Compliance />} />
              <Route path="/settings"            element={<Settings firm={null} onUpdate={() => {}} />} />
              <Route path="*"                    element={<NotFound />} />
            </Route>
            
            {/* Catch-all for unauthenticated */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
