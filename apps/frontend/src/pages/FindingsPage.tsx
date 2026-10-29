import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Search,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { api } from '../services/api';
import { Finding, RepositoryRead } from '../types';
import { SeverityBadge } from '../components/SeverityBadge';
import { FindingDetailModal } from '../components/FindingDetailModal';

export const FindingsPage: React.FC = () => {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [repos, setRepos] = useState<RepositoryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityCounts, setSeverityCounts] = useState<Record<string, number>>({});
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedRepoId, setSelectedRepoId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Finding Detail Modal
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);

  const fetchFindings = async () => {
    try {
      setLoading(true);
      const [res, reposRes] = await Promise.all([
        api.getAllFindings({
          category: selectedCategory || undefined,
          severity: selectedSeverity || undefined,
          status: selectedStatus || undefined,
          repository_id: selectedRepoId || undefined,
          search: searchQuery || undefined,
          limit: 100,
        }),
        api.getRepositories(),
      ]);

      setFindings(res.items || []);
      setSeverityCounts(res.severity_counts || {});
      setTotalCount(res.total || 0);
      setRepos(reposRes || []);
    } catch (err: any) {
      console.error('Failed to load findings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFindings();
  }, [selectedCategory, selectedSeverity, selectedStatus, selectedRepoId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchFindings();
  };

  const handleStatusUpdated = () => {
    fetchFindings();
    if (activeFinding) {
      api.getFindingDetail(activeFinding.id).then(setActiveFinding).catch(() => {});
    }
  };

  const categories = [
    { id: '', label: 'All Categories' },
    { id: 'SECURITY', label: 'Security' },
    { id: 'QUALITY', label: 'Code Quality' },
    { id: 'TESTING', label: 'Testing' },
    { id: 'DOCUMENTATION', label: 'Documentation' },
    { id: 'DEPENDENCY', label: 'Dependency' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <ShieldAlert className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Findings & Vulnerability Explorer
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
                {totalCount} Total Issues
              </span>
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              Correlated static analysis detections, multi-agent AI findings, and verified sandbox remediations
            </p>
          </div>
        </div>

        <button
          onClick={() => fetchFindings()}
          className="p-2 self-start md:self-auto rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
          title="Refresh findings"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Severity Tally Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { key: 'CRITICAL', label: 'Critical', color: 'from-rose-600/30 to-red-950/40 border-red-500/30 text-red-400' },
          { key: 'HIGH', label: 'High', color: 'from-orange-600/30 to-amber-950/40 border-orange-500/30 text-orange-400' },
          { key: 'MEDIUM', label: 'Medium', color: 'from-yellow-600/30 to-amber-950/40 border-yellow-500/30 text-yellow-400' },
          { key: 'LOW', label: 'Low', color: 'from-blue-600/30 to-indigo-950/40 border-blue-500/30 text-blue-400' },
          { key: 'INFO', label: 'Info', color: 'from-purple-600/30 to-violet-950/40 border-purple-500/30 text-purple-400' },
        ].map((sev) => {
          const count = severityCounts[sev.key] || 0;
          const isSelected = selectedSeverity === sev.key;
          return (
            <button
              key={sev.key}
              onClick={() => setSelectedSeverity(isSelected ? '' : sev.key)}
              className={`p-3.5 rounded-2xl border text-left transition-all bg-gradient-to-br ${sev.color} ${
                isSelected
                  ? 'ring-2 ring-pink-500 shadow-lg shadow-pink-500/20'
                  : 'hover:border-purple-500/50'
              }`}
            >
              <div className="text-[11px] font-mono uppercase tracking-wider text-gray-300 font-semibold">
                {sev.label}
              </div>
              <div className="text-2xl font-bold mt-0.5 font-mono">{count}</div>
            </button>
          );
        })}
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-card p-4 rounded-2xl border border-purple-500/20 flex flex-col md:flex-row items-center justify-between gap-3">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search findings by title, description, or file path..."
            className="w-full glass-input px-4 py-2 rounded-xl pl-10 text-xs font-mono text-white placeholder-gray-500 border border-purple-500/20"
          />
          <Search className="w-4 h-4 text-purple-400 absolute left-3 top-2.5" />
        </form>

        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Category Dropdown */}
          <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="bg-transparent text-purple-200 focus:outline-none text-xs"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id} className="bg-[#0f0c24] text-white">
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* Repository Dropdown */}
          <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
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

          {/* Status Dropdown */}
          <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-transparent text-purple-200 focus:outline-none text-xs"
            >
              <option value="" className="bg-[#0f0c24] text-white">All Statuses</option>
              <option value="OPEN" className="bg-[#0f0c24] text-white">Open</option>
              <option value="RESOLVED" className="bg-[#0f0c24] text-white">Resolved</option>
              <option value="FALSE_POSITIVE" className="bg-[#0f0c24] text-white">False Positive</option>
              <option value="WONT_FIX" className="bg-[#0f0c24] text-white">Won't Fix</option>
            </select>
          </div>
        </div>
      </div>

      {/* Findings Listing */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Fetching findings repository...</span>
        </div>
      ) : findings.length === 0 ? (
        <div className="glass-panel p-12 rounded-2xl border border-purple-500/20 text-center space-y-3">
          <div className="w-14 h-14 rounded-full bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-white">Zero Findings Discovered</h3>
          <p className="text-xs text-purple-300/70 max-w-md mx-auto">
            No issues match the selected filter criteria. All examined pull requests and code blocks comply with your security and quality baselines.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {findings.map((f) => (
            <div
              key={f.id}
              onClick={() => setActiveFinding(f)}
              className="glass-card p-5 rounded-2xl border border-purple-500/15 hover:border-purple-500/40 cursor-pointer transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="flex items-center space-x-2.5">
                  <SeverityBadge severity={f.severity} size="sm" />
                  <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-purple-950/60 text-purple-300 border border-purple-500/30">
                    {f.category}
                  </span>
                  <span className="text-xs text-gray-400 font-mono truncate max-w-sm">
                    {f.file_path}
                    {f.line_start && `:${f.line_start}`}
                  </span>
                </div>

                <h3 className="text-base font-semibold text-white tracking-tight hover:text-pink-300 transition-colors">
                  {f.title}
                </h3>

                <p className="text-xs text-purple-300/75 line-clamp-2">
                  {f.description}
                </p>

                {/* Evidence & Tools involved */}
                <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
                  {f.tools_involved && f.tools_involved.length > 0 && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-gray-400">Detections:</span>
                      {f.tools_involved.map((t) => (
                        <span
                          key={t}
                          className="px-2 py-0.5 rounded bg-black/40 text-cyan-300 border border-cyan-500/30 text-[10px]"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  {f.confidence !== undefined && (
                    <span className="text-gray-400 text-[10px]">
                      Confidence: <strong className="text-purple-200">{(f.confidence * 100).toFixed(0)}%</strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Action pill */}
              <div className="flex items-center space-x-3 flex-shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-purple-500/10">
                <span className="px-3 py-1.5 rounded-xl bg-purple-900/40 hover:bg-purple-800/50 border border-purple-500/30 text-purple-200 text-xs font-medium flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-pink-400" />
                  Inspect & Fix
                  <ArrowRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Finding Detail Modal */}
      {activeFinding && (
        <FindingDetailModal
          finding={activeFinding}
          onClose={() => setActiveFinding(null)}
          onStatusUpdated={handleStatusUpdated}
        />
      )}
    </div>
  );
};
