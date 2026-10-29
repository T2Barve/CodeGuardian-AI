import React, { useState, useEffect } from 'react';
import {
  Wrench,
  GitPullRequest,
  CheckCircle2,
  GitBranch,
  RefreshCw,
  ExternalLink,
  Flame,
} from 'lucide-react';
import { api } from '../services/api';
import { FixPRResponse } from '../types';

export const RemediationPage: React.FC = () => {
  const [fixPrs, setFixPrs] = useState<FixPRResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  const fetchFixPrs = async () => {
    try {
      setLoading(true);
      const res = await api.getFixPRs(statusFilter || undefined);
      setFixPrs(res || []);
    } catch (err) {
      console.error('Failed to load fix PRs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFixPrs();
  }, [statusFilter]);

  const pipelineStages = [
    { num: 1, title: 'Patch Application', desc: 'Minimal unified diff written to isolated workspace' },
    { num: 2, title: 'Syntax Verification', desc: 'Strict AST parse check verifying zero syntax regressions' },
    { num: 3, title: 'Scanner Rescan', desc: 'Bandit/Semgrep rerun confirms complete vulnerability mitigation' },
    { num: 4, title: 'Test Execution', desc: 'Automated test suite execution ensuring functional stability' },
    { num: 5, title: 'Isolated Fix PR', desc: 'Branch codeguardian/fix-* pushed to GitHub awaiting approval' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <Wrench className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Remediation Engine & Automated Fix PRs
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
                {fixPrs.length} Fix Branches
              </span>
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              5-stage sandboxed patch validation with automated isolated GitHub pull request dispatch
            </p>
          </div>
        </div>

        <button
          onClick={fetchFixPrs}
          className="p-2 self-start md:self-auto rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
          title="Refresh fix PRs"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* 5-Stage Sandbox Pipeline Graphic */}
      <div className="glass-panel p-6 rounded-2xl border border-purple-500/20 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
            <Flame className="w-4 h-4 text-pink-400" />
            5-Stage Strict Sandbox Validation Pipeline
          </h3>
          <span className="text-[11px] font-mono text-emerald-300 bg-emerald-950/40 px-2.5 py-0.5 rounded border border-emerald-500/30">
            Zero Direct-To-Main Commits Enforced
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {pipelineStages.map((stage) => (
            <div
              key={stage.num}
              className="p-3.5 rounded-xl bg-black/40 border border-purple-500/20 flex flex-col justify-between space-y-2 relative"
            >
              <div className="flex items-center justify-between">
                <span className="w-5 h-5 rounded-full bg-purple-900/60 text-pink-400 border border-purple-500/30 flex items-center justify-center text-xs font-mono font-bold">
                  {stage.num}
                </span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white tracking-tight">{stage.title}</h4>
                <p className="text-[11px] text-gray-400 mt-1 leading-snug">{stage.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Status filter bar */}
      <div className="glass-card p-4 rounded-2xl border border-purple-500/20 flex items-center justify-between">
        <div className="flex items-center space-x-2 text-xs text-purple-300 font-mono">
          <GitBranch className="w-4 h-4 text-cyan-400" />
          <span>Automated Fix PR Branch Submissions</span>
        </div>

        <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-transparent text-purple-200 focus:outline-none text-xs"
          >
            <option value="" className="bg-[#0f0c24] text-white">All PR Statuses</option>
            <option value="OPEN" className="bg-[#0f0c24] text-white">Open</option>
            <option value="MERGED" className="bg-[#0f0c24] text-white">Merged</option>
            <option value="CLOSED" className="bg-[#0f0c24] text-white">Closed</option>
          </select>
        </div>
      </div>

      {/* Fix PRs List */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Querying automated Fix PR repository...</span>
        </div>
      ) : fixPrs.length === 0 ? (
        <div className="glass-panel p-12 rounded-2xl border border-purple-500/20 text-center space-y-3">
          <div className="w-14 h-14 rounded-full bg-purple-900/30 border border-purple-500/30 flex items-center justify-center mx-auto text-purple-400">
            <GitPullRequest className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-white">No Automated Fix PRs Generated Yet</h3>
          <p className="text-xs text-purple-300/70 max-w-md mx-auto">
            To generate and submit a validated Fix PR, open any Finding from the Findings Explorer or Review Explorer and click <strong>"Remediate in Sandbox"</strong>.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {fixPrs.map((pr) => (
            <div
              key={pr.id}
              className="glass-card p-5 rounded-2xl border border-purple-500/15 hover:border-purple-500/40 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center space-x-2.5">
                  <span className="text-xs px-2 py-0.5 rounded font-mono font-semibold bg-purple-950/60 text-purple-300 border border-purple-500/30">
                    {pr.repo_name}
                  </span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-mono uppercase font-semibold border ${
                      pr.status === 'OPEN'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                        : 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                    }`}
                  >
                    {pr.status}
                  </span>
                  <span className="text-xs text-gray-400 font-mono">
                    Created {new Date(pr.created_at).toLocaleDateString()}
                  </span>
                </div>

                <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-pink-400" />
                  {pr.branch_name}
                  <span className="text-gray-500">&rarr;</span>
                  <span className="text-purple-300">{pr.base_branch}</span>
                </h3>

                <p className="text-xs text-gray-400">
                  Sandboxed remediation verified against syntax and test assertions. Developer human approval required to merge.
                </p>
              </div>

              {pr.url && (
                <a
                  href={pr.url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 rounded-xl bg-purple-900/50 hover:bg-purple-800/60 border border-purple-500/30 text-white text-xs font-medium flex items-center gap-1.5 transition-colors self-start md:self-auto"
                >
                  <span>Review on GitHub</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
