from typing import Dict, Any
from datetime import datetime
from backend.app.models.analysis import Analysis

class ReportGenerator:
    """
    Generates structured JSON and human-readable Markdown incident dossiers.
    """

    @staticmethod
    def generate_json_report(analysis: Analysis) -> Dict[str, Any]:
        return {
            "platform": "InsightX Decision Intelligence Platform",
            "version": "2.0.0",
            "analysis_id": analysis.id,
            "title": analysis.title,
            "mode": analysis.mode,
            "status": analysis.status,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            "overall_health_score": analysis.overall_score,
            "summary": analysis.summary,
            "meta_info": analysis.meta_info,
            "findings": [
                {
                    "id": f.id,
                    "rule_id": getattr(f, "rule_id", None),
                    "title": f.title,
                    "category": f.category,
                    "severity": f.severity,
                    "severity_rationale": getattr(f, "severity_rationale", None),
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "line_end": f.line_end,
                    "code_snippet": f.code_snippet,
                    "description": f.description,
                    "evidence": f.evidence,
                    "evidence_category": getattr(f, "evidence_category", "Static Code Evidence"),
                    "detection_method": f.detection_method,
                    "potential_consequences": f.potential_consequences,
                    "suggested_next_step": f.suggested_next_step,
                    "is_confirmed": f.is_confirmed,
                    "language": f.language
                }
                for f in analysis.findings
            ],
            "root_causes": [
                {
                    "id": rc.id,
                    "rank": rc.rank,
                    "title": rc.title,
                    "description": rc.description,
                    "confidence": rc.confidence,
                    "evidence_category": getattr(rc, "evidence_category", "Static Code Evidence"),
                    "cause_type": getattr(rc, "cause_type", "Static Potential Cause"),
                    "affected_files": rc.affected_files,
                    "affected_functions": rc.affected_functions,
                    "related_finding_ids": rc.related_finding_ids,
                    "evidence_summary": rc.evidence_summary,
                    "ranking_rationale": rc.ranking_rationale,
                    "consequences": getattr(rc, "consequences", None),
                    "recommended_actions_summary": getattr(rc, "recommended_actions_summary", None),
                    "missing_evidence": rc.missing_evidence,
                    "alternative_explanations": rc.alternative_explanations
                }
                for rc in analysis.root_causes
            ],
            "recommendations": [
                {
                    "id": r.id,
                    "priority": r.priority,
                    "title": r.title,
                    "problem_addressed": r.problem_addressed,
                    "why_recommended": r.why_recommended,
                    "expected_benefit": r.expected_benefit,
                    "verification_instructions": r.verification_instructions,
                    "related_finding_ids": r.related_finding_ids,
                    "related_cause_ids": getattr(r, "related_cause_ids", []),
                    "file_path": r.file_path,
                    "diff": r.diff,
                    "reviewed": r.reviewed
                }
                for r in analysis.recommendations
            ],
            "metric_anomalies": [
                {
                    "timestamp": a.timestamp,
                    "metric_name": a.metric_name,
                    "observed_value": a.observed_value,
                    "baseline_mean": a.baseline_mean,
                    "anomaly_score": a.anomaly_score,
                    "severity": a.severity
                }
                for a in analysis.metric_anomalies
            ],
            "log_issues": [
                {
                    "timestamp": l.timestamp,
                    "level": l.level,
                    "message": l.message,
                    "service": l.service,
                    "count": l.count
                }
                for l in analysis.log_issues
            ]
        }

    @classmethod
    def generate_markdown_report(cls, analysis: Analysis) -> str:
        report_data = cls.generate_json_report(analysis)
        created_str = report_data["created_at"] or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        md = []
        md.append(f"# InsightX Diagnostic Dossier: {report_data['title']}")
        md.append(f"**Analysis ID**: `{report_data['analysis_id']}`  ")
        md.append(f"**Date Generated**: {created_str} | **Mode**: `{report_data['mode']}` | **Overall Health Score**: **{report_data['overall_health_score']}/100**\n")
        md.append("---\n")

        md.append("## 1. Executive Summary & Diagnostic Narrative\n")
        md.append(report_data.get("summary") or "No narrative summary generated.")
        md.append("\n---\n")

        md.append("## 2. Ranked Probable Root Causes (Diagnose)\n")
        if not report_data["root_causes"]:
            md.append("No root causes identified. No issues or incident evidence were detected by the enabled analysis rules.\n")
        for rc in report_data["root_causes"]:
            md.append(f"### #{rc['rank']} - {rc['title']}")
            md.append(f"- **Classification**: `{rc.get('cause_type', 'Static Potential Cause')}` | **Qualitative Confidence**: `{rc['confidence']}` | **Evidence Category**: `{rc.get('evidence_category', 'Static Code Evidence')}`")
            md.append(f"- **Description**: {rc['description']}")
            if rc.get("affected_files"):
                md.append(f"- **Affected Files**: {', '.join(rc['affected_files'])}")
            md.append(f"- **Evidence Summary**: {rc.get('evidence_summary')}")
            md.append(f"- **Ranking Rationale**: {rc.get('ranking_rationale')}")
            if rc.get("consequences"):
                md.append(f"- **Potential Consequences**: {rc.get('consequences')}")
            if rc.get("missing_evidence"):
                md.append(f"- **Data Gaps / Uncertainty**: {rc.get('missing_evidence')}")
            if rc.get("alternative_explanations"):
                md.append(f"- **Alternative Explanations**: {rc.get('alternative_explanations')}")
            md.append("")
        md.append("---\n")

        md.append("## 3. Prioritized Corrective Actions (Recommend)\n")
        if not report_data["recommendations"]:
            md.append("No corrective actions required.\n")
        for rec in report_data["recommendations"]:
            md.append(f"### [{rec['priority']}] {rec['title']}")
            md.append(f"**Problem Addressed**: {rec['problem_addressed']}  ")
            md.append(f"**Why Recommended**: {rec['why_recommended']}  ")
            md.append(f"**Expected Benefit**: {rec['expected_benefit']}  ")
            md.append(f"**Verification**: {rec['verification_instructions']}\n")
            if rec.get("diff"):
                md.append("```diff")
                md.append(rec["diff"])
                md.append("```\n")
        md.append("---\n")

        md.append("## 4. Detected Code & System Findings (Detect)\n")
        md.append(f"Total Findings Detected: **{len(report_data['findings'])}**\n")
        for idx, f in enumerate(report_data["findings"], 1):
            ln = f.get("line_number")
            le = f.get("line_end")
            loc = f"{f['file_path']}:{ln}-{le}" if (ln and le and le > ln) else f"{f['file_path']}:{ln or '?'}"
            md.append(f"#### {idx}. [{f['severity']}] {f['title']}")
            md.append(f"- **Location**: `{loc}` | **Evidence Category**: `{f.get('evidence_category', 'Static Code Evidence')}`")
            md.append(f"- **Category**: {f['category']} | **Method**: {f['detection_method']}")
            if f.get("severity_rationale"):
                md.append(f"- **Severity Rationale**: {f['severity_rationale']}")
            md.append(f"- **Description**: {f['description']}")
            md.append(f"- **Evidence**: {f['evidence']}")
            if f.get("code_snippet"):
                md.append(f"```{f.get('language', 'python')}\n{f['code_snippet']}\n```")
            md.append("")

        if report_data["metric_anomalies"]:
            md.append("---\n")
            md.append("## 5. Correlated Metric Anomalies\n")
            for a in report_data["metric_anomalies"][:8]:
                md.append(f"- `{a['timestamp']}`: **{a['metric_name']}** = {a['observed_value']} (Score: {a['anomaly_score']}, Severity: {a['severity']})")

        md.append("\n---\n")
        md.append("*Generated automatically by InsightX AI Root Cause & Decision Intelligence Platform.*")

        return "\n".join(md)
