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


# ==============================================================================
# TEST B: APPLY FIX & RE-ANALYZE (REAL SOURCE PATCH + GENUINE RE-SCORE + UNDO)
# ==============================================================================
def test_b_apply_blocking_sleep_fix_and_preserve_original(client):
    original_code = (
        "import time\n\n"
        "def helper_keep_me(x: int) -> int:\n"
        "    return x * 2\n\n"
        "async def process():\n"
        "    time.sleep(5)\n"
        "    return helper_keep_me(21)\n"
    )
    r1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Async Sleep Fix Test", "code": original_code, "language": "python", "file_name": "worker.py"},
    )
    assert r1.status_code == 200
    v1 = r1.json()
    assert len(v1["findings"]) == 1
    assert v1["findings"][0]["rule_id"] == "PY_ASYNC_BLOCKING_SLEEP"
    assert v1["overall_score"] == 90.0
    assert len(v1["recommendations"]) == 1

    rec = v1["recommendations"][0]
    assert rec["auto_fixable"] is True
    assert rec["simple_explanation"]["what_is_wrong"]
    assert rec["simple_explanation"]["why_problem"]
    assert rec["simple_explanation"]["what_to_change"]
    assert rec["simple_explanation"]["how_it_helps"]
    assert rec["technical_explanation"]["location"]
    assert rec["technical_explanation"]["supporting_evidence"]

    # 1. Preview Fix
    prev_resp = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/preview",
        json={"recommendation_id": rec["id"]},
    )
    assert prev_resp.status_code == 200
    preview = prev_resp.json()
    assert preview["auto_fixable"] is True
    assert "import asyncio" in preview["patched_code"]
    assert "await asyncio.sleep(5)" in preview["patched_code"]
    assert "def helper_keep_me(x: int) -> int:" in preview["patched_code"]  # Unrelated code preserved
    assert "-    time.sleep(5)" in preview["diff"]
    assert "+    await asyncio.sleep(5)" in preview["diff"]

    # 2. Apply Fix & Re-analyze with validated hash
    apply_resp = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"], "expected_source_hash": preview["source_hash"]},
    )
    assert apply_resp.status_code == 200
    applied = apply_resp.json()

    v2 = applied["analysis"]
    comp = applied["comparison"]
    assert v2["id"] != v1["id"]
    assert v2["parent_analysis_id"] == v1["id"]
    assert v2["root_analysis_id"] == v1["id"]
    assert v2["revision_number"] == 2
    assert v2["findings"] == []
    assert v2["root_causes"] == []
    assert v2["recommendations"] == []
    assert v2["overall_score"] == 100.0

    # Verify genuine before/after comparison
    assert comp["before_score"] == 90.0
    assert comp["after_score"] == 100.0
    assert comp["score_delta"] == 10.0
    assert comp["before_findings_count"] == 1
    assert comp["after_findings_count"] == 0
    assert len(comp["resolved_findings"]) == 1
    assert len(comp["remaining_findings"]) == 0
    assert len(comp["newly_introduced_findings"]) == 0
    assert comp["status"] == "improved"

    # 3. Original v1 analysis must remain completely intact (Undo Fix target!)
    v1_again = client.get(f"/api/v1/analyses/{v1['id']}").json()
    assert len(v1_again["findings"]) == 1
    assert v1_again["overall_score"] == 90.0
    src_v1 = client.get(f"/api/v1/analyses/{v1['id']}/source").json()
    assert "time.sleep(5)" in src_v1["files"]["worker.py"]["content"]

    # 4. Revision history lists v1 and v2 in order
    revs = client.get(f"/api/v1/analyses/{v2['id']}/revisions").json()
    assert len(revs) == 2
    assert [r["revision_number"] for r in revs] == [1, 2]
    assert revs[0]["overall_score"] == 90.0
    assert revs[1]["overall_score"] == 100.0


