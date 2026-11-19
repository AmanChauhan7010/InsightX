import React, { useEffect, useState, useMemo } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FileCode2,
  FolderGit2,
  ArrowRight,
  Sparkles,
  History,
  FileText,
  Search,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  GitCompare,
  Archive,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { InfoButton } from '../../components/ui/InfoButton';
import { AnalysisSummary, SampleCase, FixComparison } from '../../types';
import { api } from '../../services/api';

interface OverviewDashboardProps {
  onSelectAnalysis: (id: string) => void;
  onOpenReport?: (id: string) => void;
  onNewAnalysis: () => void;
  onViewAllHistory: () => void;
  onLoadSample: (caseId: string) => Promise<void>;
  isLoadingSample: boolean;
  refreshSignal?: number;
}

const MODE_LABELS: Record<string, string> = {
  code: 'Source Code',
  metrics_logs: 'Logs / Metrics',
  combined: 'Combined',
};

const PAGE_SIZE = 8;

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  onSelectAnalysis,
  onOpenReport,
  onNewAnalysis,
  onViewAllHistory,
  onLoadSample,
  isLoadingSample,
  refreshSignal = 0,
}) => {
  const [allAnalyses, setAllAnalyses] = useState<AnalysisSummary[]>([]);
  const [recentDiagnoses, setRecentDiagnoses] = useState<AnalysisSummary[]>([]);
  const [sampleCases, setSampleCases] = useState<SampleCase[]>([]);
  const [loading, setLoading] = useState(true);

  // Full Analysis History controls
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'code' | 'metrics_logs' | 'combined'>('all');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [currentPage, setCurrentPage] = useState(1);

  // Revision comparison modal
  const [comparingTitle, setComparingTitle] = useState<string>('');
  const [comparisonData, setComparisonData] = useState<FixComparison | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    // Use Promise.allSettled so a single auxiliary endpoint failure never blanks out persisted history
    Promise.allSettled([
      api.listAnalyses(100),
      api.listRecentAnalyses(5),
      api.listSampleCases(),
    ])
      .then(([fullRes, recentRes, casesRes]) => {
        if (!active) return;
        const fullList = fullRes.status === 'fulfilled' ? fullRes.value : [];
        const recentList =
          recentRes.status === 'fulfilled'
            ? recentRes.value
            : fullList.slice(0, 5);
        const cases = casesRes.status === 'fulfilled' ? casesRes.value : [];

        setAllAnalyses(fullList);
        setRecentDiagnoses(recentList.slice(0, 5));
        setSampleCases(cases);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [refreshSignal]);

  // Reset pagination when filters or search change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, typeFilter, sortOrder]);

  const getFindingsTotal = (a: AnalysisSummary): number =>
    a.findings_count !== undefined
      ? a.findings_count
      : a.critical_count + a.high_count + a.medium_count + a.low_count + a.info_count;

  // Filtered & sorted full history
  const filteredHistory = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const list = allAnalyses.filter((a) => {
      const matchesType = typeFilter === 'all' || a.mode === typeFilter;
      const fileMatch = (a.file_names || []).some((fn) => fn.toLowerCase().includes(q));
      const matchesSearch =
        !q ||
        a.title.toLowerCase().includes(q) ||
        a.id.toLowerCase().includes(q) ||
        fileMatch;
      return matchesType && matchesSearch;
    });

    return [...list].sort((a, b) => {
      const ta = new Date(a.created_at).getTime();
      const tb = new Date(b.created_at).getTime();
      return sortOrder === 'desc' ? tb - ta : ta - tb;
    });
  }, [allAnalyses, searchQuery, typeFilter, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(filteredHistory.length / PAGE_SIZE));
  const paginatedHistory = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredHistory.slice(start, start + PAGE_SIZE);
  }, [filteredHistory, currentPage]);

  const handleCompareRevision = async (a: AnalysisSummary) => {
    setComparingTitle(a.title);
    setComparisonError(null);
    setComparisonData(null);
    try {
      const res = await api.compareRevisions(a.id, a.parent_analysis_id);
      setComparisonData(res);
    } catch (e: any) {
      setComparisonError(e.message || 'Unable to load revision comparison.');
    }
  };

  // KPI metrics strictly derived from actual stored analyses
  const totalAnalyses = allAnalyses.length;
  const totalFindings = allAnalyses.reduce((acc, a) => acc + getFindingsTotal(a), 0);
  const totalCriticalHigh = allAnalyses.reduce((acc, a) => acc + a.critical_count + a.high_count, 0);
  const avgScore =
    totalAnalyses > 0
      ? Math.round(allAnalyses.reduce((acc, a) => acc + a.overall_score, 0) / totalAnalyses)
      : null;

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* 1. Hero Section */}
      <div className="bg-gradient-to-r from-blue-900 to-slate-900 rounded-2xl p-8 text-white shadow-lg relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="max-w-3xl space-y-3 relative z-10">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/20 border border-blue-400/30 text-blue-200 text-xs font-medium">
            <Sparkles className="w-3.5 h-3.5 text-blue-300" />
            <span>AI Root Cause & Decision Intelligence Platform</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            From alerts to answers — detect, understand, and take the right action.
          </h1>
          <p className="text-slate-300 text-sm leading-relaxed">
            InsightX connects multi-language AST program analysis, multivariate time-series anomaly detection, and operational log correlation into a transparent 4-stage decision-support workflow:{' '}
            <strong>Detect → Diagnose → Recommend → Explain</strong>.
          </p>
          <div className="pt-2 flex items-center space-x-3">
            <Button onClick={onNewAnalysis} className="bg-blue-500 hover:bg-blue-600 shadow-md">
              <span>Start New Analysis</span>
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
            <div className="text-xs text-slate-400 flex items-center space-x-1.5 pl-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Safe Auto-Fix, Persistent History & Revisions</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Total Completed Analyses</span>
            <FolderGit2 className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-900">{totalAnalyses}</div>
          <div className="mt-1 text-xs text-slate-500">Persisted in local database</div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <span>Total Detected Findings</span>
            <FileCode2 className="w-4 h-4 text-slate-400" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-900">{totalFindings}</div>
          <div className="mt-1 text-xs text-slate-500">Across stored analyses</div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center space-x-1">
              <span>Critical / High Findings</span>
              <InfoButton topicKey="severity" />
            </div>
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-orange-600">{totalCriticalHigh}</div>
          <div className="mt-1 text-xs text-slate-500">Prioritized for remediation</div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
            <div className="flex items-center space-x-1">
              <span>Avg Health Score</span>
              <InfoButton topicKey="health_score" />
            </div>
            <Activity className="w-4 h-4 text-blue-500" />
          </div>
          <div className="mt-2 text-2xl font-bold font-mono text-blue-600">
            {avgScore !== null ? `${avgScore}/100` : '—'}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {avgScore !== null ? 'Finding-based score average' : 'No completed analyses yet'}
          </div>
        </Card>
      </div>

      {/* 3. RECENT DIAGNOSES (Latest 5) */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                <History className="w-4 h-4 text-blue-600" />
                <span>Recent Diagnoses</span>
              </h2>
              <p className="text-xs text-slate-500">
                Latest 5 persisted diagnoses — click any record to open its full findings, root causes, and recommendations.
              </p>
            </div>
            <Button onClick={onNewAnalysis} size="sm" className="text-xs">
              <span>New Analysis</span>
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {loading ? (
            <div className="p-10 text-center text-xs text-slate-400">Loading recent diagnoses...</div>
          ) : recentDiagnoses.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center">
                <FileCode2 className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-semibold text-slate-800">
                No analyses yet. Start your first analysis to explore potential issues and root causes.
              </h3>
              <Button onClick={onNewAnalysis} size="sm" className="text-xs">
                <span>Start New Analysis</span>
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {recentDiagnoses.map((a) => {
                const findingsTotal = getFindingsTotal(a);
                const primaryFile =
                  a.file_names && a.file_names.length > 0
                    ? a.file_names.length === 1
                      ? a.file_names[0]
                      : `${a.file_names[0]} (+${a.file_names.length - 1})`
                    : `${a.files_count} file(s)`;

                return (
                  <div
                    key={a.id}
                    onClick={() => onSelectAnalysis(a.id)}
                    className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-blue-50/50 transition-colors cursor-pointer group"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-sm text-slate-900 group-hover:text-blue-600 transition-colors truncate">
                          {a.title}
                        </span>
                        {(a.revision_number || 1) > 1 && (
                          <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-mono text-[10px] font-semibold">
                            Version {a.revision_number}
                          </span>
                        )}
                        <Badge variant="outline" size="sm" className="text-[10px]">
                          {MODE_LABELS[a.mode] || a.mode}
                        </Badge>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 capitalize">
                          {a.status}
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500 font-mono">
                        <span className="flex items-center space-x-1">
                          <FileText className="w-3 h-3 text-slate-400" />
                          <span>{primaryFile}</span>
                        </span>
                        <span>•</span>
                        <span>{new Date(a.created_at).toLocaleString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3 shrink-0">
                      <div className="text-right font-mono text-xs">
                        <div className="font-semibold text-slate-800">
                          {a.mode === 'metrics_logs' && findingsTotal === 0
                            ? `${a.anomalies_count || 0} anomalies`
                            : `${findingsTotal} finding${findingsTotal === 1 ? '' : 's'}`}
                        </div>
                        <div className="text-[10px] text-slate-400">
                          {a.root_causes_count ?? 0} cause{(a.root_causes_count ?? 0) === 1 ? '' : 's'}
                        </div>
                      </div>

                      <span
                        className={`px-2.5 py-1 rounded-full font-mono font-semibold text-xs ${
                          a.overall_score >= 80
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : a.overall_score >= 60
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-red-50 text-red-700 border border-red-200'
                        }`}
                      >
                        {Math.round(a.overall_score)}/100
                      </span>

                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectAnalysis(a.id);
                        }}
                        className="text-blue-600 group-hover:bg-blue-100/70 text-xs"
                      >
                        <span>Open Results</span>
                        <ArrowRight className="w-3.5 h-3.5 ml-1" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 4. FULL ANALYSIS HISTORY (Search, Filter, Sort, Pagination, Compare Revisions, Report) */}
      <Card>
        <CardHeader>
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 w-full">
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center space-x-2">
                <Archive className="w-4 h-4 text-slate-600" />
                <span>Full Analysis History</span>
                <span className="text-xs font-mono font-normal text-slate-400">
                  ({filteredHistory.length} record{filteredHistory.length === 1 ? '' : 's'})
                </span>
              </h2>
              <p className="text-xs text-slate-500">
                Search, filter, sort, open historical diagnoses, view reports, or compare Auto Fix revisions.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Search */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search name or file..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 bg-white rounded-lg border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-44"
                />
              </div>

              {/* Type Filter */}
              <select
                aria-label="Filter by analysis type"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as any)}
                className="px-2.5 py-1.5 bg-white rounded-lg border border-slate-200 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="all">All Types</option>
                <option value="code">Code</option>
                <option value="metrics_logs">Logs / Metrics</option>
                <option value="combined">Combined</option>
              </select>

              {/* Sort Date Toggle */}
              <Button
                size="sm"
                variant="outline"
                onClick={() => setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))}
                className="text-xs"
              >
                <ArrowUpDown className="w-3.5 h-3.5 mr-1" />
                <span>{sortOrder === 'desc' ? 'Newest First' : 'Oldest First'}</span>
              </Button>

              <Button size="sm" variant="outline" onClick={onViewAllHistory} className="text-xs">
                <span>Reports Archive</span>
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {paginatedHistory.length === 0 ? (
            <div className="p-10 text-center text-xs text-slate-500">
              {allAnalyses.length === 0
                ? 'No stored analyses yet.'
                : 'No historical analyses match your search or type filter.'}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50/80 border-b border-slate-100 text-slate-500 uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="px-5 py-3 font-semibold">Analysis Name</th>
                      <th className="px-4 py-3 font-semibold">Type</th>
                      <th className="px-4 py-3 font-semibold">Date</th>
                      <th className="px-4 py-3 font-semibold">Findings</th>
                      <th className="px-4 py-3 font-semibold">Root Causes</th>
                      <th className="px-4 py-3 font-semibold">Health Score</th>
                      <th className="px-4 py-3 font-semibold">Status</th>
                      <th className="px-5 py-3 font-semibold text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {paginatedHistory.map((a) => {
                      const findingsTotal = getFindingsTotal(a);
                      const fileLabel = a.file_names && a.file_names.length > 0 ? a.file_names.join(', ') : '';
                      return (
                        <tr
                          key={a.id}
                          onClick={() => onSelectAnalysis(a.id)}
                          className="hover:bg-blue-50/40 transition-colors cursor-pointer"
                        >
                          <td className="px-5 py-3">
                            <div className="flex items-center space-x-1.5">
                              <span className="font-semibold text-slate-900">{a.title}</span>
                              {(a.revision_number || 1) > 1 && (
                                <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-mono text-[10px] font-semibold">
                                  v{a.revision_number}
                                </span>
                              )}
                            </div>
                            {fileLabel && (
                              <div className="text-[11px] font-mono text-slate-400 truncate max-w-[220px]">
                                {fileLabel}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant="outline" size="sm" className="text-[10px]">
                              {MODE_LABELS[a.mode] || a.mode}
                            </Badge>
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                            {new Date(a.created_at).toLocaleString()}
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px] font-semibold text-slate-800">
                            {findingsTotal}
                          </td>
                          <td className="px-4 py-3 font-mono text-[11px] text-slate-700">
                            {a.root_causes_count ?? 0}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded-full font-mono font-semibold text-[11px] ${
                                a.overall_score >= 80
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : a.overall_score >= 60
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-red-50 text-red-700 border border-red-200'
                              }`}
                            >
                              {Math.round(a.overall_score)}/100
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 capitalize">
                              {a.status}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                            <div className="inline-flex items-center space-x-1.5">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => onSelectAnalysis(a.id)}
                                className="text-[11px] px-2.5 py-1"
                              >
                                Open
                              </Button>
                              {onOpenReport && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => onOpenReport(a.id)}
                                  className="text-[11px] px-2 py-1 text-slate-600"
                                >
                                  Report
                                </Button>
                              )}
                              {a.parent_analysis_id && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => handleCompareRevision(a)}
                                  className="text-[11px] px-2 py-1 text-blue-600"
                                  title="Compare with previous revision"
                                >
                                  <GitCompare className="w-3.5 h-3.5 mr-1" />
                                  <span>Compare</span>
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination Bar */}
              {totalPages > 1 && (
                <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <span>
                    Page {currentPage} of {totalPages} ({filteredHistory.length} total)
                  </span>
                  <div className="flex items-center space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      className="text-xs px-2.5 py-1"
                    >
                      <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                      <span>Previous</span>
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      className="text-xs px-2.5 py-1"
                    >
                      <span>Next</span>
                      <ChevronRight className="w-3.5 h-3.5 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* 5. Pre-configured Demonstration Cases */}
      {sampleCases.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Pre-configured Demonstration Cases</h2>
              <p className="text-xs text-slate-500">Explore real multi-modal scenarios with verified ground truth</p>
            </div>
            <span className="text-xs font-medium text-blue-600">1-Click Instant Execution</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {sampleCases.map((sc) => (
              <Card key={sc.id} className="p-4 flex flex-col justify-between hover:border-blue-300 transition-all">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline" size="sm" className="font-mono text-[10px] uppercase">
                      {sc.mode}
                    </Badge>
                    <span className="text-[11px] text-slate-400 font-mono">{sc.file_count} file(s)</span>
                  </div>
                  <h3 className="font-semibold text-slate-900 text-sm">{sc.name}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed line-clamp-3">{sc.description}</p>
                  <div className="flex flex-wrap gap-1 pt-1">
                    {sc.tags.map((tag) => (
                      <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="pt-4 mt-2 border-t border-slate-100">
                  <Button
                    onClick={() => onLoadSample(sc.id)}
                    size="sm"
                    variant="outline"
                    isLoading={isLoadingSample}
                    className="w-full text-blue-600 hover:bg-blue-50 border-blue-200 text-xs"
                  >
                    <span>Load Demonstration</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Revision Comparison Modal */}
      {(comparisonData || comparisonError) && (
        <Modal
          isOpen={Boolean(comparisonData || comparisonError)}
          onClose={() => {
            setComparisonData(null);
            setComparisonError(null);
          }}
          title={`Revision Comparison: ${comparingTitle}`}
          maxWidth="xl"
        >
          {comparisonError ? (
            <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs">
              {comparisonError}
            </div>
          ) : comparisonData ? (
            <div className="space-y-4 text-xs">
              <p className="text-slate-700">{comparisonData.summary}</p>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-bold text-slate-400">BEFORE</div>
                  <div className="text-lg font-bold font-mono text-slate-800">{Math.round(comparisonData.before_score)}/100</div>
                  <div className="text-[11px] font-mono text-slate-500">{comparisonData.before_findings_count} findings</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-bold text-slate-400">AFTER</div>
                  <div className="text-lg font-bold font-mono text-slate-900">{Math.round(comparisonData.after_score)}/100</div>
                  <div className="text-[11px] font-mono text-slate-500">{comparisonData.after_findings_count} findings</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                  <div className="text-[10px] font-bold text-slate-400">IMPROVEMENT</div>
                  <div className={`text-lg font-bold font-mono ${comparisonData.score_delta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {comparisonData.score_delta > 0 ? '+' : ''}{comparisonData.score_delta} pts
                  </div>
                  <div className="text-[11px] font-mono text-slate-500">
                    Resolved: {comparisonData.resolved_findings.length} • New: {comparisonData.newly_introduced_findings.length}
                  </div>
                </div>
              </div>
              <div className="flex justify-end space-x-2 pt-2 border-t border-slate-200">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const bid = comparisonData.before_analysis_id;
                    setComparisonData(null);
                    onSelectAnalysis(bid);
                  }}
                >
                  Open Original Version
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    const aid = comparisonData.after_analysis_id;
                    setComparisonData(null);
                    onSelectAnalysis(aid);
                  }}
                >
                  Open Fixed Version
                </Button>
              </div>
            </div>
          ) : null}
        </Modal>
      )}
    </div>
  );
};
