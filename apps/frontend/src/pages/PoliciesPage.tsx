import React, { useEffect, useState } from 'react';
import { 
  BookMarked, 
  Search, 
  Sparkles, 
  RefreshCw
} from 'lucide-react';

import { PolicyRead } from '../types';
import { api } from '../services/api';

export const PoliciesPage: React.FC = () => {
  const [policies, setPolicies] = useState<PolicyRead[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyRead | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  // RAG Search state
  const [ragQuery, setRagQuery] = useState<string>('SQL injection database parameterization');
  const [ragResult, setRagResult] = useState<{ results_count: number; formatted_context: string; chunks: any[] } | null>(null);
  const [searchingRag, setSearchingRag] = useState<boolean>(false);

  const loadPolicies = async () => {
    try {
      setLoading(true);
      const data = await api.getPolicies(categoryFilter === 'ALL' ? undefined : categoryFilter);
      setPolicies(data);
      if (data.length > 0 && !selectedPolicy) {
        loadPolicyDetail(data[0].id);
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadPolicyDetail = async (id: string) => {
    try {
      const detail = await api.getPolicyDetail(id);
      setSelectedPolicy(detail);
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadPolicies();
  }, [categoryFilter]);

  const handleTestRag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ragQuery.trim()) return;

    try {
      setSearchingRag(true);
      const res = await api.queryRAG(ragQuery);
      setRagResult(res);
    } catch (err: any) {
      alert(`RAG query failed: ${err.message}`);
    } finally {
      setSearchingRag(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Engineering Policies & RAG Standards</h1>
          <p className="text-sm text-slate-400 mt-1">
            Ground-truth organizational coding rules indexed into the ChromaDB vector database with strict anti-hallucination controls
          </p>
        </div>

        {/* Category Filter Pills */}
        <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-mono">
          {['ALL', 'SECURITY', 'QUALITY', 'TESTING', 'DOCUMENTATION'].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-lg transition-colors ${
                categoryFilter === cat
                  ? 'bg-cyan-950 text-cyan-400 border border-cyan-800 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Policy Browser & RAG Query Sandbox */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Policy List */}
        <div className="lg:col-span-1 space-y-3">
          {loading ? (
            <div className="glass-panel p-8 rounded-2xl border border-slate-800 text-center">
              <RefreshCw className="w-6 h-6 animate-spin text-cyan-400 mx-auto mb-2" />
              <p className="text-xs font-mono text-slate-400">Loading policy standards...</p>
            </div>
          ) : policies.length > 0 ? (
            policies.map((p) => {
              const isSelected = selectedPolicy?.id === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => loadPolicyDetail(p.id)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-slate-900 border-cyan-500/80 shadow-md shadow-cyan-950/40'
                      : 'glass-panel border-slate-800 hover:border-slate-700 bg-slate-900/40'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-2.5">
                      <BookMarked className={`w-5 h-5 ${isSelected ? 'text-cyan-400' : 'text-slate-400'}`} />
                      <div>
                        <h4 className="text-sm font-bold text-white font-mono">{p.name}</h4>
                        <span className="text-[11px] font-mono text-slate-400">v{p.version} • {p.source}</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-xs font-mono border-t border-slate-800/60 pt-2.5">
                    <span className="text-cyan-400 font-semibold">{p.category}</span>
                    <span className="text-emerald-400">Active</span>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="glass-panel p-8 rounded-2xl border border-slate-800 text-center text-xs font-mono text-slate-500">
              No policies found for this category. Click "Seed Demo" in the navbar to load standard baselines.
            </div>
          )}
        </div>

        {/* Right: Selected Policy Hierarchy & Interactive RAG Sandbox */}
        <div className="lg:col-span-2 space-y-6">
          {/* Interactive RAG Semantic Search Sandbox */}
          <div className="glass-panel p-6 rounded-2xl border border-cyan-900/50 bg-cyan-950/10 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-mono font-bold text-cyan-300 flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <span>Interactive RAG Semantic Search Sandbox</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Test live embedding similarity retrieval and anti-hallucination sentinel behavior
                </p>
              </div>
            </div>

            <form onSubmit={handleTestRag} className="flex gap-2">
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Ask or query engineering standard (e.g. SQL parameterization, complexity limits)..."
                className="flex-1 px-3.5 py-2 text-xs rounded-xl bg-slate-900 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
              />
              <button
                type="submit"
                disabled={searchingRag}
                className="px-4 py-2 rounded-xl text-xs font-mono font-bold bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-700/60 transition-colors flex items-center space-x-1.5 disabled:opacity-50"
              >
                {searchingRag ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                <span>Retrieve</span>
              </button>
            </form>

            {ragResult && (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 animate-fade-in font-mono text-xs">
                <div className="flex items-center justify-between text-slate-400 text-[11px] border-b border-slate-800 pb-2">
                  <span>Retrieved Matches: <strong className="text-cyan-400">{ragResult.results_count}</strong></span>
                  <span>Sentinel Check: {ragResult.results_count === 0 ? 'TRIGGERED (Safe)' : 'MATCHED'}</span>
                </div>
                <div className="text-slate-300 whitespace-pre-wrap leading-relaxed">
                  {ragResult.formatted_context}
                </div>
              </div>
            )}
          </div>

          {/* Selected Policy Chunks */}
          {selectedPolicy && (
            <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
              <div className="border-b border-slate-800 pb-3 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-white tracking-tight font-mono">{selectedPolicy.name}</h3>
                  <p className="text-xs font-mono text-slate-400">Source: {selectedPolicy.source}</p>
                </div>
                <span className="px-2.5 py-1 rounded-md text-xs font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                  {selectedPolicy.chunks?.length || 0} Chunks
                </span>
              </div>

              <div className="space-y-3">
                {selectedPolicy.chunks && selectedPolicy.chunks.length > 0 ? (
                  selectedPolicy.chunks.map((chunk) => (
                    <div key={chunk.id} className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span className="text-cyan-400 font-semibold">Chunk #{chunk.chunk_index}</span>
                        <span>Ref: {chunk.embedding_reference || 'vector_ref'}</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-mono bg-slate-900/50 p-3 rounded-lg border border-slate-800/80">
                        {chunk.content}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="p-6 text-center text-xs font-mono text-slate-500">
                    No chunk records loaded for this policy standard.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