def test_b_sequential_multi_fix_revisions_v1_v2_v3(client):
    code = (
        "import requests\n\n"
        "events_log = []\n\n"
        "def sync_fetch(url):\n"
        "    resp = requests.get(url)\n"
        "    events_log.append(resp.text)\n"
        "    return resp.status_code\n"
    )
    v1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Multi-Fix Progression", "code": code, "language": "python", "file_name": "sync_svc.py"},
    ).json()
    assert len(v1["findings"]) == 2  # PY_MISSING_TIMEOUT + PY_UNBOUNDED_COLLECTION
    score_v1 = v1["overall_score"]

    # Apply first fix (timeout)
    rec_timeout = next(r for r in v1["recommendations"] if r["rule_id"] == "PY_MISSING_TIMEOUT")
    res_v2 = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec_timeout["id"]},
    ).json()
    v2 = res_v2["analysis"]
    assert v2["revision_number"] == 2
    assert len(v2["findings"]) == 1
    assert v2["overall_score"] > score_v1
    assert "timeout=10" in res_v2["fixed_code"]

    # Apply second fix (unbounded collection -> deque(maxlen=1000))
    rec_mem = next(r for r in v2["recommendations"] if r["rule_id"] == "PY_UNBOUNDED_COLLECTION")
    res_v3 = client.post(
        f"/api/v1/analyses/{v2['id']}/fixes/apply",
        json={"recommendation_id": rec_mem["id"]},
    ).json()
    v3 = res_v3["analysis"]
    assert v3["revision_number"] == 3
    assert len(v3["findings"]) == 0
    assert v3["overall_score"] == 100.0
    assert "deque(maxlen=1000)" in res_v3["fixed_code"]

    # Verify full v1 -> v2 -> v3 lineage
    revs = client.get(f"/api/v1/analyses/{v3['id']}/revisions").json()
    assert [r["revision_number"] for r in revs] == [1, 2, 3]
    assert revs[0]["findings_count"] == 2
    assert revs[1]["findings_count"] == 1
    assert revs[2]["findings_count"] == 0


def test_b_apply_unawaited_coroutine_and_infinite_retry_fixes(client):
    code = (
        "async def load_data():\n"
        "    return 'done'\n\n"
        "def process():\n"
        "    load_data()\n"
    )
    v1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Coroutine Auto-Fix", "code": code, "language": "python", "file_name": "coro.py"},
    ).json()
    rec = next(r for r in v1["recommendations"] if r["rule_id"] == "PY_UNAWAITED_COROUTINE")
    assert rec["auto_fixable"] is True
    applied = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"]},
    ).json()
    assert applied["analysis"]["findings"] == []
    assert applied["analysis"]["overall_score"] == 100.0
    assert "asyncio.run(load_data())" in applied["fixed_code"]

    # Infinite retry auto-fix
    retry_code = (
        "def poll(op):\n"
        "    while True:\n"
        "        try:\n"
        "            return op()\n"
        "        except Exception:\n"
        "            pass\n"
    )
    rv1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Retry Auto-Fix", "code": retry_code, "language": "python", "file_name": "retry.py"},
    ).json()
    rec_retry = next(r for r in rv1["recommendations"] if r["rule_id"] == "PY_UNBOUNDED_RETRY")
    assert rec_retry["auto_fixable"] is True
    applied_retry = client.post(
        f"/api/v1/analyses/{rv1['id']}/fixes/apply",
        json={"recommendation_id": rec_retry["id"]},
    ).json()
    assert applied_retry["analysis"]["findings"] == []
    assert applied_retry["analysis"]["overall_score"] == 100.0


# ==============================================================================
# TEST C & F: MANUAL FIX REQUIRED, STALE HASH REJECTION, AND REGRESSION HONESTY
# ==============================================================================
def test_c_and_f_manual_fix_stale_hash_and_regressed_edit(client):
    js_code = (
        "function findUser(uid) {\n"
        "    console.log(unknownVar);\n"
        "    return uid;\n"
        "}\n"
    )
    v1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "JS Manual Fix Test", "code": js_code, "language": "javascript", "file_name": "repo.js"},
    ).json()
    rec = next(r for r in v1["recommendations"] if r["rule_id"] == "JS_UNDEFINED_NAME")
    assert rec["auto_fixable"] is False
    assert rec["manual_fix_reason"]

    # 1. Attempting automated apply on unsupported fix MUST return 422 (no fake success!)
    r_unauto = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"]},
    )
    assert r_unauto.status_code == 422

    # 2. Stale hash MUST be rejected with 409 Conflict
    r_stale = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"], "expected_source_hash": "0000stalehash", "custom_code": "function f() { return 1; }\n"},
    )
    assert r_stale.status_code == 409

    # 3. Manual edit introducing a worse bug MUST honestly report regression!
    broken_edit = "function findUser(uid { eval(uid); }\n"
    r_reg = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"], "file_path": "repo.js", "custom_code": broken_edit},
    )
    assert r_reg.status_code == 200
    reg_data = r_reg.json()
    assert reg_data["analysis"]["overall_score"] < 100.0
    assert len(reg_data["comparison"]["newly_introduced_findings"]) >= 1
    assert reg_data["comparison"]["status"] in ("regressed", "no_change")

    # 4. Empty custom_code rejected with 400
    r_empty = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"file_path": "repo.py", "custom_code": "   \n  "},
    )
    assert r_empty.status_code == 400


