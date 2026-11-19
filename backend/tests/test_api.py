import io
import zipfile
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

def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "python" in data["supported_languages"]

def test_paste_code_analysis(client):
    code = (
        "import asyncio\n"
        "import time\n\n"
        "async def handle_request(user_id: int):\n"
        "    time.sleep(1.0)\n"
        "    return 100 / user_id\n"
    )
    payload = {
        "title": "Test Paste Async Analysis",
        "code": code,
        "language": "python",
        "file_name": "handler.py"
    }
    response = client.post("/api/v1/analyses/paste", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert len(data["findings"]) >= 2
    # Verify blocking call finding
    titles = [f["title"] for f in data["findings"]]
    assert any("Blocking Synchronous Call" in t for t in titles)
    # Verify root cause
    assert len(data["root_causes"]) >= 1
    # Verify recommendation
    assert len(data["recommendations"]) >= 1

def test_multipart_single_file_upload(client):
    py_code = b"import time\nasync def srv(): time.sleep(1.0)\n"
    files = [
        ("files", ("worker.py", io.BytesIO(py_code), "text/x-python"))
    ]
    response = client.post(
        "/api/v1/analyses",
        data={"title": "Single File Upload Test", "mode": "code"},
        files=files
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["files_count"] == 1
    assert any("worker.py" in f["file_path"] for f in data["findings"])

def test_multipart_multiple_files_upload(client):
    f1 = b"def calc(x): return x / 0\n"
    f2 = b"import calc\ndef run(): return calc.calc(10)\n"
    files = [
        ("files", ("calc.py", io.BytesIO(f1), "text/x-python")),
        ("files", ("run.py", io.BytesIO(f2), "text/x-python"))
    ]
    response = client.post(
        "/api/v1/analyses",
        data={"title": "Multi File Upload Test", "mode": "code"},
        files=files
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["files_count"] == 2
    assert len(data["findings"]) >= 1

def test_zip_archive_upload(client):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("app/service.py", "def compute(): return 42\n")
        zf.writestr("app/leak.py", "import sqlite3\ndef get_db(): conn = sqlite3.connect('x.db'); return conn\n")
    zip_buffer.seek(0)

    files = [
        ("files", ("project.zip", zip_buffer, "application/zip"))
    ]
    response = client.post(
        "/api/v1/analyses",
        data={"title": "ZIP Project Test", "mode": "code"},
        files=files
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["files_count"] == 2
    assert any("leak.py" in f["file_path"] for f in data["findings"])

def test_empty_input_validation(client):
    response = client.post("/api/v1/analyses", data={"title": "Empty Test", "mode": "code"})
    assert response.status_code == 400
    assert "No valid input provided" in response.json()["detail"]

def test_list_analyses_and_detail(client):
    list_resp = client.get("/api/v1/analyses")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) > 0
    first_id = items[0]["id"]

    detail_resp = client.get(f"/api/v1/analyses/{first_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == first_id
    assert "findings" in detail
    assert "root_causes" in detail

def test_findings_filtering(client):
    list_resp = client.get("/api/v1/analyses")
    analysis_id = list_resp.json()[0]["id"]

    resp = client.get(f"/api/v1/analyses/{analysis_id}/findings?severity=Critical")
    assert resp.status_code == 200
    for finding in resp.json():
        assert finding["severity"] == "Critical"

def test_recommendation_review_toggle(client):
    list_resp = client.get("/api/v1/analyses")
    analysis_id = list_resp.json()[0]["id"]

    recs_resp = client.get(f"/api/v1/analyses/{analysis_id}/recommendations")
    recs = recs_resp.json()
    if recs:
        rec_id = recs[0]["id"]
        patch_resp = client.patch(
            f"/api/v1/analyses/{analysis_id}/recommendations/{rec_id}",
            json={"reviewed": True}
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["reviewed"] is True

def test_report_generation(client):
    list_resp = client.get("/api/v1/analyses")
    analysis_id = list_resp.json()[0]["id"]

    report_resp = client.get(f"/api/v1/analyses/{analysis_id}/report")
    assert report_resp.status_code == 200
    data = report_resp.json()
    assert "json_data" in data
    assert "markdown_report" in data
    assert "InsightX Diagnostic Dossier" in data["markdown_report"]

def test_sample_cases_and_loader(client):
    cases_resp = client.get("/api/v1/sample-cases")
    assert cases_resp.status_code == 200
    cases = cases_resp.json()
    assert len(cases) == 4

    # Load Case A
    load_resp = client.post("/api/v1/sample-cases/case_a_python_async/load")
    assert load_resp.status_code == 200
    data = load_resp.json()
    assert data["status"] == "completed"
    assert len(data["findings"]) >= 3
