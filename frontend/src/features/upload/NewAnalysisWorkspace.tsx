import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileCode,
  FolderArchive,
  FileText,
  Activity,
  Trash2,
  Play,
  CheckCircle2,
  AlertCircle,
  Code2,
  FileCheck,
  Layers,
  Sparkles
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { InfoButton } from '../../components/ui/InfoButton';
import { CodeEditor } from '../../components/ui/CodeEditor';
import { AnalysisMode, AnalysisDetail } from '../../types';
import { api } from '../../services/api';

interface NewAnalysisWorkspaceProps {
  onAnalysisComplete: (analysis: AnalysisDetail) => void;
  onProcessingChange?: (isProcessing: boolean) => void;
}

export const NewAnalysisWorkspace: React.FC<NewAnalysisWorkspaceProps> = ({
  onAnalysisComplete,
  onProcessingChange,
}) => {
  const [mode, setMode] = useState<AnalysisMode>('code');
  const [inputTab, setInputTab] = useState<'upload' | 'paste'>('upload');
  
  // File Upload State
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [metricsFile, setMetricsFile] = useState<File | null>(null);
  const [logsFile, setLogsFile] = useState<File | null>(null);

  // Paste Code State
  const [pastedTitle, setPastedTitle] = useState('Custom Source Code Scan');
  const [pastedCode, setPastedCode] = useState('');
  const [pastedLanguage, setPastedLanguage] = useState('python');
  const [pastedFileName, setPastedFileName] = useState('service.py');

  // Execution & Progress State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentStageIndex, setCurrentStageIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const metricsInputRef = useRef<HTMLInputElement>(null);
  const logsInputRef = useRef<HTMLInputElement>(null);

  const stages = [
    'Validating input formats & safety constraints',
    'Ingesting files & parsing AST syntax trees',
    'Executing static semantic & security inspection rules',
    'Correlating multimodal telemetry & causal lead-lag graph',
    'Synthesizing decision recommendations & verified code diffs'
  ];

  const handleFilesSelected = (files: FileList | null) => {
    if (!files) return;
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      if (f.name.endsWith('.csv')) {
        setMetricsFile(f);
      } else if (f.name.endsWith('.log')) {
        setLogsFile(f);
      } else {
        validFiles.push(f);
      }
    }
    setSelectedFiles((prev) => [...prev, ...validFiles]);
    setErrorMessage(null);
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleStartAnalysis = async () => {
    setErrorMessage(null);

    // Validate inputs
    if (inputTab === 'paste') {
      if (!pastedCode.trim()) {
        setErrorMessage('Please enter source code to analyze.');
        return;
      }
    } else {
      if (mode === 'code' && selectedFiles.length === 0) {
        setErrorMessage('Please upload at least one source file (.py, .js, .ts) or a project .zip.');
        return;
      }
      if (mode === 'metrics_logs' && !metricsFile && !logsFile) {
        setErrorMessage('Please upload a telemetry metrics CSV or an application log file.');
        return;
      }
      if (mode === 'combined' && (selectedFiles.length === 0 && !metricsFile && !logsFile)) {
        setErrorMessage('Combined RCA requires both source code files and associated logs/metrics.');
        return;
      }
    }

    setIsSubmitting(true);
    onProcessingChange?.(true);
    setCurrentStageIndex(0);

    // Genuine stage transitions
    const stageTimer = setInterval(() => {
      setCurrentStageIndex((prev) => {
        if (prev < stages.length - 1) return prev + 1;
        return prev;
      });
    }, 450);

    try {
      let result: AnalysisDetail;

      if (inputTab === 'paste') {
        result = await api.createPasteAnalysis({
          title: pastedTitle,
          code: pastedCode,
          language: pastedLanguage,
          file_name: pastedFileName,
        });
      } else {
        const formData = new FormData();
        formData.append('title', selectedFiles.length > 0 ? selectedFiles[0].name.replace(/\.[^/.]+$/, '') + ' Investigation' : 'System Telemetry Analysis');
        formData.append('mode', mode);

        selectedFiles.forEach((file) => {
          formData.append('files', file);
        });

        if (metricsFile) {
          formData.append('metrics_file', metricsFile);
        }
        if (logsFile) {
          formData.append('logs_file', logsFile);
        }

        result = await api.createAnalysis(formData);
      }

      clearInterval(stageTimer);
      setCurrentStageIndex(stages.length - 1);
      setTimeout(() => {
        setIsSubmitting(false);
        onProcessingChange?.(false);
        onAnalysisComplete(result);
      }, 300);
    } catch (err: any) {
      clearInterval(stageTimer);
      setIsSubmitting(false);
      onProcessingChange?.(false);
      setErrorMessage(err.message || 'Analysis failed. Please check file format.');
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      {/* Title Header */}
      <div className="space-y-1">
        <div className="flex items-center space-x-2.5">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">New Diagnostic Investigation</h1>
          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            New Analysis Draft
          </span>
          <InfoButton topicKey="rca_diagnosis" />
        </div>
        <p className="text-sm text-slate-500">
          Upload source code, project repositories, system metrics, or application logs to run independent or correlated root-cause intelligence. Previous history is preserved automatically.
        </p>
      </div>

      {/* Mode Selector Tabs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            id: 'code',
            label: 'Mode 1: Source Code Analysis',
            desc: 'Deep AST inspection of Python, JavaScript, TypeScript files or ZIP repositories.',
            badge: 'Primary Mode',
            icon: Code2
          },
          {
            id: 'metrics_logs',
            label: 'Mode 2: System / Log Analysis',
            desc: 'Multi-variate Isolation Forest, Z-Score saturation & log stack trace isolation.',
            badge: 'Telemetry',
            icon: Activity
          },
          {
            id: 'combined',
            label: 'Mode 3: Combined Root Cause',
            desc: 'Cross-modality correlation: maps runtime errors & metrics directly to source lines.',
            badge: 'End-to-End RCA',
            icon: Layers
          }
        ].map((m) => {
          const Icon = m.icon;
          const isSelected = mode === m.id;
          return (
            <div
              key={m.id}
              onClick={() => setMode(m.id as AnalysisMode)}
              className={`p-4 rounded-xl border transition-all cursor-pointer select-none ${
                isSelected
                  ? 'border-blue-600 bg-blue-50/40 shadow-sm ring-1 ring-blue-600'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded uppercase font-mono ${
                  isSelected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'
                }`}>
                  {m.badge}
                </span>
                <Icon className={`w-4 h-4 ${isSelected ? 'text-blue-600' : 'text-slate-400'}`} />
              </div>
              <h3 className="mt-2.5 font-bold text-slate-900 text-sm">{m.label}</h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">{m.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Main Workspace Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-slate-900 text-sm">Target Ingestion Workspace</span>
              <InfoButton topicKey="severity" />
            </div>

            {/* Input Method Toggle (Upload Files vs Paste Snippet) */}
            <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200/80 text-xs">
              <button
                type="button"
                onClick={() => setInputTab('upload')}
                className={`px-3 py-1 rounded-md font-medium transition-colors ${
                  inputTab === 'upload' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Upload Files / ZIP
              </button>
              <button
                type="button"
                onClick={() => setInputTab('paste')}
                className={`px-3 py-1 rounded-md font-medium transition-colors ${
                  inputTab === 'paste' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Direct Code Snippet
              </button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {inputTab === 'upload' ? (
            <div className="space-y-6">
              {/* Primary Code Upload Drag & Drop */}
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  handleFilesSelected(e.dataTransfer.files);
                }}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-300 hover:border-blue-500 rounded-xl p-8 text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-blue-50/30 group"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".py,.js,.jsx,.ts,.tsx,.zip,.sql,.json"
                  className="hidden"
                  onChange={(e) => handleFilesSelected(e.target.files)}
                />
                <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 mx-auto flex items-center justify-center group-hover:scale-105 transition-transform shadow-sm">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <h3 className="mt-3 text-sm font-semibold text-slate-800">
                  Click to browse or drag and drop source files
                </h3>
                <p className="mt-1 text-xs text-slate-500">
                  Supports single files (<strong>.py, .js, .ts</strong>), multiple files, or full repositories (<strong>.zip</strong>)
                </p>
                <div className="mt-3 flex items-center justify-center space-x-2 text-[11px] text-slate-400">
                  <span>Up to 15MB per file</span>
                  <span>•</span>
                  <span>Safe sandbox parsing</span>
                  <span>•</span>
                  <span>Zero arbitrary execution</span>
                </div>
              </div>

              {/* Selected Source Files List */}
              {selectedFiles.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                    <span>Selected Source Files ({selectedFiles.length})</span>
                    <button
                      onClick={() => setSelectedFiles([])}
                      className="text-red-600 hover:underline text-[11px]"
                    >
                      Clear All
                    </button>
                  </div>
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg max-h-48 overflow-y-auto bg-white">
                    {selectedFiles.map((file, idx) => (
                      <div key={idx} className="px-3.5 py-2 flex items-center justify-between text-xs hover:bg-slate-50">
                        <div className="flex items-center space-x-2.5 truncate">
                          <FileCode className="w-4 h-4 text-blue-500 shrink-0" />
                          <span className="font-medium text-slate-800 truncate">{file.name}</span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            {(file.size / 1024).toFixed(1)} KB
                          </span>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeFile(idx);
                          }}
                          className="text-slate-400 hover:text-red-600 p-1 rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Auxiliary Ingestion (Metrics & Logs) for Mode 2 & Mode 3 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                {/* Telemetry Metrics */}
                <div className="p-4 rounded-lg border border-slate-200/90 bg-white space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5 font-semibold text-xs text-slate-800">
                      <Activity className="w-4 h-4 text-emerald-600" />
                      <span>Telemetry Metrics (.csv)</span>
                      <InfoButton topicKey="anomaly_detection" />
                    </div>
                    {metricsFile && (
                      <button onClick={() => setMetricsFile(null)} className="text-red-500 hover:underline text-[10px]">
                        Remove
                      </button>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Timestamped CPU, memory, P95 latency, or error rates.
                  </p>
                  <input
                    ref={metricsInputRef}
                    type="file"
                    accept=".csv,.json"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && setMetricsFile(e.target.files[0])}
                  />
                  {metricsFile ? (
                    <div className="p-2 rounded bg-emerald-50 border border-emerald-200 text-xs font-mono text-emerald-800 flex items-center justify-between">
                      <span className="truncate">{metricsFile.name}</span>
                      <span className="text-[10px]">{(metricsFile.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => metricsInputRef.current?.click()}
                      className="w-full text-xs text-slate-700"
                    >
                      Browse Metrics CSV
                    </Button>
                  )}
                </div>

                {/* Application Logs */}
                <div className="p-4 rounded-lg border border-slate-200/90 bg-white space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-1.5 font-semibold text-xs text-slate-800">
                      <FileText className="w-4 h-4 text-amber-600" />
                      <span>Application Logs (.log, .txt)</span>
                      <InfoButton topicKey="evidence" />
                    </div>
                    {logsFile && (
                      <button onClick={() => setLogsFile(null)} className="text-red-500 hover:underline text-[10px]">
                        Remove
                      </button>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500">
                    RFC 5424 structured logs or traceback error streams.
                  </p>
                  <input
                    ref={logsInputRef}
                    type="file"
                    accept=".log,.txt"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && setLogsFile(e.target.files[0])}
                  />
                  {logsFile ? (
                    <div className="p-2 rounded bg-amber-50 border border-amber-200 text-xs font-mono text-amber-800 flex items-center justify-between">
                      <span className="truncate">{logsFile.name}</span>
                      <span className="text-[10px]">{(logsFile.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ) : (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => logsInputRef.current?.click()}
                      className="w-full text-xs text-slate-700"
                    >
                      Browse Logs File
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* Paste Code Editor */
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Snippet Title</label>
                  <input
                    type="text"
                    value={pastedTitle}
                    onChange={(e) => setPastedTitle(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                    placeholder="e.g. Payment Processor Check"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Target Language</label>
                  <select
                    value={pastedLanguage}
                    onChange={(e) => {
                      const nextLang = e.target.value;
                      setPastedLanguage(nextLang);
                      const extMap: Record<string, string> = { python: '.py', javascript: '.js', typescript: '.ts' };
                      const base = pastedFileName.replace(/\.[^/.]+$/, '') || 'service';
                      setPastedFileName(`${base}${extMap[nextLang] || '.py'}`);
                    }}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none bg-white"
                  >
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript</option>
                    <option value="typescript">TypeScript</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Simulated Filename</label>
                  <input
                    type="text"
                    value={pastedFileName}
                    onChange={(e) => setPastedFileName(e.target.value)}
                    className="w-full px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-mono focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none"
                    placeholder="handler.py"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Source Code Text
                </label>
                <CodeEditor
                  value={pastedCode}
                  onChange={(val) => {
                    setPastedCode(val);
                    if (errorMessage) setErrorMessage(null);
                  }}
                  language={pastedLanguage}
                  placeholder="Write or paste Python, JavaScript, or TypeScript source code here to analyze..."
                  ariaLabel="Source Code Text"
                />
              </div>
            </div>
          )}

          {/* Validation Feedback */}
          {errorMessage && (
            <div className="p-3.5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Multi-stage Progress Indicator during processing */}
          {isSubmitting && (
            <div className="p-5 rounded-xl bg-slate-50 border border-slate-200 space-y-3 animate-in fade-in">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-800">
                <span className="flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
                  <span>Executing Pipeline: Stage {currentStageIndex + 1} of {stages.length}</span>
                </span>
                <span className="font-mono text-blue-600">{Math.round(((currentStageIndex + 1) / stages.length) * 100)}%</span>
              </div>
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-blue-600 h-full transition-all duration-300 ease-out"
                  style={{ width: `${((currentStageIndex + 1) / stages.length) * 100}%` }}
                ></div>
              </div>
              <p className="text-xs text-slate-600 font-medium">
                {stages[currentStageIndex]}
              </p>
            </div>
          )}

          {/* Primary Action Button */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-100">
            <div className="text-xs text-slate-500 flex items-center space-x-1">
              <span>Code is processed independently; system telemetry is optional.</span>
            </div>
            <Button
              onClick={handleStartAnalysis}
              isLoading={isSubmitting}
              size="md"
              className="px-6 shadow-sm"
            >
              <Play className="w-4 h-4 mr-1.5 fill-current" />
              <span>Start Analysis</span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
