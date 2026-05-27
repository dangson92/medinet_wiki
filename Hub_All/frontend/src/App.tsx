import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { APP_BASE } from './services/api';
import Layout from './Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import UserManagement from './pages/UserManagement';
import HubRegistry from './pages/HubRegistry';
import CrossHubSearch from './pages/CrossHubSearch';
import AuditLog from './pages/AuditLog';
import SyncQueue from './pages/SyncQueue';
import SyncReview from './pages/SyncReview';
import APIKeyManagement from './pages/APIKeyManagement';
import DocumentIngestion from './pages/DocumentIngestion';
import Settings from './pages/Settings';
import Profile from './pages/Profile';
import TokenUsage from './pages/TokenUsage';
import Guide from './pages/Guide';
import GuideEditor from './pages/GuideEditor';
import GuideView from './pages/GuideView';
import { Loader2 } from 'lucide-react';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Loader2 size={32} className="animate-spin text-brand-indigo" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    // Phase 5 D-V3-Phase5-B3 LOCKED — basename auto prepend cho mọi route khi hub con
    // (APP_BASE='/yte'|''|'/duoc'|...). 13 sub-route giữ NGUYÊN path absolute.
    <BrowserRouter basename={APP_BASE}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="search" element={<CrossHubSearch />} />
            <Route path="documents" element={<DocumentIngestion />} />
            <Route path="documents/new" element={<DocumentIngestion mode="new" />} />
            <Route path="guide" element={<Guide />} />
            <Route path="guide/new" element={<GuideEditor />} />
            <Route path="guide/:id" element={<GuideView />} />
            <Route path="guide/:id/edit" element={<GuideEditor />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="registry" element={<HubRegistry />} />
            <Route path="sync" element={<SyncQueue />} />
            <Route path="sync/review/:batchId" element={<SyncReview />} />
            <Route path="logs" element={<AuditLog />} />
            <Route path="usage" element={<TokenUsage />} />
            <Route path="api-keys" element={<APIKeyManagement />} />
            <Route path="settings" element={<Settings />} />
            <Route path="profile" element={<Profile />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
