import React, { useState } from 'react';
import { 
  Zap, 
  Play, 
  Pause, 
  Volume2, 
  Globe, 
  CheckCircle2, 
  ArrowRight, 
  Copy, 
  Check, 
  Code2, 
  Loader2 
} from 'lucide-react';
import { api } from '../services/api';
import { CodeOptimizationResult, SupportedLanguageCode } from '../types';

const SAMPLE_BENCHMARKS = [
  {
    name: 'Nested Loop Search O(N^2)',
    code: `def find_common_items(list1, list2):
    matches = []
    for item1 in list1:
        for item2 in list2:
            if item1 == item2:
                matches.append(item1)
    return matches`,
  },
  {
    name: 'In-Loop String Concat O(N^2)',
    code: `def build_report(items):
    report = ""
    for item in items:
        report += str(item)
    return report`,
  },
  {
    name: 'Inefficient range(len(...))',
    code: `def iterate_items(arr):
    for i in range(len(arr)):
        print(arr[i])`,
  },
];

const LANGUAGES: { code: SupportedLanguageCode; name: string; native: string }[] = [
  { code: 'hi', name: 'Hindi', native: 'हिंदी' },
  { code: 'hinglish', name: 'Hinglish', native: 'Conversational' },
  { code: 'en', name: 'English', native: 'English (US)' },
  { code: 'ur', name: 'Urdu', native: 'اردو' },
  { code: 'mr', name: 'Marathi', native: 'मराठी' },
  { code: 'gu', name: 'Gujarati', native: 'ગુજરાતી' },
];

