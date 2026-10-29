import React, { useState, useEffect } from 'react';
import {
  FileText,
  RefreshCw,
  Clock,
  Lock,
} from 'lucide-react';
import { api } from '../services/api';
import { AuditLogRead } from '../types';

export const ReportsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogRead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedResourceType, setSelectedResourceType] = useState('');
  const [selectedAction, setSelectedAction] = useState('');

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      const res = await api.getAuditLogs({
        resource_type: selectedResourceType || undefined,
        action: selectedAction || undefined,
        limit: 100,
      });
      setLogs(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLogs();
  }, [selectedResourceType, selectedAction]);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <FileText className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              Compliance Reports & Audit Trail
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">
                {total} Immutable Events
              </span>
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              Cryptographically verified audit trail capturing every repository onboarding, review run, status change, and automated fix
            </p>
          </div>
        </div>

        <button
          onClick={fetchAuditLogs}
          className="p-2 self-start md:self-auto rounded-xl bg-purple-950/40 hover:bg-purple-900/50 border border-purple-500/20 text-purple-300 hover:text-white transition-colors"
          title="Refresh audit logs"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filter controls */}
      <div className="glass-card p-4 rounded-2xl border border-purple-500/20 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2 text-xs text-purple-300">
          <Lock className="w-4 h-4 text-emerald-400" />
          <span>SOC2 & ISO 27001 Compliant Audit Stream</span>
        </div>

        <div className="flex items-center space-x-2.5">
          <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
            <select
              value={selectedResourceType}
              onChange={(e) => setSelectedResourceType(e.target.value)}
              className="bg-transparent text-purple-200 focus:outline-none text-xs"
            >
              <option value="" className="bg-[#0f0c24] text-white">All Resource Types</option>
              <option value="repository" className="bg-[#0f0c24] text-white">Repository</option>
              <option value="review_job" className="bg-[#0f0c24] text-white">Review Job</option>
              <option value="finding" className="bg-[#0f0c24] text-white">Finding</option>
              <option value="remediation" className="bg-[#0f0c24] text-white">Remediation</option>
            </select>
          </div>

          <div className="glass-input px-3 py-1.5 rounded-xl border border-purple-500/20 text-xs">
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="bg-transparent text-purple-200 focus:outline-none text-xs"
            >
              <option value="" className="bg-[#0f0c24] text-white">All Actions</option>
              <option value="REPOSITORY_ONBOARDED" className="bg-[#0f0c24] text-white">Repository Onboarded</option>
              <option value="REPOSITORY_PULL_REQUESTS_SYNCED" className="bg-[#0f0c24] text-white">PRs Synced</option>
              <option value="REPOSITORY_MONITORING_TOGGLED" className="bg-[#0f0c24] text-white">Monitoring Toggled</option>
              <option value="REVIEW_TRIGGERED" className="bg-[#0f0c24] text-white">Review Triggered</option>
              <option value="FINDING_STATUS_UPDATED" className="bg-[#0f0c24] text-white">Finding Status Updated</option>
              <option value="REPOSITORY_DELETED" className="bg-[#0f0c24] text-white">Repository Deleted</option>
            </select>
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3 text-purple-300">
          <RefreshCw className="w-8 h-8 animate-spin text-pink-400" />
          <span className="text-xs font-mono">Loading immutable audit logs from database...</span>
        </div>
      ) : logs.length === 0 ? (
        <div className="glass-panel p-12 rounded-2xl border border-purple-500/20 text-center space-y-3">
          <div className="w-14 h-14 rounded-full bg-purple-900/30 border border-purple-500/30 flex items-center justify-center mx-auto text-purple-400">
            <FileText className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-white">No Audit Events Recorded Yet</h3>
          <p className="text-xs text-purple-300/70 max-w-md mx-auto">
            Audit events are automatically generated as repositories are onboarded, reviews run, and findings are mitigated.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <div
              key={log.id}
              className="glass-card p-4 rounded-xl border border-purple-500/15 hover:border-purple-500/30 transition-all flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 rounded font-mono font-semibold bg-purple-950/60 text-pink-300 border border-purple-500/30 text-[10px]">
                    {log.action}
                  </span>
                  <span className="font-mono text-purple-200">
                    {log.resource_type}: <code className="text-gray-300">{log.resource_id}</code>
                  </span>
                </div>
                <div className="text-[11px] text-gray-400 font-mono">
                  Actor: <span className="text-purple-300">{log.actor}</span>
                  {log.metadata_payload && Object.keys(log.metadata_payload).length > 0 && (
                    <span className="ml-3 text-gray-500">
                      Payload: {JSON.stringify(log.metadata_payload)}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-2 text-gray-400 font-mono text-[11px] flex-shrink-0">
                <Clock className="w-3.5 h-3.5" />
                <span>{new Date(log.timestamp).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
