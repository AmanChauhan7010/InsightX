import React from 'react';
import { X, HelpCircle, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import { InfoTopic } from '../../types';

interface InfoModalProps {
  topic: InfoTopic | null;
  isOpen: boolean;
  onClose: () => void;
}

export const InfoModal: React.FC<InfoModalProps> = ({ topic, isOpen, onClose }) => {
  if (!isOpen || !topic) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-150">
      <div 
        className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden animate-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <HelpCircle className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-900">{topic.title}</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 max-h-[80vh] overflow-y-auto text-sm text-slate-600">
          {/* Section 1 */}
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-800 flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>
              <span>1. What does this mean?</span>
            </h4>
            <p className="text-slate-600 pl-3 leading-relaxed">{topic.whatItMeans}</p>
          </div>

          {/* Section 2 */}
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-800 flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>
              <span>2. How does InsightX calculate or determine it?</span>
            </h4>
            <p className="text-slate-600 pl-3 leading-relaxed">{topic.howCalculated}</p>
          </div>

          {/* Section 3 */}
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-800 flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>
              <span>3. Why is it important?</span>
            </h4>
            <p className="text-slate-600 pl-3 leading-relaxed">{topic.whyImportant}</p>
          </div>

          {/* Section 4 */}
          <div className="p-3.5 rounded-lg bg-amber-50/70 border border-amber-200/80 space-y-1">
            <h4 className="font-semibold text-amber-900 flex items-center space-x-1.5 text-xs uppercase tracking-wider">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
              <span>4. Operational Limitations</span>
            </h4>
            <p className="text-amber-800 text-xs leading-relaxed">{topic.limitations}</p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center space-x-1.5 text-blue-600">
            <ShieldCheck className="w-4 h-4" />
            <span className="font-medium">Deterministic & Evidence-Backed</span>
          </div>
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 bg-white hover:bg-slate-100 text-slate-700 font-medium border border-slate-200 rounded-lg shadow-sm transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
