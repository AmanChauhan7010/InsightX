export type Severity = 'Critical' | 'High' | 'Medium' | 'Low' | 'Informational';
export type Confidence = 'High' | 'Medium' | 'Low';
export type AnalysisMode = 'code' | 'metrics_logs' | 'combined';
export type EvidenceCategory =
  | 'Static Code Evidence'
  | 'Log Evidence'
  | 'Metrics Evidence'
  | 'Runtime Evidence'
  | 'Correlated Evidence';

export interface Finding {
  id: string;
  analysis_id: string;
  rule_id?: string;
  title: string;
  category: string;
  severity: Severity;
  severity_rationale?: string;
  file_path: string;
  line_number?: number;
  line_end?: number;
  code_snippet?: string;
  description: string;
  evidence: string;
  evidence_category?: EvidenceCategory | string;
  detection_method: string;
  potential_consequences?: string;
  suggested_next_step?: string;
  is_confirmed: boolean;
  language: string;
}

export interface RootCause {
  id: string;
  analysis_id: string;
  rank: number;
  title: string;
  description: string;
  confidence: Confidence;
  confidence_score: number;
  evidence_category?: EvidenceCategory | string;
  cause_type?: string;
  affected_files: string[];
  affected_functions: string[];
  related_finding_ids: string[];
  evidence_summary?: string;
  ranking_rationale?: string;
  consequences?: string;
  recommended_actions_summary?: string;
  missing_evidence?: string;
  alternative_explanations?: string;
}

export interface SimpleExplanation {
  what_is_wrong?: string;
  why_problem?: string;
  what_to_change?: string;
  how_it_helps?: string;
}

export interface TechnicalExplanation {
  problem_description?: string;
  location?: string;
  detection_method?: string;
  root_cause_reasoning?: string;
  supporting_evidence?: string;
  impact?: string;
  implementation_details?: string;
  verification_instructions?: string;
  uncertainty?: string;
}

export interface Recommendation {
  id: string;
  analysis_id: string;
  priority: string; // P1 - Immediate, P2 - High, etc.
  title: string;
  problem_addressed: string;
  why_recommended: string;
  expected_benefit: string;
  verification_instructions?: string;
  related_finding_ids: string[];
  related_cause_ids?: string[];
  rule_id?: string;
  auto_fixable?: boolean;
  manual_fix_reason?: string;
  simple_explanation?: SimpleExplanation;
  technical_explanation?: TechnicalExplanation;
  file_path?: string;
  original_code?: string;
  refactored_code?: string;
  diff?: string;
  reviewed: boolean;
}

export interface Relationship {
  id: string;
  analysis_id: string;
  source: string;
  target: string;
  relationship_type: string;
  details?: string;
}

export interface MetricAnomaly {
  id: string;
  analysis_id: string;
  timestamp: string;
  metric_name: string;
  observed_value: number;
  baseline_mean?: number;
  baseline_std?: number;
  anomaly_score: number;
  severity: string;
}

export interface LogIssue {
  id: string;
  analysis_id: string;
  timestamp?: string;
  level: string;
  message: string;
  service?: string;
  file_path?: string;
  line_number?: number;
  count: number;
}

export interface AnalysisSummary {
  id: string;
  title: string;
  mode: AnalysisMode;
  status: string;
  created_at: string;
  completed_at?: string;
  files_count: number;
  lines_of_code: number;
  summary?: string;
  overall_score: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
  findings_count?: number;
  root_causes_count?: number;
  recommendations_count?: number;
  anomalies_count?: number;
  log_issues_count?: number;
  file_names?: string[];
  parent_analysis_id?: string;
  root_analysis_id?: string;
  revision_number?: number;
  applied_recommendation_title?: string;
  error_message?: string;
}

export interface AnalysisDetail {
  id: string;
  title: string;
  mode: AnalysisMode;
  status: string;
  created_at: string;
  completed_at?: string;
  files_count: number;
  lines_of_code: number;
  summary?: string;
  overall_score: number;
  error_message?: string;
  meta_info?: Record<string, any>;
  parent_analysis_id?: string;
  root_analysis_id?: string;
  revision_number?: number;
  applied_recommendation_id?: string;
  applied_recommendation_title?: string;

  findings: Finding[];
  root_causes: RootCause[];
  recommendations: Recommendation[];
  relationships: Relationship[];
  metric_anomalies: MetricAnomaly[];
  log_issues: LogIssue[];
}

export interface FixPreview {
  analysis_id: string;
  recommendation_id: string;
  recommendation_title: string;
  rule_id?: string;
  file_path: string;
  auto_fixable: boolean;
  manual_fix_reason?: string;
  source_hash: string;
  original_code: string;
  patched_code?: string;
  diff?: string;
}

export interface FixComparison {
  before_analysis_id: string;
  after_analysis_id: string;
  before_score: number;
  after_score: number;
  score_delta: number;
  before_findings_count: number;
  after_findings_count: number;
  before_severity_counts: Record<string, number>;
  after_severity_counts: Record<string, number>;
  resolved_findings: Array<Record<string, any>>;
  remaining_findings: Array<Record<string, any>>;
  newly_introduced_findings: Array<Record<string, any>>;
  status: 'improved' | 'no_change' | 'regressed';
  summary: string;
}

export interface FixApplyResult {
  analysis: AnalysisDetail;
  comparison: FixComparison;
  applied_file_path: string;
  fixed_code: string;
  source_hash: string;
  execution_output?: string;
}

export interface RevisionSummary {
  id: string;
  parent_analysis_id?: string;
  root_analysis_id?: string;
  revision_number: number;
  title: string;
  created_at: string;
  overall_score: number;
  findings_count: number;
  root_causes_count: number;
  recommendations_count: number;
  applied_recommendation_title?: string;
  status: string;
}

export interface SampleCase {
  id: string;
  name: string;
  mode: AnalysisMode;
  description: string;
  file_count: number;
  tags: string[];
}

export interface ReportData {
  analysis_id: string;
  title: string;
  generated_at: string;
  json_data: Record<string, any>;
  markdown_report: string;
}

export interface InfoTopic {
  title: string;
  whatItMeans: string;
  howCalculated: string;
  whyImportant: string;
  limitations: string;
}
