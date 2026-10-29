import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  icon: React.ReactNode;
  trend?: string;
  trendType?: 'positive' | 'negative' | 'neutral';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendType = 'neutral',
}) => {
  return (
    <div className="glass-panel rounded-xl p-5 border border-slate-800/80 shadow-md hover:border-slate-700/80 transition-all duration-200">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</span>
        <div className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
          {icon}
        </div>
      </div>
      <div className="flex items-baseline space-x-2">
        <span className="text-2xl font-bold font-mono tracking-tight text-white">{value}</span>
        {trend && (
          <span
            className={`text-xs font-medium ${
              trendType === 'positive'
                ? 'text-emerald-400'
                : trendType === 'negative'
                ? 'text-rose-400'
                : 'text-slate-400'
            }`}
          >
            {trend}
          </span>
        )}
      </div>
      <p className="text-xs text-slate-500 mt-1">{subtitle}</p>
    </div>
  );
};
