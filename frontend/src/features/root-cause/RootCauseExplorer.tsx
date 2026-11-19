import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  AlertCircle,
  FileCode,
  ArrowRight,
  Network,
  CheckCircle2,
  AlertTriangle,
  Wrench,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { ConfidenceBadge, EvidenceBadge, SeverityBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { InfoButton } from '../../components/ui/InfoButton';
import { AnalysisDetail, RootCause, Relationship } from '../../types';

interface RootCauseExplorerProps {
  analysis: AnalysisDetail;
  onNavigateToRecommendations: () => void;
}

export const RootCauseExplorer: React.FC<RootCauseExplorerProps> = ({
  analysis,
  onNavigateToRecommendations,
}) => {
  const [selectedCause, setSelectedCause] = useState<RootCause | null>(
    analysis.root_causes[0] || null
  );
  const [activeTab, setActiveTab] = useState<'causes' | 'graph'>('causes');

  // Synchronize selectedCause whenever active analysis changes (prevents stale state)
  useEffect(() => {
    setSelectedCause(analysis.root_causes[0] || null);
    setActiveTab('causes');
  }, [analysis.id, analysis.root_causes]);

  const isMultiFile = analysis.files_count > 1 || analysis.relationships.length > 0;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">Root Cause Explorer</h1>
            <InfoButton topicKey="rca_diagnosis" />
          </div>
          <p className="text-xs text-slate-500">
            Ranked causal hypotheses distinguishing static potential causes from runtime-confirmed or telemetry-correlated incidents.
          </p>
        </div>

        {/* View toggle (Ranked Hypotheses vs Relationship Graph) */}
        {isMultiFile && (
          <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-xs">
            <button
              onClick={() => setActiveTab('causes')}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
                activeTab === 'causes' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Ranked Hypotheses
            </button>
            <button
              onClick={() => setActiveTab('graph')}
              className={`px-3 py-1.5 rounded-md font-medium transition-colors flex items-center space-x-1.5 ${
                activeTab === 'graph' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Network className="w-3.5 h-3.5 text-blue-600" />
              <span>Dependency Topology</span>
            </button>
          </div>
        )}
      </div>

      {activeTab === 'causes' ? (
        analysis.root_causes.length === 0 ? (
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
            <h3 className="font-semibold text-slate-800 text-sm">No root causes identified</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              InsightX detected no issues or incident evidence requiring root-cause attribution in this analysis.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Ranked Hypotheses List */}
            <div className="space-y-3">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between px-1">
                <span>Candidate Causes ({analysis.root_causes.length})</span>
                <InfoButton topicKey="confidence" />
              </div>

              {analysis.root_causes.map((cause) => {
                const isSelected = selectedCause?.id === cause.id;
                return (
                  <div
                    key={cause.id}
                    onClick={() => setSelectedCause(cause)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50/60 border-blue-500 shadow-sm ring-1 ring-blue-500'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="w-6 h-6 rounded-full bg-slate-900 text-white font-mono text-xs font-bold flex items-center justify-center shrink-0">
                        #{cause.rank}
                      </span>
                      <div className="flex items-center gap-1.5 flex-wrap justify-end">
                        <ConfidenceBadge confidence={cause.confidence} size="sm" />
                      </div>
                    </div>

                    <h3 className="mt-2 text-sm font-semibold text-slate-900 line-clamp-2">
                      {cause.title}
                    </h3>

                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <EvidenceBadge category={cause.evidence_category || 'Static Code Evidence'} />
                      {cause.cause_type && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                          {cause.cause_type}
                        </span>
                      )}
                    </div>

                    <p className="mt-1.5 text-xs text-slate-600 line-clamp-2 leading-relaxed">
                      {cause.description}
                    </p>

                    {cause.affected_files.length > 0 && (
                      <div className="mt-2 text-[11px] font-mono text-slate-500 truncate">
                        {cause.affected_files.join(', ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Right Column: Deep Hypothesis Details */}
            <div className="lg:col-span-2">
              {selectedCause ? (
                <Card className="p-6 space-y-5">
                  {/* Header */}
                  <div className="space-y-2 pb-4 border-b border-slate-100">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="w-7 h-7 rounded-lg bg-blue-600 text-white font-mono font-bold flex items-center justify-center text-sm shadow-sm shrink-0">
                          #{selectedCause.rank}
                        </span>
                        <h2 className="text-lg font-bold text-slate-900">{selectedCause.title}</h2>
                      </div>
                      <div className="flex items-center gap-2">
                        <EvidenceBadge category={selectedCause.evidence_category || 'Static Code Evidence'} size="md" />
                        <ConfidenceBadge confidence={selectedCause.confidence} size="md" />
                      </div>
                    </div>
                    {selectedCause.cause_type && (
                      <div className="text-[11px] font-medium text-slate-500">
                        Classification: <span className="text-slate-800 font-semibold">{selectedCause.cause_type}</span>
                      </div>
                    )}
                    <div className="pt-1">
                      <h3 className="font-semibold text-[11px] text-slate-500 uppercase tracking-wider mb-1">
                        What Was Detected & Why It Could Happen
                      </h3>
                      <p className="text-xs text-slate-700 leading-relaxed">{selectedCause.description}</p>
                    </div>
                  </div>

                  {/* Evidence Summary */}
                  <div className="space-y-2 p-4 rounded-lg bg-blue-50/60 border border-blue-200">
                    <h3 className="font-semibold text-xs text-blue-900 uppercase tracking-wider flex items-center space-x-1.5">
                      <ShieldCheck className="w-4 h-4 text-blue-600" />
                      <span>Supporting Evidence</span>
                      <InfoButton topicKey="evidence" />
                    </h3>
                    <p className="text-xs text-blue-950 font-mono leading-relaxed">
                      {selectedCause.evidence_summary || 'Supported by static AST code inspection.'}
                    </p>
                  </div>

                  {/* Consequences & Ranking Rationale */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5 p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
                      <h3 className="font-semibold text-[11px] text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Potential Consequences</span>
                      </h3>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {selectedCause.consequences || 'May impact reliability, latency, or correctness under operational load.'}
                      </p>
                    </div>

                    <div className="space-y-1.5 p-3.5 rounded-lg bg-slate-50 border border-slate-200/80">
                      <h3 className="font-semibold text-[11px] text-slate-800 uppercase tracking-wider">
                        Ranking Rationale
                      </h3>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {selectedCause.ranking_rationale || 'Ranked by evidence quality and structural severity.'}
                      </p>
                    </div>
                  </div>

                  {/* Affected Entities */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                        AFFECTED SOURCE FILES
                      </span>
                      <div className="font-mono text-xs text-slate-800 space-y-1">
                        {selectedCause.affected_files.length > 0 ? (
                          selectedCause.affected_files.map((f) => (
                            <div key={f} className="flex items-center space-x-1 truncate">
                              <FileCode className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                              <span className="truncate">{f}</span>
                            </div>
                          ))
                        ) : (
                          <span className="text-slate-400">System telemetry / unmapped</span>
                        )}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                        AFFECTED FUNCTIONS / ENTRYPOINTS
                      </span>
                      <div className="font-mono text-xs text-slate-800 space-y-1">
                        {selectedCause.affected_functions.length > 0 ? (
                          selectedCause.affected_functions.map((fn) => (
                            <div key={fn} className="truncate">{fn}()</div>
                          ))
                        ) : (
                          <span className="text-slate-400">Module-level execution</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Missing Evidence / Uncertainty & Alternative Explanations */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                    <div className="p-3.5 rounded-lg bg-amber-50/70 border border-amber-200/80 space-y-1 text-xs">
                      <h4 className="font-semibold text-amber-900 flex items-center space-x-1 text-[11px] uppercase tracking-wider">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Missing Evidence & Uncertainty</span>
                      </h4>
                      <p className="text-amber-800 leading-relaxed text-[11px]">
                        {selectedCause.missing_evidence || 'No runtime telemetry uploaded to verify production frequency.'}
                      </p>
                    </div>

                    <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1 text-xs">
                      <h4 className="font-semibold text-slate-800 text-[11px] uppercase tracking-wider">
                        Alternative Explanations
                      </h4>
                      <p className="text-slate-600 leading-relaxed text-[11px]">
                        {selectedCause.alternative_explanations || 'External environmental factors may also contribute.'}
                      </p>
                    </div>
                  </div>

                  {/* Recommended Corrective Direction */}
                  {selectedCause.recommended_actions_summary && (
                    <div className="p-3.5 rounded-lg bg-emerald-50/70 border border-emerald-200 space-y-1">
                      <h4 className="font-semibold text-emerald-900 flex items-center space-x-1.5 text-[11px] uppercase tracking-wider">
                        <Wrench className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Corrective Action to Consider</span>
                      </h4>
                      <p className="text-emerald-900 text-xs leading-relaxed">
                        {selectedCause.recommended_actions_summary}
                      </p>
                    </div>
                  )}

                  {/* Linked Source Findings */}
                  {selectedCause.related_finding_ids.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-semibold text-[11px] text-slate-600 uppercase tracking-wider">
                        Linked Findings ({selectedCause.related_finding_ids.length})
                      </h4>
                      <div className="space-y-1.5">
                        {analysis.findings
                          .filter((f) => selectedCause.related_finding_ids.includes(f.id))
                          .map((lf) => (
                            <div
                              key={lf.id}
                              className="p-2.5 rounded-lg bg-slate-50 border border-slate-200/80 flex items-center justify-between gap-3 text-xs"
                            >
                              <div className="flex items-center space-x-2 min-w-0">
                                <SeverityBadge severity={lf.severity} size="sm" />
                                <span className="font-medium text-slate-800 truncate">{lf.title}</span>
                              </div>
                              <span className="font-mono text-[11px] text-slate-500 shrink-0">
                                {lf.file_path}
                                {lf.line_number
                                  ? lf.line_end && lf.line_end > lf.line_number
                                    ? `:${lf.line_number}-${lf.line_end}`
                                    : `:${lf.line_number}`
                                  : ''}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Footer Action */}
                  <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-xs text-slate-500">
                      Linked to {selectedCause.related_finding_ids.length} finding(s) in this analysis.
                    </span>
                    <Button size="sm" onClick={onNavigateToRecommendations}>
                      <span>View Prescribed Action</span>
                      <ArrowRight className="w-4 h-4 ml-1.5" />
                    </Button>
                  </div>
                </Card>
              ) : (
                <div className="p-12 text-center bg-white rounded-xl border border-slate-200 text-xs text-slate-500">
                  Select a root-cause hypothesis to view supporting evidence.
                </div>
              )}
            </div>
          </div>
        )
      ) : (
        /* Visual Call / Dependency Graph */
        <Card className="p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
                <span>Extracted AST Dependency & Call Topology</span>
                <InfoButton topicKey="dependency_graph" />
              </h2>
              <p className="text-xs text-slate-500">
                Directed graph constructed from static imports and function call sites.
              </p>
            </div>
            <span className="text-xs font-mono text-slate-500">
              {analysis.relationships.length} relationship edges
            </span>
          </div>

          <DependencyGraphView relationships={analysis.relationships} />
        </Card>
      )}
    </div>
  );
};

/* Interactive SVG Dependency Graph Component */
const DependencyGraphView: React.FC<{ relationships: Relationship[] }> = ({ relationships }) => {
  if (relationships.length === 0) {
    return (
      <div className="p-12 text-center text-xs text-slate-400">
        No cross-file or cross-module call relationships identified in this analysis.
      </div>
    );
  }

  const nodeSet = new Set<string>();
  relationships.forEach((r) => {
    nodeSet.add(r.source);
    nodeSet.add(r.target);
  });
  const nodes = Array.from(nodeSet);

  const radius = 170;
  const centerX = 360;
  const centerY = 210;

  const nodePositions = nodes.reduce((acc, node, idx) => {
    const angle = (idx / nodes.length) * 2 * Math.PI;
    acc[node] = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
    return acc;
  }, {} as Record<string, { x: number; y: number }>);

  return (
    <div className="border border-slate-200 rounded-xl bg-slate-900 p-4 overflow-hidden relative shadow-inner">
      <div className="absolute top-4 left-4 text-[10px] font-mono text-slate-400 uppercase tracking-wider flex items-center space-x-2">
        <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
        <span>Interactive Blast-Radius Graph</span>
      </div>

      <svg className="w-full h-[420px]" viewBox="0 0 720 420">
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#60A5FA" />
          </marker>
        </defs>

        {relationships.map((rel, i) => {
          const from = nodePositions[rel.source];
          const to = nodePositions[rel.target];
          if (!from || !to) return null;

          return (
            <g key={i}>
              <line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="#3B82F6"
                strokeWidth="1.5"
                strokeOpacity="0.6"
                markerEnd="url(#arrowhead)"
              />
            </g>
          );
        })}

        {nodes.map((node, i) => {
          const pos = nodePositions[node];
          const isFile = node.includes('.py') || node.includes('.js') || node.includes('.ts');

          return (
            <g key={i} className="cursor-pointer group">
              <circle
                cx={pos.x}
                cy={pos.y}
                r={isFile ? 18 : 14}
                className={isFile ? 'fill-blue-600 stroke-blue-300 stroke-2' : 'fill-slate-800 stroke-slate-600 stroke-1'}
              />
              <text
                x={pos.x}
                y={pos.y + 28}
                textAnchor="middle"
                className="fill-slate-200 font-mono text-[10px] select-none"
              >
                {node.length > 20 ? node.slice(-18) : node}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