# ==============================================================================
# TEST D: RECENT DIAGNOSES ENDPOINT, SORT ORDER & MODE FILTERING
# ==============================================================================
def test_d_recent_diagnoses_endpoint_and_filters(client):
    resp = client.get("/api/v1/analyses/recent?limit=5")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert len(items) <= 5
    # Verify newest-first ordering
    timestamps = [item["created_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)
    # Verify enriched fields exist
    first = items[0]
    assert "findings_count" in first
    assert "root_causes_count" in first
    assert "file_names" in first
    assert "revision_number" in first

    # Verify mode filtering
    code_only = client.get("/api/v1/analyses/recent?limit=10&mode=code").json()
    assert all(item["mode"] == "code" for item in code_only)


# ==============================================================================
# ADDITIONAL MANDATORY AUTO-FIX & PERSISTENCE TESTS (EXAMPLES B, C, D + TEST 7)
# ==============================================================================
def test_example_b_unclosed_file_autofix_and_escaped_handle_safety(client):
    # Safe local file open -> Auto Fix wraps with context manager and resolves finding!
    safe_open_code = (
        "def read_data(path):\n"
        '    file = open(path, "r")\n'
        "    return file.read()\n"
    )
    v1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Unclosed File AutoFix", "code": safe_open_code, "language": "python", "file_name": "reader.py"},
    ).json()
    rec = next(r for r in v1["recommendations"] if r["rule_id"] == "PY_UNCLOSED_RESOURCE")
    assert rec["auto_fixable"] is True
    applied = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"]},
    ).json()
    assert 'with open(path, "r") as file:' in applied["fixed_code"]
    assert applied["analysis"]["findings"] == []
    assert applied["analysis"]["overall_score"] == 100.0

    # Escaped handle (returned to caller) -> MUST NOT blindly wrap (Auto Fix Unavailable)
    escaped_code = (
        "def open_stream(path):\n"
        '    fh = open(path, "r")\n'
        "    return fh\n"
    )
    ev1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Escaped Handle Safety", "code": escaped_code, "language": "python", "file_name": "stream.py"},
    ).json()
    erec = next(r for r in ev1["recommendations"] if r["rule_id"] == "PY_UNCLOSED_RESOURCE")
    assert erec["auto_fixable"] is False
    assert "lifetime extends beyond this block" in (erec["manual_fix_reason"] or "")


def test_example_c_unawaited_coroutine_async_vs_sync_loop_safety(client):
    # Inside async def -> inserts `await ` cleanly
    async_ctx = (
        "async def fetch_data():\n"
        "    return 10\n\n"
        "async def main():\n"
        "    fetch_data()\n"
    )
    v1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Async Context Coroutine Fix", "code": async_ctx, "language": "python", "file_name": "main.py"},
    ).json()
    rec = next(r for r in v1["recommendations"] if r["rule_id"] == "PY_UNAWAITED_COROUTINE")
    assert rec["auto_fixable"] is True
    applied = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"]},
    ).json()
    assert "await fetch_data()" in applied["fixed_code"]
    assert applied["analysis"]["findings"] == []
    assert applied["analysis"]["overall_score"] == 100.0

    # Inside sync loop -> must NOT blindly insert `await` or loop `asyncio.run()`!
    sync_loop = (
        "async def fetch_user(uid):\n"
        "    return {'id': uid}\n\n"
        "def process_users(users):\n"
        "    results = []\n"
        "    for u in users:\n"
        "        results.append(fetch_user(u))\n"
        "    return results\n"
    )
    sv1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Sync Loop Coroutine Safety", "code": sync_loop, "language": "python", "file_name": "users.py"},
    ).json()
    srec = next(r for r in sv1["recommendations"] if r["rule_id"] == "PY_UNAWAITED_COROUTINE")
    assert srec["auto_fixable"] is False
    assert "synchronous loop" in (srec["manual_fix_reason"] or "")


