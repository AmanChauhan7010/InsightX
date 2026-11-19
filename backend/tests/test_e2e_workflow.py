import os
import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import init_db

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()

@pytest.fixture
def client():
    return TestClient(app)

def test_full_end_to_end_investigation_workflow(client):
    """
    Validates the end-to-end InsightX workflow:
    1. Upload real user Python file (payment_service.py).
    2. Backend parses AST and runs analyzers.
    3. Findings verified with accurate file and line numbers.
    4. Root causes ranked with evidence-backed rationale.
    5. Actionable recommendations with unified code diffs verified.
    6. Recommendation marked as reviewed.
    7. Evidence checklist and uncertainty disclosure verified.
    8. Structured JSON and Markdown dossier generated and verified.
    """
    # 1. Read actual user code file from disk
    sample_path = os.path.join(os.path.dirname(__file__), "../../sample_data/code/payment_service.py")
    assert os.path.exists(sample_path), f"Sample file not found at {sample_path}"
    with open(sample_path, "rb") as f:
        file_bytes = f.read()

    # Read optional application log
    log_path = os.path.join(os.path.dirname(__file__), "../../sample_data/logs/production_timeouts.log")
    with open(log_path, "rb") as f:
        log_bytes = f.read()

    # 2. Submit multi-modal analysis request
    files = [
        ("files", ("payment_service.py", io.BytesIO(file_bytes), "text/x-python")),
        ("logs_file", ("production_timeouts.log", io.BytesIO(log_bytes), "text/plain"))
    ]
    response = client.post(
        "/api/v1/analyses",
        data={"title": "End-to-End Production Settlement Audit", "mode": "combined"},
        files=files
    )
    assert response.status_code == 200, f"Analysis failed: {response.text}"
    analysis = response.json()
    analysis_id = analysis["id"]

    # 3. Verify Analysis Metadata
    assert analysis["status"] == "completed"
    assert analysis["files_count"] == 1
    assert analysis["overall_score"] < 80.0  # Degraded due to critical flaws

    # 4. Verify Findings (Detect)
    findings = analysis["findings"]
    assert len(findings) >= 3

    # Check for Blocking Sleep finding
    blocking_finding = next((f for f in findings if "Blocking" in f["title"]), None)
    assert blocking_finding is not None
    assert blocking_finding["file_path"] == "payment_service.py"
    assert blocking_finding["line_number"] == 21
    assert blocking_finding["severity"] == "Critical"
    assert "time.sleep" in blocking_finding["code_snippet"]
    assert blocking_finding["detection_method"] == "AST Async Context Analysis"

    # Check for Resource Leak finding
    leak_finding = next((f for f in findings if "Resource" in f["category"] or "Leak" in f["title"]), None)
    assert leak_finding is not None
    assert leak_finding["file_path"] == "payment_service.py"
    assert leak_finding["line_number"] == 11
    assert leak_finding["severity"] == "High"

    # 5. Verify Root Causes (Diagnose)
    root_causes = analysis["root_causes"]
    assert len(root_causes) >= 1
    top_cause = root_causes[0]
    assert top_cause["rank"] == 1
    assert top_cause["confidence"] in ("High", "Medium")
    assert top_cause["confidence_score"] > 0.70
    assert "payment_service.py" in top_cause["affected_files"]
    assert top_cause["ranking_rationale"] is not None
    assert top_cause["missing_evidence"] is not None

    # 6. Verify Recommendations (Recommend)
    recommendations = analysis["recommendations"]
    assert len(recommendations) >= 1
    top_rec = recommendations[0]
    assert top_rec["priority"] in ("P1 - Immediate", "P2 - High")
    assert top_rec["diff"] is not None
    assert "--- a/payment_service.py" in top_rec["diff"]
    assert "+++ b/payment_service.py" in top_rec["diff"]
    assert top_rec["verification_instructions"] is not None

    # 7. Update recommendation status to reviewed
    patch_resp = client.patch(
        f"/api/v1/analyses/{analysis_id}/recommendations/{top_rec['id']}",
        json={"reviewed": True}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["reviewed"] is True

    # 8. Verify Forensic Evidence & Uncertainty Audit (Explain)
    evidence_resp = client.get(f"/api/v1/analyses/{analysis_id}/evidence")
    assert evidence_resp.status_code == 200
    evidence_data = evidence_resp.json()
    assert len(evidence_data["evidence_checklist"]) >= 1
    assert evidence_data["methodology_disclaimer"] is not None

    # 9. Verify Report Generation and Retrieval
    report_resp = client.get(f"/api/v1/analyses/{analysis_id}/report")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["analysis_id"] == analysis_id
    assert "InsightX Diagnostic Dossier" in report["markdown_report"]
    assert "payment_service.py" in report["markdown_report"]
    assert "P1 - Immediate" in report["markdown_report"]
    assert report["json_data"]["status"] == "completed"
