from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# --- Finding Schemas ---
class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    title: str
    category: str
    severity: str  # Critical, High, Medium, Low, Informational
    file_path: str
    line_number: Optional[int] = None
    line_end: Optional[int] = None
    code_snippet: Optional[str] = None
    description: str
    evidence: str
    evidence_category: str = "Static Code Evidence"
    rule_id: Optional[str] = None
    severity_rationale: Optional[str] = None
    detection_method: str
    potential_consequences: Optional[str] = None
    suggested_next_step: Optional[str] = None
    is_confirmed: bool = False
    language: str = "python"


# --- Root Cause Schemas ---
class RootCauseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    rank: int
    title: str
    description: str
    confidence: str  # High, Medium, Low
    confidence_score: float
    evidence_category: str = "Static Code Evidence"
    cause_type: str = "Static Potential Cause"
    affected_files: List[str] = []
    affected_functions: List[str] = []
    related_finding_ids: List[str] = []
    evidence_summary: Optional[str] = None
    ranking_rationale: Optional[str] = None
    consequences: Optional[str] = None
    recommended_actions_summary: Optional[str] = None
    missing_evidence: Optional[str] = None
    alternative_explanations: Optional[str] = None


# --- Recommendation Schemas ---
class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    priority: str  # P1 - Immediate, P2 - High, P3 - Medium, P4 - Low
    title: str
    problem_addressed: str
    why_recommended: str
    expected_benefit: str
    verification_instructions: Optional[str] = None
    related_finding_ids: List[str] = []
    related_cause_ids: List[str] = []
    rule_id: Optional[str] = None
    auto_fixable: bool = False
    manual_fix_reason: Optional[str] = None
    simple_explanation: Dict[str, Any] = {}
    technical_explanation: Dict[str, Any] = {}
    file_path: Optional[str] = None
    original_code: Optional[str] = None
    refactored_code: Optional[str] = None
    diff: Optional[str] = None
    reviewed: bool = False


class RecommendationReviewUpdate(BaseModel):
    reviewed: bool


# --- Relationship Schemas ---
class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    source: str
    target: str
    relationship_type: str
    details: Optional[str] = None


# --- Metric Anomaly Schemas ---
class MetricAnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    timestamp: str
    metric_name: str
    observed_value: float
    baseline_mean: Optional[float] = None
    baseline_std: Optional[float] = None
    anomaly_score: float
    severity: str


# --- Log Issue Schemas ---
class LogIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_id: str
    timestamp: Optional[str] = None
    level: str
    message: str
    service: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    count: int = 1


# --- Analysis Summary & Detail Schemas ---
class AnalysisSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    mode: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    files_count: int
    lines_of_code: int
    summary: Optional[str] = None
    overall_score: float
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    findings_count: int = 0
    root_causes_count: int = 0
    recommendations_count: int = 0
    anomalies_count: int = 0
    log_issues_count: int = 0
    file_names: List[str] = []
    parent_analysis_id: Optional[str] = None
    root_analysis_id: Optional[str] = None
    revision_number: int = 1
    applied_recommendation_title: Optional[str] = None
    error_message: Optional[str] = None


class AnalysisDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    mode: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    files_count: int
    lines_of_code: int
    summary: Optional[str] = None
    overall_score: float
    error_message: Optional[str] = None
    meta_info: Dict[str, Any] = {}
    parent_analysis_id: Optional[str] = None
    root_analysis_id: Optional[str] = None
    revision_number: int = 1
    applied_recommendation_id: Optional[str] = None
    applied_recommendation_title: Optional[str] = None

    findings: List[FindingResponse] = []
    root_causes: List[RootCauseResponse] = []
    recommendations: List[RecommendationResponse] = []
    relationships: List[RelationshipResponse] = []
    metric_anomalies: List[MetricAnomalyResponse] = []
    log_issues: List[LogIssueResponse] = []


# --- Fix Preview, Apply & Revision Schemas ---
class FixPreviewRequest(BaseModel):
    recommendation_id: str
    options: Dict[str, Any] = {}


class FixPreviewResponse(BaseModel):
    analysis_id: str
    recommendation_id: str
    recommendation_title: str
    rule_id: Optional[str] = None
    file_path: str
    auto_fixable: bool
    manual_fix_reason: Optional[str] = None
    ai_fix_available: bool = False
    source_hash: str
    original_code: str
    patched_code: Optional[str] = None
    diff: Optional[str] = None


class FixApplyRequest(BaseModel):
    recommendation_id: Optional[str] = None
    expected_source_hash: Optional[str] = None
    file_path: Optional[str] = None
    custom_code: Optional[str] = None
    options: Dict[str, Any] = {}


class FixComparisonResponse(BaseModel):
    before_analysis_id: str
    after_analysis_id: str
    before_score: float
    after_score: float
    score_delta: float
    before_findings_count: int
    after_findings_count: int
    before_severity_counts: Dict[str, int]
    after_severity_counts: Dict[str, int]
    resolved_findings: List[Dict[str, Any]]
    remaining_findings: List[Dict[str, Any]]
    newly_introduced_findings: List[Dict[str, Any]]
    status: str  # "improved" | "no_change" | "regressed"
    summary: str


class FixApplyResponse(BaseModel):
    analysis: AnalysisDetailResponse
    comparison: FixComparisonResponse
    applied_file_path: str
    fixed_code: str
    source_hash: str
    execution_output: Optional[str] = None


class RevisionSummaryResponse(BaseModel):
    id: str
    parent_analysis_id: Optional[str] = None
    root_analysis_id: Optional[str] = None
    revision_number: int
    title: str
    created_at: datetime
    overall_score: float
    findings_count: int
    root_causes_count: int
    recommendations_count: int
    applied_recommendation_title: Optional[str] = None
    status: str


# --- Request Schemas ---
class PasteCodeAnalysisRequest(BaseModel):
    title: Optional[str] = "Pasted Code Analysis"
    code: str = Field(..., description="Source code text to analyze")
    language: Optional[str] = "python"
    file_name: Optional[str] = "snippet.py"
    error_trace: Optional[str] = None


class ReportResponse(BaseModel):
    analysis_id: str
    title: str
    generated_at: str
    json_data: Dict[str, Any]
    markdown_report: str


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    supported_languages: List[str]
    analyzers_active: List[str]
