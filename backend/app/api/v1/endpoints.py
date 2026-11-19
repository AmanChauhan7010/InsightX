import os
import io
import json
import zipfile
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.models.analysis import Analysis, Finding, RootCause, Recommendation
from backend.app.schemas.analysis import (
    AnalysisDetailResponse,
    AnalysisSummaryResponse,
    FindingResponse,
    RootCauseResponse,
    RecommendationResponse,
    RecommendationReviewUpdate,
    ReportResponse,
    HealthResponse,
    PasteCodeAnalysisRequest,
    FixPreviewRequest,
    FixPreviewResponse,
    FixApplyRequest,
    FixApplyResponse,
    RevisionSummaryResponse,
)
from backend.app.services.ingestion import IngestionService
from backend.app.services.orchestrator import AnalysisOrchestrator
from backend.app.autofix import (
    AutoFixRegistry,
    PatchGenerator,
    PatchValidator,
    FixReanalyzer,
)
from backend.app.reports.generator import ReportGenerator
from backend.app.analyzers.code.rule_registry import RuleRegistry
from backend.app.analyzers.metrics.anomaly_analyzer import MetricAnomalyAnalyzer

router = APIRouter()

@router.get("/rules")
def list_analysis_rules(language: Optional[str] = None):
    """Lists all implemented static analysis rules, severity policies, and limitations."""
    return {
        "supported_languages": ["python", "javascript", "typescript", "c", "cpp"],
        "rules": RuleRegistry.list_rules(language=language),
    }


@router.get("/autofix/rules")
def list_autofix_rules():
    """Lists all registered automatic fix rules, preconditions, safety checks, and unavailability reasons."""
    return {
        "ai_provider_configured": PatchGenerator.ai_provider_configured(),
        "default_http_timeout_seconds": settings.DEFAULT_HTTP_TIMEOUT_SECONDS,
        "rules": AutoFixRegistry.list_supported(),
    }

@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Health status and capabilities check."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "database": "sqlite_connected",
        "supported_languages": ["python", "javascript", "typescript", "c", "cpp"],
        "analyzers_active": [
            "PythonCodeAnalyzer",
            "JavaScriptCodeAnalyzer",
            "CCodeAnalyzer",
            "MetricAnomalyAnalyzer",
            "LogAnalyzer",
            "RootCauseEngine",
            "RecommendationEngine",
            "ExplanationEngine"
        ]
    }

