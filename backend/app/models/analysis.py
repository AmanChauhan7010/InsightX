import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

def utc_now():
    return datetime.now(timezone.utc)

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False, default="Untitled Analysis")
    mode = Column(String(50), nullable=False, default="code")  # code, metrics_logs, combined
    status = Column(String(50), nullable=False, default="completed")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
    
    files_count = Column(Integer, default=1)
    lines_of_code = Column(Integer, default=0)
    summary = Column(Text, nullable=True)
    overall_score = Column(Float, default=100.0)  # 0 to 100 health score
    error_message = Column(Text, nullable=True)
    meta_info = Column(JSON, default=dict)

    # Revision lineage & isolated source snapshot (never modifies original analysis)
    parent_analysis_id = Column(String(36), nullable=True)
    root_analysis_id = Column(String(36), nullable=True)
    revision_number = Column(Integer, default=1)
    applied_recommendation_id = Column(String(36), nullable=True)
    applied_recommendation_title = Column(String(255), nullable=True)
    source_snapshot = Column(JSON, default=dict)

    # Relationships
    findings = relationship("Finding", back_populates="analysis", cascade="all, delete-orphan", order_by="Finding.line_number")
    root_causes = relationship("RootCause", back_populates="analysis", cascade="all, delete-orphan", order_by="RootCause.rank")
    recommendations = relationship("Recommendation", back_populates="analysis", cascade="all, delete-orphan")
    relationships = relationship("Relationship", back_populates="analysis", cascade="all, delete-orphan")
    metric_anomalies = relationship("MetricAnomaly", back_populates="analysis", cascade="all, delete-orphan")
    log_issues = relationship("LogIssue", back_populates="analysis", cascade="all, delete-orphan")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)  # Critical, High, Medium, Low, Informational
    file_path = Column(String(500), nullable=False)
    line_number = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)
    code_snippet = Column(Text, nullable=True)
    
    description = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)
    evidence_category = Column(String(60), default="Static Code Evidence")
    rule_id = Column(String(100), nullable=True)
    severity_rationale = Column(Text, nullable=True)
    detection_method = Column(String(255), default="Static AST Analysis")
    potential_consequences = Column(Text, nullable=True)
    suggested_next_step = Column(Text, nullable=True)
    is_confirmed = Column(Boolean, default=False)
    language = Column(String(50), default="python")

    analysis = relationship("Analysis", back_populates="findings")


class RootCause(Base):
    __tablename__ = "root_causes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    
    rank = Column(Integer, default=1)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(String(50), default="Medium")  # High, Medium, Low
    confidence_score = Column(Float, default=0.75)  # Internal ranking score (not presented as probability)
    evidence_category = Column(String(60), default="Static Code Evidence")
    cause_type = Column(String(80), default="Static Potential Cause")
    
    affected_files = Column(JSON, default=list)
    affected_functions = Column(JSON, default=list)
    related_finding_ids = Column(JSON, default=list)
    
    evidence_summary = Column(Text, nullable=True)
    ranking_rationale = Column(Text, nullable=True)
    consequences = Column(Text, nullable=True)
    recommended_actions_summary = Column(Text, nullable=True)
    missing_evidence = Column(Text, nullable=True)
    alternative_explanations = Column(Text, nullable=True)

    analysis = relationship("Analysis", back_populates="root_causes")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    
    priority = Column(String(50), default="P2 - High")  # P1 - Immediate, P2 - High, P3 - Medium, P4 - Low
    title = Column(String(255), nullable=False)
    problem_addressed = Column(Text, nullable=False)
    why_recommended = Column(Text, nullable=False)
    expected_benefit = Column(Text, nullable=False)
    verification_instructions = Column(Text, nullable=True)
    
    related_finding_ids = Column(JSON, default=list)
    related_cause_ids = Column(JSON, default=list)
    rule_id = Column(String(100), nullable=True)
    auto_fixable = Column(Boolean, default=False)
    manual_fix_reason = Column(Text, nullable=True)
    simple_explanation = Column(JSON, default=dict)
    technical_explanation = Column(JSON, default=dict)
    file_path = Column(String(500), nullable=True)
    original_code = Column(Text, nullable=True)
    refactored_code = Column(Text, nullable=True)
    diff = Column(Text, nullable=True)
    reviewed = Column(Boolean, default=False)

    analysis = relationship("Analysis", back_populates="recommendations")


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    
    source = Column(String(255), nullable=False)
    target = Column(String(255), nullable=False)
    relationship_type = Column(String(100), default="calls")  # imports, calls, triggers, depends_on
    details = Column(String(500), nullable=True)

    analysis = relationship("Analysis", back_populates="relationships")


class MetricAnomaly(Base):
    __tablename__ = "metric_anomalies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    
    timestamp = Column(String(100), nullable=False)
    metric_name = Column(String(100), nullable=False)
    observed_value = Column(Float, nullable=False)
    baseline_mean = Column(Float, nullable=True)
    baseline_std = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=False)
    severity = Column(String(50), default="High")

    analysis = relationship("Analysis", back_populates="metric_anomalies")


class LogIssue(Base):
    __tablename__ = "log_issues"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    
    timestamp = Column(String(100), nullable=True)
    level = Column(String(50), default="ERROR")
    message = Column(Text, nullable=False)
    service = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=True)
    line_number = Column(Integer, nullable=True)
    count = Column(Integer, default=1)

    analysis = relationship("Analysis", back_populates="log_issues")
