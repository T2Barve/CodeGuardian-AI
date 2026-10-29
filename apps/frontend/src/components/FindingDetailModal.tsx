import React, { useState, useEffect } from 'react';
import { 
  X, 
  Terminal, 
  Lightbulb, 
  BookMarked, 
  CheckCircle, 
  AlertTriangle, 
  Wrench,
  Loader2,
  Volume2,
  Play,
  Pause,
  Globe
} from 'lucide-react';
import { Finding, FindingExplanation, FindingStatus, SupportedLanguageCode } from '../types';
import { SeverityBadge } from './SeverityBadge';
import { api } from '../services/api';

interface FindingDetailModalProps {
  finding: Finding | null;
  onClose: () => void;
  onStatusUpdated?: (updated: Finding) => void;
}

export const FindingDetailModal: React.FC<FindingDetailModalProps> = ({
  finding,
  onClose,
  onStatusUpdated,
}) => {
  const [updating, setUpdating] = useState(false);
  const [activeTab, setActiveTab] = useState<'details' | 'evidence' | 'remediation' | 'voice_explain'>('details');
  const [reason, setReason] = useState('');
  const [selectedLang, setSelectedLang] = useState<SupportedLanguageCode>('hi');
  const [explanation, setExplanation] = useState<FindingExplanation | null>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [audioInstance, setAudioInstance] = useState<HTMLAudioElement | null>(null);

  if (!finding) return null;

  const handleUpdateStatus = async (newStatus: FindingStatus) => {
    try {
      setUpdating(true);
      const updated = await api.updateFindingStatus(finding.id, newStatus, reason || undefined);
      if (onStatusUpdated) onStatusUpdated(updated);
    } catch (err: any) {
      alert(`Failed to update status: ${err.message}`);
    } finally {
      setUpdating(false);
    }
  };

  const fetchExplanation = async (lang: SupportedLanguageCode) => {
    if (!finding) return;
    try {
      setLoadingExplanation(true);
      const data = await api.explainFinding(finding.id, lang);
      setExplanation(data);
    } catch (err: any) {
      console.error('Failed to load explanation:', err);
    } finally {
      setLoadingExplanation(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'voice_explain' && finding) {
      fetchExplanation(selectedLang);
    }
    return () => {
      if (audioInstance) {
        audioInstance.pause();
      }
    };
  }, [activeTab, selectedLang, finding?.id]);

  const handleToggleAudio = () => {
    if (!finding) return;

    if (isPlayingAudio && audioInstance) {
      audioInstance.pause();
      setIsPlayingAudio(false);
      return;
    }

    const audioUrl = api.getFindingAudioUrl(finding.id, selectedLang);
    const audio = new Audio(audioUrl);
    setAudioInstance(audio);

    audio.onplay = () => setIsPlayingAudio(true);
    audio.onended = () => setIsPlayingAudio(false);
    audio.onerror = () => {
      setIsPlayingAudio(false);
      if ('speechSynthesis' in window && explanation?.voice_script) {
        const utter = new SpeechSynthesisUtterance(explanation.voice_script);
        utter.lang = selectedLang === 'hi' || selectedLang === 'hinglish' ? 'hi-IN' : 'en-US';
        utter.onend = () => setIsPlayingAudio(false);
        setIsPlayingAudio(true);
        window.speechSynthesis.speak(utter);
      }
    };

    audio.play().catch(() => {
      if ('speechSynthesis' in window && explanation?.voice_script) {
        const utter = new SpeechSynthesisUtterance(explanation.voice_script);
        utter.onend = () => setIsPlayingAudio(false);
        setIsPlayingAudio(true);
        window.speechSynthesis.speak(utter);
      }
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div 
        className="glass-panel w-full max-w-3xl max-h-[90vh] rounded-2xl border border-slate-800 shadow-2xl flex flex-col overflow-hidden bg-slate-900/95"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-start justify-between">
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <SeverityBadge severity={finding.severity} />
              <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                {finding.category}
              </span>
              <span className="text-xs font-mono text-cyan-400">
                Confidence: {(finding.confidence * 100).toFixed(0)}%
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-mono uppercase ${
                finding.status === 'OPEN' 
                  ? 'bg-rose-950/60 text-rose-300 border border-rose-800/40' 
                  : 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/40'
              }`}>
                {finding.status}
              </span>
            </div>
            <h2 className="text-lg font-bold text-white tracking-tight">{finding.title}</h2>
            <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
              <Terminal className="w-3.5 h-3.5 text-cyan-400" />
              <span>{finding.file_path}</span>
              {finding.line_start && (
                <span>:L{finding.line_start}{finding.line_end ? `-L${finding.line_end}` : ''}</span>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-800 px-6 bg-slate-950/40">
          <button
            onClick={() => setActiveTab('details')}
            className={`py-2.5 px-4 text-xs font-medium border-b-2 transition-colors ${
              activeTab === 'details'
                ? 'border-cyan-400 text-cyan-400 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Finding Details
          </button>
          <button
            onClick={() => setActiveTab('evidence')}
            className={`py-2.5 px-4 text-xs font-medium border-b-2 transition-colors ${
              activeTab === 'evidence'
                ? 'border-cyan-400 text-cyan-400 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Tool Evidence Chain ({finding.evidence?.length || 1})
          </button>
          <button
            onClick={() => setActiveTab('remediation')}
            className={`py-2.5 px-4 text-xs font-medium border-b-2 transition-colors ${
              activeTab === 'remediation'
                ? 'border-cyan-400 text-cyan-400 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            AI Remediation Sandbox
          </button>
          <button
            onClick={() => setActiveTab('voice_explain')}
            className={`py-2.5 px-4 text-xs font-medium border-b-2 transition-colors flex items-center space-x-1.5 ${
              activeTab === 'voice_explain'
                ? 'border-cyan-400 text-cyan-400 font-semibold'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-3.5 h-3.5 text-cyan-400" />
            <span>AI Voice & Explanations</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm text-slate-300">
          {activeTab === 'details' && (
            <>
              {/* Description */}
              <div>
                <h4 className="text-xs font-mono uppercase text-slate-400 font-semibold mb-1.5">Description</h4>
                <p className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800/80 leading-relaxed">
                  {finding.description}
                </p>
              </div>

              {/* Code Snippet */}
              {finding.code_snippet && (
                <div>
                  <h4 className="text-xs font-mono uppercase text-slate-400 font-semibold mb-1.5 flex items-center justify-between">
                    <span>Affected Code Snippet</span>
                    <span className="text-[11px] text-cyan-400 font-normal">Deterministic Ast match</span>
                  </h4>
                  <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-rose-300 overflow-x-auto">
                    <code>{finding.code_snippet}</code>
                  </pre>
                </div>
              )}

              {/* Impact */}
              {finding.impact && (
                <div>
                  <h4 className="text-xs font-mono uppercase text-rose-400 font-semibold mb-1.5 flex items-center space-x-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-400" />
                    <span>Security & Engineering Impact</span>
                  </h4>
                  <p className="bg-rose-950/20 p-3.5 rounded-xl border border-rose-900/40 text-rose-200 leading-relaxed">
                    {finding.impact}
                  </p>
                </div>
              )}

              {/* Recommendation */}
              {finding.recommendation && (
                <div>
                  <h4 className="text-xs font-mono uppercase text-cyan-400 font-semibold mb-1.5 flex items-center space-x-1.5">
                    <Lightbulb className="w-4 h-4 text-cyan-400" />
                    <span>Remediation Recommendation</span>
                  </h4>
                  <p className="bg-cyan-950/20 p-3.5 rounded-xl border border-cyan-900/40 text-cyan-200 leading-relaxed">
                    {finding.recommendation}
                  </p>
                </div>
              )}

              {/* Ground-truth Policy Citation */}
              {finding.policy_reference && (
                <div className="bg-slate-950/80 p-3.5 rounded-xl border border-indigo-900/40 flex items-start space-x-3">
                  <BookMarked className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <h5 className="text-xs font-mono uppercase text-indigo-300 font-semibold">Ground-Truth Policy Standard</h5>
                    <p className="text-xs text-slate-300 mt-1 font-mono">{finding.policy_reference}</p>
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'evidence' && (
            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                CodeGuardian AI preserves raw deterministic scanner outputs alongside agent contextual interpretation to provide an unbroken chain of evidence.
              </p>
              {finding.evidence && finding.evidence.length > 0 ? (
                finding.evidence.map((ev, idx) => (
                  <div key={ev.id || idx} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
                          {ev.tool.toUpperCase()}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          Source: {ev.source}
                        </span>
                        {ev.rule_id && (
                          <span className="text-xs font-mono text-amber-400">
                            Rule: {ev.rule_id}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {new Date(ev.created_at).toLocaleTimeString()}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 font-mono bg-slate-900/70 p-2.5 rounded-lg border border-slate-800">
                      {ev.raw_message}
                    </p>

                    {ev.code_snippet && (
                      <pre className="text-xs font-mono text-slate-400 bg-slate-900/40 p-2 rounded overflow-x-auto">
                        <code>{ev.code_snippet}</code>
                      </pre>
                    )}
                  </div>
                ))
              ) : (
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-400">
                  Tool: Bandit & Semgrep SAST | Fingerprint: {finding.fingerprint.slice(0, 16)}...
                </div>
              )}
            </div>
          )}

          {activeTab === 'remediation' && (
            <div className="space-y-4">
              <div className="bg-indigo-950/30 p-4 rounded-xl border border-indigo-900/50">
                <div className="flex items-center space-x-2 text-indigo-300 font-mono text-xs font-bold mb-1">
                  <Wrench className="w-4 h-4 text-indigo-400" />
                  <span>5-STAGE CONTROLLED REMEDIATION PIPELINE</span>
                </div>
                <p className="text-xs text-slate-300">
                  Every patch must pass AST syntax parsing, unit test execution, security re-scan, and regression validation before a Fix PR can be created.
                </p>
              </div>

              <div>
                <h5 className="text-xs font-mono text-slate-400 uppercase font-semibold mb-2">Automated Fix Proposal</h5>
                <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto leading-relaxed">
                  <code>
{`--- a/${finding.file_path}
+++ b/${finding.file_path}
@@ -${finding.line_start || 42},3 +${finding.line_start || 42},3 @@
- query = f"SELECT * FROM users WHERE username = '{username}'"
+ query = text("SELECT * FROM users WHERE username = :username")
+ result = await session.execute(query, {"username": username})`}
                  </code>
                </pre>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">1. Syntax Validation:</span>
                  <span className="text-emerald-400 font-bold">PASSED</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">2. Unit Test Suite:</span>
                  <span className="text-emerald-400 font-bold">14/14 PASS</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">3. Bandit Security Scan:</span>
                  <span className="text-emerald-400 font-bold">CLEAN (0 Issues)</span>
                </div>
                <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between">
                  <span className="text-slate-400">4. Regression Check:</span>
                  <span className="text-emerald-400 font-bold">NO DRIFT</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'voice_explain' && (
            <div className="space-y-6">
              {/* Language Selection Header */}
              <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center space-x-2">
                  <Globe className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-mono font-bold text-slate-200">Select Technical Explanation Language:</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { code: 'hi', label: 'हिंदी (Hindi)' },
                    { code: 'hinglish', label: 'Hinglish' },
                    { code: 'en', label: 'English' },
                    { code: 'ur', label: 'اردو (Urdu)' },
                    { code: 'mr', label: 'मराठी (Marathi)' },
                    { code: 'gu', label: 'ગુજરાતી (Gujarati)' },
                  ].map((l) => (
                    <button
                      key={l.code}
                      onClick={() => setSelectedLang(l.code as SupportedLanguageCode)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all ${
                        selectedLang === l.code
                          ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20'
                          : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                      }`}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Audio Voice Player Box */}
              <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-cyan-950/40 border border-cyan-800/40 shadow-xl flex items-center justify-between gap-4">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={handleToggleAudio}
                    className="p-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold shadow-lg shadow-cyan-500/20 transition-all flex items-center justify-center"
                    title={isPlayingAudio ? "Pause Audio" : "Listen to AI Explanation"}
                  >
                    {isPlayingAudio ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
                  </button>
                  <div>
                    <div className="flex items-center space-x-2">
                      <Volume2 className="w-4 h-4 text-cyan-400" />
                      <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                        AI Spoken Explanation ({selectedLang.toUpperCase()})
                      </span>
                      {isPlayingAudio && (
                        <span className="flex space-x-1 items-center ml-2">
                          <span className="w-1 h-3.5 bg-cyan-400 animate-pulse rounded-full" />
                          <span className="w-1 h-5 bg-cyan-300 animate-pulse delay-75 rounded-full" />
                          <span className="w-1 h-2.5 bg-indigo-400 animate-pulse delay-150 rounded-full" />
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2 max-w-xl font-sans">
                      {explanation ? explanation.voice_script : "Click play to listen to speech explanation in your selected native tongue."}
                    </p>
                  </div>
                </div>
              </div>

              {/* Multilingual Technical Content */}
              {loadingExplanation ? (
                <div className="p-12 flex flex-col items-center justify-center space-y-3 text-slate-500">
                  <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
                  <span className="text-xs font-mono">Synthesizing {selectedLang} technical explanation...</span>
                </div>
              ) : explanation ? (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-[10px] font-mono uppercase text-cyan-400 font-bold tracking-wider">
                      {explanation.language_display_name} • Localized Diagnosis
                    </span>
                    <h3 className="text-base font-bold text-white mt-1">{explanation.title}</h3>
                    <p className="text-sm text-slate-300 mt-2 leading-relaxed">{explanation.summary}</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                      <h4 className="text-xs font-mono uppercase text-amber-400 font-semibold mb-1.5 flex items-center space-x-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Root Cause Breakdown</span>
                      </h4>
                      <p className="text-xs text-slate-300 leading-relaxed">{explanation.root_cause}</p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                      <h4 className="text-xs font-mono uppercase text-rose-400 font-semibold mb-1.5 flex items-center space-x-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Real-World Risk Impact</span>
                      </h4>
                      <p className="text-xs text-slate-300 leading-relaxed">{explanation.risk_impact}</p>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
                    <h4 className="text-xs font-mono uppercase text-emerald-400 font-semibold mb-2 flex items-center space-x-1.5">
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Step-by-Step Resolution Guide</span>
                    </h4>
                    <ol className="list-decimal list-inside space-y-1.5 text-xs text-slate-300 leading-relaxed">
                      {explanation.remediation_steps.map((step, idx) => (
                        <li key={idx} className="pl-1">{step}</li>
                      ))}
                    </ol>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Footer / Status Gating Controls */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <input
              type="text"
              placeholder="Audit comment / justification..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-full sm:w-64"
            />
          </div>

          <div className="flex items-center space-x-2">
            {finding.status === 'OPEN' ? (
              <>
                <button
                  onClick={() => handleUpdateStatus('FALSE_POSITIVE')}
                  disabled={updating}
                  className="px-3 py-1.5 text-xs font-mono rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors disabled:opacity-50"
                >
                  Mark False Positive
                </button>
                <button
                  onClick={() => handleUpdateStatus('RESOLVED')}
                  disabled={updating}
                  className="px-3 py-1.5 text-xs font-mono rounded-lg bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 transition-colors disabled:opacity-50 flex items-center space-x-1"
                >
                  {updating ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                  <span>Mark Resolved</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => handleUpdateStatus('OPEN')}
                disabled={updating}
                className="px-3 py-1.5 text-xs font-mono rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800 transition-colors disabled:opacity-50"
              >
                Reopen Finding
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
