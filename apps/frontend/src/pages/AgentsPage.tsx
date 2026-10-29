import React, { useState, useEffect } from 'react';
import {
  Bot,
  BrainCircuit,
  Activity,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { api } from '../services/api';
import { MultiAgentControlCenterResponse } from '../types';

export const AgentsPage: React.FC = () => {
  const [data, setData] = useState<MultiAgentControlCenterResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const res = await api.getAgentsStatus();
      setData(res);
    } catch (err) {
      console.error('Failed to load agent statuses:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    const interval = setInterval(fetchAgents, 10000);
    return () => clearInterval(interval);
  }, []);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className="text-xs px-2.5 py-0.5 rounded-full font-mono font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1.5 animate-pulse">
            <Activity className="w-3.5 h-3.5" />
            EVALUATING
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="text-xs px-2.5 py-0.5 rounded-full font-mono font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/40 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            STANDBY
          </span>
        );
      default:
        return (
          <span className="text-xs px-2.5 py-0.5 rounded-full font-mono font-semibold bg-gray-800 text-gray-400 border border-gray-700">
            IDLE
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <BrainCircuit className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Multi-Agent Orchestration Fabric
              {data && (
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
                  {data.agents.length} Autonomous Agents
                </span>
              )}
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              LangGraph-orchestrated supervisor with five specialized review agents running concurrent code evaluations
            </p>
          </div>
        </div>

        <button
          onClick={fetchAgents}
          className="p-2 self-start md:self-auto rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
          title="Refresh agent telemetry"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Fabric Overview Telemetry Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Fabric Status</span>
          <div className="text-xl font-bold text-white mt-1 flex items-center gap-2 font-mono">
            {data?.is_orchestration_active ? (
              <span className="text-emerald-400 flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                Active Reviewing
              </span>
            ) : (
              <span className="text-purple-300">Operational & Idle</span>
            )}
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            {data?.active_jobs_count || 0} active PR review jobs queued
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Total Agent Runs</span>
          <div className="text-2xl font-bold text-pink-400 mt-1 font-mono">
            {data?.total_agent_executions || 0}
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            Aggregated specialist graph node evaluations
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Total Tokens Consumed</span>
          <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono">
            {data?.total_tokens_consumed.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            Prompt and completion token footprint
          </p>
        </div>

        <div className="glass-card p-4 rounded-2xl border border-purple-500/20">
          <span className="text-xs text-gray-400 font-mono">Consensus Synthesis</span>
          <div className="text-2xl font-bold text-violet-400 mt-1 font-mono">
            LangGraph
          </div>
          <p className="text-[11px] text-purple-300/70 mt-1">
            Deterministic multi-agent state merge & deduplication
          </p>
        </div>
      </div>

      {/* Agents Grid */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Querying multi-agent telemetry and state graph...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.agents.map((agent) => (
            <div
              key={agent.name}
              className="glass-card p-5 rounded-2xl border border-purple-500/20 hover:border-purple-500/40 transition-all flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-xl bg-purple-950/60 text-purple-300 border border-purple-500/30">
                      <Bot className="w-5 h-5 text-pink-400" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white tracking-tight">
                        {agent.display_name}
                      </h3>
                      <span className="text-[10px] font-mono text-purple-300/70">
                        {agent.name}
                      </span>
                    </div>
                  </div>
                  {getStatusBadge(agent.status)}
                </div>

                <p className="text-xs text-purple-200/80 leading-relaxed min-h-[3rem]">
                  {agent.role}
                </p>
              </div>

              {/* Metrics Footer */}
              <div className="space-y-2 pt-3 border-t border-purple-500/10 text-xs font-mono">
                <div className="flex justify-between text-gray-400">
                  <span>Executions:</span>
                  <span className="text-white font-semibold">{agent.total_runs}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Avg Latency:</span>
                  <span className="text-purple-300">{agent.avg_duration_ms} ms</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>Tokens Used:</span>
                  <span className="text-pink-300">{agent.total_tokens.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>LLM Provider:</span>
                  <span className="text-cyan-300 uppercase">{agent.provider} ({agent.model})</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
