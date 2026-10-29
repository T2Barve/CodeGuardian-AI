import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import { Navbar } from './components/Navbar';
import { AddRepositoryModal } from './components/AddRepositoryModal';
import { DashboardPage } from './pages/DashboardPage';
import { RepositoriesPage } from './pages/RepositoriesPage';
import { PullRequestsPage } from './pages/PullRequestsPage';
import { ReviewPage } from './pages/ReviewPage';
import { FindingsPage } from './pages/FindingsPage';
import { AgentsPage } from './pages/AgentsPage';
import { ScannersPage } from './pages/ScannersPage';
import { PoliciesPage } from './pages/PoliciesPage';
import { RemediationPage } from './pages/RemediationPage';
import { ReportsPage } from './pages/ReportsPage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { OptimizerPage } from './pages/OptimizerPage';
import { SettingsPage } from './pages/SettingsPage';
import { HealthStatus, ReadinessStatus, RepositoryRead } from './types';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [readiness, setReadiness] = useState<ReadinessStatus | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [isAddRepoModalOpen, setIsAddRepoModalOpen] = useState(false);

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
      const readyRes = await fetch('/api/v1/ready');
      if (readyRes.ok) {
        const readyData = await readyRes.json();
        setReadiness(readyData);
      }
    } catch {
      setHealth(null);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 8000);
    return () => clearInterval(interval);
  }, []);

  const triggerRefresh = () => {
    setRefreshTrigger((prev) => prev + 1);
    fetchHealth();
  };

  const handleRepositoryCreated = (_repo: RepositoryRead) => {
    triggerRefresh();
  };

  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col font-sans selection:bg-pink-500/20 selection:text-pink-300">
          <Navbar
            health={health}
            readiness={readiness}
            onOpenAddRepo={() => setIsAddRepoModalOpen(true)}
          />

          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
            <Routes>
              {/* Public Authentication Route */}
              <Route path="/login" element={<LoginPage />} />

              {/* Protected Platform Routes */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <DashboardPage
                      key={`dash-${refreshTrigger}`}
                      onOpenAddRepo={() => setIsAddRepoModalOpen(true)}
                    />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/repositories"
                element={
                  <ProtectedRoute>
                    <RepositoriesPage
                      key={`repos-${refreshTrigger}`}
                      onOpenAddRepo={() => setIsAddRepoModalOpen(true)}
                    />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pull-requests"
                element={
                  <ProtectedRoute>
                    <PullRequestsPage
                      key={`prs-${refreshTrigger}`}
                      onOpenAddRepo={() => setIsAddRepoModalOpen(true)}
                    />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/reviews"
                element={
                  <ProtectedRoute>
                    <ReviewPage key={`reviews-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/reviews/:reviewId"
                element={
                  <ProtectedRoute>
                    <ReviewPage key={`review-id-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/findings"
                element={
                  <ProtectedRoute>
                    <FindingsPage key={`findings-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/agents"
                element={
                  <ProtectedRoute>
                    <AgentsPage key={`agents-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/scanners"
                element={
                  <ProtectedRoute>
                    <ScannersPage key={`scanners-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/policies"
                element={
                  <ProtectedRoute>
                    <PoliciesPage key={`policies-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/remediation"
                element={
                  <ProtectedRoute>
                    <RemediationPage key={`rem-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/reports"
                element={
                  <ProtectedRoute>
                    <ReportsPage key={`reports-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/integrations"
                element={
                  <ProtectedRoute>
                    <IntegrationsPage key={`int-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/optimizer"
                element={
                  <ProtectedRoute>
                    <OptimizerPage key={`opt-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <SettingsPage key={`set-${refreshTrigger}`} />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          {/* Global Add Repository Modal */}
          <AddRepositoryModal
            isOpen={isAddRepoModalOpen}
            onClose={() => setIsAddRepoModalOpen(false)}
            onSuccess={handleRepositoryCreated}
          />

          {/* Footer */}
          <footer className="border-t border-purple-500/15 bg-[#090c15]/90 py-6 text-xs font-mono text-purple-300/60">
            <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex items-center space-x-2">
                <span className="text-pink-400 font-bold">CodeGuardian AI</span>
                <span>•</span>
                <span>B.Tech Major Project</span>
                <span>•</span>
                <span>SDG 9 & SDG 8</span>
              </div>

              <div className="flex items-center space-x-3 text-purple-300/80">
                <span>Darshan (Frontend)</span>
                <span>•</span>
                <span>Tanishq (AI/RAG)</span>
                <span>•</span>
                <span>Mayur (Backend)</span>
                <span>•</span>
                <span>Veer (Security)</span>
              </div>
            </div>
          </footer>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
};
