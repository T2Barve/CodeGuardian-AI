import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  ShieldAlert,
  LayoutDashboard,
  FolderGit2,
  GitPullRequest,
  FileCode2,
  BrainCircuit,
  Cpu,
  BookMarked,
  Wrench,
  FileText,
  Network,
  Settings,
  Zap,
  Plus,
  Menu,
  ChevronDown,
  LogOut,
  User as UserIcon,
} from 'lucide-react';
import { HealthStatus, ReadinessStatus } from '../types';
import { useAuth } from '../context/AuthContext';

interface NavbarProps {
  health: HealthStatus | null;
  readiness: ReadinessStatus | null;
  onOpenAddRepo: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ health, readiness, onOpenAddRepo }) => {
  const location = useLocation();
  const { user, logout, isAuthenticated } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [moreDropdownOpen, setMoreDropdownOpen] = useState(false);

  const primaryNavItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Repositories', path: '/repositories', icon: FolderGit2 },
    { name: 'Pull Requests', path: '/pull-requests', icon: GitPullRequest },
    { name: 'Reviews', path: '/reviews', icon: FileCode2 },
    { name: 'Findings', path: '/findings', icon: ShieldAlert },
    { name: 'AI Agents', path: '/agents', icon: BrainCircuit },
  ];

  const secondaryNavItems = [
    { name: 'Scanner Center', path: '/scanners', icon: Cpu },
    { name: 'Policy Library', path: '/policies', icon: BookMarked },
    { name: 'Remediation & Fix PRs', path: '/remediation', icon: Wrench },
    { name: 'Audit & Reports', path: '/reports', icon: FileText },
    { name: 'Integrations', path: '/integrations', icon: Network },
    { name: 'Optimizer & Voice', path: '/optimizer', icon: Zap },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  const isHealthy = health?.status === 'HEALTHY' || health?.status === 'OK';
  const isDbReady = readiness?.database === 'CONNECTED';

  const isSecondaryActive = secondaryNavItems.some((item) =>
    location.pathname.startsWith(item.path)
  );

  return (
    <header className="sticky top-0 z-40 border-b border-purple-500/20 bg-[#090c15]/85 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-6">
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-pink-600 to-cyan-400 p-[1px] shadow-lg shadow-purple-950/60">
              <div className="w-full h-full bg-[#090c15] rounded-[11px] flex items-center justify-center group-hover:bg-[#13112c] transition-colors">
                <ShieldAlert className="w-5 h-5 text-pink-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-extrabold text-base tracking-tight text-white font-mono">
                  CODEGUARDIAN
                </span>
                <span className="text-[10px] px-1.5 py-0.2 bg-pink-500/20 text-pink-300 border border-pink-500/40 rounded font-mono font-bold">
                  AI
                </span>
              </div>
              <p className="text-[10px] text-purple-300/70 font-mono tracking-wider">
                DEVSECOPS MULTI-AGENT
              </p>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden xl:flex items-center space-x-1">
            {primaryNavItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path);

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-purple-900/40 text-pink-300 border border-purple-500/40 shadow-sm'
                      : 'text-purple-200/80 hover:text-white hover:bg-purple-900/20'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.name}</span>
                </Link>
              );
            })}

            {/* More Engine Tools Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setMoreDropdownOpen(!moreDropdownOpen)}
                className={`flex items-center space-x-1 px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                  isSecondaryActive
                    ? 'bg-purple-900/40 text-pink-300 border border-purple-500/40'
                    : 'text-purple-200/80 hover:text-white hover:bg-purple-900/20'
                }`}
              >
                <span>Platform Hub</span>
                <ChevronDown className="w-3.5 h-3.5" />
              </button>

              {moreDropdownOpen && (
                <div
                  className="absolute left-0 mt-2 w-56 glass-panel rounded-2xl border border-purple-500/30 p-2 shadow-2xl z-50 animate-in fade-in duration-150"
                  onMouseLeave={() => setMoreDropdownOpen(false)}
                >
                  {secondaryNavItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname.startsWith(item.path);
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        onClick={() => setMoreDropdownOpen(false)}
                        className={`flex items-center space-x-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-colors ${
                          isActive
                            ? 'bg-purple-900/50 text-pink-300'
                            : 'text-purple-200/80 hover:text-white hover:bg-purple-900/30'
                        }`}
                      >
                        <Icon className="w-4 h-4 text-purple-400" />
                        <span>{item.name}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>
        </div>

        {/* Right Tools: Add Repo Button & System Status Pill */}
        <div className="flex items-center space-x-3">
          {/* Prominent Add Repository Action */}
          <button
            onClick={onOpenAddRepo}
            className="plasma-btn px-3.5 py-1.5 rounded-xl text-xs flex items-center gap-1.5 shadow-md shadow-pink-900/30"
          >
            <Plus className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Add Repository</span>
          </button>

          {/* System Status Pill */}
          <div className="hidden sm:flex items-center space-x-2 bg-black/40 border border-purple-500/20 px-3 py-1.5 rounded-xl text-xs font-mono">
            <span className="flex h-2 w-2 relative">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isHealthy ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  isHealthy ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
              />
            </span>
            <span className="text-purple-200">
              {isHealthy ? 'Engine Live' : 'Connecting'}
            </span>
            <span className="text-purple-600">|</span>
            <span className="text-purple-400 text-[11px]">
              DB: {isDbReady ? 'Ready' : 'Local'}
            </span>
          </div>
          {/* User Profile Badge & Session Actions */}
          {isAuthenticated && user ? (
            <div className="flex items-center space-x-2 pl-2 border-l border-purple-500/20">
              <div className="hidden lg:flex flex-col items-end text-right">
                <span className="text-xs font-semibold text-white leading-tight font-mono">{user.username}</span>
                <span className="text-[10px] text-pink-300 font-mono tracking-wider">{user.role.replace('_', ' ')}</span>
              </div>
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-pink-500 p-0.5 flex items-center justify-center shadow-md">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.username} className="w-full h-full rounded-[6px] object-cover" />
                ) : (
                  <UserIcon className="w-4 h-4 text-white" />
                )}
              </div>
              <button
                onClick={() => logout()}
                title="Sign Out of CodeGuardian"
                className="p-1.5 rounded-lg text-purple-300 hover:text-pink-300 hover:bg-white/10 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-purple-900/40 text-purple-200 hover:text-white border border-purple-500/30 hover:border-pink-500/50 transition-colors"
            >
              Sign In
            </Link>
          )}

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="xl:hidden p-2 rounded-xl bg-purple-950/40 text-purple-300 hover:text-white border border-purple-500/20"
          >
            <Menu className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="xl:hidden border-t border-purple-500/20 bg-[#090c15] p-4 space-y-2 animate-in fade-in duration-150">
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[...primaryNavItems, ...secondaryNavItems].map((item) => {
              const Icon = item.icon;
              const isActive =
                item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-xl transition-all ${
                    isActive
                      ? 'bg-purple-900/50 text-pink-300 font-semibold'
                      : 'text-purple-200 hover:bg-purple-950/40'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 text-purple-400" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
};
