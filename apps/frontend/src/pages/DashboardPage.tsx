import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  GitPullRequest,
  AlertOctagon,
  Clock,
  ArrowRight,
  RefreshCw,
  FolderGit2,
  Plus,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

import { MetricCard } from '../components/MetricCard';
import { RiskGradeBadge } from '../components/RiskGradeBadge';
import { SeverityBadge } from '../components/SeverityBadge';
import { AgentStatusGrid } from '../components/AgentStatusGrid';
import { DashboardSummaryResponse } from '../types';
import { api } from '../services/api';

interface DashboardPageProps {
  onOpenAddRepo?: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onOpenAddRepo }) => {
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const summary = await api.getDashboardSummary();
      setData(summary);
    } catch (err: any) {
      console.error(err.message || 'Failed to connect to CodeGuardian backend');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 12000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="flex-1 flex items-center justify-center py-24">
        <div className="flex flex-col items-center space-y-3">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <p className="text-xs font-mono text-purple-300">Loading DevSecOps live telemetry...</p>
        </div>
      </div>
    );
  }

  const hasRepos = data && data.total_repositories > 0;

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Platform Hero Banner */}
      <section className="glass-panel rounded-2xl p-6 border border-purple-500/25 relative overflow-hidden shadow-2xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 max-w-3xl">
            <div className="flex items-center space-x-2 text-xs font-mono text-purple-300">
              <span className="px-2 py-0.5 rounded bg-purple-950/80 border border-purple-500/30 text-pink-400 font-semibold">
                AUTONOMOUS DEVSECOPS
              </span>
              <span>•</span>
              <span>LANGGRAPH MULTI-AGENT CONSENSUS</span>
              <span>•</span>
              <span>CHROMADB RAG</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              CodeGuardian AI — Real-Time DevSecOps Intelligence
            </h1>
            <p className="text-xs text-purple-200/80 leading-relaxed">
              Every metric, score, defect, and trendline is derived strictly from real code analysis.
              Combines deterministic static analyzers (Bandit, Semgrep, Gitleaks, ESLint) with multi-agent consensus,
              policy RAG compliance, and sandboxed automated fix pull requests.
            </p>
          </div>

          {/* Primary Call to Action Button */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-shrink-0">
            {onOpenAddRepo && (
              <button
                onClick={onOpenAddRepo}
                className="plasma-btn px-5 py-3 rounded-xl text-xs flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                <span>Add Repository</span>
              </button>
            )}
            <Link
              to="/pull-requests"
              className="px-4 py-3 rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/30 text-purple-200 text-xs font-medium flex items-center justify-center gap-2 transition-colors"
            >
              <GitPullRequest className="w-4 h-4 text-cyan-400" />
              <span>Review Queue</span>
            </Link>
          </div>
        </div>
      </section>

      {/* Key Metric Cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Tracked Repositories"
          value={data ? `${data.total_repositories}` : '0'}
          subtitle={hasRepos ? "Active GitHub projects" : "Connect your first repo"}
          icon={<FolderGit2 className="w-5 h-5 text-cyan-400" />}
          trend="Live Sync"
          trendType="neutral"
        />
        <MetricCard
          title="Total PR Reviews"
          value={data ? `${data.total_reviews}` : '0'}
          subtitle="Multi-agent evaluated PRs"
          icon={<GitPullRequest className="w-5 h-5 text-pink-400" />}
          trend="Real-Time"
          trendType="positive"
        />
        <MetricCard
          title="Critical Vulnerabilities"
          value={data ? `${data.critical_findings}` : '0'}
          subtitle={`${data?.high_findings || 0} high severity defects`}
          icon={<AlertOctagon className="w-5 h-5 text-rose-400" />}
          trend={data && data.critical_findings > 0 ? "Blocked" : "Clear"}
          trendType={data && data.critical_findings > 0 ? "negative" : "positive"}
        />
        <MetricCard
          title="Average Review Latency"
          value={data && data.average_review_duration_ms > 0 ? `${(data.average_review_duration_ms / 1000).toFixed(1)}s` : '0.0s'}
          subtitle="SAST + Multi-Agent Pipeline"
          icon={<Clock className="w-5 h-5 text-emerald-400" />}
          trend="Sub-Minute"
          trendType="positive"
        />
      </section>

      {/* When No Repositories Exist: Prominent Guidance Hero */}
      {!hasRepos && (
        <section className="glass-panel p-10 rounded-2xl border border-purple-500/30 text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-purple-900/40 border-2 border-purple-500/40 flex items-center justify-center mx-auto text-pink-400 shadow-xl shadow-purple-900/30">
            <FolderGit2 className="w-8 h-8" />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h2 className="text-xl font-bold text-white">No GitHub Repositories Connected Yet</h2>
            <p className="text-xs text-purple-300/80">
              Onboard a public or private GitHub repository using the 5-step onboarding wizard. CodeGuardian AI will automatically evaluate incoming pull requests, compute deterministic risk scores, and present live telemetry.
            </p>
          </div>
          {onOpenAddRepo && (
            <button
              onClick={onOpenAddRepo}
              className="plasma-btn px-6 py-2.5 rounded-xl text-xs inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Onboard Your First Repository
            </button>
          )}
        </section>
      )}

      {/* Charts Row: Security Trend & Quality */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Security Trend */}
        <div className="glass-panel p-6 rounded-2xl border border-purple-500/20 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">Vulnerability Detection History</h3>
              <p className="text-xs text-purple-300/70">Severity distribution over time</p>
            </div>
            <div className="flex items-center space-x-2 text-xs font-mono">
              <span className="flex items-center text-rose-400"><span className="w-2 h-2 rounded-full bg-rose-500 mr-1" />Critical</span>
              <span className="flex items-center text-amber-400"><span className="w-2 h-2 rounded-full bg-amber-500 mr-1" />High</span>
              <span className="flex items-center text-yellow-400"><span className="w-2 h-2 rounded-full bg-yellow-500 mr-1" />Medium</span>
            </div>
          </div>

          <div className="h-64 w-full">
            {data && data.security_trend && data.security_trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.security_trend}>
                  <defs>
                    <linearGradient id="colorCrit" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#251c4a" />
                  <XAxis dataKey="date" stroke="#8a7bb8" fontSize={11} />
                  <YAxis stroke="#8a7bb8" fontSize={11} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f0c24', borderColor: '#8a2be2', borderRadius: '12px', fontSize: '12px' }}
                  />
                  <Area type="monotone" dataKey="critical" stroke="#f43f5e" fillOpacity={1} fill="url(#colorCrit)" />
                  <Area type="monotone" dataKey="high" stroke="#f59e0b" fillOpacity={1} fill="url(#colorHigh)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center text-xs font-mono text-purple-300/60 space-y-1">
                <span>No vulnerability historical trends recorded yet.</span>
                <span className="text-[11px] text-gray-500">Charts automatically populate as pull requests are analyzed.</span>
              </div>
            )}
          </div>
        </div>

        {/* Category Risk Breakdown */}
        <div className="glass-panel p-6 rounded-2xl border border-purple-500/20 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">5-Dimensional Category Risk Radar</h3>
              <p className="text-xs text-purple-300/70">Deterministic mathematical breakdown across engineering axes</p>
            </div>
            <span className="text-xs font-mono text-cyan-400">Scale: 0 - 100</span>
          </div>

          <div className="h-64 flex flex-col justify-center space-y-3">
            {[
              { label: 'Security & Vulnerabilities', score: data?.category_radar?.security || 0, color: 'bg-rose-500' },
              { label: 'Code Quality & Complexity', score: data?.category_radar?.quality || 0, color: 'bg-indigo-500' },
              { label: 'Test Coverage Gap', score: data?.category_radar?.testing || 0, color: 'bg-cyan-500' },
              { label: 'Documentation Standards', score: data?.category_radar?.documentation || 0, color: 'bg-emerald-500' },
              { label: 'Dependencies & Manifests', score: data?.category_radar?.dependency || 0, color: 'bg-amber-500' },
            ].map((cat) => (
              <div key={cat.label} className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-purple-200">{cat.label}</span>
                  <span className="text-purple-300 font-semibold">{cat.score.toFixed(1)} / 100</span>
                </div>
                <div className="h-2 w-full bg-black/50 rounded-full overflow-hidden border border-purple-500/15">
                  <div 
                    className={`h-full ${cat.color} rounded-full transition-all duration-500`} 
                    style={{ width: `${Math.min(100, Math.max(cat.score > 0 ? 5 : 0, cat.score))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Recent Reviews Table */}
      <section className="glass-panel rounded-2xl border border-purple-500/20 overflow-hidden">
        <div className="p-6 border-b border-purple-500/20 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight">Recent Pull Request Reviews</h2>
            <p className="text-xs text-purple-300/70">Live assessments executed by LangGraph Supervisor and Specialist Agents</p>
          </div>
          <Link
            to="/pull-requests"
            className="text-xs font-mono text-pink-400 hover:text-pink-300 flex items-center space-x-1"
          >
            <span>View All Pull Requests</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-purple-950/40 font-mono text-purple-300 uppercase border-b border-purple-500/20">
              <tr>
                <th className="py-3 px-6">Pull Request</th>
                <th className="py-3 px-4">Repository</th>
                <th className="py-3 px-4">Author</th>
                <th className="py-3 px-4">Risk Grade</th>
                <th className="py-3 px-4">Findings Breakdown</th>
                <th className="py-3 px-4">Gate Status</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-6 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-purple-500/10 text-purple-200">
              {data && data.recent_reviews.length > 0 ? (
                data.recent_reviews.map((rev) => (
                  <tr key={rev.review_run_id} className="hover:bg-purple-900/20 transition-colors">
                    <td className="py-3.5 px-6 font-medium text-white">
                      <div className="flex items-center space-x-2">
                        <GitPullRequest className="w-3.5 h-3.5 text-pink-400 shrink-0" />
                        <span className="font-semibold truncate max-w-xs">{rev.pr_title}</span>
                        <span className="text-purple-400 font-mono">#{rev.pr_number}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-purple-300">{rev.repo_name}</td>
                    <td className="py-3.5 px-4 font-mono text-purple-400">@{rev.author}</td>
                    <td className="py-3.5 px-4">
                      <RiskGradeBadge grade={rev.risk_grade} score={rev.risk_score} size="sm" />
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center space-x-1.5">
                        {rev.critical_count > 0 && <SeverityBadge severity="CRITICAL" count={rev.critical_count} />}
                        {rev.high_count > 0 && <SeverityBadge severity="HIGH" count={rev.high_count} />}
                        {rev.critical_count === 0 && rev.high_count === 0 && (
                          <span className="text-[11px] font-mono text-emerald-400">Clean</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-semibold ${
                        rev.is_mergeable
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                      }`}>
                        {rev.is_mergeable ? 'MERGEABLE' : 'BLOCKED'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-purple-300">
                      {rev.duration_ms ? `${rev.duration_ms}ms` : '0ms'}
                    </td>
                    <td className="py-3.5 px-6 text-right">
                      <Link
                        to={`/reviews/${rev.review_run_id}`}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-purple-900/50 hover:bg-purple-800/60 text-purple-200 border border-purple-500/30 text-xs font-mono transition-colors"
                      >
                        <span>Inspect</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-purple-300/60 font-mono">
                    No pull request reviews recorded yet. Connect a repository or trigger analysis on any open PR.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Multi-Agent Orchestration Fabric Status */}
      <AgentStatusGrid />
    </div>
  );
};
