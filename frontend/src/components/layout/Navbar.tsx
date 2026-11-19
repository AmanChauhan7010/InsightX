import React, { useEffect, useState } from 'react';
import { Activity, Plus, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from '../ui/Button';
import { api } from '../../services/api';

interface NavbarProps {
  onNewAnalysis: () => void;
  activeAnalysisTitle?: string;
  activeAnalysisScore?: number;
  isDraftMode?: boolean;
  isProcessing?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  onNewAnalysis,
  activeAnalysisTitle,
  activeAnalysisScore,
  isDraftMode = false,
  isProcessing = false,
}) => {
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    api.getHealth()
      .then(() => setIsBackendHealthy(true))
      .catch(() => setIsBackendHealthy(false));
  }, []);

  return (
    <header className="h-16 border-b border-slate-200/80 bg-white/95 backdrop-blur-sm sticky top-0 z-30 px-6 flex items-center justify-between">
      {/* Left: Branding & Current Context */}
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-sm shadow-blue-500/20 font-bold text-lg tracking-tight">
            IX
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-slate-900 tracking-tight text-base">InsightX</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                v2.0
              </span>
            </div>
            <div className="text-[11px] text-slate-500 font-medium">Root Cause & Decision Intelligence</div>
          </div>
        </div>

        {isProcessing ? (
          <div className="hidden md:flex items-center space-x-2 pl-6 border-l border-slate-200 text-xs">
            <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
            <span className="font-semibold text-blue-700">Analyzing Submitted Input...</span>
          </div>
        ) : isDraftMode ? (
          <div className="hidden md:flex items-center space-x-2 pl-6 border-l border-slate-200 text-xs">
            <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-semibold text-[11px]">
              New Analysis Draft
            </span>
            <span className="text-slate-400">Ready for new upload or source code</span>
          </div>
        ) : activeAnalysisTitle ? (
          <div className="hidden md:flex items-center space-x-2.5 pl-6 border-l border-slate-200 text-xs">
            <span className="text-slate-400 font-medium">Selected Analysis:</span>
            <span className="font-semibold text-slate-800 max-w-xs truncate">{activeAnalysisTitle}</span>
            {activeAnalysisScore !== undefined && (
              <span className={`px-2 py-0.5 rounded-full font-semibold text-[11px] ${
                activeAnalysisScore >= 80 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                activeAnalysisScore >= 60 ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                'bg-red-50 text-red-700 border border-red-200'
              }`}>
                Score: {Math.round(activeAnalysisScore)}/100
              </span>
            )}
          </div>
        ) : null}
      </div>

      {/* Right: Status Pill & Actions */}
      <div className="flex items-center space-x-4">
        {/* Backend Connectivity Status */}
        <div className="hidden sm:flex items-center space-x-1.5 text-xs px-2.5 py-1 rounded-full border border-slate-200 bg-slate-50">
          {isBackendHealthy === true ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-slate-600 font-medium">Backend Ready</span>
            </>
          ) : isBackendHealthy === false ? (
            <>
              <AlertCircle className="w-3.5 h-3.5 text-red-500" />
              <span className="text-red-600 font-medium">Backend Disconnected</span>
            </>
          ) : (
            <span className="text-slate-400">Connecting...</span>
          )}
        </div>

        <Button onClick={onNewAnalysis} size="sm" className="shadow-sm">
          <Plus className="w-4 h-4 mr-1.5" />
          <span>New Analysis</span>
        </Button>
      </div>
    </header>
  );
};
