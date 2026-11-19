import pytest
from backend.app.rca.engine import RootCauseEngine
from backend.app.recommendations.engine import RecommendationEngine

def test_rca_matches_stack_trace_to_static_defect():
    rca = RootCauseEngine()
    findings = [
        {
            "id": "find-1",
            "title": "Unguarded Division by Variable 'divisor'",
            "category": "Arithmetic Crash",
            "severity": "High",
            "file_path": "service/processor.py",
            "line_number": 42
        }
    ]
    stack_traces = [
        {
            "exception_type": "ZeroDivisionError",
            "message": "division by zero",
            "file_path": "service/processor.py",
            "line_number": 42,
            "function_name": "process_batch"
        }
    ]
    causes = rca.diagnose(findings=findings, relationships=[], stack_traces=stack_traces)
    assert len(causes) >= 1
    top_cause = causes[0]
    assert "Confirmed Runtime Crash" in top_cause["title"]
    assert top_cause["confidence"] == "High"
    assert top_cause["confidence_score"] > 0.90
    assert "service/processor.py" in top_cause["affected_files"]

def test_recommendation_diff_generation():
    engine = RecommendationEngine()
    findings = [
        {
            "id": "find-2",
            "title": "Blocking Synchronous Call in Async Function 'process'",
            "category": "Async / Event Loop Blocking",
            "severity": "Critical",
            "file_path": "async_app.py",
            "line_number": 15,
            "code_snippet": "time.sleep(2.0)"
        }
    ]
    recs = engine.generate_recommendations(findings=findings)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["priority"] == "P1 - Immediate"
    assert "asyncio.sleep" in rec["refactored_code"]
    assert "--- a/async_app.py" in rec["diff"]
    assert "+++ b/async_app.py" in rec["diff"]
