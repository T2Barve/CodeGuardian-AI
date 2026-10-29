import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Shield,
  Lock,
  User as UserIcon,
  Mail,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  RefreshCw,
  KeyRound,
} from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register, isAuthenticated } = useAuth();

  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'DEVELOPER' | 'SECURITY_LEAD'>('SECURITY_LEAD');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const destination = (location.state as any)?.from?.pathname || '/';

  // If already authenticated, redirect
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, navigate, destination]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    if (!username.trim() || !password.trim()) {
      setError('Please provide both username and password.');
      return;
    }

    setIsLoading(true);
    try {
      if (mode === 'login') {
        await login({ username: username.trim(), password });
        navigate(destination, { replace: true });
      } else {
        await register({
          username: username.trim(),
          password,
          email: email.trim() || undefined,
          role,
        });
        setSuccessMsg('Account registered successfully! Redirecting to dashboard...');
        setTimeout(() => {
          navigate(destination, { replace: true });
        }, 800);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFillDemo = () => {
    setUsername('admin');
    setPassword('CodeGuardian2026!');
    setMode('login');
    setError(null);
  };

  return (
    <div className="min-h-screen bg-[#07090e] flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background Cosmic Ambient Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-purple-600/15 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-10 right-1/4 w-[400px] h-[400px] bg-pink-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute top-10 left-10 w-[300px] h-[300px] bg-cyan-600/10 rounded-full blur-[100px] pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        {/* Brand Logo & Title */}
        <div className="flex flex-col items-center">
          <div className="relative">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-purple-600 via-pink-500 to-cyan-400 p-0.5 shadow-2xl shadow-purple-600/40 animate-pulse">
              <div className="w-full h-full bg-[#0a0d18] rounded-[14px] flex items-center justify-center">
                <Shield className="w-8 h-8 text-pink-400" />
              </div>
            </div>
          </div>
          <h2 className="mt-4 text-center text-2xl font-extrabold text-white tracking-tight flex items-center gap-2">
            CodeGuardian <span className="text-transparent bg-clip-text bg-gradient-to-r from-pink-400 to-purple-400">AI</span>
          </h2>
          <p className="mt-1 text-center text-xs text-purple-300/80">
            Autonomous Multi-Agent Code Review & DevSecOps Platform
          </p>
        </div>

        {/* Card */}
        <div className="mt-8 glass-panel py-8 px-6 sm:px-10 rounded-2xl border border-purple-500/25 shadow-2xl relative">
          {/* Mode Switcher Tabs */}
          <div className="flex rounded-xl bg-black/40 p-1 mb-6 border border-purple-500/20">
            <button
              type="button"
              onClick={() => {
                setMode('login');
                setError(null);
              }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                mode === 'login'
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode('register');
                setError(null);
              }}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all ${
                mode === 'register'
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Create Account
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-red-950/40 border border-red-500/40 text-red-300 text-xs flex items-start gap-2.5 animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1">{error}</div>
            </div>
          )}

          {/* Success Banner */}
          {successMsg && (
            <div className="mb-5 p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2.5 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <div className="flex-1">{successMsg}</div>
            </div>
          )}

          {/* Auth Form */}
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">
                {mode === 'login' ? 'Username or Email' : 'Username'}
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={mode === 'login' ? 'admin or your username' : 'Choose a unique username'}
                  className="w-full glass-input pl-9 pr-3 py-2 text-xs rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
                />
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Email Address <span className="text-gray-500 font-normal">(optional)</span>
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="user@example.com"
                    className="w-full glass-input pl-9 pr-3 py-2 text-xs rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full glass-input pl-9 pr-3 py-2 text-xs rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
                />
              </div>
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">Platform Role</label>
                <select
                  value={role}
                  onChange={(e: any) => setRole(e.target.value)}
                  className="w-full glass-input px-3 py-2 text-xs rounded-xl text-white focus:outline-none focus:border-pink-500"
                >
                  <option value="SECURITY_LEAD">Security Lead (Full Review & Remediation Approval)</option>
                  <option value="DEVELOPER">Developer (Analysis & Propose Fixes)</option>
                </select>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 plasma-btn py-2.5 px-4 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-pink-300" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>{mode === 'login' ? 'Sign In to Platform' : 'Create Protected Account'}</span>
                  <ArrowRight className="w-4 h-4 text-pink-300" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Credentials Access */}
          <div className="mt-6 pt-5 border-t border-purple-500/20">
            <div className="flex items-center justify-between text-xs text-purple-300/80 mb-2.5">
              <span className="flex items-center gap-1.5 font-medium">
                <KeyRound className="w-3.5 h-3.5 text-pink-400" />
                Default Dev Security Lead
              </span>
              <button
                type="button"
                onClick={handleFillDemo}
                className="text-pink-400 hover:text-pink-300 underline font-semibold flex items-center gap-1"
              >
                <Sparkles className="w-3 h-3" />
                Auto-Fill
              </button>
            </div>
            <div className="p-2.5 rounded-lg bg-black/40 border border-purple-500/15 font-mono text-[11px] text-gray-400 space-y-0.5">
              <div>Username: <span className="text-purple-200">admin</span></div>
              <div>Password: <span className="text-purple-200">CodeGuardian2026!</span></div>
            </div>
          </div>
        </div>

        {/* Security Notice */}
        <p className="mt-4 text-center text-[11px] text-gray-500 font-mono">
          Protected by PBKDF2-HMAC-SHA256 & RFC 7519 Cryptographic Tokens
        </p>
      </div>
    </div>
  );
};
