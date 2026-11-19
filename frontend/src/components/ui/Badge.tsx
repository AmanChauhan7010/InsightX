import React from 'react';
import { Severity, Confidence } from '../../types';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'critical' | 'high' | 'medium' | 'low' | 'info' | 'success' | 'outline';
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
}) => {
  const base = 'inline-flex items-center font-medium rounded-full transition-colors';
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  const variants = {
    default: 'bg-slate-100 text-slate-700 border border-slate-200',
    critical: 'bg-red-50 text-red-700 border border-red-200 font-semibold',
    high: 'bg-orange-50 text-orange-700 border border-orange-200 font-semibold',
    medium: 'bg-amber-50 text-amber-700 border border-amber-200 font-medium',
    low: 'bg-blue-50 text-blue-700 border border-blue-200',
    info: 'bg-slate-100 text-slate-600 border border-slate-200',
    success: 'bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium',
    outline: 'border border-slate-300 text-slate-700 bg-transparent'
  };

  return (
    <span className={`${base} ${sizeClasses} ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: Severity; size?: 'sm' | 'md' }> = ({ severity, size = 'sm' }) => {
  const map: Record<Severity, 'critical' | 'high' | 'medium' | 'low' | 'info'> = {
    Critical: 'critical',
    High: 'high',
    Medium: 'medium',
    Low: 'low',
    Informational: 'info'
  };
  return <Badge variant={map[severity] || 'info'} size={size}>{severity}</Badge>;
};

export const ConfidenceBadge: React.FC<{ confidence: Confidence; size?: 'sm' | 'md' }> = ({
  confidence,
  size = 'sm'
}) => {
  const variant = confidence === 'High' ? 'success' : confidence === 'Medium' ? 'medium' : 'low';
  return (
    <Badge variant={variant} size={size}>
      <span>{confidence} Confidence</span>
    </Badge>
  );
};

export const EvidenceBadge: React.FC<{ category?: string; size?: 'sm' | 'md' }> = ({
  category = 'Static Code Evidence',
  size = 'sm',
}) => {
  const styleMap: Record<string, string> = {
    'Static Code Evidence': 'bg-slate-100 text-slate-700 border-slate-200',
    'Log Evidence': 'bg-amber-50 text-amber-800 border-amber-200',
    'Metrics Evidence': 'bg-indigo-50 text-indigo-700 border-indigo-200',
    'Runtime Evidence': 'bg-emerald-50 text-emerald-800 border-emerald-200',
    'Correlated Evidence': 'bg-blue-50 text-blue-800 border-blue-200 font-semibold',
  };
  const cls = styleMap[category] || styleMap['Static Code Evidence'];
  const sizeCls = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';
  return (
    <span className={`inline-flex items-center rounded border font-medium ${sizeCls} ${cls}`}>
      {category}
    </span>
  );
};
