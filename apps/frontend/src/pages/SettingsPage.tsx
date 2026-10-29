import React, { useState } from 'react';
import {
  Settings,
  Sliders,
  Shield,
  Cpu,
  Save,
  CheckCircle2,
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [saved, setSaved] = useState(false);

  // Engine toggles
  const [enableBandit, setEnableBandit] = useState(true);
  const [enableSemgrep, setEnableSemgrep] = useState(true);
  const [enableGitleaks, setEnableGitleaks] = useState(true);
  const [enableEslint, setEnableEslint] = useState(true);

  // Risk thresholds
  const [criticalCutoff, setCriticalCutoff] = useState(80);
  const [blockMergeOnCritical, setBlockMergeOnCritical] = useState(true);
  const [autoFixPrs, setAutoFixPrs] = useState(true);

  // Voice narration settings
  const [defaultVoiceLang, setDefaultVoiceLang] = useState('en');

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-purple-500/20 pb-5">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-purple-900/40 text-purple-300 border border-purple-500/30">
            <Settings className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Platform & Engine Settings
            </h1>
            <p className="text-xs text-purple-300/70 mt-0.5">
              Tune static analysis engines, risk score merge gates, and multi-agent synthesis behaviors
            </p>
          </div>
        </div>

        {saved && (
          <span className="text-xs font-mono px-3 py-1 bg-emerald-950/60 text-emerald-300 border border-emerald-500/30 rounded-xl flex items-center gap-1.5 animate-in fade-in">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Settings Updated
          </span>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-5">
        {/* Static Analysis Engines */}
        <div className="glass-panel p-5 rounded-2xl border border-purple-500/20 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
            <Sliders className="w-4 h-4 text-pink-400" />
            Static Analysis Scanners
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            {[
              { label: 'Bandit AST Visitor (Python SAST)', checked: enableBandit, set: setEnableBandit },
              { label: 'Semgrep Engine (Polyglot OWASP)', checked: enableSemgrep, set: setEnableSemgrep },
              { label: 'Gitleaks Scanner (Entropy & API Keys)', checked: enableGitleaks, set: setEnableGitleaks },
              { label: 'ESLint Security Rules (JS/TS SAST)', checked: enableEslint, set: setEnableEslint },
            ].map((s) => (
              <label
                key={s.label}
                className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-purple-500/10 cursor-pointer"
              >
                <span className="text-purple-200">{s.label}</span>
                <input
                  type="checkbox"
                  checked={s.checked}
                  onChange={(e) => s.set(e.target.checked)}
                  className="rounded border-purple-500/40 text-pink-500 focus:ring-0 w-4 h-4"
                />
              </label>
            ))}
          </div>
        </div>

        {/* PR Risk Gates & Merge Thresholds */}
        <div className="glass-panel p-5 rounded-2xl border border-purple-500/20 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
            <Shield className="w-4 h-4 text-cyan-400" />
            PR Risk Gates & Merge Policies
          </h3>
          <div className="space-y-4 text-xs">
            <div>
              <div className="flex justify-between mb-1.5 font-mono">
                <span className="text-purple-200">Critical Risk Score Threshold</span>
                <span className="text-pink-400 font-bold">{criticalCutoff} / 100</span>
              </div>
              <input
                type="range"
                min="50"
                max="95"
                value={criticalCutoff}
                onChange={(e) => setCriticalCutoff(Number(e.target.value))}
                className="w-full accent-pink-500 cursor-pointer"
              />
              <p className="text-[11px] text-gray-400 mt-1">
                Pull requests scoring above this threshold receive Risk Grade F and are recommended for block.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
              <label className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-purple-500/10 cursor-pointer">
                <div>
                  <div className="text-white font-medium">Block Merge on Critical Findings</div>
                  <div className="text-[11px] text-gray-400">Mark PR unmergeable if any critical finding is unresolved</div>
                </div>
                <input
                  type="checkbox"
                  checked={blockMergeOnCritical}
                  onChange={(e) => setBlockMergeOnCritical(e.target.checked)}
                  className="rounded border-purple-500/40 text-pink-500 focus:ring-0 w-4 h-4"
                />
              </label>

              <label className="flex items-center justify-between p-3 rounded-xl bg-black/40 border border-purple-500/10 cursor-pointer">
                <div>
                  <div className="text-white font-medium">Enable Sandboxed Fix PR Generation</div>
                  <div className="text-[11px] text-gray-400">Allow 1-click automated fix branch creation</div>
                </div>
                <input
                  type="checkbox"
                  checked={autoFixPrs}
                  onChange={(e) => setAutoFixPrs(e.target.checked)}
                  className="rounded border-purple-500/40 text-pink-500 focus:ring-0 w-4 h-4"
                />
              </label>
            </div>
          </div>
        </div>

        {/* Multilingual Voice Narration Settings */}
        <div className="glass-panel p-5 rounded-2xl border border-purple-500/20 space-y-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
            <Cpu className="w-4 h-4 text-violet-400" />
            AI Voice & Multilingual Preferences
          </h3>
          <div className="text-xs space-y-2">
            <label className="text-purple-200 block font-medium">Default Audio Narration Language</label>
            <div className="glass-input px-3 py-2 rounded-xl border border-purple-500/20 max-w-xs">
              <select
                value={defaultVoiceLang}
                onChange={(e) => setDefaultVoiceLang(e.target.value)}
                className="bg-transparent text-white focus:outline-none w-full text-xs"
              >
                <option value="en" className="bg-[#0f0c24] text-white">English (Default)</option>
                <option value="hi" className="bg-[#0f0c24] text-white">Hindi (हिन्दी)</option>
                <option value="hinglish" className="bg-[#0f0c24] text-white">Hinglish (Colloquial Hindi+English)</option>
                <option value="ur" className="bg-[#0f0c24] text-white">Urdu (اردو)</option>
                <option value="mr" className="bg-[#0f0c24] text-white">Marathi (मराठी)</option>
                <option value="gu" className="bg-[#0f0c24] text-white">Gujarati (ગુજરાતી)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            className="plasma-btn px-6 py-2.5 rounded-xl text-xs flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            Save Preferences
          </button>
        </div>
      </form>
    </div>
  );
};
