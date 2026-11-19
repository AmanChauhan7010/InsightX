import React, { useState, useMemo, useEffect } from 'react';
import {
  Search,
  ChevronRight,
  CheckCircle2,
  Copy,
  Check,
  RotateCcw,
  Activity,
  FileText,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Badge, SeverityBadge, EvidenceBadge } from '../../components/ui/Badge';
import { Card, CardHeader, CardContent } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { InfoButton } from '../../components/ui/InfoButton';
import { AnalysisDetail, Finding } from '../../types';

interface AnalysisResultsProps {
  analysis: AnalysisDetail;
  onNavigateToRecommendations: () => void;
  onNavigateToRootCause: () => void;
}

export const AnalysisResults: React.FC<AnalysisResultsProps> = ({
  analysis,
  onNavigateToRecommendations,
  onNavigateToRootCause,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedFile, setSelectedFile] = useState<string>('all');
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);
  const [copied, setCopied] = useState(false);

  // Clear local filter/modal state whenever active analysis changes
  useEffect(() => {
    setSearchQuery('');
    setSelectedSeverity('all');
    setSelectedCategory('all');
    setSelectedFile('all');
    setActiveFinding(null);
  }, [analysis.id]);

  const categories = useMemo(() => {
    return Array.from(new Set(analysis.findings.map((f) => f.category))).sort();
  }, [analysis.findings]);

  const files = useMemo(() => {
    return Array.from(new Set(analysis.findings.map((f) => f.file_path))).sort();
  }, [analysis.findings]);

  const severityCounts = useMemo(() => {
    const counts = { Critical: 0, High: 0, Medium: 0, Low: 0, Informational: 0 };
    analysis.findings.forEach((f) => {
      if (counts[f.severity] !== undefined) {
        counts[f.severity]++;
      }
    });
    return counts;
  }, [analysis.findings]);

  const filteredFindings = useMemo(() => {
    return analysis.findings.filter((f) => {
      const matchesSearch =
        searchQuery === '' ||
        f.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (f.code_snippet && f.code_snippet.toLowerCase().includes(searchQuery.toLowerCase())) ||
        f.file_path.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesSeverity = selectedSeverity === 'all' || f.severity === selectedSeverity;
      const matchesCategory = selectedCategory === 'all' || f.category === selectedCategory;
      const matchesFile = selectedFile === 'all' || f.file_path === selectedFile;

      return matchesSearch && matchesSeverity && matchesCategory && matchesFile;
    });
  }, [analysis.findings, searchQuery, selectedSeverity, selectedCategory, selectedFile]);

  const hasActiveFilters =
    searchQuery !== '' ||
    selectedSeverity !== 'all' ||
    selectedCategory !== 'all' ||
    selectedFile !== 'all';

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedSeverity('all');
    setSelectedCategory('all');
    setSelectedFile('all');
  };

  const handleCopySnippet = (snippet: string) => {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatLineRange = (finding: Finding): string => {
    if (!finding.line_number) return '';
    if (finding.line_end && finding.line_end > finding.line_number) {
      return `:${finding.line_number}-${finding.line_end}`;
    }
    return `:${finding.line_number}`;
  };

  const formatModalLineLabel = (finding: Finding): string => {
    if (!finding.line_number) return 'Module scope';
    if (finding.line_end && finding.line_end > finding.line_number) {
      return `Lines ${finding.line_number}-${finding.line_end}`;
    }
    return `Line ${finding.line_number}`;
  };

  const scoreMeaning: string | undefined = analysis.meta_info?.score_breakdown?.meaning;
  const metricsSeries: Array<Record<string, any>> = analysis.meta_info?.metrics_series || [];
  const metricsAnalyzed: string[] = (analysis.meta_info?.metrics_analyzed || []).slice(0, 4);
  const metricsIntervals: Array<Record<string, any>> = analysis.meta_info?.metrics_intervals || [];
  const logsLimitation: string | undefined = analysis.meta_info?.logs_limitation;
  const hasTelemetryOrLogs = analysis.metric_anomalies.length > 0 || analysis.log_issues.length > 0 || metricsSeries.length > 0;
  const chartColors = ['#2563EB', '#DC2626', '#D97706', '#059669'];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Failed Analysis Banner */}
      {analysis.status === 'failed' && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs flex items-start space-x-2.5">
          <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Analysis failed to complete</div>
            <p className="mt-0.5 text-red-700">{analysis.error_message || 'An unexpected error occurred during processing.'}</p>
          </div>
        </div>
      )}

      {/* Log Parsing Limitation Notice */}
      {logsLimitation && (
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>{logsLimitation}</span>
        </div>
      )}

      {/* Header Summary & Health Score Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">{analysis.title}</h1>
            <Badge variant="outline" size="sm" className="uppercase font-mono text-[10px]">
              {analysis.mode}
            </Badge>
          </div>
          <div className="flex items-center space-x-4 text-xs text-slate-500 font-mono">
            <span>{analysis.files_count} file(s) analyzed</span>
            <span>•</span>
            <span>{analysis.lines_of_code} total lines of code</span>
            <span>•</span>
            <span>{analysis.findings.length} detected findings</span>
          </div>
          {scoreMeaning && (
            <p className="text-[11px] text-slate-500 pt-0.5">{scoreMeaning}</p>
          )}
        </div>

        {/* Scorecard pill */}
        <div className="flex items-center space-x-4">
          <div className="text-right">
            <div className="flex items-center space-x-1 justify-end text-xs text-slate-500 font-medium">
              <span>Health Score</span>
              <InfoButton topicKey="health_score" />
            </div>
            <div className={`text-2xl font-bold font-mono ${
              analysis.overall_score >= 80 ? 'text-emerald-600' :
              analysis.overall_score >= 60 ? 'text-amber-600' :
              'text-red-600'
            }`}>
              {Math.round(analysis.overall_score)}/100
            </div>
          </div>
          <div className="flex flex-col space-y-1">
            <Button size="sm" onClick={onNavigateToRootCause} className="text-xs">
              Root Causes ({analysis.root_causes.length})
            </Button>
            <Button size="sm" variant="outline" onClick={onNavigateToRecommendations} className="text-xs">
              Remediations ({analysis.recommendations.length})
            </Button>
          </div>
        </div>
      </div>

      {/* Severity Breakdown Bar */}
      <div className="space-y-2">
        <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider px-0.5">
          <span>Severity Distribution</span>
          <InfoButton topicKey="severity" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: 'Critical', count: severityCounts.Critical, color: 'text-red-700 bg-red-50 border-red-200' },
            { label: 'High', count: severityCounts.High, color: 'text-orange-700 bg-orange-50 border-orange-200' },
            { label: 'Medium', count: severityCounts.Medium, color: 'text-amber-700 bg-amber-50 border-amber-200' },
            { label: 'Low', count: severityCounts.Low, color: 'text-blue-700 bg-blue-50 border-blue-200' },
            { label: 'Informational', count: severityCounts.Informational, color: 'text-slate-700 bg-slate-50 border-slate-200' }
          ].map((item) => (
            <div
              key={item.label}
              onClick={() => setSelectedSeverity(selectedSeverity === item.label ? 'all' : item.label)}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${item.color} ${
                selectedSeverity === item.label ? 'ring-2 ring-slate-800' : ''
              }`}
            >
              <div className="text-[11px] font-semibold uppercase">{item.label}</div>
              <div className="text-xl font-bold font-mono mt-1">{item.count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search findings by title, code snippet, or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white rounded-lg border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>

        <div className="flex gap-2">
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="px-3 py-2 bg-white rounded-lg border border-slate-200 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          >
            <option value="all">All Severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
            <option value="Informational">Informational</option>
          </select>

          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-3 py-2 bg-white rounded-lg border border-slate-200 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 max-w-xs"
          >
            <option value="all">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          <select
            value={selectedFile}
            onChange={(e) => setSelectedFile(e.target.value)}
            className="px-3 py-2 bg-white rounded-lg border border-slate-200 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 max-w-xs"
          >
            <option value="all">All Files</option>
            {files.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Findings List or Distinct Empty States */}
      <div className="space-y-3">
        {analysis.findings.length === 0 ? (
          !hasTelemetryOrLogs && analysis.status !== 'failed' ? (
            /* STATE A: No detected findings across all modalities */
            <div className="p-12 text-center bg-white rounded-xl border border-slate-200 space-y-2">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
              <h3 className="font-semibold text-slate-800 text-sm">No issues detected</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                InsightX completed the analysis and found no issues covered by the enabled detection rules.
              </p>
            </div>
          ) : null
        ) : filteredFindings.length === 0 ? (
          /* STATE B: Findings exist but active filters hide them */
          <div className="p-12 text-center bg-white rounded-xl border border-slate-200 space-y-3">
            <Search className="w-7 h-7 text-slate-400 mx-auto" />
            <h3 className="font-semibold text-slate-800 text-sm">No findings match the selected filters.</h3>
            <p className="text-xs text-slate-500">
              {analysis.findings.length} finding(s) exist in this analysis, but none match your current search or filter criteria.
            </p>
            {hasActiveFilters && (
              <Button size="sm" variant="outline" onClick={resetFilters} className="text-xs">
                <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                <span>Reset Filters</span>
              </Button>
            )}
          </div>
        ) : (
          filteredFindings.map((finding) => (
            <div
              key={finding.id}
              onClick={() => setActiveFinding(finding)}
              className="p-4 bg-white rounded-xl border border-slate-200 hover:border-blue-400 hover:shadow-sm transition-all cursor-pointer group"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={finding.severity} />
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                      {finding.category}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      {finding.file_path}{formatLineRange(finding)}
                    </span>
                    <EvidenceBadge category={finding.evidence_category || 'Static Code Evidence'} />
                  </div>

                  <h3 className="text-sm font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                    {finding.title}
                  </h3>

                  <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">
                    {finding.description}
                  </p>

                  {finding.code_snippet && (
                    <div className="pt-1">
                      <code className="text-[11px] font-mono px-2 py-1 rounded bg-slate-900 text-slate-100 block truncate">
                        {finding.code_snippet.split('\n')[0]}
                      </code>
                    </div>
                  )}
                </div>

                <div className="shrink-0 flex items-center self-center text-slate-400 group-hover:text-blue-600 transition-colors">
                  <span className="text-xs font-medium mr-1 hidden sm:inline">Details</span>
                  <ChevronRight className="w-4 h-4" />
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* System Metrics Time-Series Chart & Anomalies (Mode 2 & Mode 3) */}
      {(metricsSeries.length > 0 || analysis.metric_anomalies.length > 0) && (
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-blue-600" />
              <h2 className="text-sm font-bold text-slate-900">System Metrics & Detected Anomalies</h2>
              <InfoButton topicKey="anomaly_detection" />
            </div>
            <div className="flex items-center space-x-2">
              <EvidenceBadge category="Metrics Evidence" />
              <span className="text-xs font-mono text-slate-500">
                {analysis.metric_anomalies.length} anomaly event(s)
              </span>
            </div>
          </div>

          {metricsSeries.length > 0 && metricsAnalyzed.length > 0 && (
            <div className="w-full h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metricsSeries} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="timestamp" tick={{ fontSize: 10, fill: '#64748B' }} minTickGap={24} />
                  <YAxis tick={{ fontSize: 10, fill: '#64748B' }} />
                  <Tooltip contentStyle={{ fontSize: '11px', borderRadius: '8px', borderColor: '#CBD5E1' }} />
                  <Legend wrapperStyle={{ fontSize: '11px' }} />
                  {metricsAnalyzed.map((metricKey, idx) => (
                    <Line
                      key={metricKey}
                      type="monotone"
                      dataKey={metricKey}
                      stroke={chartColors[idx % chartColors.length]}
                      strokeWidth={2}
                      dot={false}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {metricsIntervals.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                Anomalous Intervals
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {metricsIntervals.map((iv, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-slate-800">{iv.metric_name}</div>
                      <div className="text-[11px] text-slate-500">{iv.start} → {iv.end}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-red-600 font-bold">Peak: {iv.peak_value}</div>
                      <div className="text-[10px] text-slate-400">{iv.count} point(s)</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Application Log Issues Panel (Mode 2 & Mode 3) */}
      {analysis.log_issues.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-amber-600" />
                <h2 className="text-sm font-bold text-slate-900">Observed Application Log Events</h2>
              </div>
              <div className="flex items-center space-x-2">
                <EvidenceBadge category="Log Evidence" />
                <span className="text-xs font-mono text-slate-500">
                  {analysis.log_issues.length} issue group(s)
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-100">
              {analysis.log_issues.map((log) => (
                <div key={log.id} className="px-5 py-3 flex items-start justify-between gap-4 text-xs">
                  <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded font-mono text-[10px] font-bold ${
                        log.level === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                        log.level === 'ERROR' ? 'bg-orange-100 text-orange-700' :
                        'bg-amber-100 text-amber-700'
                      }`}>
                        {log.level}
                      </span>
                      {log.service && <span className="font-mono text-[11px] text-slate-500">[{log.service}]</span>}
                      {log.timestamp && <span className="font-mono text-[10px] text-slate-400">{log.timestamp}</span>}
                    </div>
                    <div className="font-mono text-[11px] text-slate-800 break-words">{log.message}</div>
                  </div>
                  <span className="shrink-0 font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                    ×{log.count}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Detailed Finding Modal */}
      {activeFinding && (
        <Modal
          isOpen={!!activeFinding}
          onClose={() => setActiveFinding(null)}
          title={
            <div className="flex items-center space-x-2">
              <SeverityBadge severity={activeFinding.severity} />
              <span className="truncate">{activeFinding.title}</span>
            </div>
          }
          maxWidth="2xl"
        >
          <div className="space-y-5 text-xs text-slate-700">
            {/* Metadata Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 rounded-lg bg-slate-50 border border-slate-200/80 font-mono text-[11px]">
              <div>
                <span className="text-slate-400 block text-[10px]">FILE</span>
                <span className="font-semibold text-slate-800 truncate block">{activeFinding.file_path}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">SOURCE LOCATION</span>
                <span className="font-semibold text-slate-800">
                  {formatModalLineLabel(activeFinding)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">CATEGORY</span>
                <span className="font-semibold text-slate-800 truncate block">{activeFinding.category}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">EVIDENCE TYPE</span>
                <div className="mt-0.5">
                  <EvidenceBadge category={activeFinding.evidence_category || 'Static Code Evidence'} />
                </div>
              </div>
            </div>

            {/* Severity Assignment Rationale */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200/80 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="font-semibold text-slate-900 text-xs uppercase tracking-wider flex items-center space-x-1.5">
                  <span>Severity Rationale ({activeFinding.severity})</span>
                  <InfoButton topicKey="severity" />
                </h4>
                <span className="font-mono text-[10px] text-slate-400">{activeFinding.detection_method}</span>
              </div>
              <p className="text-slate-600 leading-relaxed text-xs">
                {activeFinding.severity_rationale || `Assigned ${activeFinding.severity} based on deterministic static impact policy.`}
              </p>
            </div>

            {/* Description */}
            <div className="space-y-1">
              <h4 className="font-semibold text-slate-900 text-xs uppercase tracking-wider">
                Defect Diagnosis & Context
              </h4>
              <p className="text-slate-600 leading-relaxed text-xs">{activeFinding.description}</p>
            </div>

            {/* Code Snippet with Exact Multi-Line Numbers */}
            {activeFinding.code_snippet && (
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-slate-900 text-xs uppercase tracking-wider">
                    Source Code Context
                  </h4>
                  <button
                    onClick={() => handleCopySnippet(activeFinding.code_snippet || '')}
                    className="inline-flex items-center space-x-1 text-[11px] text-blue-600 hover:text-blue-800"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy Snippet'}</span>
                  </button>
                </div>
                <div className="rounded-lg bg-slate-900 p-3 text-slate-100 font-mono text-xs overflow-x-auto border border-slate-800 space-y-0.5">
                  {activeFinding.code_snippet.split('\n').map((codeLine, idx) => (
                    <div key={idx} className="flex whitespace-pre">
                      <span className="text-slate-500 select-none pr-3 border-r border-slate-700 mr-3 w-8 text-right shrink-0">
                        {(activeFinding.line_number || 1) + idx}
                      </span>
                      <code>{codeLine}</code>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Supporting Evidence */}
            <div className="space-y-1 p-3 rounded-lg bg-blue-50/60 border border-blue-200">
              <h4 className="font-semibold text-blue-900 text-xs uppercase tracking-wider flex items-center space-x-1.5">
                <span>Supporting Evidence</span>
                <InfoButton topicKey="evidence" />
              </h4>
              <p className="text-blue-800 leading-relaxed font-mono text-[11px] whitespace-pre-wrap">
                {activeFinding.evidence}
              </p>
            </div>

            {/* Dedicated Logical Error Verification & Dynamic Output Card */}
            {activeFinding.category === 'Logical Error' && (
              <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-purple-950 text-xs uppercase tracking-wider flex items-center space-x-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                    <span>Automated Test Verification & Dynamic Outputs</span>
                  </h4>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                    activeFinding.is_confirmed
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      : 'bg-amber-100 text-amber-800 border border-amber-300'
                  }`}>
                    {activeFinding.is_confirmed ? 'Confirmed via Test Execution' : 'Suspected Semantic Defect'}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2.5 rounded bg-white border border-purple-100">
                    <span className="text-[10px] font-bold text-slate-400 block uppercase">ACTUAL RUNTIME OUTPUT</span>
                    <span className="text-red-600 font-semibold mt-0.5 block">
                      {activeFinding.evidence.match(/• Actual Output:\s*([^\n]+)/)?.[1] || 'N/A'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-white border border-purple-100">
                    <span className="text-[10px] font-bold text-slate-400 block uppercase">EXPECTED REFERENCE OUTPUT</span>
                    <span className="text-emerald-700 font-semibold mt-0.5 block">
                      {activeFinding.evidence.match(/• Expected Output:\s*([^\n]+)/)?.[1] || 'Reliable specification required'}
                    </span>
                  </div>
                </div>

                {activeFinding.suggested_next_step && (
                  <div className="text-[11px] text-purple-900 bg-white/70 p-2 rounded border border-purple-100">
                    <span className="font-bold">Suggested Correction: </span>
                    <span>{activeFinding.suggested_next_step}</span>
                  </div>
                )}
              </div>
            )}

            {/* Potential Operational Consequences */}
            {activeFinding.potential_consequences && (
              <div className="space-y-1">
                <h4 className="font-semibold text-slate-900 text-xs uppercase tracking-wider">
                  Potential Operational Impact
                </h4>
                <p className="text-slate-600 leading-relaxed">{activeFinding.potential_consequences}</p>
              </div>
            )}

            {/* Suggested Next Step */}
            {activeFinding.suggested_next_step && (
              <div className="space-y-1 p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                <h4 className="font-semibold text-emerald-900 text-xs uppercase tracking-wider flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Suggested Next Step</span>
                </h4>
                <p className="text-emerald-800 text-xs leading-relaxed">{activeFinding.suggested_next_step}</p>
              </div>
            )}

            {/* Modal Actions */}
            <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
              <Button size="sm" variant="outline" onClick={() => setActiveFinding(null)}>
                Close
              </Button>
              <Button
                size="sm"
                onClick={() => {
                  setActiveFinding(null);
                  onNavigateToRecommendations();
                }}
              >
                <span>View Recommended Refactoring</span>
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
