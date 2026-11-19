"""
InsightX Command Line Interface (CLI)
Automated anomaly detection, root cause diagnosis, and action recommendation tool.
"""

import argparse
import sys
import json
import pandas as pd
from datetime import datetime

from insightx.config import PLATFORM_NAME, TAGLINE, AUTHORS
from insightx.data_generator import generate_telemetry_dataset
from insightx.data_loader import TelemetryDataLoader
from insightx.anomaly_detector import MultiTierAnomalyDetector
from insightx.root_cause_engine import RootCauseEngine
from insightx.recommendation_engine import ActionRecommendationEngine
from insightx.explanation_engine import ExplanationEngine
from insightx.evaluation import run_comprehensive_benchmark
from insightx.code_analyzer import CodeDiagnosticEngine

def main():
    parser = argparse.ArgumentParser(
        description=f"{PLATFORM_NAME}: {TAGLINE}"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="cpu_pipeline_delay",
        choices=["cpu_pipeline_delay", "memory_leak_crash", "db_pool_exhaustion", "external_api_timeout", "normal"],
        help="Predefined scenario to simulate and analyze"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to custom CSV or JSON telemetry dataset"
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run quantitative multi-scenario benchmark evaluation"
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="Code snippet string to diagnose"
    )
    parser.add_argument(
        "--code-file",
        type=str,
        default=None,
        help="Path to source code file (.py, .js, .sql, etc.) to diagnose"
    )
    parser.add_argument(
        "--code-zip",
        type=str,
        default=None,
        help="Path to codebase project archive (.zip) or 'demo' for sample microservice repo"
    )
    parser.add_argument(
        "--error-trace",
        type=str,
        default=None,
        help="Optional runtime error message or stack trace"
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="python",
        help="Language of the code snippet (default: python)"
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Save incident analysis report to JSON file"
    )

    args = parser.parse_args()

    print("=" * 70)
    print(f" {PLATFORM_NAME} — AI Root Cause & Decision Intelligence Platform ")
    print(f" {AUTHORS[0]} & {AUTHORS[1]} | DA-IICT ")
    print("=" * 70)

    if args.benchmark:
        print("\n[>] Running Comprehensive Model Evaluation Benchmark...")
        results = run_comprehensive_benchmark()
        agg = results["aggregate"]
        print("\n--- AGGREGATE EVALUATION METRICS ---")
        print(f"  * Anomaly Detection Precision:  {agg['anomaly_precision']*100:.1f}%")
        print(f"  * Anomaly Detection Recall:     {agg['anomaly_recall']*100:.1f}%")
        print(f"  * Anomaly Detection F1-Score:   {agg['anomaly_f1']*100:.1f}%")
        print(f"  * RCA Top-1 Accuracy:           {agg['rca_top1_accuracy']*100:.1f}%")
        print(f"  * RCA Top-3 Accuracy:           {agg['rca_top3_accuracy']*100:.1f}%")
        print(f"  * RCA Mean Reciprocal Rank:     {agg['rca_mrr']:.3f}")
        print(f"  * Recommendation Relevance@5:   {agg['recommendation_relevance_at_5']*100:.1f}%")
        print(f"  * Explanation Quality Rating:   {agg['explanation_quality_rating']}/5.0")
        print("=" * 70)
        return

    # Project ZIP Archive Analysis Mode
    if args.code_zip:
        code_engine = CodeDiagnosticEngine()
        if args.code_zip.lower() == "demo":
            print("\n[+] Loading demo multi-service repository archive...")
            zip_bytes = code_engine.get_demo_project_zip()
            proj_name = "Demo Microservice Repository"
        else:
            print(f"\n[+] Reading project ZIP archive: {args.code_zip}")
            with open(args.code_zip, "rb") as f:
                zip_bytes = f.read()
            proj_name = args.code_zip

        print("[1/3] Decompressing archive and scanning all source files across directories...")
        z_res = code_engine.analyze_project_zip(zip_bytes, error_trace=args.error_trace, project_name=proj_name)

        if z_res.get("status") == "ERROR":
            print(f"\n❌ Error: {z_res.get('error')}")
            return

        status_icon = "✅" if z_res["status"] == "HEALTHY" else "🚨"
        print(f"\n{status_icon} PROJECT REPOSITORY AUDIT: {z_res['project_name']}")
        print(f"    Overall Health Score: {z_res['project_health_score']}/100")
        print(f"    Total Files Scanned:  {z_res['total_files_scanned']}")
        print(f"    Total Lines of Code:  {z_res['total_lines_of_code']}")
        print(f"    Clean Files:          {z_res['clean_files_count']}")
        print(f"    Defective Files:      {z_res['defective_files_count']}")
        print(f"    Critical Defects:     {z_res['severity_counts']['Critical']}")
        print(f"    High Risk Defects:    {z_res['severity_counts']['High']}")

        print("\n[2/3] GLOBAL PROJECT-WIDE ROOT CAUSE ATTRIBUTION:")
        for cause in z_res["global_ranked_root_causes"][:5]:
            print(f"    #{cause['rank']} {cause['cause']} — {cause['confidence_pct']}% confidence")
            print(f"       File: {cause['file']} (Line {cause['line']}) | {cause['score_type']}")

        print("\n[3/3] FILE-BY-FILE STATUS BREAKDOWN:")
        for path, f_res in z_res["file_results"].items():
            f_icon = "✅" if f_res["status"] == "HEALTHY" else "⚠️"
            print(f"    {f_icon} {path:35} | Health: {f_res['health_score']:3}/100 | {f_res['issues_count']} issues")

        if args.output_json:
            export_data = {
                "project_name": z_res["project_name"],
                "project_health_score": z_res["project_health_score"],
                "total_files_scanned": z_res["total_files_scanned"],
                "total_lines_of_code": z_res["total_lines_of_code"],
                "global_root_causes": z_res["global_ranked_root_causes"],
                "severity_counts": z_res["severity_counts"]
            }
            with open(args.output_json, "w") as f:
                json.dump(export_data, f, indent=2, default=str)
            print(f"\n[✓] Project audit report exported to: {args.output_json}")

        print("=" * 70)
        return

    # Code Analysis Mode
    if args.code or args.code_file:
        if args.code_file:
            print(f"\n[+] Reading source code from file: {args.code_file}")
            with open(args.code_file, "r") as f:
                code_text = f.read()
        else:
            code_text = args.code

        print(f"[1/4] Running AST & Semantic Defect Analysis (Language: {args.lang})...")
        code_engine = CodeDiagnosticEngine()
        res = code_engine.analyze_code(code_text, language=args.lang, error_trace=args.error_trace)

        status_icon = "✅" if res["status"] == "HEALTHY" else "⚠️"
        print(f"\n{status_icon} CODE DIAGNOSTIC VERDICT: {res['status']} (Health Score: {res['health_score']}/100)")
        print(f"    Issues Flagged: {res['issues_count']}")

        if res["issues"]:
            print("\n[2/4] IDENTIFIED DEFECTS & ISSUES:")
            for iss in res["issues"]:
                print(f"    • [{iss.get('severity', 'Medium')}] {iss.get('type')}: {iss.get('description')} (Line {iss.get('line', 1)})")
                if iss.get("code_snippet"):
                    print(f"      Code: {iss['code_snippet']}")

        print("\n[3/4] RANKED PROBABLE ROOT CAUSES:")
        for idx, cause in enumerate(res["ranked_root_causes"][:3], 1):
            print(f"    {idx}. {cause['cause']} — {cause['confidence_pct']}% confidence")
            print(f"       Origin: {cause['origin']} | {cause['description']}")

        print("\n[4/4] RECOMMENDED CORRECTIVE ACTIONS:")
        for idx, rec in enumerate(res["recommendations"][:2], 1):
            conf_str = f" — Confidence: {rec['confidence_pct']}%" if "confidence_pct" in rec else ""
            print(f"    {idx}. {rec['action']} [{rec.get('impact', 'High Impact')}]{conf_str}")
            print(f"       {rec.get('description', '')}")

        print("\n" + "-" * 70)
        print(" EXPLAINABLE AI (XAI) NARRATIVE")
        print("-" * 70)
        exp = res["explanation"]
        print(f"Summary: {exp.get('summary', '')}")
        print("\nSupporting Evidence:")
        for ev in exp.get("evidence", []):
            print(f"  • {ev}")
        print(f"\nWhy Fix Resolves It:\n{exp.get('why_fix', exp.get('why_verdict', ''))}")
        print("-" * 70)

        print("\n💡 REFACTORED / CORRECTED CODE:")
        print(res.get("refactored_code", code_text))
        print("=" * 70)

        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(res, f, indent=2, default=str)
            print(f"\n[✓] Code diagnostic report exported to: {args.output_json}")
        return

    # Load dataset
    if args.file:
        print(f"\n[+] Loading custom telemetry file: {args.file}")
        loader = TelemetryDataLoader()
        if args.file.endswith(".csv"):
            raw_df = pd.read_csv(args.file)
        else:
            raw_df = pd.read_json(args.file)
        df = loader.clean_and_prepare(raw_df)
        logs_df = pd.DataFrame()
        scenario_key = "custom_file"
    else:
        print(f"\n[+] Generating telemetry for scenario: {args.scenario}")
        pkg = generate_telemetry_dataset(scenario=args.scenario)
        df = pkg["metrics_df"]
        logs_df = pkg["logs_df"]
        scenario_key = args.scenario

    # Step 1: Detect Anomalies
    print("[1/4] Running Anomaly Detection Engine (Isolation Forest + Dynamic Bounds)...")
    detector = MultiTierAnomalyDetector()
    det_res = detector.fit_predict(df, logs_df)
    summary = det_res["summary"]
    print(f"      -> Detected {summary['anomaly_points_detected']} anomaly points.")
    print(f"      -> Dominant Metric: {summary['primary_metric_name']} (Severity: {summary['primary_severity']})")
    print(f"      -> Peak Timestamp:  {summary['peak_timestamp']}")

    # Step 2: Root Cause Analysis
    print("[2/4] Executing Root Cause Diagnosis & Lead-Lag Correlation...")
    rca = RootCauseEngine()
    rca_res = rca.diagnose(det_res["result_df"], summary, logs_df)
    top_cause = rca_res["top_cause"]
    print(f"      -> Top Root Cause: {top_cause['cause']} ({top_cause['confidence_pct']}% confidence)")
    print(f"      -> Root Service:   {rca_res['root_service']}")
    print(f"      -> Blast Radius:   {', '.join(rca_res['blast_radius_services'])}")

    # Step 3: Recommend Actions
    print("[3/4] Synthesizing Action Recommendations & Runbook Mapping...")
    rec = ActionRecommendationEngine()
    rec_res = rec.recommend(top_cause, summary)
    top_act = rec_res["top_recommendation"]
    print(f"      -> Top Action:     {top_act['action']} [{top_act['impact']}]")
    print(f"      -> Est. MTTR:      {top_act['mttr_estimate']}")
    print(f"      -> Runbook CMD:    {top_act['runbook']['command']}")

    # Step 4: Explain Decisions
    print("[4/4] Generating Explainable AI (XAI) Narrative & Evidence...")
    exp = ExplanationEngine()
    exp_res = exp.explain(summary, rca_res, rec_res, scenario_key)
    print("\n" + "-" * 70)
    print(" EXPLANATION SUMMARY")
    print("-" * 70)
    print(exp_res["top_explanation"])
    print("\nSUPPORTING EVIDENCE:")
    for ev in exp_res["supporting_evidence"]:
        print(f"  • {ev}")
    print(f"\nWHY THIS ACTION:\n{exp_res['why_action']}")
    print("-" * 70)

    if args.output_json:
        report = {
            "platform": PLATFORM_NAME,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "root_cause": rca_res["ranked_causes"],
            "recommendations": rec_res["ranked_actions"],
            "explanation": exp_res
        }
        with open(args.output_json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n[✓] Audit report saved to: {args.output_json}")

if __name__ == "__main__":
    main()

