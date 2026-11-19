import math
from typing import Dict, Any, List, Tuple
from backend.app.analyzers.code.rule_registry import RuleRegistry


class EvidenceCategory:
    """Explicit, non-fabricated evidence categories for InsightX findings and root causes."""
    STATIC_CODE = "Static Code Evidence"
    LOG = "Log Evidence"
    METRICS = "Metrics Evidence"
    RUNTIME = "Runtime Evidence"
    CORRELATED = "Correlated Evidence"

    ALL = {STATIC_CODE, LOG, METRICS, RUNTIME, CORRELATED}


class SeverityPolicy:
    """
    Deterministic, explainable severity classification policy backed by RuleRegistry.
    """

    @classmethod
    def classify(cls, rule_id: str, default_severity: str = "Medium", context_note: str = "") -> Tuple[str, str]:
        rule = RuleRegistry.get(rule_id)
        if rule is not None:
            severity = rule.default_severity
            rationale = rule.severity_rationale
        else:
            severity = default_severity
            rationale = f"Assigned {default_severity} based on deterministic static impact policy for rule '{rule_id}'."

        if context_note:
            rationale = f"{rationale} Context: {context_note}"
        return severity, rationale

    @classmethod
    def elevate_for_runtime_confirmation(cls, current_severity: str, current_rationale: str, exception_type: str) -> Tuple[str, str]:
        if current_severity in ("High", "Medium"):
            return (
                "Critical",
                f"Elevated from {current_severity} to Critical because uploaded runtime traceback directly confirms active '{exception_type}' execution at this code location. ({current_rationale})"
            )
        return (
            current_severity,
            f"Corroborated by uploaded runtime traceback ('{exception_type}'). {current_rationale}"
        )


