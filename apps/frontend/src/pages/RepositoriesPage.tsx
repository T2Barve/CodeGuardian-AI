import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FolderGit2,
  GitPullRequest,
  Search,
  ExternalLink,
  ChevronRight,
  Code2,
  RefreshCw,
  Plus,
  Trash2,
  Power,
  RotateCw,
  CheckCircle2,
} from 'lucide-react';
import { RepositoryRead, RepositoryDetail } from '../types';
import { RiskGradeBadge } from '../components/RiskGradeBadge';
import { api } from '../services/api';
import { AddRepositoryModal } from '../components/AddRepositoryModal';

interface RepositoriesPageProps {
  onOpenAddRepo?: () => void;
}

export const RepositoriesPage: React.FC<RepositoriesPageProps> = () => {
  const [repositories, setRepositories] = useState<RepositoryRead[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<RepositoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadRepos = async (preferredSelectedId?: string) => {
    try {
      setLoading(true);
      const data = await api.getRepositories();
      setRepositories(data);
      if (data.length > 0) {
        const idToSelect = preferredSelectedId || (selectedRepo ? selectedRepo.id : data[0].id);
        const exists = data.find((r) => r.id === idToSelect);
        loadRepoDetail(exists ? idToSelect : data[0].id);
      } else {
        setSelectedRepo(null);
      }
    } catch (err: any) {
      console.error('Failed to load repositories:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadRepoDetail = async (id: string) => {
    try {
      setDetailLoading(true);
      const detail = await api.getRepositoryDetail(id);
      setSelectedRepo(detail);
    } catch (err: any) {
      console.error('Failed to load repository detail:', err);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadRepos();
  }, []);

  const handleSyncPRs = async (repoId: string) => {
    try {
      setSyncingId(repoId);
      const res = await api.syncRepository(repoId);
      setActionNotice(res.message);
      await loadRepoDetail(repoId);
      await loadRepos(repoId);
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionNotice(`Sync error: ${err.message}`);
      setTimeout(() => setActionNotice(null), 5000);
    } finally {
      setSyncingId(null);
    }
  };

  const handleToggleMonitoring = async (repoId: string, currentStatus: boolean) => {
    try {
      const updated = await api.updateRepositoryMonitoring(repoId, !currentStatus);
      setActionNotice(
        `Monitoring ${updated.is_active ? 'activated' : 'paused'} for ${updated.owner}/${updated.name}.`
      );
      await loadRepos(repoId);
      if (selectedRepo && selectedRepo.id === repoId) {
        setSelectedRepo({ ...selectedRepo, is_active: updated.is_active });
      }
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionNotice(`Error: ${err.message}`);
      setTimeout(() => setActionNotice(null), 5000);
    }
  };

  const handleDeleteRepo = async (repoId: string, repoName: string) => {
    if (!window.confirm(`Are you sure you want to disconnect repository '${repoName}' from CodeGuardian AI?`)) {
      return;
    }

    try {
      const res = await api.deleteRepository(repoId);
      setActionNotice(res.message);
      setSelectedRepo(null);
      await loadRepos();
      setTimeout(() => setActionNotice(null), 4000);
    } catch (err: any) {
      setActionNotice(`Deletion error: ${err.message}`);
      setTimeout(() => setActionNotice(null), 5000);
    }
  };

  const filteredRepos = repositories.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.owner.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <FolderGit2 className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Tracked GitHub Repositories
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
                {repositories.length} Active
              </span>
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              Continuous DevSecOps webhook monitoring, multi-agent evaluation, and automated PR remediation
            </p>
          </div>
        </div>

        {/* Primary Action Button */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => loadRepos()}
            className="p-2 rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
            title="Refresh repository list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="plasma-btn px-4 py-2 rounded-xl text-xs flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Repository
          </button>
        </div>
      </div>

      {/* Action Notification */}
      {actionNotice && (
        <div className="p-3.5 rounded-xl bg-purple-900/40 border border-pink-500/40 text-pink-200 text-xs flex items-center gap-2.5 shadow-lg shadow-pink-900/20 animate-in fade-in duration-150">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* Main Grid: Repo List & Selected Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Repo List */}
        <div className="lg:col-span-1 space-y-3">
          {/* Search Bar */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-purple-400" />
            <input
              type="text"
              placeholder="Search repositories..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full glass-input pl-9 pr-4 py-2 rounded-xl text-xs font-mono text-white placeholder-gray-500 border border-purple-500/20"
            />
          </div>

          {loading ? (
            <div className="p-8 text-center glass-panel rounded-2xl border border-purple-500/20">
              <RefreshCw className="w-6 h-6 animate-spin text-pink-400 mx-auto mb-2" />
              <p className="text-xs font-mono text-purple-300">Loading repositories...</p>
            </div>
          ) : filteredRepos.length > 0 ? (
            <div className="space-y-2.5 max-h-[70vh] overflow-y-auto pr-1">
              {filteredRepos.map((repo) => {
                const isSelected = selectedRepo?.id === repo.id;
                return (
                  <div
                    key={repo.id}
                    onClick={() => loadRepoDetail(repo.id)}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-purple-900/40 border-pink-500 shadow-lg shadow-pink-500/10'
                        : 'glass-card border-purple-500/15 hover:border-purple-500/40'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-2.5 truncate">
                        <FolderGit2
                          className={`w-5 h-5 flex-shrink-0 ${
                            isSelected ? 'text-pink-400' : 'text-purple-400'
                          }`}
                        />
                        <div className="truncate">
                          <h3 className="text-sm font-bold text-white font-mono truncate">
                            {repo.name}
                          </h3>
                          <p className="text-xs text-purple-300/70 font-mono">@{repo.owner}</p>
                        </div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold flex-shrink-0 ${
                          repo.is_active
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : 'bg-gray-800 text-gray-400 border border-gray-700'
                        }`}
                      >
                        {repo.is_active ? 'MONITORED' : 'PAUSED'}
                      </span>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-xs font-mono text-purple-300/80 border-t border-purple-500/10 pt-2.5">
                      <div className="flex items-center space-x-1.5">
                        <Code2 className="w-3.5 h-3.5 text-cyan-400" />
                        <span>{repo.language || 'Code'}</span>
                      </div>
                      <div className="flex items-center space-x-2 text-[11px]">
                        <span>{repo.pull_requests_count} PRs</span>
                        <span>•</span>
                        <span>{repo.reviews_count} Reviews</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-8 text-center glass-panel rounded-2xl border border-purple-500/20 space-y-3">
              <FolderGit2 className="w-8 h-8 text-purple-400 mx-auto" />
              <p className="text-xs font-mono text-purple-300">No repositories found.</p>
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="plasma-btn px-4 py-2 rounded-xl text-xs inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Your First Repository
              </button>
            </div>
          )}
        </div>

        {/* Right Column: Selected Repo Details & PR Explorer */}
        <div className="lg:col-span-2">
          {detailLoading ? (
            <div className="glass-panel p-16 rounded-2xl border border-purple-500/20 text-center space-y-2">
              <RefreshCw className="w-6 h-6 animate-spin text-pink-400 mx-auto" />
              <p className="text-xs font-mono text-purple-300">Loading pull request telemetry...</p>
            </div>
          ) : selectedRepo ? (
            <div className="glass-panel rounded-2xl border border-purple-500/20 overflow-hidden space-y-6 p-6">
              {/* Header Info & Management Controls */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
                <div>
                  <div className="flex items-center space-x-2 text-xs font-mono text-purple-300 mb-1">
                    <span>DEFAULT BRANCH: <strong className="text-pink-300">{selectedRepo.default_branch}</strong></span>
                    <span>•</span>
                    <span>ID: {selectedRepo.github_repo_id}</span>
                  </div>
                  <h2 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
                    <span>{selectedRepo.owner}/{selectedRepo.name}</span>
                  </h2>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* Sync Pull Requests from GitHub */}
                  <button
                    onClick={() => handleSyncPRs(selectedRepo.id)}
                    disabled={syncingId === selectedRepo.id}
                    className="px-3 py-1.5 rounded-xl bg-purple-900/40 hover:bg-purple-800/50 border border-purple-500/30 text-purple-200 text-xs font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
                    title="Fetch latest open pull requests from GitHub"
                  >
                    <RotateCw className={`w-3.5 h-3.5 text-cyan-400 ${syncingId === selectedRepo.id ? 'animate-spin' : ''}`} />
                    <span>Sync PRs</span>
                  </button>

                  {/* Toggle Monitoring */}
                  <button
                    onClick={() => handleToggleMonitoring(selectedRepo.id, selectedRepo.is_active)}
                    className={`px-3 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      selectedRepo.is_active
                        ? 'bg-amber-950/40 border-amber-500/30 text-amber-300 hover:bg-amber-900/50'
                        : 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300 hover:bg-emerald-900/50'
                    }`}
                    title="Toggle continuous monitoring"
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>{selectedRepo.is_active ? 'Pause' : 'Activate'}</span>
                  </button>

                  {/* View on GitHub */}
                  <a
                    href={selectedRepo.url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 rounded-xl bg-black/40 hover:bg-purple-900/40 border border-purple-500/30 text-purple-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
                  >
                    <span>GitHub</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>

                  {/* Disconnect / Delete */}
                  <button
                    onClick={() => handleDeleteRepo(selectedRepo.id, `${selectedRepo.owner}/${selectedRepo.name}`)}
                    className="p-1.5 rounded-xl bg-red-950/40 hover:bg-red-900/50 border border-red-500/30 text-red-300 hover:text-red-200 transition-colors"
                    title="Disconnect repository"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* PRs Section */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                    <GitPullRequest className="w-4 h-4 text-pink-400" />
                    <span>
                      Tracked Pull Requests ({selectedRepo.recent_pull_requests.length})
                    </span>
                  </h3>
                  <Link
                    to="/pull-requests"
                    className="text-xs text-pink-400 hover:underline flex items-center gap-1"
                  >
                    Open Full PR Queue &rarr;
                  </Link>
                </div>

                <div className="space-y-2.5">
                  {selectedRepo.recent_pull_requests.length > 0 ? (
                    selectedRepo.recent_pull_requests.map((pr) => (
                      <div
                        key={pr.id}
                        className="glass-card p-4 rounded-xl border border-purple-500/15 hover:border-purple-500/30 flex flex-col md:flex-row md:items-center justify-between gap-3 transition-all"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="text-pink-400 font-mono font-bold text-xs">
                              #{pr.number}
                            </span>
                            <span className="text-sm font-semibold text-white">
                              {pr.title}
                            </span>
                          </div>
                          <div className="flex items-center space-x-3 text-xs font-mono text-purple-300/70">
                            <span>@{pr.author}</span>
                            <span>•</span>
                            <span>{pr.source_branch} &rarr; {pr.target_branch}</span>
                            <span>•</span>
                            <span>Commit: {pr.commit_sha.slice(0, 7)}</span>
                          </div>
                        </div>

                        <div className="flex items-center space-x-3">
                          {pr.latest_risk_grade && (
                            <RiskGradeBadge
                              grade={pr.latest_risk_grade}
                              score={pr.latest_risk_score}
                              size="sm"
                            />
                          )}

                          {pr.latest_review_run_id ? (
                            <Link
                              to={`/reviews/${pr.latest_review_run_id}`}
                              className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-purple-900/50 hover:bg-purple-800/60 text-purple-200 border border-purple-500/30 text-xs font-mono font-semibold transition-colors"
                            >
                              <span>Report</span>
                              <ChevronRight className="w-3.5 h-3.5" />
                            </Link>
                          ) : (
                            <span className="text-xs font-mono text-amber-300/80 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-500/30">
                              Awaiting Review
                            </span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-8 text-center border border-dashed border-purple-500/20 rounded-xl text-xs font-mono text-purple-300/70 space-y-2">
                      <p>No pull requests currently registered for this repository.</p>
                      <button
                        onClick={() => handleSyncPRs(selectedRepo.id)}
                        className="plasma-btn px-4 py-1.5 rounded-lg text-xs inline-flex items-center gap-1.5"
                      >
                        <RotateCw className="w-3.5 h-3.5" />
                        Sync Open PRs from GitHub
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="glass-panel p-16 rounded-2xl border border-purple-500/20 text-center text-xs font-mono text-purple-300/70 space-y-3">
              <FolderGit2 className="w-8 h-8 text-purple-400 mx-auto" />
              <p>Select a repository to inspect its details and pull request evaluations.</p>
            </div>
          )}
        </div>
      </div>

      {/* Add Repository Modal */}
      <AddRepositoryModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={(newRepo) => {
          loadRepos(newRepo.id);
        }}
      />
    </div>
  );
};
