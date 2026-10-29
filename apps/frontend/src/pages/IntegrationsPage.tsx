import React, { useState, useEffect } from 'react';
import {
  Network,
  Database,
  Layers,
  Webhook,
  Github,
  Cpu,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import { api } from '../services/api';
import { IntegrationsStatusResponse } from '../types';

export const IntegrationsPage: React.FC = () => {
  const [data, setData] = useState<IntegrationsStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchIntegrations = async () => {
    try {
      setLoading(true);
      const res = await api.getIntegrationsStatus();
      setData(res);
    } catch (err) {
      console.error('Failed to load integrations status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'CONNECTED':
        return (
          <span className="text-xs px-2.5 py-1 rounded-full font-mono font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            CONNECTED
          </span>
        );
      case 'PENDING':
        return (
          <span className="text-xs px-2.5 py-1 rounded-full font-mono font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            PENDING CONFIG
          </span>
        );
      case 'UNCONFIGURED':
        return (
          <span className="text-xs px-2.5 py-1 rounded-full font-mono font-semibold bg-gray-800 text-gray-400 border border-gray-700 flex items-center gap-1.5">
            OPTIONAL
          </span>
        );
      default:
        return (
          <span className="text-xs px-2.5 py-1 rounded-full font-mono font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1.5">
            <XCircle className="w-3.5 h-3.5" />
            OFFLINE
          </span>
        );
    }
  };

  const getComponentIcon = (id: string) => {
    switch (id) {
      case 'database':
        return <Database className="w-6 h-6 text-cyan-400" />;
      case 'queue':
        return <Layers className="w-6 h-6 text-pink-400" />;
      case 'github_webhook':
        return <Webhook className="w-6 h-6 text-purple-400" />;
      case 'github_api':
        return <Github className="w-6 h-6 text-emerald-400" />;
      case 'llm_provider':
        return <Cpu className="w-6 h-6 text-violet-400" />;
      case 'scanners':
        return <ShieldCheck className="w-6 h-6 text-teal-400" />;
      default:
        return <Network className="w-6 h-6 text-purple-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <Network className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Infrastructure & Integrations Hub
              {data && (
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-mono ${
                  data.all_ready 
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {data.all_ready ? 'All Core Systems Operational' : 'Action Required'}
                </span>
              )}
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              Live operational health and connection credentials for database, queues, GitHub, LLM engines, and vector stores
            </p>
          </div>
        </div>

        <button
          onClick={fetchIntegrations}
          className="p-2 self-start md:self-auto rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
          title="Re-check connections"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Components Grid */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Pinging integrated platform components...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {data?.components.map((comp) => (
            <div
              key={comp.id}
              className="glass-card p-5 rounded-2xl border border-purple-500/20 hover:border-purple-500/40 transition-all flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2.5 rounded-xl bg-black/40 border border-purple-500/20">
                      {getComponentIcon(comp.id)}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white tracking-tight">
                        {comp.name}
                      </h3>
                      <span className="text-[11px] font-mono text-purple-300/70">
                        {comp.category}
                      </span>
                    </div>
                  </div>
                  {getStatusBadge(comp.status)}
                </div>

                <p className="text-xs text-purple-200/80 leading-relaxed font-mono">
                  {comp.details}
                </p>
              </div>

              {/* Metadata tags */}
              {comp.metadata && Object.keys(comp.metadata).length > 0 && (
                <div className="pt-3 border-t border-purple-500/10 flex flex-wrap gap-2 text-[10px] font-mono">
                  {Object.entries(comp.metadata).map(([k, v]) => (
                    <span
                      key={k}
                      className="px-2 py-0.5 rounded bg-black/40 text-gray-300 border border-purple-500/20"
                    >
                      <strong className="text-purple-300">{k}:</strong> {v}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
