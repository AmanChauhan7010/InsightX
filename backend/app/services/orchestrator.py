import ast
import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session

from backend.app.analyzers.code.python_analyzer import PythonCodeAnalyzer
from backend.app.analyzers.code.js_analyzer import JavaScriptCodeAnalyzer
from backend.app.analyzers.code.c_analyzer import CCodeAnalyzer
from backend.app.analyzers.metrics.anomaly_analyzer import MetricAnomalyAnalyzer
from backend.app.analyzers.logs.log_analyzer import LogAnalyzer
from backend.app.rca.engine import RootCauseEngine
from backend.app.recommendations.engine import RecommendationEngine
from backend.app.explanations.engine import ExplanationEngine
from backend.app.services.scoring import HealthScoreCalculator, EvidenceCategory
from backend.app.services.fix_engine import sha256_text
from backend.app.models.analysis import (
    Analysis, Finding, RootCause, Recommendation, Relationship, MetricAnomaly, LogIssue
)


class AnalysisOrchestrator:
    """
    Main Orchestrator executing the 4-stage InsightX workflow:
    STAGE 1: DETECT (AST parsing, cross-file symbol discovery, metric anomaly detection, log parsing)
    STAGE 2: DIAGNOSE (Multimodal causal correlation & root-cause ranking)
    STAGE 3: RECOMMEND (Prioritized corrective actions & before/after diffs)
    STAGE 4: EXPLAIN (Explainable AI narrative, categorized evidence, & transparent scoring)
    """

    def __init__(self, db: Session):
        self.db = db
        self.py_analyzer = PythonCodeAnalyzer()
        self.js_analyzer = JavaScriptCodeAnalyzer()
        self.c_analyzer = CCodeAnalyzer()
        self.metrics_analyzer = MetricAnomalyAnalyzer()
        self.log_analyzer = LogAnalyzer()
        self.rca_engine = RootCauseEngine()
        self.rec_engine = RecommendationEngine()
        self.explanation_engine = ExplanationEngine()

    def _prescan_python_async_exports(self, code_files: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """Extracts top-level `async def` exports per module stem across multi-file Python uploads."""
        exports: Dict[str, Set[str]] = {}
        for cf in code_files:
            if cf.get("language") != "python":
                continue
            try:
                tree = ast.parse(cf["content"], filename=cf["file_path"])
            except SyntaxError:
                continue
            async_names = {
                stmt.name for stmt in tree.body if isinstance(stmt, ast.AsyncFunctionDef)
            }
            if async_names:
                rel_no_ext = os.path.splitext(cf["file_path"])[0]
                dotted = rel_no_ext.replace("/", ".")
                stem = os.path.basename(rel_no_ext)
                exports.setdefault(dotted, set()).update(async_names)
                exports.setdefault(stem, set()).update(async_names)
        return exports

    def run_analysis(
        self,
        title: str = "Analysis",
        mode: str = "code",
        code_files: List[Dict[str, Any]] = None,
        metrics_content: Optional[str] = None,
        metrics_filename: str = "metrics.csv",
        logs_content: Optional[str] = None,
        logs_filename: str = "app.log",
        error_trace: Optional[str] = None,
        parent_analysis_id: Optional[str] = None,
        root_analysis_id: Optional[str] = None,
        revision_number: int = 1,
        applied_recommendation_id: Optional[str] = None,
        applied_recommendation_title: Optional[str] = None,
    ) -> Analysis:
        code_files = code_files or []

        analysis_id = str(uuid.uuid4())
        source_snapshot = {
            cf["file_path"]: {
                "content": cf["content"],
                "language": cf["language"],
                "sha256": sha256_text(cf["content"]),
            }
            for cf in code_files
        }
        analysis = Analysis(
            id=analysis_id,
            title=title,
            mode=mode,
            status="processing",
            created_at=datetime.now(timezone.utc),
            files_count=len(code_files) or (1 if metrics_content or logs_content else 0),
            lines_of_code=sum(f.get("lines_count", 0) for f in code_files),
            parent_analysis_id=parent_analysis_id,
            root_analysis_id=root_analysis_id or analysis_id,
            revision_number=revision_number,
            applied_recommendation_id=applied_recommendation_id,
            applied_recommendation_title=applied_recommendation_title,
            source_snapshot=source_snapshot,
        )
        self.db.add(analysis)
        self.db.commit()

        try:
            # -------------------------------------------------------------
            # STAGE 1: DETECT
            # -------------------------------------------------------------
            all_findings: List[Dict[str, Any]] = []
            all_relationships: List[Dict[str, Any]] = []
            files_map: Dict[str, str] = {}
            incomplete_files: List[str] = []

            # Cross-file async symbol map for multi-file Python repositories
            external_async_symbols = (
                self._prescan_python_async_exports(code_files) if len(code_files) > 1 else {}
            )

            for cf in code_files:
                f_path = cf["file_path"]
                content = cf["content"]
                lang = cf["language"]
                files_map[f_path] = content

                if lang == "python":
                    res = self.py_analyzer.analyze(
                        content,
                        file_path=f_path,
                        external_async_symbols=external_async_symbols,
                    )
                    if not res.get("ast_parsed", True):
                        incomplete_files.append(f_path)
                    all_findings.extend(res["findings"])
                    all_relationships.extend(res["relationships"])

                    # Modular Logical Error Detection & Test Case Verification
                    if res.get("ast_parsed", True):
                        try:
                            from backend.app.analyzers.logical import LogicalErrorDetector
                            log_findings, log_rels = LogicalErrorDetector.detect(content, file_path=f_path)
                            all_findings.extend(log_findings)
                            all_relationships.extend(log_rels)
                        except Exception:
                            # Completely isolated: logical evaluation failure never impacts base pipeline
                            pass
                elif lang in ("javascript", "typescript"):
                    res = self.js_analyzer.analyze(content, file_path=f_path)
                    all_findings.extend(res["findings"])
                    all_relationships.extend(res["relationships"])
                elif lang in ("c", "cpp"):
                    res = self.c_analyzer.analyze(content, file_path=f_path)
                    all_findings.extend(res["findings"])
                    all_relationships.extend(res["relationships"])

            # Assign unique UUIDs to every finding BEFORE RCA & Recommendation stages
            for f_data in all_findings:
                f_data["id"] = str(uuid.uuid4())
                if not f_data.get("evidence_category"):
                    f_data["evidence_category"] = EvidenceCategory.STATIC_CODE

            metric_results: Dict[str, Any] = {"valid": True, "anomalies": []}
            if metrics_content is not None:
                metric_results = self.metrics_analyzer.analyze(metrics_content, file_name=metrics_filename)

            log_results: Dict[str, Any] = {"valid": True, "issues": [], "stack_traces": []}
            if logs_content or error_trace:
                combined_logs = (logs_content or "") + ("\n" + error_trace if error_trace else "")
                log_results = self.log_analyzer.analyze(combined_logs, file_name=logs_filename)

            metric_anomalies = metric_results.get("anomalies", [])
            log_issues = log_results.get("issues", [])
            stack_traces = log_results.get("stack_traces", [])

            incomplete_parse = bool(
                incomplete_files
                or (metrics_content is not None and not metric_results.get("valid", True))
                or ((logs_content or error_trace) and not log_results.get("valid", True))
            )

            # -------------------------------------------------------------
            # STAGE 2: DIAGNOSE (Root Cause Analysis)
            # -------------------------------------------------------------
            raw_root_causes = self.rca_engine.diagnose(
                findings=all_findings,
                relationships=all_relationships,
                metric_anomalies=metric_anomalies,
                log_issues=log_issues,
                stack_traces=stack_traces,
                mode=mode,
            )

            # Strict invariant: only retain root causes backed by real findings or real telemetry/log evidence
            valid_finding_id_set = {f_data["id"] for f_data in all_findings}
            has_telemetry_or_log_evidence = bool(
                metric_anomalies
                or stack_traces
                or any((l.get("level") or "").upper() in ("CRITICAL", "ERROR") for l in log_issues)
            )
            root_causes: List[Dict[str, Any]] = []
            for rc_data in raw_root_causes:
                linked_findings = [fid for fid in rc_data.get("related_finding_ids", []) if fid in valid_finding_id_set]
                ev_cat = rc_data.get("evidence_category", EvidenceCategory.STATIC_CODE)
                if linked_findings or (
                    has_telemetry_or_log_evidence
                    and ev_cat in (EvidenceCategory.METRICS, EvidenceCategory.LOG, EvidenceCategory.RUNTIME, EvidenceCategory.CORRELATED)
                ):
                    rc_data["related_finding_ids"] = linked_findings
                    rc_data["id"] = str(uuid.uuid4())
                    root_causes.append(rc_data)

            for idx, rc_data in enumerate(root_causes, 1):
                rc_data["rank"] = idx

            # -------------------------------------------------------------
            # STAGE 3: RECOMMEND
            # -------------------------------------------------------------
            recommendations = self.rec_engine.generate_recommendations(
                findings=all_findings,
                files_map=files_map,
                root_causes=root_causes,
            )

            # -------------------------------------------------------------
            # STAGE 4: EXPLAIN & TRANSPARENT HEALTH SCORE
            # -------------------------------------------------------------
            score_breakdown = HealthScoreCalculator.compute(
                findings=all_findings,
                metric_anomalies=metric_anomalies,
                log_issues=log_issues,
                files_count=analysis.files_count,
                mode=mode,
                incomplete_parse=incomplete_parse,
            )
            overall_score = score_breakdown["score"]

            summary_text = (
                f"Completed {mode.replace('_', ' ').title()} analysis across {analysis.files_count} artifact(s). "
                f"Detected {len(all_findings)} code finding(s), {len(metric_anomalies)} metric anomaly event(s), "
                f"and {len(log_issues)} log issue group(s)."
            )
            if log_results.get("limitation"):
                summary_text += f" Note: {log_results['limitation']}"
            if metric_results.get("validation_error"):
                summary_text += f" Note: {metric_results['validation_error']}"

            explanation_bundle = self.explanation_engine.explain(
                analysis_summary=summary_text,
                findings=all_findings,
                root_causes=root_causes,
                recommendations=recommendations,
                metric_anomalies=metric_anomalies,
                log_issues=log_issues,
                stack_traces=stack_traces,
                score_breakdown=score_breakdown,
            )

            # -------------------------------------------------------------
            # PERSIST TO DATABASE
            # -------------------------------------------------------------
            analysis.status = "completed"
            analysis.completed_at = datetime.now(timezone.utc)
            analysis.summary = explanation_bundle["narrative"]
            analysis.overall_score = overall_score
            analysis.meta_info = {
                "explanation_bundle": explanation_bundle,
                "score_breakdown": score_breakdown,
                "evidence_categories_present": explanation_bundle.get("evidence_categories_present", []),
                "incomplete_files": incomplete_files,
                "metrics_summary": metric_results.get("summary"),
                "metrics_series": metric_results.get("time_series", []),
                "metrics_intervals": metric_results.get("anomalous_intervals", []),
                "metrics_data_quality": metric_results.get("data_quality", {}),
                "metrics_analyzed": metric_results.get("metrics_analyzed", []),
                "metrics_validation_error": metric_results.get("validation_error"),
                "logs_summary": log_results.get("summary"),
                "logs_limitation": log_results.get("limitation"),
                "logs_repeated_patterns": log_results.get("repeated_patterns", []),
                "file_names": [cf["file_path"] for cf in code_files]
                or ([metrics_filename] if metrics_content else [])
                + ([logs_filename] if logs_content else []),
                "raw_metrics_content": metrics_content if (metrics_content and len(metrics_content) <= 500_000) else None,
                "raw_metrics_filename": metrics_filename if metrics_content else None,
                "raw_logs_content": logs_content if (logs_content and len(logs_content) <= 500_000) else None,
                "raw_logs_filename": logs_filename if logs_content else None,
            }

            valid_finding_ids = {f_data["id"] for f_data in all_findings}
            valid_cause_ids = {rc_data["id"] for rc_data in root_causes}

            for f_data in all_findings:
                self.db.add(Finding(
                    id=f_data["id"],
                    analysis_id=analysis_id,
                    title=f_data["title"],
                    category=f_data["category"],
                    severity=f_data["severity"],
                    file_path=f_data["file_path"],
                    line_number=f_data.get("line_number"),
                    line_end=f_data.get("line_end"),
                    code_snippet=f_data.get("code_snippet"),
                    description=f_data["description"],
                    evidence=f_data["evidence"],
                    evidence_category=f_data.get("evidence_category", EvidenceCategory.STATIC_CODE),
                    rule_id=f_data.get("rule_id"),
                    severity_rationale=f_data.get("severity_rationale"),
                    detection_method=f_data.get("detection_method", "Static AST Analysis"),
                    potential_consequences=f_data.get("potential_consequences"),
                    suggested_next_step=f_data.get("suggested_next_step"),
                    is_confirmed=f_data.get("is_confirmed", False),
                    language=f_data.get("language", "python"),
                ))

            for rc_data in root_causes:
                rel_ids = [fid for fid in rc_data.get("related_finding_ids", []) if fid in valid_finding_ids]
                self.db.add(RootCause(
                    id=rc_data["id"],
                    analysis_id=analysis_id,
                    rank=rc_data["rank"],
                    title=rc_data["title"],
                    description=rc_data["description"],
                    confidence=rc_data["confidence"],
                    confidence_score=rc_data["confidence_score"],
                    evidence_category=rc_data.get("evidence_category", EvidenceCategory.STATIC_CODE),
                    cause_type=rc_data.get("cause_type", "Static Potential Cause"),
                    affected_files=rc_data.get("affected_files", []),
                    affected_functions=rc_data.get("affected_functions", []),
                    related_finding_ids=rel_ids,
                    evidence_summary=rc_data.get("evidence_summary"),
                    ranking_rationale=rc_data.get("ranking_rationale"),
                    consequences=rc_data.get("consequences"),
                    recommended_actions_summary=rc_data.get("recommended_actions_summary"),
                    missing_evidence=rc_data.get("missing_evidence"),
                    alternative_explanations=rc_data.get("alternative_explanations"),
                ))

            for r_data in recommendations:
                rel_f_ids = [fid for fid in r_data.get("related_finding_ids", []) if fid in valid_finding_ids]
                rel_c_ids = [cid for cid in r_data.get("related_cause_ids", []) if cid in valid_cause_ids]
                self.db.add(Recommendation(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    priority=r_data["priority"],
                    title=r_data["title"],
                    problem_addressed=r_data["problem_addressed"],
                    why_recommended=r_data["why_recommended"],
                    expected_benefit=r_data["expected_benefit"],
                    verification_instructions=r_data.get("verification_instructions"),
                    related_finding_ids=rel_f_ids,
                    related_cause_ids=rel_c_ids,
                    rule_id=r_data.get("rule_id"),
                    auto_fixable=bool(r_data.get("auto_fixable", False)),
                    manual_fix_reason=r_data.get("manual_fix_reason"),
                    simple_explanation=r_data.get("simple_explanation") or {},
                    technical_explanation=r_data.get("technical_explanation") or {},
                    file_path=r_data.get("file_path"),
                    original_code=r_data.get("original_code"),
                    refactored_code=r_data.get("refactored_code"),
                    diff=r_data.get("diff"),
                    reviewed=r_data.get("reviewed", False),
                ))

            for rel in all_relationships:
                self.db.add(Relationship(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    source=rel["source"],
                    target=rel["target"],
                    relationship_type=rel["relationship_type"],
                    details=rel.get("details"),
                ))

            for a_data in metric_anomalies:
                self.db.add(MetricAnomaly(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    timestamp=a_data["timestamp"],
                    metric_name=a_data["metric_name"],
                    observed_value=a_data["observed_value"],
                    baseline_mean=a_data.get("baseline_mean"),
                    baseline_std=a_data.get("baseline_std"),
                    anomaly_score=a_data["anomaly_score"],
                    severity=a_data.get("severity", "High"),
                ))

            for l_data in log_issues:
                self.db.add(LogIssue(
                    id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    timestamp=l_data.get("timestamp"),
                    level=l_data["level"],
                    message=l_data["message"],
                    service=l_data.get("service"),
                    file_path=l_data.get("file_path"),
                    line_number=l_data.get("line_number"),
                    count=l_data.get("count", 1),
                ))

            self.db.commit()
            self.db.refresh(analysis)
            return analysis

        except Exception as e:
            self.db.rollback()
            analysis.status = "failed"
            analysis.error_message = str(e)
            analysis.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            raise
