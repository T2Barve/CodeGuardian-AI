import React from 'react';
import { SeverityLevel } from '../types';

interface SeverityBadgeProps {
  severity: SeverityLevel | string;
  count?: number;
  size?: 'sm' | 'md';
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity, count, size = 'sm' }) => {
  const sev = severity.toUpperCase();

  const styles: Record<string, { bg: string; text: string; border: string; dot: string }> = {
    CRITICAL: {
      bg: 'bg-rose-950/70',
      text: 'text-rose-400',
      border: 'border-rose-800/60',
      dot: 'bg-rose-500',
    },
    HIGH: {
      bg: 'bg-amber-950/70',
      text: 'text-amber-400',
      border: 'border-amber-800/60',
      dot: 'bg-amber-500',
    },
    MEDIUM: {
      bg: 'bg-yellow-950/60',
      text: 'text-yellow-400',
      border: 'border-yellow-800/50',
      dot: 'bg-yellow-500',
    },
    LOW: {
      bg: 'bg-blue-950/60',
      text: 'text-blue-400',
      border: 'border-blue-800/50',
      dot: 'bg-blue-500',
    },
    INFO: {
      bg: 'bg-slate-900',
      text: 'text-slate-400',
      border: 'border-slate-800',
      dot: 'bg-slate-500',
    },
  };

  const style = styles[sev] || styles.INFO;
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span
      className={`inline-flex items-center font-mono font-medium rounded-md border ${style.bg} ${style.text} ${style.border} ${padding}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${style.dot}`} />
      {sev}
      {count !== undefined && <span className="ml-1 opacity-80">({count})</span>}
    </span>
  );
};
