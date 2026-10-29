import React from 'react';
import { ShieldCheck, Terminal, GitPullRequest } from 'lucide-react';
import { HealthStatus } from '../types';

interface HeaderProps {
  health: HealthStatus | null;
  loading: boolean;
}

export const Header: React.FC<HeaderProps> = ({ health, loading }) => {
  return (
    <header className="glass-panel border-b border-slate-800/80 sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
      <div className="flex items-center space-x-3.5">
        <div className="bg-gradient-to-tr from-cyan-600 to-sky-400 p-2.5 rounded-xl shadow-lg shadow-sky-500/20 flex items-center justify-center">
          <ShieldCheck className="w-6 h-6 text-white" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-bold text-lg tracking-tight text-white">CodeGuardian</span>
            <span className="text-xs uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-semibold">
              AI DevSecOps
            </span>
          </div>
          <p className="text-xs text-slate-400 font-medium">Autonomous Multi-Agent PR Review & Remediation Platform</p>
        </div>
      </div>

      <div className="flex items-center space-x-6 text-sm">
        <div className="flex items-center space-x-2 text-slate-300">
          <GitPullRequest className="w-4 h-4 text-sky-400" />
          <span className="text-xs text-slate-400">PR Gateway:</span>
          <span className="text-xs font-mono font-semibold text-slate-200">Active</span>
        </div>

        <div className="flex items-center space-x-2 border-l border-slate-800 pl-6">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="text-xs text-slate-400">API Gateway:</span>
          {loading ? (
            <span className="text-xs font-mono text-slate-400 animate-pulse">Connecting...</span>
          ) : health?.status === 'healthy' ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-950/70 text-emerald-400 border border-emerald-800/60">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-ping"></span>
              Live (v{health.version})
            </span>
          ) : (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-mono font-medium bg-amber-950/70 text-amber-400 border border-amber-800/60">
              Offline
            </span>
          )}
        </div>
      </div>
    </header>
  );
};