class HealthScoreCalculator:
    """
    Deterministic, reproducible, explainable health score engine (0-100).

    - Score 100 explicitly means: "No issues detected by the enabled analysis rules."
      It does NOT claim the software is bug-free.
    - If parsing or analysis failed/was incomplete, never returns 100/100.
    - Applies duplicate diminishing returns (35% weight for duplicates 2..4 in same file/rule).
    - Applies mild logarithmic scale normalization to non-Critical findings in multi-file
      projects while keeping Critical deductions undiluted.
    """

    BASE_WEIGHTS: Dict[str, float] = {
        "Critical": 18.0,
        "High": 10.0,
        "Medium": 5.0,
        "Low": 2.0,
        "Informational": 0.0,
    }

    DUPLICATE_FACTOR = 0.35
    MAX_DUPLICATES_COUNTED = 3

    @classmethod
    def compute(
        cls,
        findings: List[Dict[str, Any]],
        metric_anomalies: List[Dict[str, Any]] = None,
        log_issues: List[Dict[str, Any]] = None,
        files_count: int = 1,
        mode: str = "code",
        incomplete_parse: bool = False,
    ) -> Dict[str, Any]:
        metric_anomalies = metric_anomalies or []
        log_issues = log_issues or []
        files_count = max(1, files_count)

        norm_factor = 1.0 if files_count <= 1 else round(1.0 / (1.0 + 0.15 * math.log2(files_count)), 4)

        deductions_by_severity: Dict[str, float] = {
            "Critical": 0.0,
            "High": 0.0,
            "Medium": 0.0,
            "Low": 0.0,
            "Informational": 0.0,
        }

        seen_counts: Dict[Tuple[str, str], int] = {}
        raw_unweighted_penalty = 0.0
        code_penalty = 0.0

        for f in findings:
            sev = f.get("severity", "Medium")
            base_w = cls.BASE_WEIGHTS.get(sev, 5.0)
            key = (f.get("file_path", ""), f.get("rule_id") or f.get("title", ""))
            occ = seen_counts.get(key, 0)
            seen_counts[key] = occ + 1

            raw_unweighted_penalty += base_w

            if occ == 0:
                effective_w = base_w
            elif occ <= cls.MAX_DUPLICATES_COUNTED:
                effective_w = base_w * cls.DUPLICATE_FACTOR
            else:
                effective_w = 0.0

            if sev != "Critical":
                effective_w *= norm_factor

            effective_w = round(effective_w, 2)
            code_penalty += effective_w
            deductions_by_severity[sev] = round(deductions_by_severity.get(sev, 0.0) + effective_w, 2)

        metric_penalty = 0.0
        seen_metrics: Dict[str, int] = {}
        for a in metric_anomalies:
            m_key = a.get("metric_name", "metric").split(" ")[0]
            occ = seen_metrics.get(m_key, 0)
            seen_metrics[m_key] = occ + 1
            metric_penalty += 4.0 if occ == 0 else (1.0 if occ <= 3 else 0.0)
        metric_penalty = min(15.0, round(metric_penalty, 2))

        log_penalty = 0.0
        seen_log_levels: Dict[str, int] = {}
        for l in log_issues:
            lvl = (l.get("level") or "ERROR").upper()
            occ = seen_log_levels.get(lvl, 0)
            seen_log_levels[lvl] = occ + 1
            if lvl == "CRITICAL":
                log_penalty += 8.0 if occ == 0 else (2.0 if occ <= 2 else 0.0)
            elif lvl == "ERROR":
                log_penalty += 4.0 if occ == 0 else (1.0 if occ <= 3 else 0.0)
            elif lvl == "WARN":
                log_penalty += 1.0 if occ == 0 else 0.0
        log_penalty = min(20.0, round(log_penalty, 2))

        total_deduction = round(code_penalty + metric_penalty + log_penalty, 2)
        final_score = round(max(0.0, min(100.0, 100.0 - total_deduction)), 1)

        # Never give 100/100 when parsing or analysis was incomplete
        if incomplete_parse and final_score >= 100.0:
            final_score = 80.0
            total_deduction = max(total_deduction, 20.0)

        duplicate_dampening_saved = round(max(0.0, raw_unweighted_penalty - code_penalty), 2)

        if incomplete_parse:
            meaning = "Incomplete analysis: one or more files failed to parse cleanly; deeper static rules could not run on unparseable files."
        elif len(findings) == 0 and len(metric_anomalies) == 0 and len(log_issues) == 0:
            meaning = "No issues detected by the enabled analysis rules."
        elif final_score >= 85.0:
            meaning = "Low detected risk based on enabled rules; minor findings warrant review."
        elif final_score >= 65.0:
            meaning = "Moderate risk detected; one or more High/Medium findings should be remediated."
        elif final_score >= 40.0:
            meaning = "Elevated risk detected across multiple findings; remediation strongly advised before release."
        else:
            meaning = "Severe risk profile detected; critical or compounding defects require immediate engineering attention."

        included = ["Enabled static AST & pattern rules for supported languages (Python, JS/TS)"]
        if metric_anomalies or mode in ("metrics_logs", "combined"):
            included.append("Uploaded time-series metric anomaly deviations (Z-Score, MAD/IQR & Isolation Forest)")
        if log_issues or mode in ("metrics_logs", "combined"):
            included.append("Uploaded application log error and stack-trace severity")

        excluded = [
            "Runtime business logic correctness and functional test coverage",
            "Third-party packages or external infrastructure not included in upload",
            "Dynamic reflection, runtime metaprogramming, and full penetration testing",
        ]

        return {
            "score": final_score,
            "base_score": 100.0,
            "meaning": meaning,
            "analysis_complete": not incomplete_parse,
            "total_deduction": total_deduction,
            "code_deduction": round(code_penalty, 2),
            "metric_deduction": metric_penalty,
            "log_deduction": log_penalty,
            "deductions_by_severity": deductions_by_severity,
            "duplicate_dampening_saved": duplicate_dampening_saved,
            "files_analyzed": files_count,
            "normalization_factor": norm_factor,
            "weights": cls.BASE_WEIGHTS,
            "included_scope": included,
            "excluded_scope": excluded,
        }
