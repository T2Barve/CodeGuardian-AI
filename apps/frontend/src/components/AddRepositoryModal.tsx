import React, { useState, useEffect } from 'react';
import {
  X,
  CheckCircle2,
  AlertCircle,
  Copy,
  ExternalLink,
  Github,
  Search,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  Lock,
  Globe,
  Sliders,
} from 'lucide-react';
import { api } from '../services/api';
import {
  GitHubAccessibleRepo,
  RepositoryRead,
  RepositoryValidateResponse,
} from '../types';

interface AddRepositoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (repo: RepositoryRead) => void;
}

export const AddRepositoryModal: React.FC<AddRepositoryModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [step, setStep] = useState<number>(1);
  const [inputMode, setInputMode] = useState<'url' | 'connect' | 'public'>('url');
  
  // Step 1 State
  const [repoUrl, setRepoUrl] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [userRepos, setUserRepos] = useState<GitHubAccessibleRepo[]>([]);
  const [loadingUserRepos, setLoadingUserRepos] = useState(false);
  const [userReposConfigured, setUserReposConfigured] = useState<boolean>(true);
  const [searchFilter, setSearchFilter] = useState('');

  // Step 2 State (Verified Metadata)
  const [verifiedMeta, setVerifiedMeta] = useState<RepositoryValidateResponse | null>(null);

  // Step 3 State (Scope & Permissions)
  const [monitoringMode, setMonitoringMode] = useState<'all' | 'new' | 'manual'>('all');
  const [scanners, setScanners] = useState({
    bandit: true,
    semgrep: true,
    gitleaks: true,
    eslint: true,
  });
  const [autoSyncPrs, setAutoSyncPrs] = useState(true);

  // Step 4 State (Webhook details)
  const [copiedWebhook, setCopiedWebhook] = useState(false);

  // Step 5 State (Onboarding execution)
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdRepo, setCreatedRepo] = useState<RepositoryRead | null>(null);

  // Reset state on modal open/close
  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setValidationError(null);
      setSubmitError(null);
      setCreatedRepo(null);
      if (inputMode === 'connect') {
        loadUserRepos();
      }
    }
  }, [isOpen]);

  const loadUserRepos = async () => {
    setLoadingUserRepos(true);
    try {
      const res = await api.getUserGitHubRepositories();
      setUserReposConfigured(res.configured);
      setUserRepos(res.repositories || []);
    } catch {
      setUserReposConfigured(false);
    } finally {
      setLoadingUserRepos(false);
    }
  };

  if (!isOpen) return null;

  // Real URL validation with backend
  const handleValidateUrl = async (urlToValidate?: string) => {
    const targetUrl = urlToValidate || repoUrl;
    if (!targetUrl.trim()) {
      setValidationError('Please enter a GitHub repository URL.');
      return;
    }

    setIsValidating(true);
    setValidationError(null);

    try {
      const result = await api.validateRepository(targetUrl.trim());
      setVerifiedMeta(result);
      setStep(2);
    } catch (err: any) {
      setValidationError(err.message || 'Validation failed. Verify that the repository exists and is accessible.');
    } finally {
      setIsValidating(false);
    }
  };

  const handleSelectUserRepo = (repo: GitHubAccessibleRepo) => {
    const url = repo.url || `https://github.com/${repo.full_name}`;
    setRepoUrl(url);
    handleValidateUrl(url);
  };

  const handleFinalSubmit = async () => {
    if (!verifiedMeta) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const newRepo = await api.createRepository({
        url: verifiedMeta.url,
        is_active: monitoringMode !== 'manual',
        auto_sync_prs: autoSyncPrs,
        default_branch: verifiedMeta.default_branch,
        language: verifiedMeta.language || undefined,
      });

      setCreatedRepo(newRepo);
      setStep(5);
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to onboard repository.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedWebhook(true);
    setTimeout(() => setCopiedWebhook(false), 2000);
  };

  const webhookFullUrl = `${window.location.origin}/api/v1/github/webhook`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div 
        className="w-full max-w-3xl glass-panel rounded-2xl border border-purple-500/30 overflow-hidden shadow-2xl relative flex flex-col max-h-[92vh]"
        style={{ background: 'linear-gradient(180deg, #120e2e 0%, #090c15 100%)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-purple-500/20 bg-purple-950/20">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-gradient-to-tr from-purple-600 to-pink-500 text-white shadow-lg shadow-purple-600/30">
              <Github className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Onboard GitHub Repository
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  Step {step} of 5
                </span>
              </h2>
              <p className="text-xs text-purple-300/70">
                Continuous DevSecOps, Multi-Agent Review & Automated Sandboxed Fixes
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step Indicator Progress Bar */}
        <div className="grid grid-cols-5 border-b border-purple-500/15 bg-black/40 text-xs">
          {[
            { num: 1, title: 'Repository Input' },
            { num: 2, title: 'Verification' },
            { num: 3, title: 'Scope & Scanners' },
            { num: 4, title: 'Webhook Setup' },
            { num: 5, title: 'Confirmation' },
          ].map((s) => {
            const isActive = step === s.num;
            const isDone = step > s.num;
            return (
              <div
                key={s.num}
                className={`flex items-center justify-center py-2.5 px-2 border-r last:border-r-0 border-purple-500/10 transition-colors ${
                  isActive
                    ? 'bg-purple-900/40 text-pink-400 font-semibold border-b-2 border-b-pink-500'
                    : isDone
                    ? 'bg-purple-950/20 text-emerald-400'
                    : 'text-gray-500'
                }`}
              >
                <span
                  className={`w-4 h-4 rounded-full flex items-center justify-center mr-1.5 text-[10px] ${
                    isDone
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : isActive
                      ? 'bg-pink-500/20 text-pink-400 border border-pink-500/40'
                      : 'bg-gray-800 text-gray-500'
                  }`}
                >
                  {isDone ? '✓' : s.num}
                </span>
                <span className="truncate">{s.title}</span>
              </div>
            );
          })}
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* STEP 1: Repository Input */}
          {step === 1 && (
            <div className="space-y-5 animate-in fade-in duration-150">
              {/* Option Selector Tabs */}
              <div className="grid grid-cols-3 gap-2 p-1 bg-black/50 rounded-xl border border-purple-500/20 text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setInputMode('url')}
                  className={`py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                    inputMode === 'url'
                      ? 'bg-purple-700 text-white shadow-md'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Globe className="w-3.5 h-3.5" />
                  Option B: Paste URL
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setInputMode('connect');
                    loadUserRepos();
                  }}
                  className={`py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                    inputMode === 'connect'
                      ? 'bg-purple-700 text-white shadow-md'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Github className="w-3.5 h-3.5" />
                  Option A: GitHub Account
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setInputMode('public');
                    setRepoUrl('https://github.com/psf/requests');
                  }}
                  className={`py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                    inputMode === 'public'
                      ? 'bg-purple-700 text-white shadow-md'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Option C: Public Read-Only
                </button>
              </div>

              {/* Paste URL Form */}
              {(inputMode === 'url' || inputMode === 'public') && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-purple-200 mb-1.5">
                      GitHub Repository URL
                    </label>
                    <div className="relative">
                      <input
                        type="url"
                        value={repoUrl}
                        onChange={(e) => {
                          setRepoUrl(e.target.value);
                          setValidationError(null);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleValidateUrl();
                          }
                        }}
                        placeholder="https://github.com/owner/repository"
                        className="w-full glass-input px-4 py-3 rounded-xl pl-11 text-sm font-mono text-white placeholder-gray-500 border border-purple-500/30"
                      />
                      <Github className="w-5 h-5 text-purple-400 absolute left-3.5 top-3.5" />
                    </div>
                    <p className="text-[11px] text-gray-400 mt-1.5">
                      Supports formats: <code className="text-purple-300">https://github.com/owner/repo</code> or <code className="text-purple-300">owner/repo</code>
                    </p>
                  </div>

                  {/* Public Quick Presets */}
                  {inputMode === 'public' && (
                    <div className="p-3.5 bg-purple-950/30 rounded-xl border border-purple-500/20 space-y-2">
                      <span className="text-xs font-medium text-purple-300 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-pink-400" />
                        Try with popular open source repositories:
                      </span>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {[
                          'https://github.com/tiangolo/fastapi',
                          'https://github.com/pallets/flask',
                          'https://github.com/psf/requests',
                          'https://github.com/django/django',
                        ].map((preset) => (
                          <button
                            key={preset}
                            type="button"
                            onClick={() => {
                              setRepoUrl(preset);
                              handleValidateUrl(preset);
                            }}
                            className="text-xs px-2.5 py-1 bg-white/5 hover:bg-purple-600/30 border border-purple-500/30 rounded-lg text-purple-200 hover:text-white transition-colors"
                          >
                            {preset.replace('https://github.com/', '')}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* GitHub Account Selection */}
              {inputMode === 'connect' && (
                <div className="space-y-3">
                  {!userReposConfigured ? (
                    <div className="p-4 rounded-xl bg-purple-950/40 border border-purple-500/30 text-xs text-purple-200 space-y-2">
                      <div className="flex items-center gap-2 font-semibold text-pink-300">
                        <AlertCircle className="w-4 h-4" />
                        GitHub Token Not Configured in Environment
                      </div>
                      <p className="text-gray-300">
                        To list personal and organization repositories directly, set <code className="text-purple-300 bg-black/40 px-1 py-0.5 rounded">GITHUB_TOKEN</code> in your backend <code className="text-purple-300 bg-black/40 px-1 py-0.5 rounded">.env</code>.
                      </p>
                      <button
                        type="button"
                        onClick={() => setInputMode('url')}
                        className="mt-2 text-xs text-pink-400 hover:underline font-medium"
                      >
                        Switch to Direct URL Input &rarr;
                      </button>
                    </div>
                  ) : loadingUserRepos ? (
                    <div className="py-8 flex flex-col items-center justify-center space-y-2 text-purple-300">
                      <RefreshCw className="w-6 h-6 animate-spin text-pink-400" />
                      <span className="text-xs">Fetching repositories from GitHub...</span>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="relative">
                        <input
                          type="text"
                          value={searchFilter}
                          onChange={(e) => setSearchFilter(e.target.value)}
                          placeholder="Search your repositories..."
                          className="w-full glass-input px-3 py-2 rounded-lg pl-9 text-xs"
                        />
                        <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                      </div>
                      <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
                        {userRepos
                          .filter((r) =>
                            r.full_name.toLowerCase().includes(searchFilter.toLowerCase())
                          )
                          .map((repo) => (
                            <button
                              key={repo.id || repo.full_name}
                              type="button"
                              onClick={() => handleSelectUserRepo(repo)}
                              className="w-full p-2.5 rounded-lg bg-black/30 hover:bg-purple-900/40 border border-purple-500/10 hover:border-purple-500/30 flex items-center justify-between text-left transition-colors"
                            >
                              <div className="flex items-center space-x-2.5 truncate">
                                {repo.is_private ? (
                                  <Lock className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                                ) : (
                                  <Globe className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                                )}
                                <span className="font-mono text-xs text-white truncate">
                                  {repo.full_name}
                                </span>
                              </div>
                              <span className="text-[11px] text-purple-300/80 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-500/20">
                                {repo.language || 'Code'}
                              </span>
                            </button>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Validation Error Banner */}
              {validationError && (
                <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/40 text-red-300 text-xs flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-400" />
                  <div>
                    <div className="font-semibold">Repository Validation Error</div>
                    <div className="mt-0.5">{validationError}</div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 2: Verification Results */}
          {step === 2 && verifiedMeta && (
            <div className="space-y-5 animate-in fade-in duration-150">
              <div className="p-4 rounded-xl bg-purple-950/30 border border-purple-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-purple-800/40 text-purple-300 border border-purple-500/30">
                      <Github className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white font-mono flex items-center gap-2">
                        {verifiedMeta.full_name}
                        {verifiedMeta.is_private ? (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            Private
                          </span>
                        ) : (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                            Public
                          </span>
                        )}
                      </h3>
                      <p className="text-xs text-purple-300/80 mt-0.5">
                        {verifiedMeta.description || 'No description provided.'}
                      </p>
                    </div>
                  </div>
                  <a
                    href={verifiedMeta.url}
                    target="_blank"
                    rel="noreferrer"
                    className="p-2 text-purple-400 hover:text-white rounded-lg hover:bg-white/10"
                    title="View on GitHub"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>

                <div className="grid grid-cols-4 gap-2.5 pt-2 text-xs border-t border-purple-500/20">
                  <div className="p-2.5 rounded-lg bg-black/40">
                    <span className="text-gray-400 block text-[11px]">Primary Language</span>
                    <span className="font-semibold text-purple-200 mt-0.5 block truncate">
                      {verifiedMeta.language || 'Polyglot'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-black/40">
                    <span className="text-gray-400 block text-[11px]">Default Branch</span>
                    <span className="font-semibold text-purple-200 mt-0.5 block font-mono truncate">
                      {verifiedMeta.default_branch}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-black/40">
                    <span className="text-gray-400 block text-[11px]">Open PRs</span>
                    <span className="font-semibold text-emerald-300 mt-0.5 block font-mono">
                      {verifiedMeta.open_pull_requests_count}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-black/40">
                    <span className="text-gray-400 block text-[11px]">Open Issues</span>
                    <span className="font-semibold text-purple-200 mt-0.5 block font-mono">
                      {verifiedMeta.open_issues_count}
                    </span>
                  </div>
                </div>

                {verifiedMeta.exists_in_database && (
                  <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-500/40 text-amber-300 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>
                      Notice: This repository is already registered in CodeGuardian. Continuing will update its monitoring configuration.
                    </span>
                  </div>
                )}
              </div>

              <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                <span>
                  Repository verified successfully against GitHub. Security checks passed (No SSRF, valid GitHub domain).
                </span>
              </div>
            </div>
          )}

          {/* STEP 3: Scope & Permissions */}
          {step === 3 && (
            <div className="space-y-5 animate-in fade-in duration-150">
              <div>
                <label className="text-xs font-semibold text-purple-200 block mb-2">
                  Pull Request Monitoring Scope
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    {
                      id: 'all',
                      title: 'All Open PRs',
                      desc: 'Automatically evaluate existing and future pull requests',
                    },
                    {
                      id: 'new',
                      title: 'New PRs Only',
                      desc: 'Trigger reviews only for PRs opened after onboarding',
                    },
                    {
                      id: 'manual',
                      title: 'Manual On-Demand',
                      desc: 'Require manual review dispatch via UI or Webhook',
                    },
                  ].map((mode) => (
                    <div
                      key={mode.id}
                      onClick={() => setMonitoringMode(mode.id as any)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                        monitoringMode === mode.id
                          ? 'bg-purple-900/40 border-pink-500 shadow-md shadow-pink-500/10'
                          : 'bg-black/30 border-purple-500/20 hover:border-purple-500/40'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold text-xs text-white">{mode.title}</span>
                        <input
                          type="radio"
                          checked={monitoringMode === mode.id}
                          onChange={() => {}}
                          className="text-pink-500 focus:ring-0"
                        />
                      </div>
                      <p className="text-[11px] text-gray-400">{mode.desc}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-purple-200 block mb-2">
                  Static Analysis Engine Profiles
                </label>
                <div className="grid grid-cols-2 gap-2.5 text-xs">
                  {[
                    { key: 'bandit', name: 'Bandit AST Scanner', desc: 'Python SQLi, command injection, crypto' },
                    { key: 'semgrep', name: 'Semgrep Polyglot SAST', desc: 'OWASP Top 10 rules across JS/TS/Py/Go' },
                    { key: 'gitleaks', name: 'Gitleaks Secret Scanner', desc: 'Entropy & regex secret detection' },
                    { key: 'eslint', name: 'ESLint Security & Quality', desc: 'JS/TS AST danger patterns & bugs' },
                  ].map((scan) => (
                    <label
                      key={scan.key}
                      className="flex items-start space-x-2.5 p-3 rounded-lg bg-black/30 border border-purple-500/20 hover:border-purple-500/30 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={scanners[scan.key as keyof typeof scanners]}
                        onChange={(e) =>
                          setScanners({ ...scanners, [scan.key]: e.target.checked })
                        }
                        className="mt-0.5 rounded border-purple-500/40 text-pink-500 focus:ring-0"
                      />
                      <div>
                        <div className="font-medium text-white">{scan.name}</div>
                        <div className="text-[11px] text-gray-400">{scan.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-purple-950/20 border border-purple-500/20 flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-white">Sync Initial Pull Requests</div>
                  <div className="text-[11px] text-gray-400">
                    Immediately fetch and queue open PRs from GitHub on creation
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={autoSyncPrs}
                  onChange={(e) => setAutoSyncPrs(e.target.checked)}
                  className="rounded border-purple-500/40 text-pink-500 focus:ring-0 w-4 h-4"
                />
              </div>
            </div>
          )}

          {/* STEP 4: Webhook & Polling Configuration */}
          {step === 4 && (
            <div className="space-y-4 animate-in fade-in duration-150">
              <div className="p-4 rounded-xl bg-purple-950/30 border border-purple-500/30 space-y-3">
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-pink-400" />
                  GitHub Webhook Configuration
                </h3>
                <p className="text-xs text-gray-300">
                  To receive real-time pull request review triggers upon push or PR opening, configure this Webhook in your GitHub repository settings under <span className="text-purple-300 font-mono">Settings &rarr; Webhooks &rarr; Add Webhook</span>.
                </p>

                {/* Webhook URL input */}
                <div>
                  <label className="text-[11px] font-semibold text-purple-300 block mb-1">
                    Payload URL
                  </label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      readOnly
                      value={webhookFullUrl}
                      className="w-full glass-input px-3 py-2 rounded-lg text-xs font-mono text-gray-200"
                    />
                    <button
                      type="button"
                      onClick={() => copyToClipboard(webhookFullUrl)}
                      className="px-3 py-2 bg-purple-700 hover:bg-purple-600 rounded-lg text-xs font-medium text-white flex items-center gap-1.5 transition-colors flex-shrink-0"
                    >
                      {copiedWebhook ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
                      {copiedWebhook ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>

                {/* Content Type & Secret */}
                <div className="grid grid-cols-2 gap-3 pt-1 text-xs">
                  <div>
                    <label className="text-[11px] font-semibold text-purple-300 block mb-1">
                      Content type
                    </label>
                    <div className="glass-input px-3 py-2 rounded-lg font-mono text-purple-200">
                      application/json
                    </div>
                  </div>
                  <div>
                    <label className="text-[11px] font-semibold text-purple-300 block mb-1">
                      Events to trigger
                    </label>
                    <div className="glass-input px-3 py-2 rounded-lg font-mono text-purple-200">
                      Pull requests, Pushes
                    </div>
                  </div>
                </div>
              </div>

              {submitError && (
                <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/40 text-red-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}
            </div>
          )}

          {/* STEP 5: Confirmation & Initial Sync Complete */}
          {step === 5 && createdRepo && (
            <div className="py-6 flex flex-col items-center justify-center text-center space-y-4 animate-in fade-in duration-200">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 border-2 border-emerald-500/50 flex items-center justify-center text-emerald-400 shadow-xl shadow-emerald-500/20">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">
                  Repository Successfully Connected!
                </h3>
                <p className="text-xs text-gray-300 max-w-md mx-auto mt-1">
                  <strong className="text-purple-300 font-mono">{createdRepo.owner}/{createdRepo.name}</strong> is now registered for continuous multi-agent code analysis and automated sandboxed remediation.
                </p>
              </div>

              <div className="w-full max-w-md p-4 rounded-xl bg-black/40 border border-purple-500/20 text-left text-xs space-y-2">
                <div className="flex justify-between py-1 border-b border-purple-500/10">
                  <span className="text-gray-400">Monitoring Status:</span>
                  <span className="text-emerald-400 font-semibold">ACTIVE</span>
                </div>
                <div className="flex justify-between py-1 border-b border-purple-500/10">
                  <span className="text-gray-400">Default Branch:</span>
                  <span className="text-white font-mono">{createdRepo.default_branch}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-gray-400">Initial Pull Requests:</span>
                  <span className="text-purple-300 font-medium">Synchronized</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-purple-500/20 bg-purple-950/20">
          {step > 1 && step < 5 ? (
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-300 hover:text-white hover:bg-white/10 transition-colors flex items-center gap-1.5"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
          ) : (
            <div></div>
          )}

          <div className="flex items-center space-x-3">
            {step < 5 && (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
            )}

            {step === 1 && (
              <button
                type="button"
                disabled={isValidating || !repoUrl.trim()}
                onClick={() => handleValidateUrl()}
                className="plasma-btn px-5 py-2.5 rounded-xl text-xs flex items-center gap-2 disabled:opacity-50"
              >
                {isValidating ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Validating URL...
                  </>
                ) : (
                  <>
                    Verify Repository
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            )}

            {step === 2 && (
              <button
                type="button"
                onClick={() => setStep(3)}
                className="plasma-btn px-5 py-2.5 rounded-xl text-xs flex items-center gap-2"
              >
                Configure Monitoring
                <ArrowRight className="w-4 h-4" />
              </button>
            )}

            {step === 3 && (
              <button
                type="button"
                onClick={() => setStep(4)}
                className="plasma-btn px-5 py-2.5 rounded-xl text-xs flex items-center gap-2"
              >
                Webhook Setup
                <ArrowRight className="w-4 h-4" />
              </button>
            )}

            {step === 4 && (
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleFinalSubmit}
                className="plasma-btn px-6 py-2.5 rounded-xl text-xs flex items-center gap-2 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Connecting Repository...
                  </>
                ) : (
                  <>
                    Complete Onboarding
                    <CheckCircle2 className="w-4 h-4" />
                  </>
                )}
              </button>
            )}

            {step === 5 && (
              <button
                type="button"
                onClick={() => {
                  if (createdRepo) onSuccess(createdRepo);
                  onClose();
                }}
                className="plasma-btn px-6 py-2.5 rounded-xl text-xs flex items-center gap-2"
              >
                Go to Repositories & Reviews
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
