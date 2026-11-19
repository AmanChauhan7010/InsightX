import {
  AnalysisDetail,
  AnalysisSummary,
  Finding,
  RootCause,
  Recommendation,
  SampleCase,
  ReportData,
  FixPreview,
  FixApplyResult,
  RevisionSummary,
} from '../types';

const API_BASE = '/api/v1';

export const api = {
  // Health
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Backend unavailable');
    return res.json();
  },

  // Analyses
  async listAnalyses(limit = 25, mode?: string): Promise<AnalysisSummary[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (mode && mode !== 'all') params.append('mode', mode);
    const res = await fetch(`${API_BASE}/analyses?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to load analysis history');
    return res.json();
  },

  async listRecentAnalyses(limit = 10, mode?: string): Promise<AnalysisSummary[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (mode && mode !== 'all') params.append('mode', mode);
    const res = await fetch(`${API_BASE}/analyses/recent?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to load recent diagnoses');
    return res.json();
  },

  async getAnalysis(id: string): Promise<AnalysisDetail> {
    const res = await fetch(`${API_BASE}/analyses/${id}`);
    if (!res.ok) throw new Error(`Failed to load analysis ${id}`);
    return res.json();
  },

  async createAnalysis(formData: FormData): Promise<AnalysisDetail> {
    const res = await fetch(`${API_BASE}/analyses`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
      throw new Error(err.detail || 'Analysis request failed');
    }
    return res.json();
  },

  async createPasteAnalysis(payload: {
    title?: string;
    code: string;
    language?: string;
    file_name?: string;
    error_trace?: string;
  }): Promise<AnalysisDetail> {
    const res = await fetch(`${API_BASE}/analyses/paste`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Pasted analysis failed' }));
      throw new Error(err.detail || 'Analysis request failed');
    }
    return res.json();
  },

  // Findings
  async getFindings(analysisId: string, filter?: { severity?: string; category?: string }): Promise<Finding[]> {
    let url = `${API_BASE}/analyses/${analysisId}/findings`;
    const params = new URLSearchParams();
    if (filter?.severity) params.append('severity', filter.severity);
    if (filter?.category) params.append('category', filter.category);
    if (params.toString()) url += `?${params.toString()}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to load findings');
    return res.json();
  },

  // Causes
  async getCauses(analysisId: string): Promise<RootCause[]> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/causes`);
    if (!res.ok) throw new Error('Failed to load root causes');
    return res.json();
  },

  // Recommendations
  async getRecommendations(analysisId: string): Promise<Recommendation[]> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/recommendations`);
    if (!res.ok) throw new Error('Failed to load recommendations');
    return res.json();
  },

  async updateRecommendationStatus(analysisId: string, recId: string, reviewed: boolean): Promise<Recommendation> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/recommendations/${recId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewed }),
    });
    if (!res.ok) throw new Error('Failed to update recommendation status');
    return res.json();
  },

  // Safe Fix Preview, Apply & Revision Tracking
  async previewFix(
    analysisId: string,
    recommendationId: string,
    options?: Record<string, any>
  ): Promise<FixPreview> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/fixes/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recommendation_id: recommendationId, options: options || {} }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to preview fix' }));
      throw new Error(err.detail || 'Failed to preview fix');
    }
    return res.json();
  },

  async applyFix(
    analysisId: string,
    payload: {
      recommendation_id?: string;
      expected_source_hash?: string;
      file_path?: string;
      custom_code?: string;
      options?: Record<string, any>;
    }
  ): Promise<FixApplyResult> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/fixes/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to apply fix' }));
      throw new Error(err.detail || 'Failed to apply fix');
    }
    return res.json();
  },

  async compareRevisions(analysisId: string, otherId?: string) {
    const params = otherId ? `?other_id=${encodeURIComponent(otherId)}` : '';
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/revisions/compare${params}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to compare revisions' }));
      throw new Error(err.detail || 'Failed to compare revisions');
    }
    return res.json();
  },

  async getRevisions(analysisId: string): Promise<RevisionSummary[]> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/revisions`);
    if (!res.ok) throw new Error('Failed to load analysis revisions');
    return res.json();
  },

  async getSourceSnapshot(analysisId: string): Promise<{
    analysis_id: string;
    revision_number: number;
    files: Record<string, { content: string; language: string; sha256: string }>;
  }> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/source`);
    if (!res.ok) throw new Error('Failed to load stored source files');
    return res.json();
  },

  // Evidence
  async getEvidence(analysisId: string) {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/evidence`);
    if (!res.ok) throw new Error('Failed to load evidence');
    return res.json();
  },

  // Report
  async getReport(analysisId: string): Promise<ReportData> {
    const res = await fetch(`${API_BASE}/analyses/${analysisId}/report`);
    if (!res.ok) throw new Error('Failed to load report');
    return res.json();
  },

  getReportDownloadUrl(analysisId: string): string {
    return `${API_BASE}/analyses/${analysisId}/report/download`;
  },

  // Sample Cases
  async listSampleCases(): Promise<SampleCase[]> {
    const res = await fetch(`${API_BASE}/sample-cases`);
    if (!res.ok) throw new Error('Failed to list sample cases');
    return res.json();
  },

  async loadSampleCase(caseId: string): Promise<AnalysisDetail> {
    const res = await fetch(`${API_BASE}/sample-cases/${caseId}/load`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to load demo case' }));
      throw new Error(err.detail || 'Failed to load demo case');
    }
    return res.json();
  },
};
