import React from 'react';
import { RiskGrade } from '../types';

interface RiskGradeBadgeProps {
  grade?: RiskGrade | string | null;
  score?: number | null;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskGradeBadge: React.FC<RiskGradeBadgeProps> = ({ grade = 'A', score, size = 'md' }) => {
  const g = (grade || 'A').toUpperCase();

  const gradeConfig: Record<string, { label: string; bg: string; text: string; border: string; desc: string }> = {
    A: {
      label: 'GRADE A',
      bg: 'bg-emerald-950/80',
      text: 'text-emerald-400',
      border: 'border-emerald-700/60',
      desc: 'Minimal Risk — Mergeable',
    },
    B: {
      label: 'GRADE B',
      bg: 'bg-cyan-950/80',
      text: 'text-cyan-400',
      border: 'border-cyan-700/60',
      desc: 'Low Risk — Minor Findings',
    },
    C: {
      label: 'GRADE C',
      bg: 'bg-yellow-950/80',
      text: 'text-yellow-400',
      border: 'border-yellow-700/60',
      desc: 'Moderate Risk — Attention Recommended',
    },
    D: {
      label: 'GRADE D',
      bg: 'bg-orange-950/80',
      text: 'text-orange-400',
      border: 'border-orange-700/60',
      desc: 'Elevated Risk — Remediation Required',
    },
    F: {
      label: 'GRADE F',
      bg: 'bg-rose-950/90',
      text: 'text-rose-400',
      border: 'border-rose-700/70',
      desc: 'Critical Risk — Merge BLOCKED',
    },
  };

  const current = gradeConfig[g] || gradeConfig.A;

  if (size === 'sm') {
    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-xs font-bold border ${current.bg} ${current.text} ${current.border}`}
      >
        {g}
        {score !== undefined && score !== null && (
          <span className="ml-1 opacity-80 text-[10px]">({score.toFixed(0)})</span>
        )}
      </span>
    );
  }

  if (size === 'lg') {
    return (
      <div className={`p-4 rounded-xl border ${current.bg} ${current.border} flex items-center justify-between`}>
        <div>
          <div className="flex items-center space-x-2">
            <span className={`text-2xl font-black font-mono ${current.text}`}>{current.label}</span>
            {score !== undefined && score !== null && (
              <span className="text-sm font-mono text-slate-400">Score: {score.toFixed(1)} / 100</span>
            )}
          </div>
          <p className="text-xs text-slate-300 mt-1">{current.desc}</p>
        </div>
      </div>
    );
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-md font-mono text-xs font-semibold border ${current.bg} ${current.text} ${current.border}`}
    >
      {current.label}
      {score !== undefined && score !== null && (
        <span className="ml-1.5 opacity-80 font-normal">({score.toFixed(1)})</span>
      )}
    </span>
  );
};
