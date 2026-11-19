from typing import Dict, Any, List, Optional
from backend.app.core.config import settings
from backend.app.services.scoring import EvidenceCategory


class ExplanationEngine:
    """
    Transparent Explainable AI (XAI) Synthesis Engine.
    Produces evidence-backed narrative explanations, categorized audit trails,
    and explicit uncertainty disclosures without fabricating runtime proof or probabilities.
    """

    def explain(
        self,
        analysis_summary: str,
        findings: List[Dict[str, Any]],
        root_causes: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        metric_anomalies: List[Dict[str, Any]] = None,
        log_issues: List[Dict[str, Any]] = None,
        stack_traces: List[Dict[str, Any]] = None,
        score_breakdown: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metric_anomalies = metric_anomalies or []
        log_issues = log_issues or []
        stack_traces = stack_traces or []

        narrative = self._generate_deterministic_narrative(
            analysis_summary, findings, root_causes, recommendations, metric_anomalies, log_issues, score_breakdown
        )

        evidence_checklist = self._build_evidence_checklist(findings, metric_anomalies, log_issues, stack_traces)
        evidence_categories_present = sorted({item["evidence_category"] for item in evidence_checklist})
        uncertainty_statement = self._build_uncertainty_statement(
            findings, root_causes, metric_anomalies, log_issues, stack_traces
        )

        llm_enhanced = False
        llm_notes = None
        if settings.GEMINI_API_KEY or settings.OPENAI_API_KEY:
            try:
                llm_notes = self._query_llm_enhancement(findings, root_causes, recommendations)
                if llm_notes:
                    llm_enhanced = True
            except Exception:
                llm_enhanced = False

        return {
            "narrative": narrative,
            "evidence_checklist": evidence_checklist,
            "evidence_categories_present": evidence_categories_present,
            "uncertainty_statement": uncertainty_statement,
            "llm_enhanced": llm_enhanced,
            "llm_notes": llm_notes,
            "methodology_disclaimer": (
                "InsightX derives findings and root-cause hypotheses deterministically from the uploaded artifacts. "
                "Static Code Evidence identifies structural or control-flow risks in source code and does not prove a "
                "production runtime incident unless independently corroborated by uploaded Log, Metrics, or Runtime Evidence."
            ),
        }

    def _generate_deterministic_narrative(
        self,
        summary: str,
        findings: List[Dict[str, Any]],
        root_causes: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        metric_anomalies: List[Dict[str, Any]],
        log_issues: List[Dict[str, Any]],
        score_breakdown: Optional[Dict[str, Any]] = None,
    ) -> str:
        parts = [f"### Executive Diagnostic Narrative\n\n{summary}\n"]

        if not findings and not root_causes and not metric_anomalies and not log_issues:
            parts.append(
                "**Clean Analysis Result**: No issues were detected by the enabled static rules or telemetry analyzers. "
                "No root-cause hypotheses or corrective actions were generated. Note that a 100/100 score indicates "
                "zero findings under the enabled rules rather than a guarantee that the software is free of all defects.\n"
            )
            return "\n".join(parts)

        top_cause = root_causes[0] if root_causes else None
        if top_cause:
            parts.append(
                f"**Primary Hypothesis**: {top_cause['title']} "
                f"({top_cause.get('cause_type', 'Static Potential Cause')} | "
                f"Qualitative Confidence: {top_cause.get('confidence', 'Medium')} | "
                f"Evidence: {top_cause.get('evidence_category', EvidenceCategory.STATIC_CODE)}).\n"
                f"{top_cause['description']}\n\n"
                f"**Ranking Rationale**: {top_cause.get('ranking_rationale', 'Prioritized by evidence quality and structural impact.')}\n"
            )

        high_findings = [f for f in findings if f.get("severity") in ("Critical", "High")]
        if high_findings:
            first = high_findings[0]
            loc = f"{first['file_path']}:{first.get('line_number', '?')}"
            if first.get("line_end") and first.get("line_number") and first["line_end"] > first["line_number"]:
                loc = f"{first['file_path']}:{first['line_number']}-{first['line_end']}"
            parts.append(
                f"**High-Impact Code Findings**: Identified {len(high_findings)} Critical/High static finding(s). "
                f"Lead finding: '{first['title']}' at `{loc}` ({first.get('evidence_category', EvidenceCategory.STATIC_CODE)}).\n"
            )

        if metric_anomalies:
            parts.append(
                f"**Metrics Evidence**: Detected {len(metric_anomalies)} anomalous time-series observation(s) "
                "via dynamic Z-score saturation bounds and Isolation Forest.\n"
            )

        if recommendations:
            top_rec = recommendations[0]
            parts.append(
                f"**Top Recommended Action**: {top_rec['title']} ({top_rec['priority']}).\n"
                f"*{top_rec['why_recommended']}* Expected benefit: {top_rec['expected_benefit']}\n"
            )

        return "\n".join(parts)

    def _build_evidence_checklist(
        self,
        findings: List[Dict[str, Any]],
        metric_anomalies: List[Dict[str, Any]],
        log_issues: List[Dict[str, Any]],
        stack_traces: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        checklist = []
        for f in findings:
            ln = f.get("line_number")
            le = f.get("line_end")
            loc = f"{f['file_path']}:{ln}-{le}" if (ln and le and le > ln) else f"{f['file_path']}:{ln or '?'}"
            ev_cat = f.get("evidence_category") or EvidenceCategory.STATIC_CODE
            checklist.append({
                "evidence_category": ev_cat,
                "type": ev_cat,
                "label": f"{f['title']} ({loc})",
                "evidence": f["evidence"],
                "severity": f.get("severity", "Medium"),
                "verified": ev_cat in (EvidenceCategory.CORRELATED, EvidenceCategory.RUNTIME),
            })

        for t in stack_traces:
            checklist.append({
                "evidence_category": EvidenceCategory.RUNTIME,
                "type": EvidenceCategory.RUNTIME,
                "label": f"Traceback: {t.get('exception_type', 'Error')} ({t.get('file_path', '?')}:{t.get('line_number', '?')})",
                "evidence": t.get("message", "Execution stack trace recorded in uploaded logs."),
                "severity": "Critical",
                "verified": True,
            })

        for a in metric_anomalies[:8]:
            checklist.append({
                "evidence_category": EvidenceCategory.METRICS,
                "type": EvidenceCategory.METRICS,
                "label": f"{a['metric_name']} deviation at {a['timestamp']}",
                "evidence": f"Observed {a['observed_value']} (baseline mean: {a.get('baseline_mean')}, anomaly score: {a['anomaly_score']})",
                "severity": a.get("severity", "High"),
                "verified": True,
            })

        for l in log_issues[:8]:
            checklist.append({
                "evidence_category": EvidenceCategory.LOG,
                "type": EvidenceCategory.LOG,
                "label": f"[{l['level']}] {l['message'][:80]}",
                "evidence": f"Occurred {l.get('count', 1)} time(s). Service: {l.get('service') or 'app'}",
                "severity": "High" if l.get("level") in ("CRITICAL", "ERROR") else "Medium",
                "verified": True,
            })

        return checklist

    def _build_uncertainty_statement(
        self,
        findings: List[Dict[str, Any]],
        root_causes: List[Dict[str, Any]],
        metric_anomalies: List[Dict[str, Any]],
        log_issues: List[Dict[str, Any]],
        stack_traces: List[Dict[str, Any]],
    ) -> str:
        if not findings and not metric_anomalies and not log_issues and not stack_traces:
            return (
                "No issues were detected by the enabled static rules. Static analysis only covers implemented "
                "AST and pattern rules and does not execute the uploaded code or verify business logic correctness."
            )

        notes = []
        if not log_issues and not stack_traces:
            notes.append(
                "No application logs or execution stack traces were uploaded; code findings represent Static Code Evidence "
                "and do not prove a live runtime failure occurred."
            )
        if not metric_anomalies:
            notes.append(
                "No system time-series metrics were uploaded; latency, memory, and CPU impact cannot be quantified from telemetry."
            )
        if root_causes and root_causes[0].get("missing_evidence"):
            notes.append(f"Primary Data Gap: {root_causes[0]['missing_evidence']}")

        if not notes:
            return "Multiple independent evidence sources (Code, Logs/Runtime Traces, and Metrics) were available for cross-modal correlation."
        return " | ".join(notes)

    def _query_llm_enhancement(
        self,
        findings: List[Dict[str, Any]],
        root_causes: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
    ) -> Optional[str]:
        return None
