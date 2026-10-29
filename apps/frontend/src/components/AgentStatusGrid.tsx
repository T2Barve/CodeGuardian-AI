import React from 'react';
import { ShieldAlert, Code2, TestTube2, BookOpen, Layers, Bot } from 'lucide-react';

interface AgentInfo {
  name: string;
  role: string;
  tools: string;
  icon: React.ReactNode;
  status: 'Ready' | 'Active' | 'Standby';
}

const agents: AgentInfo[] = [
  {
    name: 'Supervisor Agent',
    role: 'Orchestrator & State Reducer',
    tools: 'LangGraph StateGraph, AST Partitioning',
    icon: <Bot className="w-4 h-4 text-cyan-400" />,
    status: 'Ready',
  },
  {
    name: 'Security Agent',
    role: 'CWE / OWASP Vulnerability Analysis',
    tools: 'Semgrep, Bandit, Gitleaks',
    icon: <ShieldAlert className="w-4 h-4 text-rose-400" />,
    status: 'Ready',
  },
  {
    name: 'Quality Agent',
    role: 'Maintainability & Complexity Review',
    tools: 'AST Metrics, ESLint, Standards RAG',
    icon: <Code2 className="w-4 h-4 text-amber-400" />,
    status: 'Ready',
  },
  {
    name: 'Testing Agent',
    role: 'Test-Gap & Regression Risk Analysis',
    tools: 'Coverage Gap Mapper, AST Branch Tracer',
    icon: <TestTube2 className="w-4 h-4 text-indigo-400" />,
    status: 'Ready',
  },
  {
    name: 'Documentation Agent',
    role: 'Public API & Contract Alignment',
    tools: 'Docstring Validator, Interface Auditor',
    icon: <BookOpen className="w-4 h-4 text-emerald-400" />,
    status: 'Ready',
  },
  {
    name: 'Dependency Agent',
    role: 'Supply Chain & Version Risk',
    tools: 'Lockfile Diff Parser, Manifest Auditor',
    icon: <Layers className="w-4 h-4 text-purple-400" />,
    status: 'Ready',
  },
];

export const AgentStatusGrid: React.FC = () => {
  return (
    <div className="glass-panel rounded-xl p-5 border border-slate-800/80">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">LangGraph Multi-Agent Fabric</h3>
          <p className="text-xs text-slate-400">Specialist autonomous agents coordinated via typed ReviewState</p>
        </div>
        <span className="text-xs font-mono px-2.5 py-1 rounded-full bg-cyan-950/60 text-cyan-400 border border-cyan-800/50">
          6 Registered Agents
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className="p-3.5 rounded-lg bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className="p-1.5 rounded-md bg-slate-800/80">{agent.icon}</div>
                  <span className="text-xs font-semibold text-slate-200">{agent.name}</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800/50">
                  {agent.status}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mb-2 leading-relaxed">{agent.role}</p>
            </div>
            <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[10px] text-slate-500">
              <span className="font-mono">Tools:</span>
              <span className="text-slate-400 truncate ml-1">{agent.tools}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