def test_example_d_configurable_timeout_policy_and_revision_compare(client):
    code = (
        "import requests\n\n"
        "def ping(url):\n"
        "    response = requests.get(url)\n"
        "    return response.status_code\n"
    )
    v1 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Configurable Timeout Test", "code": code, "language": "python", "file_name": "ping.py"},
    ).json()
    rec = next(r for r in v1["recommendations"] if r["rule_id"] == "PY_MISSING_TIMEOUT")

    # Preview with custom timeout policy = 25s
    prev = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/preview",
        json={"recommendation_id": rec["id"], "options": {"timeout_seconds": 25}},
    ).json()
    assert prev["auto_fixable"] is True
    assert "timeout=25" in prev["patched_code"]

    applied = client.post(
        f"/api/v1/analyses/{v1['id']}/fixes/apply",
        json={"recommendation_id": rec["id"], "expected_source_hash": prev["source_hash"], "options": {"timeout_seconds": 25}},
    ).json()
    v2_id = applied["analysis"]["id"]
    assert "timeout=25" in applied["fixed_code"]
    assert applied["analysis"]["findings"] == []

    # Dedicated revision compare endpoint returns exact before/after metrics
    cmp_resp = client.get(f"/api/v1/analyses/{v2_id}/revisions/compare")
    assert cmp_resp.status_code == 200
    cmp_data = cmp_resp.json()
    assert cmp_data["before_analysis_id"] == v1["id"]
    assert cmp_data["after_analysis_id"] == v2_id
    assert cmp_data["score_delta"] > 0

    # Autofix rules registry endpoint
    rules_resp = client.get("/api/v1/autofix/rules")
    assert rules_resp.status_code == 200
    assert rules_resp.json()["default_http_timeout_seconds"] == 10.0


def test_7_persistence_survives_fresh_session_and_client():
    """Simulates backend restart by creating a brand new TestClient and querying SQLite directly."""
    c1 = TestClient(app)
    created = c1.post(
        "/api/v1/analyses/paste",
        json={
            "title": "Restart Persistence Check",
            "code": "import time\nasync def job():\n    time.sleep(1)\n",
            "language": "python",
            "file_name": "persist_job.py",
        },
    ).json()
    aid = created["id"]

    # Brand new client instance reading persisted history
    c2 = TestClient(app)
    recent = c2.get("/api/v1/analyses/recent?limit=10").json()
    assert any(item["id"] == aid for item in recent)
    restored = c2.get(f"/api/v1/analyses/{aid}").json()
    assert restored["id"] == aid
    assert len(restored["findings"]) == 1
    assert restored["overall_score"] == 90.0


def test_syntax_error_autofix_and_apply_flow():
    """
    Verifies that Python syntax errors (like missing commas in function calls)
    are marked auto-fixable, generate clean diffs, and can be applied via the
    apply endpoint to successfully resolve the compilation error and elevate health score.
    """
    client = TestClient(app)

    # User's exact snippet
    user_code = "printf(hii chi=omu)\n"
    res = client.post(
        "/api/v1/analyses/paste",
        json={
            "title": "Syntax Error Test",
            "code": user_code,
            "file_name": "service.py",
            "language": "python",
        },
    )
    assert res.status_code == 200
    data = res.json()
    orig_id = data["id"]
    assert len(data["findings"]) >= 1
    assert any(f["rule_id"] == "PY_SYNTAX_ERROR" for f in data["findings"])

    recs = data["recommendations"]
    syntax_rec = next((r for r in recs if r["rule_id"] == "PY_SYNTAX_ERROR"), None)
    assert syntax_rec is not None
    assert syntax_rec["auto_fixable"] is True
    assert syntax_rec["diff"] is not None

    # Preview fix
    preview_res = client.post(
        f"/api/v1/analyses/{orig_id}/fixes/preview",
        json={"recommendation_id": syntax_rec["id"]},
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["auto_fixable"] is True
    assert "print(hii, chi=omu)" in preview_data["diff"]

    # Apply fix
    apply_res = client.post(
        f"/api/v1/analyses/{orig_id}/fixes/apply",
        json={"recommendation_id": syntax_rec["id"]},
    )
    assert apply_res.status_code == 200
    result = apply_res.json()
    assert result["applied_file_path"] == "service.py"
    assert "print(hii, chi=omu)" in result["fixed_code"]

    # Check comparison
    comp = result["comparison"]
    assert comp["score_delta"] > 0
    assert len(comp["resolved_findings"]) >= 1
    assert not any(f["rule_id"] == "PY_SYNTAX_ERROR" for f in result["analysis"]["findings"])
    assert result["fixed_code"] is not None