export const OptimizerPage: React.FC = () => {
  const [code, setCode] = useState(SAMPLE_BENCHMARKS[0].code);
  const [selectedLang, setSelectedLang] = useState<SupportedLanguageCode>('hi');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CodeOptimizationResult | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [copied, setCopied] = useState(false);
  const [audioInstance, setAudioInstance] = useState<HTMLAudioElement | null>(null);

  const handleOptimize = async () => {
    try {
      setLoading(true);
      if (audioInstance) {
        audioInstance.pause();
        setIsPlayingAudio(false);
      }
      const data = await api.optimizeCode(code, 'python', selectedLang);
      setResult(data);
    } catch (err: any) {
      alert(`Optimization failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAudio = () => {
    if (!result) return;

    if (isPlayingAudio && audioInstance) {
      audioInstance.pause();
      setIsPlayingAudio(false);
      return;
    }

    const audioUrl = api.getOptimizationAudioUrl(selectedLang);
    const audio = new Audio(audioUrl);
    setAudioInstance(audio);

    audio.onplay = () => setIsPlayingAudio(true);
    audio.onended = () => setIsPlayingAudio(false);
    audio.onerror = () => {
      setIsPlayingAudio(false);
      // Fallback to browser Web Speech API
      if ('speechSynthesis' in window && result.voice_script) {
        const utter = new SpeechSynthesisUtterance(result.voice_script);
        utter.lang = selectedLang === 'hi' || selectedLang === 'hinglish' ? 'hi-IN' : 'en-US';
        utter.onend = () => setIsPlayingAudio(false);
        setIsPlayingAudio(true);
        window.speechSynthesis.speak(utter);
      }
    };

    audio.play().catch(() => {
      // Browser autoplay restriction fallback to Web Speech API
      if ('speechSynthesis' in window && result.voice_script) {
        const utter = new SpeechSynthesisUtterance(result.voice_script);
        utter.onend = () => setIsPlayingAudio(false);
        setIsPlayingAudio(true);
        window.speechSynthesis.speak(utter);
      }
    });
  };

  const handleCopyCode = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.optimized_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-tr from-cyan-600 to-indigo-600 shadow-lg shadow-cyan-950/40">
              <Zap className="w-6 h-6 text-cyan-200" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight flex items-center space-x-2">
                <span>NLP Code Optimization & Complexity Studio</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/60 font-mono">
                  O(N^2) → O(N)
                </span>
              </h1>
              <p className="text-sm text-slate-400 mt-1">
                Static AST algorithmic analysis, complexity reduction, and multi-lingual voice explanations.
              </p>
            </div>
          </div>
        </div>

        {/* Language Selector */}
        <div className="flex items-center space-x-2 bg-slate-900 p-1.5 rounded-xl border border-slate-800">
          <Globe className="w-4 h-4 text-cyan-400 ml-2" />
          <div className="flex flex-wrap gap-1">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => setSelectedLang(lang.code)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all ${
                  selectedLang === lang.code
                    ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {lang.name} <span className="opacity-70 text-[10px]">({lang.native})</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Preset Benchmarks */}
      <div className="flex items-center space-x-3 text-xs text-slate-400">
        <span className="font-mono text-slate-500 uppercase tracking-wider">Load Benchmark:</span>
        {SAMPLE_BENCHMARKS.map((b) => (
          <button
            key={b.name}
            onClick={() => {
              setCode(b.code);
              setResult(null);
            }}
            className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-slate-700 font-mono transition-colors"
          >
            {b.name}
          </button>
        ))}
      </div>

      {/* Main Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Code Editor */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden flex flex-col bg-slate-900/60">
          <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Code2 className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                Original Code (Input)
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">Python 3.12+ AST</span>
          </div>
          <div className="p-4 flex-1 flex flex-col">
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              rows={14}
              className="w-full flex-1 p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition-colors resize-none leading-relaxed"
              placeholder="Paste Python code with loops or calculations..."
            />
            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs font-mono text-slate-500">
                {code.split('\n').length} lines • {code.length} chars
              </span>
              <button
                onClick={handleOptimize}
                disabled={loading || !code.trim()}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-slate-950 font-bold text-xs font-mono tracking-wide shadow-lg shadow-cyan-950/50 flex items-center space-x-2 transition-all disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4 fill-current" />}
                <span>{loading ? 'Optimizing AST...' : 'Optimize & Analyze Complexity'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Optimized Output / Results */}
        <div className="glass-panel rounded-2xl border border-slate-800 overflow-hidden flex flex-col bg-slate-900/60">
          <div className="p-4 border-b border-slate-800 bg-slate-950/60 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                Optimized Replacement (Output)
              </span>
            </div>
            {result && (
              <button
                onClick={handleCopyCode}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-300 flex items-center space-x-1 transition-colors"
              >
                {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-slate-400" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            )}
          </div>

          <div className="p-4 flex-1 flex flex-col">
            {result ? (
              <div className="space-y-4 flex-1 flex flex-col">
                {/* Complexity Delta Bar */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">Time Complexity</span>
                    <div className="flex items-center space-x-2 mt-1">
                      <span className="text-xs font-mono text-rose-400 line-through">{result.original_time_complexity}</span>
                      <ArrowRight className="w-3 h-3 text-slate-500" />
                      <span className="text-xs font-mono text-emerald-400 font-bold">{result.optimized_time_complexity}</span>
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">Performance Gain</span>
                    <span className="text-xs font-mono text-cyan-400 font-bold mt-1 block">
                      {result.performance_improvement_factor}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 col-span-2 sm:col-span-1">
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">AST Syntax Check</span>
                    <span className="text-xs font-mono text-emerald-400 font-bold mt-1 flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{result.syntax_valid ? 'Valid & Verified' : 'Syntax Check Failed'}</span>
                    </span>
                  </div>
                </div>

                {/* Code Window */}
                <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto flex-1 leading-relaxed">
                  <code>{result.optimized_code}</code>
                </pre>

                {/* AI Audio Player Bar */}
                <div className="p-3 rounded-xl bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950/50 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={handleToggleAudio}
                      className="p-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold transition-all shadow-md shadow-cyan-500/20"
                    >
                      {isPlayingAudio ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
                    </button>
                    <div>
                      <div className="flex items-center space-x-2">
                        <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
                        <span className="text-xs font-mono font-bold text-white">
                          AI Voice Narration ({selectedLang.toUpperCase()})
                        </span>
                        {isPlayingAudio && (
                          <span className="flex space-x-0.5 items-center">
                            <span className="w-1 h-3 bg-cyan-400 animate-pulse rounded-full" />
                            <span className="w-1 h-4 bg-cyan-300 animate-pulse delay-75 rounded-full" />
                            <span className="w-1 h-2 bg-indigo-400 animate-pulse delay-150 rounded-full" />
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-1 max-w-md mt-0.5">
                        {result.voice_script}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-3 text-slate-500">
                <Code2 className="w-12 h-12 text-slate-700" />
                <p className="text-sm">Click "Optimize & Analyze Complexity" to run AST complexity reduction.</p>
                <p className="text-xs text-slate-600 font-mono">
                  Identifies nested quadratic loops, string allocations, and linear scans.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Multilingual Explanation Card */}
      {result && (
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Globe className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-bold text-white tracking-tight">
                Multilingual Optimization Explanation ({LANGUAGES.find((l) => l.code === selectedLang)?.native})
              </h3>
            </div>
            <span className="text-xs font-mono text-cyan-400">
              {LANGUAGES.find((l) => l.code === selectedLang)?.name}
            </span>
          </div>
          <p className="text-sm text-slate-300 bg-slate-950/60 p-4 rounded-xl border border-slate-800 leading-relaxed font-sans">
            {result.multilingual_explanations[selectedLang] || result.explanation}
          </p>
        </div>
      )}
    </div>
  );
};
