import subprocess
import sys
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session

from backend.app.models.analysis import Analysis, Recommendation
from backend.app.autofix.patch_applier import PatchApplier
from backend.app.autofix.patch_validator import sha256_text


class FixReanalyzer:
    """
    Re-runs the actual InsightX AnalysisOrchestrator on an isolated patched working copy,
    persists a linked revision (v2, v3...) without overwriting the original analysis,
    and computes a strictly factual before/after comparison.
    """

    @classmethod
    def apply_and_reanalyze(
        cls,
        db: Session,
        original_analysis: Analysis,
        target_file: str,
        patched_code: str,
        applied_title: str,
        recommendation: Recommendation = None,
    ) -> Dict[str, Any]:
        snapshot = original_analysis.source_snapshot or {}
        working_files = PatchApplier.build_working_copy(snapshot, target_file, patched_code)

        meta = original_analysis.meta_info or {}
        root_id = original_analysis.root_analysis_id or original_analysis.id
        next_rev = (original_analysis.revision_number or 1) + 1
        base_title = original_analysis.title.split(" (Rev ")[0]
        new_title = f"{base_title} (Rev {next_rev})"

        from backend.app.services.orchestrator import AnalysisOrchestrator

        orchestrator = AnalysisOrchestrator(db)
        new_analysis = orchestrator.run_analysis(
            title=new_title,
            mode=original_analysis.mode,
            code_files=working_files,
            metrics_content=meta.get("raw_metrics_content"),
            metrics_filename=meta.get("raw_metrics_filename") or "metrics.csv",
            logs_content=meta.get("raw_logs_content"),
            logs_filename=meta.get("raw_logs_filename") or "app.log",
            parent_analysis_id=original_analysis.id,
            root_analysis_id=root_id,
            revision_number=next_rev,
            applied_recommendation_id=recommendation.id if recommendation else None,
            applied_recommendation_title=applied_title,
        )

        if recommendation is not None:
            recommendation.reviewed = True
            db.commit()

        comparison = cls.compute_comparison(original_analysis, new_analysis)

        # Safely run the repaired Python script to capture its actual runtime console output
        execution_output: Optional[str] = None
        if target_file.endswith(".py"):
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", patched_code],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                output_parts = []
                if proc.stdout:
                    output_parts.append(proc.stdout)
                if proc.stderr:
                    output_parts.append(proc.stderr)
                execution_output = "".join(output_parts).strip() if output_parts else "[Process completed successfully with exit code 0]"
            except subprocess.TimeoutExpired:
                execution_output = "[Execution timed out after 3 seconds]"
            except Exception as e:
                execution_output = f"[Execution notice: {str(e)}]"

        return {
            "analysis": new_analysis,
            "comparison": comparison,
            "applied_file_path": target_file,
            "fixed_code": patched_code,
            "source_hash": sha256_text(patched_code),
            "execution_output": execution_output,
        }

    @staticmethod
    def compute_comparison(before_analysis: Analysis, after_analysis: Analysis) -> Dict[str, Any]:
        def sev_counts(findings_list) -> Dict[str, int]:
            counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Informational": 0}
            for f in findings_list:
                if f.severity in counts:
                    counts[f.severity] += 1
            return counts

        def f_key(f) -> Tuple[str, str, str]:
            return (f.file_path or "", f.rule_id or f.title, f.category or "")

        def serialize(f) -> Dict[str, Any]:
            return {
                "id": f.id,
                "rule_id": f.rule_id,
                "title": f.title,
                "severity": f.severity,
                "category": f.category,
                "file_path": f.file_path,
                "line_number": f.line_number,
            }

        before_findings = list(before_analysis.findings or [])
        after_findings = list(after_analysis.findings or [])

        after_pool: Dict[Tuple[str, str, str], List[Any]] = {}
        for af in after_findings:
            after_pool.setdefault(f_key(af), []).append(af)

        resolved = []
        remaining = []
        matched_after_ids = set()

        for bf in before_findings:
            k = f_key(bf)
            if after_pool.get(k):
                matched_af = after_pool[k].pop(0)
                matched_after_ids.add(matched_af.id)
                remaining.append(serialize(matched_af))
            else:
                resolved.append(serialize(bf))

        newly_introduced = [serialize(af) for af in after_findings if af.id not in matched_after_ids]

        before_score = round(float(before_analysis.overall_score or 0.0), 1)
        after_score = round(float(after_analysis.overall_score or 0.0), 1)
        score_delta = round(after_score - before_score, 1)

        if score_delta > 0 or (len(resolved) > 0 and len(newly_introduced) == 0 and score_delta >= 0):
            status = "improved"
            summary = (
                f"Re-analysis resolved {len(resolved)} finding(s) and changed Health Score by "
                f"{'+' if score_delta >= 0 else ''}{score_delta} points ({before_score} -> {after_score})."
            )
        elif score_delta < 0 or len(newly_introduced) > len(resolved):
            status = "regressed"
            summary = (
                f"Warning: Re-analysis detected {len(newly_introduced)} new finding(s) and Health Score changed by "
                f"{score_delta} points ({before_score} -> {after_score}). Review or Undo Fix."
            )
        else:
            status = "no_change"
            summary = (
                f"Re-analysis completed with no net score change ({before_score} -> {after_score}); "
                f"{len(remaining)} finding(s) remain."
            )

        return {
            "before_analysis_id": before_analysis.id,
            "after_analysis_id": after_analysis.id,
            "before_score": before_score,
            "after_score": after_score,
            "score_delta": score_delta,
            "before_findings_count": len(before_findings),
            "after_findings_count": len(after_findings),
            "before_severity_counts": sev_counts(before_findings),
            "after_severity_counts": sev_counts(after_findings),
            "resolved_findings": resolved,
            "remaining_findings": remaining,
            "newly_introduced_findings": newly_introduced,
            "status": status,
            "summary": summary,
        }
