import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Lock,
  Sparkles,
  Activity,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '../../components/ui/Card';
import { EvidenceBadge } from '../../components/ui/Badge';
import { InfoButton } from '../../components/ui/InfoButton';
import { AnalysisDetail } from '../../types';
import { api } from '../../services/api';

interface EvidenceViewProps {
  analysis: AnalysisDetail;
}

export const EvidenceView: React.FC<EvidenceViewProps> = ({ analysis }) => {
  const [evidenceData, setEvidenceData] = useState<any>(null);
  const [explanationMode, setExplanationMode] = useState<'simple' | 'technical'>('simple');

  useEffect(() => {
    let active = true;
    setEvidenceData(null);
    api.getEvidence(analysis.id)
      .then((data) => {
        if (active) setEvidenceData(data);
      })
      .catch((e) => console.error(e));
    return () => {
      active = false;
    };
  }, [analysis.id]);

  const explanationBundle = analysis.meta_info?.explanation_bundle || {};
  const scoreBreakdown = analysis.meta_info?.score_breakdown || null;
  const checklist = evidenceData?.evidence_checklist || explanationBundle.evidence_checklist || [];
  const uncertainty = evidenceData?.uncertainty_statement || explanationBundle.uncertainty_statement || '';
  const disclaimer = evidenceData?.methodology_disclaimer || explanationBundle.methodology_disclaimer || '';

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header + Segmented Toggle */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Explanations & Forensic Evidence Audit
            </h1>
            <InfoButton topicKey="evidence" />
          </div>
          <p className="text-xs text-slate-500">
            Transparent Explainable AI (XAI) trail distinguishing Static Code, Log, Metrics, Runtime, and Correlated Evidence.
          </p>
        </div>

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

      {/* Primary Narrative Card */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                {explanationMode === 'simple' ? 'Plain-Language Summary' : 'Executive Technical Diagnostic Narrative'}
              </h2>
              <p className="text-[11px] text-slate-500">
                {explanationMode === 'simple'
                  ? 'Clear, everyday summary based on the exact findings detected in your upload'
                  : 'Synthesized multi-stage technical reasoning grounded in empirical evidence'}
              </p>
            </div>
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono">
            Mode: {analysis.mode}
          </span>
        </div>

        {explanationMode === 'simple' ? (
          <div className="space-y-2.5 text-xs text-slate-700 leading-relaxed">
            {analysis.findings.length === 0 && analysis.metric_anomalies.length === 0 && analysis.log_issues.length === 0 ? (
              <p>
                InsightX checked your uploaded files and did not find any problems covered by its enabled checks.
                Your health score is <strong>100/100</strong>.
              </p>
            ) : (
              <>
                <p>
                  InsightX scanned <strong>{analysis.files_count}</strong> file(s) and found{' '}
                  <strong>{analysis.findings.length}</strong> code issue(s),{' '}
                  <strong>{analysis.metric_anomalies.length}</strong> metric anomaly event(s), and{' '}
                  <strong>{analysis.log_issues.length}</strong> log warning/error group(s).
                  The current health score is <strong>{Math.round(analysis.overall_score)}/100</strong>.
                </p>
                {analysis.recommendations.length > 0 && (
                  <p>
                    <strong>Top suggested next step:</strong>{' '}
                    {analysis.recommendations[0].simple_explanation?.what_to_change || analysis.recommendations[0].title}{' '}
                    ({analysis.recommendations[0].simple_explanation?.how_it_helps || analysis.recommendations[0].expected_benefit})
                  </p>
                )}
              </>
            )}
          </div>
        ) : (
          <div className="prose prose-sm max-w-none text-slate-700 text-xs leading-relaxed space-y-3 whitespace-pre-line">
            {analysis.summary || 'Diagnostic evaluation completed successfully.'}
          </div>
        )}
      </Card>

      {/* Transparent Health Score Breakdown */}
      {scoreBreakdown && (
        <Card className="p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-bold text-slate-900">Health Score Calculation Breakdown</h3>
              <InfoButton topicKey="health_score" />
            </div>
            <span className="font-mono text-sm font-bold text-slate-900">
              {Math.round(scoreBreakdown.score)}/100
            </span>
          </div>
          <p className="text-xs text-slate-600">{scoreBreakdown.meaning}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-[10px] text-slate-400 block">BASE SCORE</span>
              <span className="font-semibold text-slate-800">{scoreBreakdown.base_score}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-[10px] text-slate-400 block">TOTAL DEDUCTION</span>
              <span className="font-semibold text-slate-800">-{scoreBreakdown.total_deduction}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-[10px] text-slate-400 block">DUPLICATE DAMPENING</span>
              <span className="font-semibold text-emerald-700">+{scoreBreakdown.duplicate_dampening_saved} saved</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80">
              <span className="text-[10px] text-slate-400 block">SCALE FACTOR</span>
              <span className="font-semibold text-slate-800">{scoreBreakdown.normalization_factor} ({scoreBreakdown.files_analyzed} file)</span>
            </div>
          </div>
        </Card>
      )}

      {/* Uncertainty & Limitations Disclosure */}
      <Card className="p-5 bg-amber-50/50 border-amber-200 space-y-2">
        <div className="flex items-center space-x-2 text-amber-900">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
          <h3 className="text-xs font-bold uppercase tracking-wider">
            Uncertainty & Analytical Assumptions
          </h3>
          <InfoButton topicKey="confidence" />
        </div>
        <p className="text-xs text-amber-800 leading-relaxed">
          {uncertainty || 'All diagnostic conclusions are grounded strictly in the uploaded files. Static Code Evidence does not confirm runtime incidents unless corroborated by execution logs or metrics.'}
        </p>
      </Card>

      {/* Supporting Evidence Checklist Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Empirical Evidence Audit Trail</h3>
              <p className="text-xs text-slate-500">Categorized evidence items supporting findings and hypotheses</p>
            </div>
            <span className="text-xs font-mono text-slate-500">{checklist.length} evidence item(s)</span>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {checklist.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No defect or incident evidence items were recorded for this clean analysis.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-100 text-[10px] text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Evidence Category</th>
                    <th className="px-5 py-3 font-semibold">Artifact / Location</th>
                    <th className="px-5 py-3 font-semibold">Supporting Detail</th>
                    <th className="px-5 py-3 font-semibold text-right">Evidence Basis</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {checklist.map((item: any, idx: number) => {
                    const cat = item.evidence_category || item.type || 'Static Code Evidence';
                    return (
                      <tr key={idx} className="hover:bg-slate-50/60 transition-colors">
                        <td className="px-5 py-3.5 font-medium">
                          <EvidenceBadge category={cat} />
                        </td>
                        <td className="px-5 py-3.5 font-mono text-slate-900 font-medium">
                          {item.label}
                        </td>
                        <td className="px-5 py-3.5 text-slate-600 font-mono text-[11px]">
                          {item.evidence}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          {item.verified ? (
                            <span className="inline-flex items-center space-x-1 text-emerald-700 font-medium text-[11px]">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Observed / Correlated</span>
                            </span>
                          ) : (
                            <span className="text-slate-500 font-medium text-[11px]">
                              Static Inspection
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Methodology Disclaimer Card */}
      <div className="p-4 rounded-xl bg-slate-100 border border-slate-200 text-xs text-slate-600 flex items-start space-x-3">
        <Lock className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="font-semibold text-slate-800 text-[11px] uppercase tracking-wider">
            Integrity Guarantee & Evidence Policy
          </h4>
          <p className="leading-relaxed text-[11px]">
            {disclaimer || 'InsightX derives findings and root causes deterministically from uploaded artifacts without fabricating runtime proof, stack traces, or execution history.'}
          </p>
        </div>
      </div>
    </div>
  );
};
