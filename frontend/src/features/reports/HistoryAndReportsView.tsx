import React, { useState, useEffect } from 'react';
import {
  Archive,
  Download,
  FileText,
  FileCode,
  FolderGit2,
  ExternalLink,
  Copy,
  Check,
  CheckCircle2,
  RefreshCw
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { AnalysisDetail, AnalysisSummary, ReportData } from '../../types';
import { api } from '../../services/api';

interface HistoryAndReportsViewProps {
  activeAnalysis: AnalysisDetail | null;
  onSelectAnalysis: (id: string) => void;
}

export const HistoryAndReportsView: React.FC<HistoryAndReportsViewProps> = ({
  activeAnalysis,
  onSelectAnalysis,
}) => {
  const [historyList, setHistoryList] = useState<AnalysisSummary[]>([]);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [reportTab, setReportTab] = useState<'markdown' | 'json'>('markdown');
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    let active = true;
    setReportData(null);
    if (activeAnalysis) {
      api.getReport(activeAnalysis.id)
        .then((res) => {
          if (active) setReportData(res);
        })
        .catch((e) => console.error(e));
    }
    return () => {
      active = false;
    };
  }, [activeAnalysis?.id]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const list = await api.listAnalyses(50);
      setHistoryList(list);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyReport = () => {
    if (!reportData) return;
    const textToCopy =
      reportTab === 'markdown'
        ? reportData.markdown_report
        : JSON.stringify(reportData.json_data, null, 2);
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadMarkdown = () => {
    if (!activeAnalysis) return;
    window.open(api.getReportDownloadUrl(activeAnalysis.id), '_blank');
  };

  const handleDownloadJson = () => {
    if (!reportData) return;
    const blob = new Blob([JSON.stringify(reportData.json_data, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `insightx-report-${reportData.analysis_id.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">
          Analysis History & Exportable Incident Dossiers
        </h1>
        <p className="text-xs text-slate-500">
          Review past investigations, switch active targets, and export standardized reports in human-readable Markdown or machine-readable JSON.
        </p>
      </div>

      {/* Active Report Export Section */}
      {activeAnalysis && reportData && (
        <Card>
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 w-full">
              <div>
                <h2 className="text-sm font-bold text-slate-900">
                  Incident Dossier: {reportData.title}
                </h2>
                <div className="flex items-center space-x-2 text-xs text-slate-500 font-mono mt-0.5">
                  <span>ID: {reportData.analysis_id.slice(0, 12)}...</span>
                  <span>•</span>
                  <span>Generated: {new Date(reportData.generated_at).toLocaleString()}</span>
                </div>
              </div>

              {/* Format Toggle & Download Buttons */}
              <div className="flex items-center space-x-2">
                <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-xs">
                  <button
                    onClick={() => setReportTab('markdown')}
                    className={`px-3 py-1 rounded-md font-medium transition-colors ${
                      reportTab === 'markdown' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Markdown Dossier
                  </button>
                  <button
                    onClick={() => setReportTab('json')}
                    className={`px-3 py-1 rounded-md font-medium transition-colors ${
                      reportTab === 'json' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Structured JSON
                  </button>
                </div>

                <Button size="sm" variant="outline" onClick={handleCopyReport} className="text-xs">
                  {copied ? <Check className="w-3.5 h-3.5 mr-1 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </Button>

                {reportTab === 'markdown' ? (
                  <Button size="sm" onClick={handleDownloadMarkdown} className="text-xs shadow-sm">
                    <Download className="w-3.5 h-3.5 mr-1.5" />
                    <span>Download .md</span>
                  </Button>
                ) : (
                  <Button size="sm" onClick={handleDownloadJson} className="text-xs shadow-sm">
                    <Download className="w-3.5 h-3.5 mr-1.5" />
                    <span>Download JSON</span>
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {reportTab === 'markdown' ? (
              <div className="rounded-xl bg-slate-950 p-6 text-slate-200 font-mono text-xs overflow-x-auto max-h-[500px] border border-slate-800 leading-relaxed whitespace-pre-wrap select-text">
                {reportData.markdown_report}
              </div>
            ) : (
              <pre className="rounded-xl bg-slate-950 p-6 text-emerald-400 font-mono text-xs overflow-x-auto max-h-[500px] border border-slate-800 leading-relaxed select-text">
                {JSON.stringify(reportData.json_data, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      )}

      {/* Analysis Archive Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <h2 className="text-base font-semibold text-slate-900">Stored Historical Investigations</h2>
              <p className="text-xs text-slate-500">Persistent SQLite database records</p>
            </div>
            <Button size="sm" variant="outline" onClick={loadHistory} className="text-xs">
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              <span>Refresh</span>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-[10px] text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th className="px-5 py-3 font-semibold">Investigation Title</th>
                  <th className="px-5 py-3 font-semibold">Mode</th>
                  <th className="px-5 py-3 font-semibold">Files</th>
                  <th className="px-5 py-3 font-semibold">Health Score</th>
                  <th className="px-5 py-3 font-semibold">Defect Breakdown</th>
                  <th className="px-5 py-3 font-semibold">Date Completed</th>
                  <th className="px-5 py-3 font-semibold text-right">Switch Target</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {historyList.map((a) => {
                  const isActive = activeAnalysis?.id === a.id;
                  return (
                    <tr
                      key={a.id}
                      className={`hover:bg-blue-50/50 transition-colors ${
                        isActive ? 'bg-blue-50/60 font-medium' : ''
                      }`}
                    >
                      <td className="px-5 py-3.5">
                        <div className="font-semibold text-slate-900">{a.title}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{a.id}</div>
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge variant="outline" size="sm" className="uppercase font-mono text-[10px]">
                          {a.mode}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 font-mono text-slate-600">
                        {a.files_count} file(s)
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`px-2 py-0.5 rounded-full font-mono font-semibold text-[11px] ${
                          a.overall_score >= 80 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                          a.overall_score >= 60 ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                          'bg-red-50 text-red-700 border border-red-200'
                        }`}>
                          {Math.round(a.overall_score)}/100
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                          {a.critical_count > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-bold">
                              {a.critical_count} Crit
                            </span>
                          )}
                          {a.high_count > 0 && (
                            <span className="px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-semibold">
                              {a.high_count} High
                            </span>
                          )}
                          {a.critical_count === 0 && a.high_count === 0 && (
                            <span className="text-emerald-600 font-medium flex items-center space-x-1">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Pass</span>
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 font-mono text-[11px]">
                        {new Date(a.created_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        {isActive ? (
                          <span className="text-blue-600 font-semibold text-xs px-2 py-1 rounded bg-blue-100">
                            Active
                          </span>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onSelectAnalysis(a.id)}
                            className="text-xs"
                          >
                            Open
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
