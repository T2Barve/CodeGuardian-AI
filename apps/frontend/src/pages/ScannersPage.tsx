import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Terminal,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Code2,
  KeyRound,
  FileCheck2,
} from 'lucide-react';
import { api } from '../services/api';
import { ScannerCenterResponse } from '../types';

export const ScannersPage: React.FC = () => {
  const [data, setData] = useState<ScannerCenterResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchScanners = async () => {
    try {
      setLoading(true);
      const res = await api.getScannersStatus();
      setData(res);
    } catch (err) {
      console.error('Failed to load scanner center data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScanners();
  }, []);

  const getScannerIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case 'bandit':
        return <ShieldCheck className="w-6 h-6 text-emerald-400" />;
      case 'semgrep':
        return <Code2 className="w-6 h-6 text-cyan-400" />;
      case 'gitleaks':
        return <KeyRound className="w-6 h-6 text-pink-400" />;
      case 'eslint':
        return <FileCheck2 className="w-6 h-6 text-violet-400" />;
      default:
        return <Terminal className="w-6 h-6 text-purple-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <Cpu className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Static Analysis Scanner Center
              {data && (
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                  {data.operational_tools} / {data.total_tools} Operational
                </span>
              )}
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              Verified AST visitors, entropy parsers, and polyglot static analysis engines running before agent evaluation
            </p>
          </div>
        </div>

        <button
          onClick={fetchScanners}
          className="p-2 self-start md:self-auto rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
          title="Refresh scanner statuses"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Active Engines</span>
          <div className="text-2xl font-bold text-white mt-1 font-mono">
            {data ? `${data.operational_tools} Active` : '—'}
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            Running concurrently on incoming PR diffs in isolated workspaces
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Vulnerability Taxonomy</span>
          <div className="text-2xl font-bold text-pink-400 mt-1 font-mono">
            OWASP & CWE
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            Deterministic mapping into unified Finding and Evidence schema
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Telemetry Correlation</span>
          <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono">
            LangGraph Supervisor
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            Raw scanner outputs automatically correlated with multi-agent reviews
          </p>
        </div>
      </div>

      {/* Scanners Grid */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Verifying local scanner engines and CLI binaries...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data?.tools.map((tool) => {
            const isOperational = tool.is_operational;

            return (
              <div
                key={tool.name}
                className="glass-card p-5 rounded-2xl border border-purple-500/20 hover:border-purple-500/40 transition-all space-y-4"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2.5 rounded-xl bg-black/40 border border-purple-500/20">
                      {getScannerIcon(tool.name)}
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white tracking-tight">
                        {tool.display_name}
                      </h3>
                      <span className="text-[11px] font-mono text-purple-300/80">
                        {tool.category}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`text-xs px-2.5 py-1 rounded-full font-mono font-semibold flex items-center gap-1.5 border ${
                      isOperational
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}
                  >
                    {isOperational ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5" />
                    )}
                    {isOperational ? 'OPERATIONAL' : 'OFFLINE'}
                  </span>
                </div>

                <p className="text-xs text-purple-200/80 leading-relaxed">
                  {tool.description}
                </p>

                {/* Coverage tags */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-[11px] text-gray-400 font-mono block">
                    Supported Detection Coverage:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {tool.supported_coverage.map((cov) => (
                      <span
                        key={cov}
                        className="text-[10px] px-2 py-0.5 rounded-md bg-purple-950/60 text-purple-300 border border-purple-500/20 font-mono"
                      >
                        {cov}
                      </span>
                    ))}
                  </div>
                </div>

                {/* CLI & DB Metrics Footer */}
                <div className="pt-3 border-t border-purple-500/10 flex items-center justify-between text-xs font-mono">
                  <span className="text-gray-400 flex items-center gap-1">
                    <Terminal className="w-3.5 h-3.5 text-purple-400" />
                    <code>{tool.version_command}</code>
                  </span>
                  <span className="text-pink-300 font-semibold">
                    {tool.total_detections} Verified Detections
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
