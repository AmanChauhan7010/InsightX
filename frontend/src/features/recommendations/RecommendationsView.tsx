import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  Copy,
  Check,
  FileCode,
  CheckSquare,
  Square,
  ChevronDown,
  ChevronUp,
  Play,
  Eye,
  Undo2,
  Download,
  AlertTriangle,
  Sparkles,
  Wrench,
  Edit3,
  History,
  TrendingUp,
  TrendingDown,
  Minus,
  Terminal,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { InfoButton } from '../../components/ui/InfoButton';
import { CodeEditor } from '../../components/ui/CodeEditor';
import {
  AnalysisDetail,
  Recommendation,
  FixPreview,
  FixApplyResult,
  RevisionSummary,
} from '../../types';
import { api } from '../../services/api';

interface RecommendationsViewProps {
  analysis: AnalysisDetail;
  onRefreshAnalysis: () => void;
  onAnalysisUpdated?: (updated: AnalysisDetail, fixResult?: FixApplyResult) => void;
  onSelectAnalysis?: (id: string) => void;
  lastFixResult?: FixApplyResult | null;
  onClearFixResult?: () => void;
}

export const RecommendationsView: React.FC<RecommendationsViewProps> = ({
  analysis,
  onRefreshAnalysis,
  onAnalysisUpdated,
  onSelectAnalysis,
  lastFixResult,
  onClearFixResult,
}) => {
  const [explanationMode, setExplanationMode] = useState<'simple' | 'technical'>('simple');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(
    new Set(analysis.recommendations.map((r) => r.id))
  );

  // Fix preview, apply, manual edit, and updated code viewer state
  const [previewData, setPreviewData] = useState<FixPreview | null>(null);
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [timeoutPolicy, setTimeoutPolicy] = useState<number>(10);
  const [fixError, setFixError] = useState<string | null>(null);

  // Manual edit modal state
  const [manualEditRec, setManualEditRec] = useState<Recommendation | null>(null);
  const [manualFilePath, setManualFilePath] = useState<string>('');
  const [manualCode, setManualCode] = useState<string>('');
  const [manualLanguage, setManualLanguage] = useState<string>('python');
  const [manualSourceHash, setManualSourceHash] = useState<string | undefined>(undefined);
  const [isApplyingManual, setIsApplyingManual] = useState(false);

  // View Updated Code modal state
  const [showUpdatedCodeModal, setShowUpdatedCodeModal] = useState(false);
  const [copiedFixed, setCopiedFixed] = useState(false);

  // Revision history strip
  const [revisions, setRevisions] = useState<RevisionSummary[]>([]);

  useEffect(() => {
    setExpandedIds(new Set(analysis.recommendations.map((r) => r.id)));
    setCopiedId(null);
    setFixError(null);
    setPreviewData(null);
    setManualEditRec(null);

    let active = true;
    api.getRevisions(analysis.id)
      .then((revs) => {
        if (active) setRevisions(revs);
      })
      .catch(() => {
        if (active) setRevisions([]);
      });
    return () => {
      active = false;
    };
  }, [analysis.id, analysis.recommendations]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCopyDiff = (rec: Recommendation) => {
    if (rec.diff || rec.refactored_code) {
      navigator.clipboard?.writeText(rec.diff || rec.refactored_code || '');
      setCopiedId(rec.id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const handleToggleReviewed = async (rec: Recommendation) => {
    try {
      await api.updateRecommendationStatus(analysis.id, rec.id, !rec.reviewed);
      onRefreshAnalysis();
    } catch (e) {
      console.error(e);
    }
  };

  const handlePreviewFix = async (rec: Recommendation, customTimeout?: number) => {
    setFixError(null);
    setPreviewLoadingId(rec.id);
    try {
      const opts = rec.rule_id === 'PY_MISSING_TIMEOUT' ? { timeout_seconds: customTimeout ?? timeoutPolicy } : {};
      const preview = await api.previewFix(analysis.id, rec.id, opts);
      setPreviewData(preview);
    } catch (e: any) {
      setFixError(e.message || 'Unable to generate fix preview.');
    } finally {
      setPreviewLoadingId(null);
    }
  };

  const handleApplyFix = async (recId: string, expectedSourceHash?: string, ruleId?: string) => {
    setFixError(null);
    setApplyingId(recId);
    try {
      const opts = ruleId === 'PY_MISSING_TIMEOUT' ? { timeout_seconds: timeoutPolicy } : {};
      const result = await api.applyFix(analysis.id, {
        recommendation_id: recId,
        expected_source_hash: expectedSourceHash,
        options: opts,
      });
      setPreviewData(null);
      if (onAnalysisUpdated) {
        onAnalysisUpdated(result.analysis, result);
      }
    } catch (e: any) {
      setFixError(e.message || 'Failed to apply fix and re-analyze.');
    } finally {
      setApplyingId(null);
    }
  };

  const handleOpenManualEdit = async (rec: Recommendation) => {
    setFixError(null);
    try {
      const src = await api.getSourceSnapshot(analysis.id);
      const targetPath = rec.file_path && src.files[rec.file_path]
        ? rec.file_path
        : Object.keys(src.files)[0];
      if (!targetPath || !src.files[targetPath]) {
        setFixError('Stored source snapshot is not available for this historical analysis. Re-run the scan to edit code.');
        return;
      }
      setManualFilePath(targetPath);
      setManualCode(src.files[targetPath].content);
      setManualLanguage(src.files[targetPath].language || 'python');
      setManualSourceHash(src.files[targetPath].sha256);
      setManualEditRec(rec);
    } catch (e: any) {
      setFixError(e.message || 'Could not load source code for editing.');
    }
  };

  const handleApplyManualEdit = async () => {
    if (!manualCode.trim()) {
      setFixError('Updated source code cannot be empty.');
      return;
    }
    setIsApplyingManual(true);
    setFixError(null);
    try {
      const result = await api.applyFix(analysis.id, {
        recommendation_id: manualEditRec?.id,
        expected_source_hash: manualSourceHash,
        file_path: manualFilePath,
        custom_code: manualCode,
      });
      setManualEditRec(null);
      if (onAnalysisUpdated) {
        onAnalysisUpdated(result.analysis, result);
      }
    } catch (e: any) {
      setFixError(e.message || 'Failed to re-analyze updated code.');
    } finally {
      setIsApplyingManual(false);
    }
  };

  const handleUndoFix = () => {
    if (analysis.parent_analysis_id && onSelectAnalysis) {
      onClearFixResult?.();
      onSelectAnalysis(analysis.parent_analysis_id);
    }
  };

  const handleCopyFixedCode = () => {
    if (!lastFixResult?.fixed_code) return;
    navigator.clipboard?.writeText(lastFixResult.fixed_code);
    setCopiedFixed(true);
    setTimeout(() => setCopiedFixed(false), 1800);
  };

  const handleDownloadFixedFile = () => {
    if (!lastFixResult?.fixed_code) return;
    const blob = new Blob([lastFixResult.fixed_code], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = lastFixResult.applied_file_path.split('/').pop() || 'fixed_code.py';
    a.click();
    URL.revokeObjectURL(url);
  };

  const priorityColor = (priority: string) => {
    if (priority.includes('P1')) return 'bg-red-50 text-red-700 border-red-200 font-bold';
    if (priority.includes('P2')) return 'bg-orange-50 text-orange-700 border-orange-200 font-semibold';
    if (priority.includes('P3')) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-blue-50 text-blue-700 border-blue-200';
  };

  const activeComparison =
    lastFixResult && lastFixResult.comparison.after_analysis_id === analysis.id
      ? lastFixResult.comparison
      : null;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header + Segmented Simple/Technical Toggle */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Decision Recommendations & Remediation
            </h1>
            {(analysis.revision_number || 1) > 1 && (
              <span className="px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                Revision v{analysis.revision_number}
              </span>
            )}
            <InfoButton topicKey="recommendations" />
          </div>
          <p className="text-xs text-slate-500">
            Preview safe patches, apply fixes to an isolated working copy, and verify real backend re-analysis improvement.
          </p>
        </div>

        {/* Two-Mode Explanation Segmented Toggle */}
        <div
          role="group"
          aria-label="Explanation Mode"
          className="inline-flex rounded-lg bg-slate-100 p-1 border border-slate-200 text-xs self-start md:self-auto"
        >
          <button
            type="button"
            onClick={() => setExplanationMode('simple')}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
              explanationMode === 'simple'
                ? 'bg-white text-blue-700 shadow-sm font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Simple Explanation
          </button>
          <button
            type="button"
            onClick={() => setExplanationMode('technical')}
            className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
              explanationMode === 'technical'
                ? 'bg-white text-blue-700 shadow-sm font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Technical Explanation
          </button>
        </div>
      </div>

      {/* Revision History Bar (when multiple revisions exist) */}
      {revisions.length > 1 && (
        <Card className="p-3.5 bg-slate-50/80 border-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center space-x-2 text-xs font-semibold text-slate-700">
              <History className="w-4 h-4 text-blue-600" />
              <span>Revision History</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {revisions.map((rev) => {
                const isCurrent = rev.id === analysis.id;
                return (
                  <button
                    key={rev.id}
                    type="button"
                    onClick={() => !isCurrent && onSelectAnalysis?.(rev.id)}
                    className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-colors ${
                      isCurrent
                        ? 'bg-blue-600 text-white border-blue-600 font-semibold'
                        : 'bg-white text-slate-700 border-slate-200 hover:border-blue-400'
                    }`}
                    title={rev.applied_recommendation_title || 'Original uploaded code'}
                  >
                    v{rev.revision_number}: {Math.round(rev.overall_score)}/100 ({rev.findings_count} findings)
                  </button>
                );
              })}
            </div>
          </div>
        </Card>
      )}

      {/* Error Feedback Banner */}
      {fixError && (
        <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <span>{fixError}</span>
        </div>
      )}

      {/* Before / After Fix Improvement Card (computed strictly from real backend re-analysis) */}
      {activeComparison && lastFixResult && (
        <Card className={`p-5 space-y-4 border-2 ${
          activeComparison.status === 'improved'
            ? 'border-emerald-300 bg-emerald-50/40'
            : activeComparison.status === 'regressed'
            ? 'border-red-300 bg-red-50/40'
            : 'border-amber-300 bg-amber-50/40'
        }`}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-2.5">
              {activeComparison.status === 'improved' ? (
                <TrendingUp className="w-5 h-5 text-emerald-600" />
              ) : activeComparison.status === 'regressed' ? (
                <TrendingDown className="w-5 h-5 text-red-600" />
              ) : (
                <Minus className="w-5 h-5 text-amber-600" />
              )}
              <div>
                <h2 className="text-sm font-bold text-slate-900">
                  Fix Re-Analysis Result — {lastFixResult.applied_file_path}
                </h2>
                <p className="text-xs text-slate-600">{activeComparison.summary}</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => setShowUpdatedCodeModal(true)} className="text-xs bg-white">
                <Eye className="w-3.5 h-3.5 mr-1" />
                <span>View Fixed Code</span>
              </Button>
              <Button size="sm" variant="outline" onClick={handleCopyFixedCode} className="text-xs bg-white">
                {copiedFixed ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
                <span>{copiedFixed ? 'Copied' : 'Copy Fixed Code'}</span>
              </Button>
              <Button size="sm" variant="outline" onClick={handleDownloadFixedFile} className="text-xs bg-white">
                <Download className="w-3.5 h-3.5 mr-1" />
                <span>Download Fixed Code</span>
              </Button>
              {analysis.parent_analysis_id && (
                <Button size="sm" variant="outline" onClick={handleUndoFix} className="text-xs bg-white text-slate-700">
                  <Undo2 className="w-3.5 h-3.5 mr-1" />
                  <span>Undo Fix</span>
                </Button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <div className="p-3.5 rounded-lg bg-white border border-slate-200 space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">BEFORE FIX</div>
              <div className="text-lg font-bold font-mono text-slate-800">
                {Math.round(activeComparison.before_score)}/100
              </div>
              <div className="text-slate-600 font-mono text-[11px]">
                Findings: {activeComparison.before_findings_count} (Crit: {activeComparison.before_severity_counts.Critical || 0}, High: {activeComparison.before_severity_counts.High || 0})
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-white border border-slate-200 space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">AFTER FIX</div>
              <div className="text-lg font-bold font-mono text-slate-900">
                {Math.round(activeComparison.after_score)}/100
              </div>
              <div className="text-slate-600 font-mono text-[11px]">
                Findings: {activeComparison.after_findings_count} (Crit: {activeComparison.after_severity_counts.Critical || 0}, High: {activeComparison.after_severity_counts.High || 0})
              </div>
            </div>

            <div className="p-3.5 rounded-lg bg-white border border-slate-200 space-y-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">IMPROVEMENT</div>
              <div className={`text-lg font-bold font-mono ${
                activeComparison.score_delta > 0
                  ? 'text-emerald-600'
                  : activeComparison.score_delta < 0
                  ? 'text-red-600'
                  : 'text-slate-700'
              }`}>
                {activeComparison.score_delta > 0 ? '+' : ''}{activeComparison.score_delta} points
              </div>
              <div className="text-slate-600 font-mono text-[11px]">
                Resolved: {activeComparison.resolved_findings.length} • Remaining: {activeComparison.remaining_findings.length}
                {activeComparison.newly_introduced_findings.length > 0 && (
                  <span className="text-red-600 font-semibold"> • New: {activeComparison.newly_introduced_findings.length}</span>
                )}
              </div>
            </div>
          </div>

          {/* Terminal / Console Execution Output */}
          {lastFixResult.execution_output && (
            <div className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono text-xs space-y-2">
              <div className="flex items-center justify-between text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                <span className="flex items-center space-x-1.5 text-emerald-400">
                  <Terminal className="w-3.5 h-3.5" />
                  <span>COMMAND PROMPT / TERMINAL EXECUTION OUTPUT</span>
                </span>
                <span className="text-slate-400 font-normal">
                  $ python3 {lastFixResult.applied_file_path}
                </span>
              </div>
              <div className="bg-black/70 rounded p-2.5 text-emerald-300 font-mono text-xs whitespace-pre-wrap selection:bg-emerald-800 border border-slate-800">
                {lastFixResult.execution_output}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Recommendations List */}
      <div className="space-y-4">
        {analysis.recommendations.length === 0 ? (
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 space-y-3">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
            <h3 className="font-semibold text-slate-800 text-sm">No remediation required</h3>
            <p className="text-xs text-slate-500">
              All inspected code structures and metrics passed the enabled detection rules.
            </p>
            {analysis.parent_analysis_id && !activeComparison && (
              <Button size="sm" variant="outline" onClick={handleUndoFix} className="text-xs">
                <Undo2 className="w-3.5 h-3.5 mr-1.5" />
                <span>View Previous Revision (Undo Fix)</span>
              </Button>
            )}
          </div>
        ) : (
          analysis.recommendations.map((rec) => {
            const isExpanded = expandedIds.has(rec.id);
            const simple = rec.simple_explanation || {};
            const tech = rec.technical_explanation || {};
            const isPython = rec.file_path ? rec.file_path.endsWith('.py') : (!rec.rule_id?.startsWith('JS_') && !rec.rule_id?.startsWith('TS_') && !rec.rule_id?.startsWith('C_'));
            const canAutoFix = Boolean(rec.auto_fixable);

            return (
              <Card key={rec.id} className="overflow-hidden border-slate-200">
                {/* Action Card Header */}
                <div
                  onClick={() => toggleExpand(rec.id)}
                  className="p-5 flex flex-col lg:flex-row lg:items-start justify-between gap-4 cursor-pointer hover:bg-slate-50/50 transition-colors border-b border-slate-100"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs border font-mono ${priorityColor(rec.priority)}`}>
                        {rec.priority}
                      </span>
                      {canAutoFix ? (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 flex items-center space-x-1">
                          <Sparkles className="w-3 h-3" />
                          <span>Auto Fix Ready</span>
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 flex items-center space-x-1">
                          <Wrench className="w-3 h-3" />
                          <span>Auto Fix Unavailable</span>
                        </span>
                      )}
                      {rec.file_path && (
                        <span className="text-xs font-mono text-slate-500 flex items-center space-x-1">
                          <FileCode className="w-3.5 h-3.5 text-blue-500" />
                          <span>{rec.file_path}</span>
                        </span>
                      )}
                      {rec.reviewed && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 flex items-center space-x-1">
                          <Check className="w-3 h-3" />
                          <span>Reviewed</span>
                        </span>
                      )}
                    </div>

                    <h3 className="text-base font-bold text-slate-900">{rec.title}</h3>
                    <p className="text-xs text-slate-600 leading-relaxed">
                      {explanationMode === 'simple'
                        ? simple.what_is_wrong || rec.problem_addressed
                        : tech.problem_description || rec.problem_addressed}
                    </p>
                  </div>

                  {/* Primary Action Controls: [Auto Fix] [Apply Fix] [Preview Fix] [Mark Reviewed] */}
                  <div className="flex flex-wrap items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                    {canAutoFix ? (
                      <>
                        <Button
                          size="sm"
                          onClick={() => handlePreviewFix(rec)}
                          isLoading={previewLoadingId === rec.id || applyingId === rec.id}
                          className="text-xs shadow-sm bg-blue-600 hover:bg-blue-700 text-white"
                        >
                          <Sparkles className="w-3.5 h-3.5 mr-1" />
                          <span>Auto Fix</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleApplyFix(rec.id, undefined, rec.rule_id)}
                          isLoading={applyingId === rec.id}
                          className="text-xs border-emerald-300 text-emerald-800 hover:bg-emerald-50"
                        >
                          <Play className="w-3.5 h-3.5 mr-1 fill-current text-emerald-600" />
                          <span>Apply Fix</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handlePreviewFix(rec)}
                          isLoading={previewLoadingId === rec.id}
                          className="text-xs"
                        >
                          <Eye className="w-3.5 h-3.5 mr-1" />
                          <span>Preview Fix</span>
                        </Button>
                      </>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleOpenManualEdit(rec)}
                        className="text-xs border-amber-300 text-amber-800 hover:bg-amber-50"
                      >
                        <Edit3 className="w-3.5 h-3.5 mr-1" />
                        <span>Edit & Re-analyze</span>
                      </Button>
                    )}

                    <button
                      type="button"
                      onClick={() => handleToggleReviewed(rec)}
                      className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                        rec.reviewed
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                          : 'bg-white text-slate-600 hover:bg-slate-50 border-slate-300'
                      }`}
                      title="Toggle reviewed status"
                    >
                      {rec.reviewed ? (
                        <CheckSquare className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Square className="w-3.5 h-3.5 text-slate-400" />
                      )}
                      <span className="hidden sm:inline">{rec.reviewed ? 'Reviewed' : 'Mark Reviewed'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => toggleExpand(rec.id)}
                      className="text-slate-400 p-1 hover:text-slate-700"
                      aria-label="Toggle recommendation details"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Collapsible Details: Mode-Specific Explanation + Unified Diff */}
                {isExpanded && (
                  <div className="p-5 space-y-5 bg-white text-xs text-slate-700">
                    {!canAutoFix && rec.manual_fix_reason && (
                      <div className="p-3 rounded-lg bg-amber-50/70 border border-amber-200 text-amber-900 text-xs flex items-start space-x-2">
                        <Wrench className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-semibold">Auto Fix Unavailable: </span>
                          <span>{rec.manual_fix_reason}</span>
                        </div>
                      </div>
                    )}

                    {explanationMode === 'simple' ? (
                      /* MODE A: SIMPLE EXPLANATION */
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                        <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                            1. WHAT IS WRONG?
                          </span>
                          <p className="text-slate-800 leading-relaxed">
                            {simple.what_is_wrong || rec.problem_addressed}
                          </p>
                        </div>
                        <div className="p-3.5 rounded-lg bg-amber-50/50 border border-amber-200/80 space-y-1">
                          <span className="text-[10px] font-bold text-amber-900 uppercase tracking-wider block">
                            2. WHY IS IT A PROBLEM?
                          </span>
                          <p className="text-amber-950 leading-relaxed">
                            {simple.why_problem || rec.why_recommended}
                          </p>
                        </div>
                        <div className="p-3.5 rounded-lg bg-blue-50/60 border border-blue-200 space-y-1">
                          <span className="text-[10px] font-bold text-blue-900 uppercase tracking-wider block">
                            3. WHAT SHOULD I CHANGE?
                          </span>
                          <p className="text-blue-950 leading-relaxed">
                            {simple.what_to_change || rec.title}
                          </p>
                        </div>
                        <div className="p-3.5 rounded-lg bg-emerald-50/60 border border-emerald-200 space-y-1">
                          <span className="text-[10px] font-bold text-emerald-900 uppercase tracking-wider block">
                            4. HOW WILL THE CHANGE HELP?
                          </span>
                          <p className="text-emerald-950 leading-relaxed">
                            {simple.how_it_helps || rec.expected_benefit}
                          </p>
                        </div>
                      </div>
                    ) : (
                      /* MODE B: TECHNICAL EXPLANATION */
                      <div className="space-y-3.5">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200/80 font-mono text-[11px]">
                          <div>
                            <span className="text-[10px] text-slate-400 block">CODE LOCATION</span>
                            <span className="font-semibold text-slate-800">{tech.location || rec.file_path || 'Module scope'}</span>
                          </div>
                          <div>
                            <span className="text-[10px] text-slate-400 block">DETECTION METHOD</span>
                            <span className="font-semibold text-slate-800">{tech.detection_method || 'Static AST Analysis'}</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                          <div className="p-3.5 rounded-lg bg-blue-50/60 border border-blue-200 space-y-1">
                            <span className="text-[10px] font-bold text-blue-900 uppercase tracking-wider block">
                              ROOT-CAUSE REASONING
                            </span>
                            <p className="text-blue-950 leading-relaxed">
                              {tech.root_cause_reasoning || rec.why_recommended}
                            </p>
                          </div>

                          <div className="p-3.5 rounded-lg bg-emerald-50/60 border border-emerald-200 space-y-1">
                            <span className="text-[10px] font-bold text-emerald-900 uppercase tracking-wider block">
                              PERFORMANCE / SECURITY IMPACT
                            </span>
                            <p className="text-emerald-950 leading-relaxed">
                              {tech.impact || rec.expected_benefit}
                            </p>
                          </div>
                        </div>

                        {tech.supporting_evidence && (
                          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                              <span>SUPPORTING EVIDENCE</span>
                              <InfoButton topicKey="evidence" />
                            </span>
                            <p className="font-mono text-[11px] text-slate-800">{tech.supporting_evidence}</p>
                          </div>
                        )}

                        {rec.verification_instructions && (
                          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                              VERIFICATION INSTRUCTIONS
                            </span>
                            <p className="text-slate-800 font-mono text-xs leading-relaxed">
                              {tech.verification_instructions || rec.verification_instructions}
                            </p>
                          </div>
                        )}

                        {tech.uncertainty && (
                          <div className="text-[11px] text-slate-500 italic">
                            Uncertainty note: {tech.uncertainty}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Proposed Code Refactoring Diff */}
                    {rec.diff && (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                            PROPOSED CODE CORRECTION (UNIFIED DIFF)
                          </span>
                          <div className="flex items-center space-x-2">
                            {canAutoFix && (
                              <Button
                                size="sm"
                                onClick={() => handleApplyFix(rec.id, undefined, rec.rule_id)}
                                isLoading={applyingId === rec.id}
                                className="text-xs h-7 px-2.5 bg-emerald-600 hover:bg-emerald-700 text-white"
                              >
                                <Play className="w-3 h-3 mr-1 fill-current" />
                                <span>Apply Fix</span>
                              </Button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleCopyDiff(rec)}
                              className="inline-flex items-center space-x-1 text-xs text-blue-600 hover:text-blue-800 font-medium"
                            >
                              {copiedId === rec.id ? (
                                <Check className="w-3.5 h-3.5 text-emerald-600" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                              <span>{copiedId === rec.id ? 'Copied' : 'Copy Diff'}</span>
                            </button>
                          </div>
                        </div>

                        <div className="rounded-xl bg-slate-950 text-slate-100 font-mono text-xs overflow-x-auto border border-slate-800 p-4 leading-relaxed">
                          {rec.diff.split('\n').map((line, idx) => {
                            let lineClass = 'text-slate-300';
                            if (line.startsWith('+') && !line.startsWith('+++')) {
                              lineClass = 'text-emerald-400 bg-emerald-950/40 px-1 rounded block';
                            } else if (line.startsWith('-') && !line.startsWith('---')) {
                              lineClass = 'text-red-400 bg-red-950/40 px-1 rounded block';
                            } else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) {
                              lineClass = 'text-blue-400 font-semibold';
                            }
                            return (
                              <div key={idx} className={lineClass}>
                                {line || ' '}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })
        )}
      </div>

      {/* Modal 1: Fix Preview & Confirmation */}
      {previewData && (
        <Modal
          isOpen={!!previewData}
          onClose={() => setPreviewData(null)}
          title={`Preview Fix: ${previewData.file_path}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between font-mono text-[11px]">
              <span className="font-semibold text-slate-800">{previewData.recommendation_title}</span>
              <span className="text-slate-400">SHA256: {previewData.source_hash.slice(0, 12)}</span>
            </div>

            {previewData.rule_id === 'PY_MISSING_TIMEOUT' && (
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-blue-50/60 border border-blue-200 text-xs">
                <label className="font-medium text-blue-900">Configurable HTTP Timeout Policy (seconds):</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="number"
                    min={1}
                    max={120}
                    value={timeoutPolicy}
                    onChange={(e) => {
                      const val = Math.max(1, Number(e.target.value) || 10);
                      setTimeoutPolicy(val);
                      const rec = analysis.recommendations.find((r) => r.id === previewData.recommendation_id);
                      if (rec) handlePreviewFix(rec, val);
                    }}
                    className="w-20 px-2 py-1 rounded border border-blue-300 bg-white font-mono text-xs text-slate-900"
                  />
                  <span className="text-blue-700 font-mono">sec</span>
                </div>
              </div>
            )}

            {previewData.diff ? (
              <>
                <div className="rounded-xl bg-slate-950 text-slate-100 font-mono text-xs overflow-x-auto max-h-96 border border-slate-800 p-4 leading-relaxed">
                  {previewData.diff.split('\n').map((line, idx) => {
                    let cls = 'text-slate-300';
                    if (line.startsWith('+') && !line.startsWith('+++')) cls = 'text-emerald-400 bg-emerald-950/40 px-1 block';
                    else if (line.startsWith('-') && !line.startsWith('---')) cls = 'text-red-400 bg-red-950/40 px-1 block';
                    else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) cls = 'text-blue-400 font-semibold';
                    return <div key={idx} className={cls}>{line || ' '}</div>;
                  })}
                </div>
                <p className="text-[11px] text-slate-500">
                  Confirming applies this patch to an isolated working copy, preserves Revision v{analysis.revision_number || 1}, and runs a fresh backend static analysis.
                </p>
                <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-200">
                  <Button size="sm" variant="outline" onClick={() => setPreviewData(null)}>Cancel</Button>
                  <Button
                    size="sm"
                    onClick={() => handleApplyFix(previewData.recommendation_id, previewData.source_hash, previewData.rule_id)}
                    isLoading={applyingId === previewData.recommendation_id}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                    <span>Apply Fix & Re-analyze</span>
                  </Button>
                </div>
              </>
            ) : (
              <div className="space-y-3">
                <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
                  <strong>Auto Fix Notice:</strong> {previewData.manual_fix_reason || 'Diagnostic patch ready for execution.'}
                </div>
                <div className="flex justify-end space-x-2">
                  <Button size="sm" variant="outline" onClick={() => setPreviewData(null)}>Close</Button>
                  <Button
                    size="sm"
                    onClick={() => handleApplyFix(previewData.recommendation_id, previewData.source_hash, previewData.rule_id)}
                    isLoading={applyingId === previewData.recommendation_id}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                    <span>Apply Fix & Re-analyze</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const r = analysis.recommendations.find((x) => x.id === previewData.recommendation_id);
                      setPreviewData(null);
                      if (r) handleOpenManualEdit(r);
                    }}
                  >
                    <Wrench className="w-3.5 h-3.5 mr-1" />
                    <span>Open Editor to Apply Fix</span>
                  </Button>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Modal 2: Manual Edit & Re-analyze */}
      {manualEditRec && (
        <Modal
          isOpen={!!manualEditRec}
          onClose={() => setManualEditRec(null)}
          title={`Manual Fix & Re-analyze: ${manualFilePath}`}
          maxWidth="2xl"
        >
          <div className="space-y-4 text-xs">
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
              <div className="font-semibold">{manualEditRec.title}</div>
              <p className="mt-0.5 text-[11px]">{manualEditRec.manual_fix_reason || manualEditRec.why_recommended}</p>
            </div>
            <CodeEditor
              value={manualCode}
              onChange={setManualCode}
              language={manualLanguage}
              minHeightClass="h-80"
              ariaLabel="Manual Fix Source Editor"
            />
            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-200">
              <Button size="sm" variant="outline" onClick={() => setManualEditRec(null)}>Cancel</Button>
              <Button size="sm" onClick={handleApplyManualEdit} isLoading={isApplyingManual}>
                <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                <span>Apply Fix & Re-analyze</span>
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal 3: View Updated Code */}
      {showUpdatedCodeModal && lastFixResult && (
        <Modal
          isOpen={showUpdatedCodeModal}
          onClose={() => setShowUpdatedCodeModal(false)}
          title={`Updated Source Code: ${lastFixResult.applied_file_path}`}
          maxWidth="2xl"
        >
          <div className="space-y-4">
            <CodeEditor
              value={lastFixResult.fixed_code}
              onChange={() => {}}
              language={lastFixResult.applied_file_path.endsWith('.ts') ? 'typescript' : lastFixResult.applied_file_path.endsWith('.js') ? 'javascript' : 'python'}
              readOnly
              minHeightClass="h-72"
              ariaLabel="Updated Fixed Source Code"
            />
            {lastFixResult.execution_output && (
              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-slate-100 font-mono text-xs space-y-1.5">
                <div className="flex items-center justify-between text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                  <span className="flex items-center space-x-1.5 text-emerald-400">
                    <Terminal className="w-3.5 h-3.5" />
                    <span>Program Execution Output (python3 {lastFixResult.applied_file_path}):</span>
                  </span>
                </div>
                <div className="bg-black/70 rounded p-2 text-emerald-300 font-mono text-xs whitespace-pre-wrap">
                  {lastFixResult.execution_output}
                </div>
              </div>
            )}
            <div className="flex items-center justify-end space-x-2">
              <Button size="sm" variant="outline" onClick={handleCopyFixedCode}>
                {copiedFixed ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
                <span>{copiedFixed ? 'Copied' : 'Copy Fixed Code'}</span>
              </Button>
              <Button size="sm" onClick={handleDownloadFixedFile}>
                <Download className="w-3.5 h-3.5 mr-1.5" />
                <span>Download Corrected File</span>
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
