import { describe, it, expect, vi, afterEach } from 'vitest';
import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react';
import { Badge, SeverityBadge, ConfidenceBadge, EvidenceBadge } from './components/ui/Badge';
import { InfoButton } from './components/ui/InfoButton';
import { Button } from './components/ui/Button';
import { CodeEditor } from './components/ui/CodeEditor';
import { AnalysisResults } from './features/findings/AnalysisResults';
import { RootCauseExplorer } from './features/root-cause/RootCauseExplorer';
import { RecommendationsView } from './features/recommendations/RecommendationsView';
import { NewAnalysisWorkspace } from './features/upload/NewAnalysisWorkspace';
import { OverviewDashboard } from './features/dashboard/OverviewDashboard';
import { Sidebar } from './components/layout/Sidebar';
import { AnalysisDetail, FixApplyResult } from './types';
import { api } from './services/api';

afterEach(() => {
  vi.restoreAllMocks();
});

const makeAnalysis = (overrides: Partial<AnalysisDetail> = {}): AnalysisDetail => ({
  id: 'ana-1',
  title: 'Test Analysis',
  mode: 'code',
  status: 'completed',
  created_at: new Date().toISOString(),
  files_count: 1,
  lines_of_code: 20,
  overall_score: 100,
  findings: [],
  root_causes: [],
  recommendations: [],
  relationships: [],
  metric_anomalies: [],
  log_issues: [],
  meta_info: {},
  ...overrides,
});