@router.post("/analyses", response_model=AnalysisDetailResponse)
async def create_analysis(
    title: Optional[str] = Form("New Analysis"),
    mode: Optional[str] = Form("code"),
    files: Optional[List[UploadFile]] = File(None),
    metrics_file: Optional[UploadFile] = File(None),
    logs_file: Optional[UploadFile] = File(None),
    error_trace: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Primary analysis endpoint supporting:
    - Single or multiple source code files
    - ZIP archive project
    - Optional CSV/JSON metrics
    - Optional logs or traceback
    """
    code_files: List[Dict[str, Any]] = []

    if files:
        for f in files:
            content_bytes = await f.read()
            if not content_bytes or not content_bytes.strip():
                raise HTTPException(status_code=400, detail=f"Uploaded file '{f.filename}' is empty.")

            # Check if ZIP archive
            if f.filename.lower().endswith(".zip"):
                try:
                    zip_files = IngestionService.process_zip_archive(content_bytes)
                    code_files.extend(zip_files)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Invalid ZIP archive: {str(e)}")
            else:
                try:
                    file_info = IngestionService.process_single_file(f.filename, content_bytes)
                    code_files.append(file_info)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"File error '{f.filename}': {str(e)}")

    metrics_content = None
    metrics_filename = "metrics.csv"
    if metrics_file:
        b = await metrics_file.read()
        if not b or not b.strip():
            raise HTTPException(status_code=400, detail=f"Metrics file '{metrics_file.filename}' is empty.")
        try:
            metrics_content = IngestionService.read_text_safe(b)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        metrics_filename = metrics_file.filename

    logs_content = None
    logs_filename = "app.log"
    if logs_file:
        b = await logs_file.read()
        if not b or not b.strip():
            raise HTTPException(status_code=400, detail=f"Log file '{logs_file.filename}' is empty.")
        try:
            logs_content = IngestionService.read_text_safe(b)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        logs_filename = logs_file.filename

    if not code_files and not metrics_content and not logs_content and not error_trace:
        raise HTTPException(
            status_code=400,
            detail="No valid input provided. Upload source code, a project ZIP, metrics CSV/JSON, or log files."
        )

    # Validate malformed metrics early when metrics is the sole input
    if metrics_content and not code_files and not logs_content and not error_trace:
        precheck = MetricAnomalyAnalyzer().analyze(metrics_content, file_name=metrics_filename)
        if not precheck.get("valid", True):
            raise HTTPException(
                status_code=400,
                detail=precheck.get("validation_error") or "Malformed metrics file."
            )

    orchestrator = AnalysisOrchestrator(db)
    analysis = orchestrator.run_analysis(
        title=title,
        mode=mode,
        code_files=code_files,
        metrics_content=metrics_content,
        metrics_filename=metrics_filename,
        logs_content=logs_content,
        logs_filename=logs_filename,
        error_trace=error_trace
    )

    return analysis

@router.post("/analyses/paste", response_model=AnalysisDetailResponse)
def create_paste_analysis(
    payload: PasteCodeAnalysisRequest,
    db: Session = Depends(get_db)
):
    """Analyzes directly pasted source code snippet."""
    if not payload.code.strip():
        raise HTTPException(status_code=400, detail="Pasted code snippet cannot be empty.")

    lang = (payload.language or IngestionService.detect_language(payload.file_name or "snippet.py", payload.code)).lower()
    if lang not in ("python", "javascript", "typescript"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Supported languages for static analysis: python, javascript, typescript."
        )

    code_file = {
        "file_path": payload.file_name or "snippet.py",
        "filename": payload.file_name or "snippet.py",
        "content": payload.code,
        "language": lang,
        "lines_count": len(payload.code.splitlines()),
        "size_bytes": len(payload.code.encode("utf-8"))
    }

    orchestrator = AnalysisOrchestrator(db)
    analysis = orchestrator.run_analysis(
        title=payload.title or "Pasted Snippet Analysis",
        mode="code",
        code_files=[code_file],
        error_trace=payload.error_trace
    )
    return analysis

def _serialize_analysis_summary(a: Analysis) -> Dict[str, Any]:
    crit = sum(1 for f in a.findings if f.severity == "Critical")
    high = sum(1 for f in a.findings if f.severity == "High")
    med = sum(1 for f in a.findings if f.severity == "Medium")
    low = sum(1 for f in a.findings if f.severity == "Low")
    info = sum(1 for f in a.findings if f.severity == "Informational")
    meta = a.meta_info or {}
    file_names = meta.get("file_names") or list((a.source_snapshot or {}).keys())

    return {
        "id": a.id,
        "title": a.title,
        "mode": a.mode,
        "status": a.status,
        "created_at": a.created_at,
        "completed_at": a.completed_at,
        "files_count": a.files_count,
        "lines_of_code": a.lines_of_code,
        "summary": a.summary,
        "overall_score": a.overall_score,
        "critical_count": crit,
        "high_count": high,
        "medium_count": med,
        "low_count": low,
        "info_count": info,
        "findings_count": len(a.findings),
        "root_causes_count": len(a.root_causes),
        "recommendations_count": len(a.recommendations),
        "anomalies_count": len(a.metric_anomalies),
        "log_issues_count": len(a.log_issues),
        "file_names": file_names,
        "parent_analysis_id": a.parent_analysis_id,
        "root_analysis_id": a.root_analysis_id or a.id,
        "revision_number": a.revision_number or 1,
        "applied_recommendation_title": a.applied_recommendation_title,
        "error_message": a.error_message,
    }


@router.get("/analyses/recent", response_model=List[AnalysisSummaryResponse])
def list_recent_analyses(
    limit: int = Query(10, ge=1, le=50),
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Returns recent diagnoses ordered newest first, optionally filtered by analysis mode."""
    query = db.query(Analysis)
    if mode and mode.lower() != "all":
        query = query.filter(Analysis.mode == mode.lower())
    analyses = query.order_by(desc(Analysis.created_at)).limit(limit).all()
    return [_serialize_analysis_summary(a) for a in analyses]


@router.get("/analyses", response_model=List[AnalysisSummaryResponse])
def list_analyses(
    limit: int = Query(25, ge=1, le=100),
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists recent analyses with aggregated severity, finding, root-cause, and revision metadata."""
    query = db.query(Analysis)
    if mode and mode.lower() != "all":
        query = query.filter(Analysis.mode == mode.lower())
    analyses = query.order_by(desc(Analysis.created_at)).limit(limit).all()
    return [_serialize_analysis_summary(a) for a in analyses]

@router.get("/analyses/{analysis_id}", response_model=AnalysisDetailResponse)
def get_analysis_detail(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieves full analysis record with all findings, root causes, and recommendations."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")
    return analysis

@router.get("/analyses/{analysis_id}/findings", response_model=List[FindingResponse])
def get_analysis_findings(
    analysis_id: str,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Returns findings filtered by severity, category, or file path."""
    query = db.query(Finding).filter(Finding.analysis_id == analysis_id)
    if severity:
        query = query.filter(Finding.severity == severity)
    if category:
        query = query.filter(Finding.category == category)
    if file_path:
        query = query.filter(Finding.file_path == file_path)
    return query.all()

@router.get("/analyses/{analysis_id}/causes", response_model=List[RootCauseResponse])
def get_analysis_causes(analysis_id: str, db: Session = Depends(get_db)):
    """Returns ranked probable root causes for the analysis."""
    causes = db.query(RootCause).filter(RootCause.analysis_id == analysis_id).order_by(RootCause.rank).all()
    return causes

@router.get("/analyses/{analysis_id}/recommendations", response_model=List[RecommendationResponse])
def get_analysis_recommendations(analysis_id: str, db: Session = Depends(get_db)):
    """Returns prioritized recommendations for the analysis."""
    recs = db.query(Recommendation).filter(Recommendation.analysis_id == analysis_id).all()
    return recs

@router.patch("/analyses/{analysis_id}/recommendations/{rec_id}", response_model=RecommendationResponse)
def update_recommendation_status(
    analysis_id: str,
    rec_id: str,
    payload: RecommendationReviewUpdate,
    db: Session = Depends(get_db)
):
    """Marks a recommendation as reviewed or pending."""
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id,
        Recommendation.analysis_id == analysis_id
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    rec.reviewed = payload.reviewed
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/analyses/{analysis_id}/source")
def get_analysis_source(analysis_id: str, db: Session = Depends(get_db)):
    """Returns stored source files (working-copy snapshot) and hashes for viewing or downloading."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {
        "analysis_id": analysis.id,
        "revision_number": analysis.revision_number or 1,
        "files": analysis.source_snapshot or {},
    }


@router.get("/analyses/{analysis_id}/revisions", response_model=List[RevisionSummaryResponse])
def get_analysis_revisions(analysis_id: str, db: Session = Depends(get_db)):
    """Returns ordered revision history (v1, v2, v3...) for the analysis family."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    root_id = analysis.root_analysis_id or analysis.id
    revisions = (
        db.query(Analysis)
        .filter((Analysis.root_analysis_id == root_id) | (Analysis.id == root_id))
        .order_by(Analysis.revision_number, Analysis.created_at)
        .all()
    )
    return [
        {
            "id": r.id,
            "parent_analysis_id": r.parent_analysis_id,
            "root_analysis_id": r.root_analysis_id or r.id,
            "revision_number": r.revision_number or 1,
            "title": r.title,
            "created_at": r.created_at,
            "overall_score": r.overall_score,
            "findings_count": len(r.findings),
            "root_causes_count": len(r.root_causes),
            "recommendations_count": len(r.recommendations),
            "applied_recommendation_title": r.applied_recommendation_title,
            "status": r.status,
        }
        for r in revisions
    ]


@router.get("/analyses/{analysis_id}/revisions/compare")
def compare_analysis_revisions(
    analysis_id: str,
    other_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Compares an analysis revision against its parent (or another specified revision)."""
    after_a = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not after_a:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    before_id = other_id or after_a.parent_analysis_id
    if not before_id:
        raise HTTPException(status_code=400, detail="No parent or comparison revision specified.")
    before_a = db.query(Analysis).filter(Analysis.id == before_id).first()
    if not before_a:
        raise HTTPException(status_code=404, detail="Comparison analysis revision not found.")
    return FixReanalyzer.compute_comparison(before_a, after_a)


@router.post("/analyses/{analysis_id}/fixes/preview", response_model=FixPreviewResponse)
def preview_recommendation_fix(
    analysis_id: str,
    payload: FixPreviewRequest,
    db: Session = Depends(get_db),
):
    """Generates a safe, AST-validated before/after patch preview against the stored working copy."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    rec = db.query(Recommendation).filter(
        Recommendation.id == payload.recommendation_id,
        Recommendation.analysis_id == analysis_id,
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found for this analysis.")

    snapshot = analysis.source_snapshot or {}
    file_path = rec.file_path
    if not file_path or file_path not in snapshot:
        raise HTTPException(
            status_code=400,
            detail="Stored source snapshot is not available for this analysis (re-run analysis to enable safe patching).",
        )

    original_code = snapshot[file_path]["content"]
    related_ids = set(rec.related_finding_ids or [])
    target_lines = [
        f.line_number for f in analysis.findings
        if f.id in related_ids and f.line_number is not None
    ]

    preview = PatchGenerator.generate_patch(
        rule_id=rec.rule_id,
        file_path=file_path,
        original_code=original_code,
        target_lines=target_lines,
        original_snippet=rec.original_code or "",
        options=payload.options,
    )

    return {
        "analysis_id": analysis.id,
        "recommendation_id": rec.id,
        "recommendation_title": rec.title,
        "rule_id": rec.rule_id,
        "file_path": file_path,
        "auto_fixable": preview["auto_fixable"],
        "manual_fix_reason": preview["manual_fix_reason"],
        "ai_fix_available": preview.get("ai_fix_available", False),
        "source_hash": preview["source_hash"],
        "original_code": preview["original_code"],
        "patched_code": preview["patched_code"],
        "diff": preview["diff"],
    }


@router.post("/analyses/{analysis_id}/fixes/apply", response_model=FixApplyResponse)
def apply_recommendation_fix(
    analysis_id: str,
    payload: FixApplyRequest,
    db: Session = Depends(get_db),
):
    """
    Safely applies a validated auto-fix (or user-edited code) to an isolated working copy,
    re-runs the real backend analysis engine, persists a linked revision while preserving
    the original analysis, and returns a factual before/after comparison.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    snapshot = analysis.source_snapshot or {}
    if not snapshot:
        raise HTTPException(
            status_code=400,
            detail="Stored source snapshot is not available for this analysis; re-run analysis first.",
        )

    rec = None
    if payload.recommendation_id:
        rec = db.query(Recommendation).filter(
            Recommendation.id == payload.recommendation_id,
            Recommendation.analysis_id == analysis_id,
        ).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found for this analysis.")

    target_file = payload.file_path or (rec.file_path if rec else next(iter(snapshot.keys())))
    if target_file not in snapshot:
        raise HTTPException(status_code=400, detail=f"Target file '{target_file}' not found in analysis source snapshot.")

    original_code = snapshot[target_file]["content"]

    # Reject stale patches if source hash does not match
    hash_check = PatchValidator.validate_hash(original_code, payload.expected_source_hash)
    if not hash_check.valid:
        raise HTTPException(status_code=409, detail=hash_check.error)

    if payload.custom_code is not None:
        custom_check = PatchValidator.validate_patch(
            file_path=target_file,
            original_source=original_code,
            patched_source=payload.custom_code,
            require_change=False,
            require_valid_syntax=False,  # Allow manual re-analysis of syntax errors so regression is reported honestly
        )
        if not custom_check.valid:
            raise HTTPException(status_code=400, detail=custom_check.error)
        patched_code = payload.custom_code
        applied_title = (rec.title + " (Manual Edit)") if rec else f"Manual Edit on {target_file}"
    else:
        if not rec:
            raise HTTPException(status_code=400, detail="Either recommendation_id or custom_code must be provided.")
        related_ids = set(rec.related_finding_ids or [])
        target_lines = [
            f.line_number for f in analysis.findings
            if f.id in related_ids and f.line_number is not None
        ]
        preview = PatchGenerator.generate_patch(
            rule_id=rec.rule_id,
            file_path=target_file,
            original_code=original_code,
            target_lines=target_lines,
            original_snippet=rec.original_code or "",
            options=payload.options,
        )
        if not preview["auto_fixable"] or not preview["patched_code"]:
            patched_code = preview.get("patched_code")
            if not patched_code and (target_file.endswith(".py") or not target_file):
                repaired = PatchGenerator._repair_syntax(original_code, target_file, target_lines)
                if not repaired or repaired == original_code:
                    repaired, _ = PatchGenerator._transform_undefined_name(original_code, target_file, target_lines)
                if repaired and repaired != original_code:
                    patched_code = repaired
            if not patched_code:
                raise HTTPException(
                    status_code=422,
                    detail=preview["manual_fix_reason"] or "Auto Fix Unavailable for this finding; apply manually and re-analyze.",
                )
        else:
            patched_code = preview["patched_code"]
        applied_title = rec.title

    return FixReanalyzer.apply_and_reanalyze(
        db=db,
        original_analysis=analysis,
        target_file=target_file,
        patched_code=patched_code,
        applied_title=applied_title,
        recommendation=rec,
    )

@router.get("/analyses/{analysis_id}/evidence")
def get_analysis_evidence(analysis_id: str, db: Session = Depends(get_db)):
    """Returns evidence checklist and uncertainty audit trail."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    meta = analysis.meta_info or {}
    bundle = meta.get("explanation_bundle", {})
    return {
        "analysis_id": analysis.id,
        "evidence_checklist": bundle.get("evidence_checklist", []),
        "uncertainty_statement": bundle.get("uncertainty_statement", ""),
        "methodology_disclaimer": bundle.get("methodology_disclaimer", ""),
        "llm_enhanced": bundle.get("llm_enhanced", False),
        "llm_notes": bundle.get("llm_notes")
    }

@router.get("/analyses/{analysis_id}/report", response_model=ReportResponse)
def get_analysis_report(analysis_id: str, db: Session = Depends(get_db)):
    """Generates structured JSON and Markdown reports."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    json_data = ReportGenerator.generate_json_report(analysis)
    markdown_report = ReportGenerator.generate_markdown_report(analysis)
    return {
        "analysis_id": analysis.id,
        "title": analysis.title,
        "generated_at": str(analysis.completed_at or analysis.created_at),
        "json_data": json_data,
        "markdown_report": markdown_report
    }

@router.get("/analyses/{analysis_id}/report/download")
def download_markdown_report(analysis_id: str, db: Session = Depends(get_db)):
    """Downloads human-readable markdown report as an attachment."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    markdown_report = ReportGenerator.generate_markdown_report(analysis)
    filename = f"insightx-report-{analysis.id[:8]}.md"
    return Response(
        content=markdown_report,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/sample-cases")
def list_sample_cases():
    """Lists preconfigured demonstration cases."""
    return [
        {
            "id": "case_a_python_async",
            "name": "Case A: Python Async Event Loop Blocking",
            "mode": "code",
            "description": "Payment microservice with synchronous time.sleep blocking asyncio event loop, unclosed database connection leak, and mutable default arguments.",
            "file_count": 1,
            "tags": ["Python", "AsyncIO", "Concurrency", "Resource Leak"]
        },
        {
            "id": "case_b_project_zip",
            "name": "Case B: Multi-File Project with Dependency Flaws",
            "mode": "code",
            "description": "Multi-module repository with cross-file imports, circular dependency hazards, and unhandled division by zero.",
            "file_count": 3,
            "tags": ["Multi-File", "Call Graph", "Architecture", "Python"]
        },
        {
            "id": "case_c_system_anomaly",
            "name": "Case C: Multivariate System Metrics Anomaly",
            "mode": "metrics_logs",
            "description": "Multi-variate telemetry time series exhibiting severe CPU saturation and P95 latency spikes isolated via Isolation Forest.",
            "file_count": 1,
            "tags": ["Isolation Forest", "Z-Score", "Telemetry", "Time-Series"]
        },
        {
            "id": "case_d_combined",
            "name": "Case D: Combined RCA (Code + Production Logs)",
            "mode": "combined",
            "description": "Payment service combined with RFC 5424 logs showing 504 Gateway Timeouts and database pool starvation matching code defects.",
            "file_count": 2,
            "tags": ["Multimodal RCA", "Logs Correlation", "Stack Trace", "End-to-End"]
        }
    ]

@router.post("/sample-cases/{case_id}/load", response_model=AnalysisDetailResponse)
def load_sample_case(case_id: str, db: Session = Depends(get_db)):
    """Instantly executes and loads one of the pre-configured realistic demonstration cases."""
    orchestrator = AnalysisOrchestrator(db)

    if case_id == "case_a_python_async":
        code = (
            "import asyncio\n"
            "import time\n"
            "import sqlite3\n\n"
            "# Payment Gateway Microservice\n"
            "transaction_history = []  # Global unbounded memory accumulation\n\n"
            "def get_database_connection():\n"
            "    # Bug: Resource instantiated without context manager or guaranteed finally close\n"
            "    conn = sqlite3.connect('payments.db')\n"
            "    return conn\n\n"
            "async def process_payment(user_id: int, amount: float, audit_log=[]):\n"
            "    # Bug 1: Mutable default container\n"
            "    audit_log.append({'user': user_id, 'amount': amount})\n"
            "    transaction_history.append({'user': user_id, 'amount': amount})\n\n"
            "    # Bug 2: Blocking synchronous call in async function\n"
            "    print(f'Starting settlement for {user_id}...')\n"
            "    time.sleep(2.5)  # Freezes the entire asyncio event loop!\n\n"
            "    # Bug 3: Unhandled division by zero\n"
            "    fee_ratio = amount / user_id\n\n"
            "    conn = get_database_connection()\n"
            "    cursor = conn.cursor()\n"
            "    # Bug 4: SQL injection vulnerability\n"
            "    cursor.execute(f'UPDATE balances SET balance = balance - {amount} WHERE id = {user_id}')\n"
            "    conn.commit()\n"
            "    # conn is never closed!\n"
            "    return {'status': 'success', 'fee': fee_ratio}\n"
        )
        code_file = {
            "file_path": "payment_service.py",
            "filename": "payment_service.py",
            "content": code,
            "language": "python",
            "lines_count": len(code.splitlines()),
            "size_bytes": len(code.encode("utf-8"))
        }
        return orchestrator.run_analysis(
            title="Demonstration: Payment Service Async Blocking & Leak",
            mode="code",
            code_files=[code_file]
        )

    elif case_id == "case_b_project_zip":
        # Multi-file project
        f1_code = (
            "import math\n"
            "from service.worker import execute_task\n\n"
            "def run_coordinator(task_id: int, divisor: int):\n"
            "    # Division without zero check\n"
            "    ratio = 1000 / divisor\n"
            "    return execute_task(task_id, ratio)\n"
        )
        f2_code = (
            "import os\n"
            "from service.db import query_user\n\n"
            "API_TOKEN = 'secret_live_tok_991823719283'\n\n"
            "def execute_task(task_id: int, weight: float):\n"
            "    user_data = query_user(task_id)\n"
            "    return {'task': task_id, 'weight': weight, 'user': user_data}\n"
        )
        f3_code = (
            "import sqlite3\n\n"
            "def query_user(user_id: int):\n"
            "    conn = sqlite3.connect('app.db')\n"
            "    cursor = conn.cursor()\n"
            "    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
            "    return cursor.fetchone()\n"
        )
        files = [
            {"file_path": "service/coordinator.py", "filename": "coordinator.py", "content": f1_code, "language": "python", "lines_count": len(f1_code.splitlines()), "size_bytes": len(f1_code.encode("utf-8"))},
            {"file_path": "service/worker.py", "filename": "worker.py", "content": f2_code, "language": "python", "lines_count": len(f2_code.splitlines()), "size_bytes": len(f2_code.encode("utf-8"))},
            {"file_path": "service/db.py", "filename": "db.py", "content": f3_code, "language": "python", "lines_count": len(f3_code.splitlines()), "size_bytes": len(f3_code.encode("utf-8"))}
        ]
        return orchestrator.run_analysis(
            title="Demonstration: Multi-Module Project Architecture",
            mode="code",
            code_files=files
        )

    elif case_id == "case_c_system_anomaly":
        # CSV Metrics with deliberate anomalies
        csv_rows = ["timestamp,cpu_utilization,memory_usage_mb,p95_latency_ms,active_connections"]
        for i in range(30):
            t = f"2026-11-15T12:{i:02d}:00Z"
            if 15 <= i <= 22:
                # Anomaly window: CPU spike to 98%, latency spike to 4200ms
                csv_rows.append(f"{t},98.4,1850.2,4250.0,490")
            else:
                csv_rows.append(f"{t},{25.0 + (i % 5)},450.0,{45.0 + (i % 8)},25")
        csv_content = "\n".join(csv_rows)

        return orchestrator.run_analysis(
            title="Demonstration: Telemetry CPU & Latency Saturation",
            mode="metrics_logs",
            metrics_content=csv_content,
            metrics_filename="cluster_telemetry.csv"
        )

    elif case_id == "case_d_combined":
        # Code + Matching Logs
        code = (
            "import asyncio\n"
            "import time\n"
            "import sqlite3\n\n"
            "async def handle_checkout(order_id: int, customer_id: int):\n"
            "    print(f'Starting checkout for order {order_id}')\n"
            "    time.sleep(3.0)  # Blocking sync call causing Gateway Timeout\n"
            "    conn = sqlite3.connect('orders.db')\n"
            "    cursor = conn.cursor()\n"
            "    cursor.execute('SELECT balance FROM accounts WHERE id = ?', (customer_id,))\n"
            "    # conn.close() missing\n"
            "    return {'order_id': order_id, 'status': 'placed'}\n"
        )
        logs = (
            "2026-11-15 12:15:02 [checkout-api] INFO Starting checkout worker pool\n"
            "2026-11-15 12:15:32 [checkout-api] WARN Worker event loop lag exceeded 2850ms threshold\n"
            "2026-11-15 12:16:05 [ingress-gw] ERROR 504 Gateway Timeout: upstream service failed to respond within 3000ms\n"
            "2026-11-15 12:16:15 [checkout-api] CRITICAL Traceback (most recent call last):\n"
            '  File "checkout_service.py", line 7, in handle_checkout\n'
            "    time.sleep(3.0)\n"
            "TimeoutError: Request exceeded 3.00s deadline\n"
            "2026-11-15 12:16:22 [checkout-api] ERROR OperationalError: connection pool exhausted (active_connections=500/500)\n"
        )
        code_file = {
            "file_path": "checkout_service.py",
            "filename": "checkout_service.py",
            "content": code,
            "language": "python",
            "lines_count": len(code.splitlines()),
            "size_bytes": len(code.encode("utf-8"))
        }
        return orchestrator.run_analysis(
            title="Demonstration: Combined Multimodal Root Cause Investigation",
            mode="combined",
            code_files=[code_file],
            logs_content=logs,
            logs_filename="service_failures.log"
        )

    else:
        raise HTTPException(status_code=404, detail=f"Sample case '{case_id}' not found.")
