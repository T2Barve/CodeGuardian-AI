import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  GitPullRequest, 
  Cpu, 
  AlertTriangle, 
  CheckCircle2, 
  BookMarked, 
  Terminal, 
  FileText, 
  ArrowLeft,
  RefreshCw
} from 'lucide-react';

import { ReviewReport, Finding } from '../types';
import { RiskGradeBadge } from '../components/RiskGradeBadge';
import { SeverityBadge } from '../components/SeverityBadge';
import { FindingDetailModal } from '../components/FindingDetailModal';
import { api } from '../services/api';

export const ReviewPage: React.FC = () => {
  const { reviewId } = useParams<{ reviewId?: string }>();
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [showMarkdown, setShowMarkdown] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'summary' | 'security' | 'quality' | 'testing' | 'documentation' | 'dependencies' | 'agents' | 'timeline'>('summary');
  const [selectedFinding, setSelectedFinding] = useState<Finding | null>(null);

  const loadReview = async () => {
    try {
      setLoading(true);
      setError(null);

      // If no reviewId provided in route, fetch recent reviews and pick the first one
      let targetId = reviewId;
      if (!targetId) {
        const dashboard = await api.getDashboardSummary();
        if (dashboard.recent_reviews.length > 0) {
          targetId = dashboard.recent_reviews[0].review_run_id;
        } else {
          setError('No reviews available. Seed demo data to preview a review run.');
          setLoading(false);
          return;
        }
      }

      const rep = await api.getReviewReport(targetId);
      setReport(rep);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch review report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReview();
  }, [reviewId]);

  const loadMarkdownReport = async () => {
    if (!report) return;
    try {
      const md = await api.getReviewMarkdown(report.summary.review_run_id);
      setMarkdown(md);
      setShowMarkdown(true);
    } catch (err: any) {
      alert(`Failed to load markdown: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center py-24">
        <div className="flex flex-col items-center space-y-3">
          <RefreshCw className="w-8 h-8 animate-spin text-cyan-400" />
          <p className="text-sm font-mono text-slate-400">Loading Pull Request review analysis...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="glass-panel p-12 rounded-2xl border border-slate-800 text-center space-y-4 max-w-xl mx-auto my-12">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Review Report Not Available</h2>
        <p className="text-xs font-mono text-slate-400">{error || 'Review ID not found.'}</p>
        <Link
          to="/"
          className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-mono bg-cyan-950 text-cyan-300 border border-cyan-800"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Dashboard</span>
        </Link>
      </div>
    );
  }

  const { summary, category_breakdown, risk_driving_factors, findings, agent_summaries } = report;

  // Filter findings by category for tabs
  const securityFindings = findings.filter((f) => f.category === 'SECURITY');
  const qualityFindings = findings.filter((f) => f.category === 'QUALITY');
  const testingFindings = findings.filter((f) => f.category === 'TESTING');
  const docFindings = findings.filter((f) => f.category === 'DOCUMENTATION');
  const depFindings = findings.filter((f) => f.category === 'DEPENDENCY');

  return (
    <div className="space-y-8 animate-fade-in">
      {/* PR Header Bar */}
      <section className="glass-panel rounded-2xl border border-slate-800/80 p-6 bg-gradient-to-r from-slate-900 via-slate-900/90 to-cyan-950/20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center space-x-2 text-xs font-mono text-cyan-400">
              <Link to="/repositories" className="hover:underline flex items-center space-x-1">
                <span>{summary.repo_name}</span>
              </Link>
              <span>•</span>
              <span>PR #{summary.pr_number}</span>
              <span>•</span>
              <span className="text-slate-400">{summary.source_branch} &rarr; {summary.target_branch}</span>
            </div>

            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center space-x-2">
              <GitPullRequest className="w-6 h-6 text-cyan-400 shrink-0" />
              <span>{summary.pr_title}</span>
            </h1>

            <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-slate-400 pt-1">
              <span>Author: <strong className="text-slate-300">@{summary.author}</strong></span>
              <span>•</span>
              <span>Commit: <strong className="text-slate-300">{summary.commit_sha.slice(0, 7)}</strong></span>
              <span>•</span>
              <span>Duration: <strong className="text-slate-300">{summary.duration_ms}ms</strong></span>
              <span>•</span>
              <span>Total Findings: <strong className="text-slate-300">{summary.total_findings}</strong></span>
            </div>
          </div>

          {/* Risk & Mergeability Status */}
          <div className="flex items-center space-x-4 bg-slate-950/80 border border-slate-800 p-4 rounded-xl">
            <div className="text-right">
              <div className="text-[11px] font-mono text-slate-400">Deterministic Risk Assessment</div>
              <div className="flex items-center justify-end space-x-2 mt-0.5">
                <span className="text-xl font-mono font-bold text-white">{summary.risk_score.toFixed(1)}</span>
                <span className="text-xs text-slate-500 font-mono">/ 100</span>
              </div>
              <div className="mt-1 flex items-center justify-end space-x-2">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  summary.is_mergeable 
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' 
                    : 'bg-rose-950 text-rose-400 border border-rose-800'
                }`}>
                  {summary.is_mergeable ? '✅ MERGEABLE' : '🚫 MERGE BLOCKED'}
                </span>
                <span className="text-[10px] font-mono text-slate-400">{summary.recommended_action}</span>
              </div>
            </div>
            <RiskGradeBadge grade={summary.risk_grade} score={summary.risk_score} size="lg" />
          </div>
        </div>
      </section>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-800 overflow-x-auto gap-2">
        {[
          { id: 'summary', label: 'Executive Summary', count: null },
          { id: 'security', label: 'Security Vulnerabilities', count: securityFindings.length },
          { id: 'quality', label: 'Code Quality & Smells', count: qualityFindings.length },
          { id: 'testing', label: 'Test Coverage Gap', count: testingFindings.length },
          { id: 'documentation', label: 'Documentation Drift', count: docFindings.length },
          { id: 'dependencies', label: 'Dependencies', count: depFindings.length },
          { id: 'agents', label: 'Agent Fabric Telemetry', count: agent_summaries.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id as any);
              setShowMarkdown(false);
            }}
            className={`py-3 px-4 text-xs font-mono font-semibold border-b-2 transition-all whitespace-nowrap flex items-center space-x-1.5 ${
              activeTab === tab.id && !showMarkdown
                ? 'border-cyan-400 text-cyan-400 bg-cyan-950/20 rounded-t-lg'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40'
            }`}
          >
            <span>{tab.label}</span>
            {tab.count !== null && tab.count > 0 && (
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                tab.id === 'security' ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-slate-800 text-slate-300'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}

        <button
          onClick={() => {
            loadMarkdownReport();
          }}
          className={`py-3 px-4 text-xs font-mono font-semibold border-b-2 transition-all whitespace-nowrap ml-auto flex items-center space-x-1.5 ${
            showMarkdown
              ? 'border-cyan-400 text-cyan-400 bg-cyan-950/20 rounded-t-lg'
              : 'border-transparent text-slate-400 hover:text-cyan-300'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>GitHub Markdown View</span>
        </button>
      </div>

      {/* Markdown View Toggle */}
      {showMarkdown && (
        <section className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-sm font-mono font-bold text-white flex items-center space-x-2">
              <FileText className="w-4 h-4 text-cyan-400" />
              <span>Full GitHub PR Review Report (Markdown Stream)</span>
            </h3>
            <button
              onClick={() => setShowMarkdown(false)}
              className="text-xs font-mono text-cyan-400 hover:underline"
            >
              Close Markdown View
            </button>
          </div>
          <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">
            {markdown || 'Loading report markdown...'}
          </pre>
        </section>
      )}

      {/* Tab: Summary */}
      {activeTab === 'summary' && !showMarkdown && (
        <div className="space-y-6">
          {/* Findings Distribution Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-center">
              <div className="text-[11px] font-mono text-slate-400">Total Findings</div>
              <div className="text-xl font-bold font-mono text-white mt-1">{summary.total_findings}</div>
            </div>
            <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-900/50 text-center">
              <div className="text-[11px] font-mono text-rose-400">Critical Blockers</div>
              <div className="text-xl font-bold font-mono text-rose-400 mt-1">{summary.critical_count}</div>
            </div>
            <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900/50 text-center">
              <div className="text-[11px] font-mono text-amber-400">High Severity</div>
              <div className="text-xl font-bold font-mono text-amber-400 mt-1">{summary.high_count}</div>
            </div>
            <div className="p-4 rounded-xl bg-yellow-950/30 border border-yellow-900/40 text-center">
              <div className="text-[11px] font-mono text-yellow-400">Medium Severity</div>
              <div className="text-xl font-bold font-mono text-yellow-400 mt-1">{summary.medium_count}</div>
            </div>
            <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-900/40 text-center">
              <div className="text-[11px] font-mono text-blue-400">Low Warnings</div>
              <div className="text-xl font-bold font-mono text-blue-400 mt-1">{summary.low_count}</div>
            </div>
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-center">
              <div className="text-[11px] font-mono text-slate-400">Informational</div>
              <div className="text-xl font-bold font-mono text-slate-300 mt-1">{summary.info_count}</div>
            </div>
          </div>

          {/* Key Risk Drivers */}
          {risk_driving_factors && risk_driving_factors.length > 0 && (
            <div className="glass-panel p-6 rounded-2xl border border-amber-900/40 bg-amber-950/10 space-y-3">
              <h3 className="text-sm font-mono font-bold text-amber-300 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Deterministic Risk Driving Factors</span>
              </h3>
              <ul className="space-y-1.5 text-xs text-slate-300 font-mono">
                {risk_driving_factors.map((factor, idx) => (
                  <li key={idx} className="flex items-start space-x-2">
                    <span className="text-amber-400">•</span>
                    <span>{factor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Category Radar Matrix Table */}
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <h3 className="text-sm font-semibold text-white">Category Dimension Breakdown</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {[
                { label: 'Security', score: category_breakdown.security, count: securityFindings.length, color: 'text-rose-400' },
                { label: 'Quality', score: category_breakdown.quality, count: qualityFindings.length, color: 'text-indigo-400' },
                { label: 'Testing', score: category_breakdown.testing, count: testingFindings.length, color: 'text-cyan-400' },
                { label: 'Documentation', score: category_breakdown.documentation, count: docFindings.length, color: 'text-emerald-400' },
                { label: 'Dependencies', score: category_breakdown.dependency, count: depFindings.length, color: 'text-amber-400' },
              ].map((c) => (
                <div key={c.label} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1">
                  <span className="text-xs font-mono text-slate-400">{c.label}</span>
                  <div className={`text-xl font-bold font-mono ${c.color}`}>{c.score.toFixed(1)}</div>
                  <div className="text-[11px] font-mono text-slate-500">{c.count} findings identified</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Security / Quality / Testing / Docs / Deps Finding Lists */}
      {(['security', 'quality', 'testing', 'documentation', 'dependencies'].includes(activeTab)) && !showMarkdown && (
        <div className="space-y-4">
          {(() => {
            const list = 
              activeTab === 'security' ? securityFindings :
              activeTab === 'quality' ? qualityFindings :
              activeTab === 'testing' ? testingFindings :
              activeTab === 'documentation' ? docFindings : depFindings;

            if (list.length === 0) {
              return (
                <div className="glass-panel p-12 rounded-2xl border border-slate-800 text-center space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                  <h4 className="text-sm font-semibold text-white">Clean Dimension</h4>
                  <p className="text-xs font-mono text-slate-400">
                    No defects or violations identified under the {activeTab.toUpperCase()} category.
                  </p>
                </div>
              );
            }

            return list.map((f) => (
              <div
                key={f.id}
                onClick={() => setSelectedFinding(f)}
                className="glass-panel p-5 rounded-xl border border-slate-800 hover:border-slate-700 cursor-pointer transition-all space-y-3 bg-slate-900/40"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-2.5">
                    <SeverityBadge severity={f.severity} />
                    <h4 className="text-sm font-bold text-white tracking-tight">{f.title}</h4>
                  </div>
                  <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
                    <span className="text-cyan-400 font-semibold">{f.category}</span>
                    <span>•</span>
                    <span>Confidence: {(f.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">{f.description}</p>

                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/60 pt-3 text-xs font-mono text-slate-400">
                  <div className="flex items-center space-x-2">
                    <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{f.file_path}:{f.line_start || 1}</span>
                  </div>
                  {f.policy_reference && (
                    <div className="flex items-center space-x-1.5 text-indigo-400">
                      <BookMarked className="w-3.5 h-3.5" />
                      <span className="truncate max-w-xs">{f.policy_reference}</span>
                    </div>
                  )}
                  <button className="text-cyan-400 hover:underline flex items-center space-x-1">
                    <span>Inspect Evidence & Remediation</span>
                    <span>&rarr;</span>
                  </button>
                </div>
              </div>
            ));
          })()}
        </div>
      )}

      {/* Tab: Agent Telemetry Matrix */}
      {activeTab === 'agents' && !showMarkdown && (
        <section className="glass-panel rounded-2xl border border-slate-800 overflow-hidden space-y-4 p-6">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">LangGraph Multi-Agent Execution Telemetry</h3>
            <p className="text-xs text-slate-400 mt-1">
              Deterministic routing by Supervisor Agent with isolated parallel specialist agent runs
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 font-semibold text-slate-400 uppercase border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Agent Name</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Duration</th>
                  <th className="py-3 px-4">Token Consumption</th>
                  <th className="py-3 px-4">Identified Findings</th>
                  <th className="py-3 px-4">Error State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 text-slate-300">
                {agent_summaries.map((ag) => (
                  <tr key={ag.agent_name} className="hover:bg-slate-800/40">
                    <td className="py-3.5 px-4 font-bold text-white flex items-center space-x-2">
                      <Cpu className="w-4 h-4 text-cyan-400" />
                      <span>{ag.agent_name}</span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                        ag.status === 'COMPLETED' 
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                          : 'bg-rose-950 text-rose-400 border border-rose-800'
                      }`}>
                        {ag.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">{ag.duration_ms}ms</td>
                    <td className="py-3.5 px-4 text-slate-400">{ag.token_usage} tokens</td>
                    <td className="py-3.5 px-4 font-semibold text-cyan-300">{ag.findings_count}</td>
                    <td className="py-3.5 px-4 text-slate-500">{ag.error || 'None (Clean)'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Finding Detail Modal */}
      <FindingDetailModal
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
        onStatusUpdated={(updated) => {
          setSelectedFinding(updated);
          loadReview();
        }}
      />
    </div>
  );
};