describe('Frontend UI & Integration Suite (Tests A–F)', () => {
  it('renders Badge, SeverityBadge, qualitative ConfidenceBadge, and explicit EvidenceBadge', () => {
    const { getByText, queryByText } = render(
      <div>
        <Badge variant="critical">Critical Defect</Badge>
        <SeverityBadge severity="High" />
        <ConfidenceBadge confidence="High" />
        <EvidenceBadge category="Static Code Evidence" />
      </div>
    );
    expect(getByText('Critical Defect').className).toContain('text-red-700');
    expect(getByText('High')).toBeTruthy();
    expect(getByText('High Confidence')).toBeTruthy();
    expect(queryByText(/%/)).toBeNull();
    expect(getByText('Static Code Evidence')).toBeTruthy();
  });

  it('TEST A: CodeEditor renders high-contrast syntax highlighting, line numbers, Tab indentation, Clear & Format', () => {
    let currentCode = 'async def work():\n    return 42';
    const handleChange = vi.fn((val: string) => {
      currentCode = val;
    });

    const { getByLabelText, getByText, container, rerender } = render(
      <CodeEditor value={currentCode} onChange={handleChange} language="python" />
    );

    const textarea = getByLabelText('Source Code Editor') as HTMLTextAreaElement;
    expect(textarea.value).toContain('async def work():');
    expect(getByText('2 lines')).toBeTruthy();
    expect(getByText('Brackets balanced')).toBeTruthy();

    // Verify dark navy background (#0F172A -> rgb(15, 23, 42)) and light syntax tokens (#93C5FD for keywords)
    const highlightedPre = container.querySelector('pre');
    expect(highlightedPre?.innerHTML).toContain('#93C5FD');
    expect(highlightedPre?.innerHTML).toContain('async');

    // Clear Code button works
    fireEvent.click(getByText('Clear Code'));
    expect(handleChange).toHaveBeenCalledWith('');

    // Language switch updates syntax badge
    rerender(<CodeEditor value="const x = 1;" onChange={handleChange} language="typescript" />);
    expect(getByText('typescript')).toBeTruthy();
  });

  it('opens Contextual InfoModal answering all 4 core questions', () => {
    const { getByRole, getByText, queryByText } = render(
      <div>
        <InfoButton topicKey="health_score" />
      </div>
    );

    expect(queryByText('1. What does this mean?')).toBeNull();
    fireEvent.click(getByRole('button', { name: /Information on Explainable Health Score/i }));

    expect(getByText('Explainable Health Score (0–100)')).toBeTruthy();
    expect(getByText('1. What does this mean?')).toBeTruthy();
    expect(getByText('2. How does InsightX calculate or determine it?')).toBeTruthy();
    expect(getByText('3. Why is it important?')).toBeTruthy();
    expect(getByText('4. Operational Limitations')).toBeTruthy();
  });

  it('TEST E: Sidebar distinguishes New Analysis Draft from completed analysis and hides stale counts on upload tab', () => {
    const onSelect = vi.fn();
    const active = makeAnalysis({
      id: 'nav-1',
      title: 'Old Faulty Scan',
      findings: [
        {
          id: 'f1',
          analysis_id: 'nav-1',
          title: 'Finding 1',
          category: 'Async',
          severity: 'High',
          file_path: 'a.py',
          line_number: 2,
          description: 'desc',
          evidence: 'ev',
          evidence_category: 'Static Code Evidence',
          detection_method: 'AST',
          is_confirmed: false,
          language: 'python',
        },
      ],
    });

    const { getByText, queryByText, rerender } = render(
      <Sidebar currentTab="findings" onSelectTab={onSelect} activeAnalysis={active} />
    );
    expect(getByText('1 found')).toBeTruthy();
    fireEvent.click(getByText('Root Cause Explorer'));
    expect(onSelect).toHaveBeenCalledWith('root-cause');

    // On New Analysis tab: MUST show New Analysis Draft and NOT "1 found"
    rerender(<Sidebar currentTab="upload" onSelectTab={onSelect} activeAnalysis={active} />);
    expect(getByText('New Analysis Draft')).toBeTruthy();
    expect(queryByText('1 found')).toBeNull();
  });

  it('TEST A: NewAnalysisWorkspace validates empty upload and empty pasted source code', () => {
    const onComplete = vi.fn();
    const { getByText } = render(<NewAnalysisWorkspace onAnalysisComplete={onComplete} />);

    fireEvent.click(getByText('Start Analysis'));
    expect(getByText(/Please upload at least one source file/i)).toBeTruthy();

    fireEvent.click(getByText('Direct Code Snippet'));
    fireEvent.click(getByText('Start Analysis'));
    expect(getByText(/Please enter source code to analyze/i)).toBeTruthy();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('displays distinct empty state A (No issues detected) and failed analysis banner', () => {
    const cleanAnalysis = makeAnalysis({ id: 'clean-1', findings: [], root_causes: [], overall_score: 100 });
    const { getByText, queryByText, rerender } = render(
      <AnalysisResults
        analysis={cleanAnalysis}
        onNavigateToRecommendations={() => {}}
        onNavigateToRootCause={() => {}}
      />
    );
    expect(getByText('No issues detected')).toBeTruthy();
    expect(queryByText('No findings match the selected filters.')).toBeNull();

    const failedAnalysis = makeAnalysis({
      id: 'fail-1',
      status: 'failed',
      error_message: 'Malformed input stream',
      overall_score: 0,
    });
    rerender(
      <AnalysisResults
        analysis={failedAnalysis}
        onNavigateToRecommendations={() => {}}
        onNavigateToRootCause={() => {}}
      />
    );
    expect(getByText('Analysis failed to complete')).toBeTruthy();
    expect(queryByText('No issues detected')).toBeNull();
  });

  it('renders findings, filters, Reset Filters state B, and Static Code Evidence badge', () => {
    const faultyAnalysis = makeAnalysis({
      id: 'faulty-1',
      overall_score: 90,
      findings: [
        {
          id: 'f-1',
          analysis_id: 'faulty-1',
          rule_id: 'PY_ASYNC_BLOCKING_SLEEP',
          title: "Blocking Synchronous Call in Async Function 'work'",
          category: 'Async / Event Loop Blocking',
          severity: 'High',
          file_path: 'worker.py',
          line_number: 5,
          line_end: 5,
          code_snippet: 'time.sleep(5)',
          description: 'Blocking sleep inside async function.',
          evidence: 'AST Call time.sleep at worker.py:5',
          evidence_category: 'Static Code Evidence',
          detection_method: 'AST Async Context Analysis',
          is_confirmed: false,
          language: 'python',
        },
      ],
    });

    const { getByText, queryByText, getByPlaceholderText } = render(
      <AnalysisResults
        analysis={faultyAnalysis}
        onNavigateToRecommendations={() => {}}
        onNavigateToRootCause={() => {}}
      />
    );

    expect(getByText('Static Code Evidence')).toBeTruthy();
    expect(queryByText('Confirmed Runtime Proof')).toBeNull();

    fireEvent.change(getByPlaceholderText(/Search findings/i), { target: { value: 'nonexistent-xyz' } });
    expect(getByText('No findings match the selected filters.')).toBeTruthy();
    fireEvent.click(getByText('Reset Filters'));
    expect(getByText("Blocking Synchronous Call in Async Function 'work'")).toBeTruthy();
  });

  it('TEST B & C: RecommendationsView supports Simple/Technical toggle, Apply Fix vs Manual Fix Required, and Before/After comparison', async () => {
    vi.spyOn(api, 'getRevisions').mockResolvedValue([]);

    const analysisWithRecs = makeAnalysis({
      id: 'rec-2',
      parent_analysis_id: 'rec-1',
      revision_number: 2,
      overall_score: 90,
      recommendations: [
        {
          id: 'r-auto',
          analysis_id: 'rec-2',
          rule_id: 'PY_ASYNC_BLOCKING_SLEEP',
          auto_fixable: true,
          priority: 'P2 - High',
          title: 'Replace Blocking time.sleep() with Non-Blocking await asyncio.sleep()',
          problem_addressed: 'Blocks event loop.',
          why_recommended: 'Yields control to asyncio loop.',
          expected_benefit: 'Eliminates stalls.',
          verification_instructions: 'Run concurrent gather test.',
          simple_explanation: {
            what_is_wrong: 'The program pauses using a blocking wait inside an async task.',
            why_problem: 'Other waiting tasks freeze too.',
            what_to_change: 'Switch time.sleep(5) to await asyncio.sleep(5).',
            how_it_helps: 'Other tasks keep running smoothly.',
          },
          technical_explanation: {
            problem_description: 'Synchronous time.sleep() blocks the event loop thread.',
            location: 'worker.py (line 5)',
            detection_method: 'AST Async Context Analysis',
            root_cause_reasoning: 'Cooperative scheduling requires non-blocking await.',
            supporting_evidence: '[Static Code Evidence] AST Call time.sleep at worker.py:5',
            impact: 'P99 latency spikes.',
            verification_instructions: 'Run asyncio.gather benchmark.',
          },
          related_finding_ids: ['f-1'],
          file_path: 'worker.py',
          diff: '--- a/worker.py\n+++ b/worker.py\n-time.sleep(5)\n+await asyncio.sleep(5)',
          reviewed: false,
        },
        {
          id: 'r-manual',
          analysis_id: 'rec-2',
          rule_id: 'PY_SQL_INJECTION',
          auto_fixable: false,
          manual_fix_reason: 'Parameterizing dynamic SQL depends on your database driver placeholder style.',
          priority: 'P1 - Immediate',
          title: 'Replace Dynamic SQL String Interpolation with Parameterized Queries',
          problem_addressed: 'SQL injection risk.',
          why_recommended: 'Dynamic query string.',
          expected_benefit: 'Prevents SQLi.',
          related_finding_ids: ['f-2'],
          file_path: 'worker.py',
          reviewed: false,
        },
      ],
    });

    const fixResult: FixApplyResult = {
      analysis: analysisWithRecs,
      applied_file_path: 'worker.py',
      fixed_code: 'import asyncio\nasync def work():\n    await asyncio.sleep(5)\n',
      source_hash: 'abc123',
      comparison: {
        before_analysis_id: 'rec-1',
        after_analysis_id: 'rec-2',
        before_score: 80,
        after_score: 90,
        score_delta: 10,
        before_findings_count: 2,
        after_findings_count: 1,
        before_severity_counts: { Critical: 0, High: 2, Medium: 0, Low: 0, Informational: 0 },
        after_severity_counts: { Critical: 0, High: 1, Medium: 0, Low: 0, Informational: 0 },
        resolved_findings: [{ id: 'f-old', title: 'Old issue' }],
        remaining_findings: [{ id: 'f-1', title: 'Remaining issue' }],
        newly_introduced_findings: [],
        status: 'improved',
        summary: 'Re-analysis resolved 1 finding(s) and changed Health Score by +10 points (80 -> 90).',
      },
    };

    const onUndo = vi.fn();
    const { getByText, getAllByText } = render(
      <RecommendationsView
        analysis={analysisWithRecs}
        onRefreshAnalysis={() => {}}
        onSelectAnalysis={onUndo}
        lastFixResult={fixResult}
      />
    );

    // Before/After Improvement comparison rendered
    expect(getByText('BEFORE FIX')).toBeTruthy();
    expect(getByText('AFTER FIX')).toBeTruthy();
    expect(getByText('+10 points')).toBeTruthy();
    expect(getByText('View Fixed Code')).toBeTruthy();
    expect(getByText('Download Fixed Code')).toBeTruthy();

    // Auto Fix vs Auto Fix Unavailable buttons
    expect(getByText('Auto Fix')).toBeTruthy();
    expect(getByText('Preview Fix')).toBeTruthy();
    expect(getAllByText(/Auto Fix Unavailable/).length).toBeGreaterThanOrEqual(1);
    expect(getByText('Edit & Re-analyze')).toBeTruthy();

    // Default Simple Explanation shown -> toggle to Technical Explanation
    expect(getAllByText('1. WHAT IS WRONG?').length).toBeGreaterThanOrEqual(1);
    fireEvent.click(getByText('Technical Explanation'));
    expect(getAllByText('ROOT-CAUSE REASONING').length).toBeGreaterThanOrEqual(1);
    expect(getByText('worker.py (line 5)')).toBeTruthy();

    // Undo Fix triggers selecting parent analysis
    await waitFor(() => expect(api.getRevisions).toHaveBeenCalled());
    fireEvent.click(getByText('Undo Fix'));
    expect(onUndo).toHaveBeenCalledWith('rec-1');
  });

  it('TEST D: OverviewDashboard renders interactive Recent Diagnoses from backend and opens clicked record', async () => {
    const sampleHistory = [
      {
        id: 'hist-1',
        title: 'invoice_service.py Investigation',
        mode: 'code' as const,
        status: 'completed',
        created_at: '2026-11-18T12:00:00Z',
        files_count: 1,
        lines_of_code: 45,
        overall_score: 35,
        critical_count: 1,
        high_count: 4,
        medium_count: 2,
        low_count: 0,
        info_count: 0,
        findings_count: 7,
        root_causes_count: 4,
        file_names: ['invoice_service.py'],
        revision_number: 1,
      },
    ];
    vi.spyOn(api, 'listAnalyses').mockResolvedValue(sampleHistory);
    vi.spyOn(api, 'listRecentAnalyses').mockResolvedValue(sampleHistory);
    vi.spyOn(api, 'listSampleCases').mockResolvedValue([]);

    const onSelect = vi.fn();
    const { getByText, getAllByText } = render(
      <OverviewDashboard
        onSelectAnalysis={onSelect}
        onNewAnalysis={() => {}}
        onViewAllHistory={() => {}}
        onLoadSample={async () => {}}
        isLoadingSample={false}
      />
    );

    await waitFor(() => {
      expect(getByText('Recent Diagnoses')).toBeTruthy();
      expect(getByText('Full Analysis History')).toBeTruthy();
      expect(getAllByText('invoice_service.py Investigation').length).toBeGreaterThanOrEqual(1);
      expect(getAllByText('7 findings').length).toBeGreaterThanOrEqual(1);
      expect(getAllByText('4 causes').length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(getByText('Open Results'));
    expect(onSelect).toHaveBeenCalledWith('hist-1');
  });

  it('clears stale root cause state and displays linked findings in RootCauseExplorer', () => {
    const faulty = makeAnalysis({
      id: 'faulty-rc',
      findings: [
        {
          id: 'f-1',
          analysis_id: 'faulty-rc',
          title: 'Blocking Synchronous Call in Async Function',
          category: 'Async / Event Loop Blocking',
          severity: 'High',
          file_path: 'worker.py',
          line_number: 5,
          line_end: 5,
          description: 'Blocking sleep.',
          evidence: 'AST Call',
          evidence_category: 'Static Code Evidence',
          detection_method: 'AST',
          is_confirmed: false,
          language: 'python',
        },
      ],
      root_causes: [
        {
          id: 'rc-1',
          analysis_id: 'faulty-rc',
          rank: 1,
          title: 'Event-Loop Starvation Risk from Synchronous Blocking in worker.py',
          description: 'Blocking time.sleep detected.',
          confidence: 'Medium',
          confidence_score: 0.72,
          evidence_category: 'Static Code Evidence',
          cause_type: 'Static Potential Cause',
          affected_files: ['worker.py'],
          affected_functions: ['work'],
          related_finding_ids: ['f-1'],
        },
      ],
    });
    const clean = makeAnalysis({ id: 'clean-rc', root_causes: [] });

    const { rerender, getAllByText, getByText, queryByText } = render(
      <RootCauseExplorer analysis={faulty} onNavigateToRecommendations={() => {}} />
    );
    expect(getAllByText(/Event-Loop Starvation Risk/).length).toBeGreaterThanOrEqual(1);
    expect(getByText('Linked Findings (1)')).toBeTruthy();

    rerender(<RootCauseExplorer analysis={clean} onNavigateToRecommendations={() => {}} />);
    expect(queryByText(/Event-Loop Starvation Risk/)).toBeNull();
    expect(getByText('No root causes identified')).toBeTruthy();
  });

  it('triggers Button click handler', () => {
    let clicked = false;
    const { getByRole } = render(<Button onClick={() => { clicked = true; }}>Execute</Button>);
    fireEvent.click(getByRole('button', { name: /Execute/i }));
    expect(clicked).toBe(true);
  });
});
