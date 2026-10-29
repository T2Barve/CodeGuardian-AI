import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  GitPullRequest,
  Search,
  Filter,
  Play,
  CheckCircle2,
  Clock,
  User,
  GitBranch,
  RefreshCw,
  FileCode,
  Plus,
} from 'lucide-react';
import { api } from '../services/api';
import { PullRequestItem, RepositoryRead } from '../types';
import { RiskGradeBadge } from '../components/RiskGradeBadge';

interface PullRequestsPageProps {
  onOpenAddRepo?: () => void;
}

export const PullRequestsPage: React.FC<PullRequestsPageProps> = ({ onOpenAddRepo }) => {
  const [prs, setPrs] = useState<PullRequestItem[]>([]);
  const [repos, setRepos] = useState<RepositoryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRepoId, setSelectedRepoId] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchPRs = async () => {
    try {
      setLoading(true);
      const [prsRes, reposRes] = await Promise.all([
        api.getPullRequests({
          repository_id: selectedRepoId || undefined,
          status: statusFilter || undefined,
          search: searchQuery || undefined,
          limit: 100,
        }),
        api.getRepositories(),
      ]);
      setPrs(prsRes.items || []);
      setRepos(reposRes || []);
    } catch (err: any) {
      console.error('Failed to load pull requests:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPRs();
  }, [selectedRepoId, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchPRs();
  };

  const handleTriggerAnalysis = async (prId: string) => {
    try {
      setAnalyzingId(prId);
      const res = await api.analyzePullRequest(prId);
      setActionMessage(`Review job queued (${res.job_id}). Analysis underway.`);
      setTimeout(() => {
        setActionMessage(null);
        fetchPRs();
      }, 3000);
    } catch (err: any) {
      setActionMessage(`Error triggering analysis: ${err.message}`);
      setTimeout(() => setActionMessage(null), 5000);
    } finally {
      setAnalyzingId(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
              <GitPullRequest className="w-6 h-6 text-pink-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                Pull Request Review Queue
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
                  {prs.length} Tracked
                </span>
              </h1>
              <p className="text-xs text-purple-300/70 mt-0.5">
                Real-time pull request evaluation, multi-agent risk scoring & automated fix branches
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchPRs()}
            className="p-2 rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
            title="Refresh pull request list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {onOpenAddRepo && (
            <button
              onClick={onOpenAddRepo}
              className="plasma-btn px-4 py-2 rounded-xl text-xs flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Repository
            </button>
          )}
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div className="p-3.5 rounded-xl bg-purple-900/40 border border-pink-500/40 text-pink-200 text-xs flex items-center gap-2.5 shadow-lg shadow-pink-900/20 animate-in fade-in duration-150">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {/* Search and Filters Bar */}
      <div className="glass-card p-4 rounded-2xl border border-purple-500/20 flex flex-col md:flex-row items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search PRs by title, author, or branch..."
            className="w-full glass-input px-4 py-2 rounded-xl pl-10 text-xs font-mono text-white placeholder-gray-500 border border-purple-500/20"
          />
          <Search className="w-4 h-4 text-purple-400 absolute left-3 top-2.5" />
        </form>

        <div className="flex items-center space-x-2.5 w-full md:w-auto">
          {/* Repository Filter */}
          <div className="flex items-center space-x-1.5 glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
            <Filter className="w-3.5 h-3.5 text-purple-400" />
            <select
              value={selectedRepoId}
              onChange={(e) => setSelectedRepoId(e.target.value)}
              className="bg-transparent text-purple-200 focus:outline-none text-xs"
            >
              <option value="" className="bg-[#0f0c24] text-white">All Repositories</option>
              {repos.map((r) => (
                <option key={r.id} value={r.id} className="bg-[#0f0c24] text-white">
                  {r.owner}/{r.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-transparent text-purple-200 focus:outline-none text-xs"
            >
              <option value="" className="bg-[#0f0c24] text-white">All Statuses</option>
              <option value="OPEN" className="bg-[#0f0c24] text-white">Open</option>
              <option value="CLOSED" className="bg-[#0f0c24] text-white">Closed</option>
              <option value="MERGED" className="bg-[#0f0c24] text-white">Merged</option>
            </select>
          </div>
        </div>
      </div>

      {/* Pull Requests Table / Card List */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Fetching pull requests from database & GitHub...</span>
        </div>
      ) : prs.length === 0 ? (
        <div className="glass-panel p-12 rounded-2xl border border-purple-500/20 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-purple-900/30 border border-purple-500/30 flex items-center justify-center mx-auto text-purple-400">
            <GitPullRequest className="w-7 h-7" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">No Pull Requests Found</h3>
            <p className="text-xs text-purple-300/70 max-w-md mx-auto mt-1">
              {repos.length === 0
                ? 'No repositories have been connected yet. Onboard a repository to start tracking pull requests.'
                : 'No pull requests match your current filters. Sync open pull requests or open a PR on GitHub.'}
            </p>
          </div>
          {onOpenAddRepo && repos.length === 0 && (
            <button
              onClick={onOpenAddRepo}
              className="plasma-btn px-5 py-2.5 rounded-xl text-xs font-semibold inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Onboard First Repository
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {prs.map((pr) => {
            const hasRun = Boolean(pr.latest_review_run_id);
            const isAnalyzing = analyzingId === pr.id;

            return (
              <div
                key={pr.id}
                className="glass-card p-5 rounded-2xl border border-purple-500/15 hover:border-purple-500/40 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                {/* PR Left Meta */}
                <div className="space-y-2 flex-1">
                  <div className="flex items-center space-x-2.5">
                    <span className="text-xs px-2 py-0.5 rounded font-mono font-semibold bg-purple-950/60 text-purple-300 border border-purple-500/30">
                      {pr.repo_name || 'Repository'} #{pr.number}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase font-semibold border ${
                        pr.status === 'OPEN'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                          : pr.status === 'MERGED'
                          ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                          : 'bg-gray-800 text-gray-400 border-gray-700'
                      }`}
                    >
                      {pr.status}
                    </span>
                    <span className="text-xs text-gray-400 flex items-center gap-1 font-mono">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(pr.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <h3 className="text-base font-semibold text-white tracking-tight hover:text-pink-300 transition-colors">
                    {pr.title}
                  </h3>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-purple-300/80 font-mono">
                    <span className="flex items-center gap-1">
                      <User className="w-3.5 h-3.5 text-purple-400" />
                      {pr.author}
                    </span>
                    <span className="text-purple-600">•</span>
                    <span className="flex items-center gap-1">
                      <GitBranch className="w-3.5 h-3.5 text-pink-400" />
                      <span className="text-purple-200">{pr.source_branch}</span>
                      <span className="text-gray-500">&rarr;</span>
                      <span className="text-purple-400">{pr.target_branch}</span>
                    </span>
                    <span className="text-purple-600">•</span>
                    <span className="text-gray-400 text-[11px]">
                      Commit: <code className="text-purple-300">{pr.commit_sha.slice(0, 7)}</code>
                    </span>
                  </div>
                </div>

                {/* PR Right Status & Actions */}
                <div className="flex items-center space-x-3 flex-shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-purple-500/10">
                  {hasRun ? (
                    <div className="flex items-center space-x-3">
                      <div className="text-right">
                        <div className="text-[10px] text-gray-400 font-mono uppercase">
                          Risk Score: <span className="text-white font-bold">{pr.latest_risk_score ?? 0}/100</span>
                        </div>
                        <div className="text-[11px] text-purple-300">
                          {pr.findings_count} findings detected
                        </div>
                      </div>
                      <RiskGradeBadge grade={pr.latest_risk_grade || 'C'} size="sm" />
                      <Link
                        to={`/reviews/${pr.latest_review_run_id}`}
                        className="px-3 py-1.5 rounded-xl bg-purple-900/50 hover:bg-purple-800/60 border border-purple-500/30 text-purple-200 hover:text-white text-xs font-medium flex items-center gap-1.5 transition-colors"
                      >
                        <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                        Report
                      </Link>
                    </div>
                  ) : (
                    <div className="text-right">
                      <span className="text-xs text-amber-300/90 bg-amber-950/40 px-2.5 py-1 rounded-lg border border-amber-500/30 font-mono">
                        Awaiting Review
                      </span>
                    </div>
                  )}

                  {/* Trigger Manual Review Button */}
                  <button
                    onClick={() => handleTriggerAnalysis(pr.id)}
                    disabled={isAnalyzing}
                    className="plasma-btn px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 disabled:opacity-50"
                    title="Dispatch multi-agent review analysis"
                  >
                    {isAnalyzing ? (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Play className="w-3.5 h-3.5 fill-current" />
                    )}
                    <span>{hasRun ? 'Re-Analyze' : 'Analyze'}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
