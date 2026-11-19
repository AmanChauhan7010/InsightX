import React from 'react';
import {
  LayoutDashboard,
  PlusCircle,
  FileSearch,
  GitBranch,
  Wrench,
  FileCheck2,
  Archive,
  ExternalLink,
  Shield
} from 'lucide-react';
import { AnalysisDetail } from '../../types';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tabId: string) => void;
  activeAnalysis: AnalysisDetail | null;
  isProcessing?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  activeAnalysis,
  isProcessing = false,
}) => {
  const isDraftMode = currentTab === 'upload';
  const showActiveBadges = !isDraftMode && !isProcessing && !!activeAnalysis;

  const navItems = [
    { id: 'overview', label: 'Overview Dashboard', icon: LayoutDashboard },
    { id: 'upload', label: 'New Analysis', icon: PlusCircle },
    { id: 'findings', label: 'Analysis Results', icon: FileSearch, badge: showActiveBadges ? activeAnalysis?.findings.length : undefined },
    { id: 'root-cause', label: 'Root Cause Explorer', icon: GitBranch, badge: showActiveBadges ? activeAnalysis?.root_causes.length : undefined },
    { id: 'recommendations', label: 'Recommendations', icon: Wrench, badge: showActiveBadges ? activeAnalysis?.recommendations.length : undefined },
    { id: 'evidence', label: 'Explanations & Evidence', icon: FileCheck2 },
    { id: 'reports', label: 'History & Reports', icon: Archive },
  ];

  return (
    <aside className="w-64 border-r border-slate-200/80 bg-white flex flex-col justify-between shrink-0 select-none">
      {/* Navigation Links */}
      <div className="p-4 space-y-1">
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-3 mb-2">
          Investigation Workflow
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-blue-50 text-blue-700 font-semibold border border-blue-100 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span
                  className={`text-[11px] px-2 py-0.5 rounded-full font-mono font-semibold ${
                    isActive ? 'bg-blue-200/80 text-blue-800' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Active Context Card (Explicitly distinguishes Draft vs Processing vs Completed Analysis) */}
      <div className="p-4 border-t border-slate-100">
        {isProcessing ? (
          <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 space-y-1.5 text-xs">
            <div className="flex items-center space-x-2 text-blue-700 font-semibold">
              <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
              <span>Analysis Processing</span>
            </div>
            <div className="text-[11px] text-blue-800">Running AST parsers, RCA & scoring...</div>
          </div>
        ) : isDraftMode ? (
          <div className="p-3 rounded-lg bg-blue-50/60 border border-blue-200/80 space-y-1.5 text-xs">
            <div className="flex items-center justify-between text-blue-700 font-semibold">
              <span>New Analysis Draft</span>
              <span className="uppercase font-mono text-[10px]">DRAFT</span>
            </div>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Preparing a fresh analysis. Previous history remains saved.
            </p>
            {activeAnalysis && (
              <button
                type="button"
                onClick={() => onSelectTab('findings')}
                className="text-[11px] text-blue-600 hover:underline font-medium pt-1 block truncate max-w-full text-left"
              >
                Return to: {activeAnalysis.title}
              </button>
            )}
          </div>
        ) : activeAnalysis ? (
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-2 text-xs">
            <div className="flex items-center justify-between text-slate-500 font-medium">
              <span>Selected Analysis</span>
              <span className="uppercase font-mono text-[10px] text-blue-600 font-bold">
                {activeAnalysis.mode}
                {(activeAnalysis.revision_number || 1) > 1 ? ` · v${activeAnalysis.revision_number}` : ''}
              </span>
            </div>
            <div className="font-semibold text-slate-900 truncate" title={activeAnalysis.title}>
              {activeAnalysis.title}
            </div>
            <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-200/60">
              <span className="text-slate-500">Findings:</span>
              <span className="font-semibold text-slate-800 font-mono">{activeAnalysis.findings.length} found</span>
            </div>
          </div>
        ) : (
          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/60 text-xs text-slate-500 text-center">
            No analysis currently loaded. Click <strong className="text-blue-600 cursor-pointer" onClick={() => onSelectTab('upload')}>New Analysis</strong> to start.
          </div>
        )}

        <div className="mt-3 text-[11px] text-slate-400 flex items-center justify-between px-1">
          <span>InsightX Engine</span>
          <span className="flex items-center space-x-1 text-slate-500">
            <Shield className="w-3 h-3 text-emerald-500" />
            <span>AST + XAI</span>
          </span>
        </div>
      </div>
    </aside>
  );
};
