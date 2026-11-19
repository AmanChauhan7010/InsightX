import io
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.analyzers.code.python_analyzer import PythonCodeAnalyzer
from backend.app.services.scoring import EvidenceCategory, HealthScoreCalculator


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# TEST CASE 1: Blocking time.sleep() inside async function
# ==============================================================================
def test_case_1_blocking_time_sleep_in_async():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import time\n\n"
        "async def serve_job():\n"
        "    time.sleep(5)\n"
        "    return 'done'\n"
    )
    res = analyzer.analyze(code, file_path="jobs.py")
    matches = [f for f in res["findings"] if f["rule_id"] == "PY_ASYNC_BLOCKING_SLEEP"]
    assert len(matches) == 1
    f = matches[0]
    assert f["file_path"] == "jobs.py"
    assert f["line_number"] == 4
    assert f["severity"] == "High"  # Not Critical by default in static-only mode
    assert f["evidence_category"] == EvidenceCategory.STATIC_CODE
    assert f["is_confirmed"] is False


# ==============================================================================
# TEST CASE 2: Async function called without await (multiple variations)
# ==============================================================================
def test_case_2_unawaited_coroutine_variations():
    analyzer = PythonCodeAnalyzer()

    # 2a. Inserted into collection without gather/await (renamed identifiers)
    code_collection = (
        "async def load_profile(account_id):\n"
        "    return {'account': account_id}\n\n"
        "def collect_profiles(ids):\n"
        "    output = []\n"
        "    for item in ids:\n"
        "        output.append(load_profile(item))\n"
        "    return output\n"
    )
    res = analyzer.analyze(code_collection, file_path="profiles.py")
    coro_findings = [f for f in res["findings"] if f["rule_id"] == "PY_UNAWAITED_COROUTINE"]
    assert len(coro_findings) == 1
    assert coro_findings[0]["line_number"] == 7
    assert "load_profile" in coro_findings[0]["title"]

    # 2b. Assigned to a variable and never awaited + standalone discarded call
    code_discarded = (
        "async def sync_record(rec_id):\n"
        "    return rec_id\n\n"
        "def trigger(rec_id):\n"
        "    sync_record(rec_id)\n"
        "    pending = sync_record(rec_id)\n"
        "    return str(pending)\n"
    )
    res2 = analyzer.analyze(code_discarded, file_path="syncer.py")
    coro2 = [f for f in res2["findings"] if f["rule_id"] == "PY_UNAWAITED_COROUTINE"]
    assert len(coro2) == 2
    assert {f["line_number"] for f in coro2} == {5, 6}

    # 2c. Class async method called via self without await
    code_method = (
        "class OrderClient:\n"
        "    async def pull_order(self, oid):\n"
        "        return {'oid': oid}\n\n"
        "    def inspect(self, oid):\n"
        "        data = self.pull_order(oid)\n"
        "        return data\n"
    )
    res3 = analyzer.analyze(code_method, file_path="orders.py")
    assert any(f["rule_id"] == "PY_UNAWAITED_COROUTINE" and f["line_number"] == 6 for f in res3["findings"])


# ==============================================================================
# TEST CASE 3: Potential infinite retry with swallowed errors
# ==============================================================================
def test_case_3_infinite_retry_with_swallowed_errors():
    analyzer = PythonCodeAnalyzer()
    code = (
        "async def pull_remote_payload(client):\n"
        "    while True:\n"
        "        try:\n"
        "            return await client.get_payload()\n"
        "        except Exception:\n"
        "            pass\n"
    )
    res = analyzer.analyze(code, file_path="fetcher.py")
    retry_findings = [f for f in res["findings"] if f["rule_id"] == "PY_UNBOUNDED_RETRY"]
    assert len(retry_findings) == 1
    rf = retry_findings[0]
    assert rf["file_path"] == "fetcher.py"
    assert rf["line_number"] == 2
    assert rf["line_end"] == 6
    assert rf["severity"] == "High"
    assert rf["evidence_category"] == EvidenceCategory.STATIC_CODE


# ==============================================================================
# TEST CASE 4: Legitimate bounded retry mechanism & legitimate event loop (NO false positives)
# ==============================================================================
def test_case_4_legitimate_bounded_retry_no_false_positive():
    analyzer = PythonCodeAnalyzer()
    bounded_code = (
        "import asyncio\n"
        "import logging\n\n"
        "logger = logging.getLogger(__name__)\n\n"
        "async def fetch_with_cap(client, max_attempts=3):\n"
        "    attempts = 0\n"
        "    while True:\n"
        "        try:\n"
        "            return await client.read()\n"
        "        except TimeoutError as err:\n"
        "            attempts += 1\n"
        "            logger.warning('retry %d: %s', attempts, err)\n"
        "            if attempts >= max_attempts:\n"
        "                raise\n"
        "            await asyncio.sleep(2 ** attempts)\n\n"
        "async def queue_consumer(queue):\n"
        "    while True:\n"
        "        item = await queue.get()\n"
        "        if item is None:\n"
        "            break\n"
    )
    res = analyzer.analyze(bounded_code, file_path="safe_retry.py")
    retry_or_loop = [
        f for f in res["findings"]
        if f["rule_id"] in ("PY_UNBOUNDED_RETRY", "PY_UNBOUNDED_RETRY_INSPECT", "PY_UNCONTROLLED_LOOP")
    ]
    assert retry_or_loop == []


# ==============================================================================
# TEST CASE 5: Proper await asyncio.sleep() (NO blocking-sleep false positive)
# ==============================================================================
def test_case_5_proper_await_asyncio_sleep():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import asyncio\n"
        "from asyncio import sleep\n\n"
        "async def polite_wait():\n"
        "    await asyncio.sleep(1.5)\n"
        "    await sleep(0.5)\n"
        "    return True\n"
    )
    res = analyzer.analyze(code, file_path="good_async.py")
    assert not any(f["rule_id"] == "PY_ASYNC_BLOCKING_SLEEP" for f in res["findings"])
    assert res["findings"] == []


# ==============================================================================
# TEST CASE 6: Correctly awaited & scheduled async functions (NO unawaited false positive)
# ==============================================================================
def test_case_6_correctly_awaited_and_scheduled_coroutines():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import asyncio\n"
        "from typing import Coroutine\n\n"
        "async def query_item(item_id: int):\n"
        "    await asyncio.sleep(0.01)\n"
        "    return {'id': item_id}\n\n"
        "async def run_all(ids):\n"
        "    direct = await query_item(1)\n"
        "    task = asyncio.create_task(query_item(2))\n"
        "    gathered = await asyncio.gather(*[query_item(i) for i in ids])\n"
        "    pending = []\n"
        "    for i in ids:\n"
        "        pending.append(query_item(i))\n"
        "    batch = await asyncio.gather(*pending)\n"
        "    later = query_item(3)\n"
        "    later_val = await later\n"
        "    return direct, await task, gathered, batch, later_val\n\n"
        "def explicit_factory(item_id: int) -> Coroutine:\n"
        "    return query_item(item_id)\n"
    )
    res = analyzer.analyze(code, file_path="proper_coro.py")
    assert not any("UNAWAITED_COROUTINE" in f["rule_id"] for f in res["findings"])


# ==============================================================================
# TEST CASE 7: Previously detected missing HTTP timeout still works
# ==============================================================================
def test_case_7_missing_http_timeout():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import requests\n\n"
        "def check_status(endpoint):\n"
        "    resp = requests.get(endpoint)\n"
        "    return resp.status_code\n"
    )
    res = analyzer.analyze(code, file_path="http_client.py")
    matches = [f for f in res["findings"] if f["rule_id"] == "PY_MISSING_TIMEOUT"]
    assert len(matches) == 1
    assert matches[0]["line_number"] == 4
    assert matches[0]["severity"] == "Medium"


# ==============================================================================
# TEST CASE 8: Clean Python file -> 0 findings, 0 root causes, 0 recommendations, 100/100
# ==============================================================================
def test_case_8_clean_python_file_end_to_end(client):
    clean_code = (
        "import asyncio\n"
        "import logging\n\n"
        "logger = logging.getLogger(__name__)\n\n"
        "async def compute_ratio(numerator: float, denominator: float) -> float:\n"
        "    if denominator == 0:\n"
        "        raise ValueError('denominator must be non-zero')\n"
        "    await asyncio.sleep(0.01)\n"
        "    return numerator / denominator\n\n"
        "def read_config(path: str) -> str:\n"
        "    with open(path, 'r', encoding='utf-8') as handle:\n"
        "        return handle.read()\n"
    )
    resp = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Clean Application Test", "code": clean_code, "language": "python", "file_name": "clean_app.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["findings"] == []
    assert data["root_causes"] == []
    assert data["recommendations"] == []
    assert data["overall_score"] == 100.0
    assert data["meta_info"]["score_breakdown"]["meaning"] == "No issues detected by the enabled analysis rules."


# ==============================================================================
# TEST CASE 9: Accurate line numbers with leading blank lines, decorators, classes, CRLF
# ==============================================================================
def test_case_9_accurate_line_numbers_with_blank_lines_and_decorators():
    analyzer = PythonCodeAnalyzer()
    # 3 leading blank lines + imports + class + decorator + nested function + CRLF endings
    code = (
        "\r\n"
        "\r\n"
        "\r\n"
        "import time\r\n"
        "import functools\r\n"
        "\r\n"
        "def trace(fn):\r\n"
        "    return fn\r\n"
        "\r\n"
        "class WorkerService:\r\n"
        "    @trace\r\n"
        "    async def execute(self):\r\n"
        "        def inner_sync():\r\n"
        "            time.sleep(0.1)  # sync nested helper, NOT directly async\r\n"
        "        time.sleep(5)  # line 15: blocking call inside async def\r\n"
        "        return inner_sync\r\n"
    )
    res = analyzer.analyze(code, file_path="decorated.py")
    blocking = [f for f in res["findings"] if f["rule_id"] == "PY_ASYNC_BLOCKING_SLEEP"]
    # Only line 15 should be flagged (nested sync def on line 14 must NOT be flagged as in_async!)
    assert len(blocking) == 1
    assert blocking[0]["line_number"] == 15
    assert "time.sleep(5)" in blocking[0]["code_snippet"]


# ==============================================================================
# TEST CASE 10: Switching from faulty analysis to clean analysis yields zero stale data
# ==============================================================================
def test_case_10_switch_faulty_to_clean_no_stale_state(client):
    faulty_code = "import time\nasync def slow():\n    time.sleep(5)\n"
    clean_code = "def add(a: int, b: int) -> int:\n    return a + b\n"

    r_faulty = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Faulty Run", "code": faulty_code, "language": "python", "file_name": "faulty.py"},
    )
    assert r_faulty.status_code == 200
    faulty_data = r_faulty.json()
    assert len(faulty_data["findings"]) == 1
    assert len(faulty_data["root_causes"]) == 1
    assert len(faulty_data["recommendations"]) == 1

    # Verify all finding/cause IDs belong exclusively to faulty_data
    faulty_finding_ids = {f["id"] for f in faulty_data["findings"]}
    for rc in faulty_data["root_causes"]:
        assert rc["analysis_id"] == faulty_data["id"]
        assert set(rc["related_finding_ids"]).issubset(faulty_finding_ids)
    for rec in faulty_data["recommendations"]:
        assert rec["analysis_id"] == faulty_data["id"]
        assert set(rec["related_finding_ids"]).issubset(faulty_finding_ids)

    r_clean = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Clean Run", "code": clean_code, "language": "python", "file_name": "clean.py"},
    )
    assert r_clean.status_code == 200
    clean_data = r_clean.json()

    # Re-fetch clean via GET endpoint to confirm persistent clean state
    fetched_clean = client.get(f"/api/v1/analyses/{clean_data['id']}").json()
    assert fetched_clean["findings"] == []
    assert fetched_clean["root_causes"] == []
    assert fetched_clean["recommendations"] == []
    assert fetched_clean["overall_score"] == 100.0


# ==============================================================================
# TEST CASE 11: Identical issue patterns in different files produce file-specific evidence
# ==============================================================================
def test_case_11_identical_patterns_in_different_files(client):
    file_a = b"import time\nasync def job_alpha():\n    time.sleep(3)\n"
    file_b = b"\n\nimport time\nasync def job_beta():\n    time.sleep(7)\n"
    resp = client.post(
        "/api/v1/analyses",
        data={"title": "Dual File Check", "mode": "code"},
        files=[
            ("files", ("alpha_worker.py", io.BytesIO(file_a), "text/x-python")),
            ("files", ("beta_worker.py", io.BytesIO(file_b), "text/x-python")),
        ],
    )
    assert resp.status_code == 200
    data = resp.json()
    by_file = {f["file_path"]: f for f in data["findings"]}
    assert "alpha_worker.py" in by_file and "beta_worker.py" in by_file
    assert by_file["alpha_worker.py"]["line_number"] == 3
    assert "time.sleep(3)" in by_file["alpha_worker.py"]["code_snippet"]
    assert by_file["beta_worker.py"]["line_number"] == 5
    assert "time.sleep(7)" in by_file["beta_worker.py"]["code_snippet"]

    # Verify recommendations preserve file-specific sleep durations!
    recs_by_file = {r["file_path"]: r for r in data["recommendations"]}
    assert "await asyncio.sleep(3)" in recs_by_file["alpha_worker.py"]["refactored_code"]
    assert "await asyncio.sleep(7)" in recs_by_file["beta_worker.py"]["refactored_code"]


# ==============================================================================
# TEST CASE 12: Evidence category verification (no runtime-proof labels on code-only)
# ==============================================================================
def test_case_12_evidence_categories_code_only_vs_combined(client):
    code_only = (
        "import time\n"
        "async def handler():\n"
        "    time.sleep(5)\n"
    )
    resp = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Code Only Evidence Check", "code": code_only, "language": "python", "file_name": "svc.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for f in data["findings"]:
        assert f["evidence_category"] == EvidenceCategory.STATIC_CODE
        assert f["is_confirmed"] is False
    for rc in data["root_causes"]:
        assert rc["evidence_category"] == EvidenceCategory.STATIC_CODE
        assert rc["cause_type"] == "Static Potential Cause"

    # Verify recommendation explicitly mentions asyncio.sleep(5) and import asyncio
    rec = data["recommendations"][0]
    assert "await asyncio.sleep(5)" in rec["refactored_code"]
    assert "import asyncio" in rec["why_recommended"] or "import asyncio" in rec["refactored_code"]


# ==============================================================================
# FULL TEST A SUITE: Faulty Python application containing all 8 target defect classes
# ==============================================================================
def test_full_faulty_app_detects_all_8_issues(client):
    faulty_app = (
        "import time\n"
        "import requests\n\n"
        "audit_cache = []\n\n"
        "async def fetch_record(rec_id):\n"
        "    return {'id': rec_id}\n\n"
        "async def process_endpoint(url, path):\n"
        "    time.sleep(4)\n"
        "    resp = requests.get(url)\n"
        "    f = open(path, 'r')\n"
        "    audit_cache.append(resp.text)\n"
        "    while True:\n"
        "        try:\n"
        "            return await fetch_record(1)\n"
        "        except Exception:\n"
        "            pass\n\n"
        "def batch_fetch(ids):\n"
        "    out = []\n"
        "    for i in ids:\n"
        "        out.append(fetch_record(i))\n"
        "    return out\n"
    )
    resp = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Full Faulty App Audit", "code": faulty_app, "language": "python", "file_name": "faulty_app.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    rule_ids = {f["rule_id"] for f in data["findings"]}

    expected_rules = {
        "PY_ASYNC_BLOCKING_SLEEP",
        "PY_ASYNC_BLOCKING_HTTP",
        "PY_MISSING_TIMEOUT",
        "PY_UNCLOSED_RESOURCE",
        "PY_UNBOUNDED_COLLECTION",
        "PY_UNBOUNDED_RETRY",
        "PY_SILENT_EXCEPT",
        "PY_UNAWAITED_COROUTINE",
    }
    assert expected_rules.issubset(rule_ids), f"Missing rules: {expected_rules - rule_ids}"

    # Verify recommendations are rule-accurate (no wrong db.connect or asyncio.sleep for HTTP/memory!)
    rec_titles = [r["title"] for r in data["recommendations"]]
    assert any("asyncio.sleep" in t for t in rec_titles)
    assert any("Async Client" in t for t in rec_titles)
    assert any("Bound Retry Loops" in t for t in rec_titles)
    assert any("Await or Schedule Coroutine" in t for t in rec_titles)
    assert any("Bound In-Memory Collection" in t for t in rec_titles)


# ==============================================================================
# HEALTH SCORE DEDUPLICATION & EXPLAINABILITY TEST
# ==============================================================================
def test_health_score_deduplication_and_normalization():
    # Duplicate occurrences of same rule should incur diminished penalty vs distinct rules
    dup_findings = [
        {"file_path": "a.py", "rule_id": "PY_MISSING_TIMEOUT", "severity": "Medium", "title": "Missing timeout"}
        for _ in range(5)
    ]
    breakdown = HealthScoreCalculator.compute(findings=dup_findings, files_count=1)
    assert breakdown["duplicate_dampening_saved"] > 0
    # 1st = 5.0, next 3 = 3 * 1.75 = 5.25, 5th = 0 -> total = 10.25 -> score = 89.8
    assert breakdown["score"] == pytest.approx(89.8, abs=0.1)


# ==============================================================================
# ADDITIONAL GENERALIZATION & EDGE-CASE TESTS (ISSUES 1-5)
# ==============================================================================
def test_sync_unbounded_retry_and_nested_and_flag_loops():
    analyzer = PythonCodeAnalyzer()

    # 1. Synchronous while True with swallowed exception
    sync_retry = (
        "def poll_backend(client):\n"
        "    while True:\n"
        "        try:\n"
        "            return client.fetch()\n"
        "        except Exception:\n"
        "            pass\n"
    )
    res1 = analyzer.analyze(sync_retry, file_path="poller.py")
    retries1 = [f for f in res1["findings"] if f["rule_id"] == "PY_UNBOUNDED_RETRY"]
    assert len(retries1) == 1
    assert retries1[0]["line_number"] == 2
    assert retries1[0]["line_end"] == 6

    # 2. Try nested inside `if` inside `while True` + specific exception silently swallowed without backoff
    nested_retry = (
        "def run_sync(enabled, action):\n"
        "    while True:\n"
        "        if enabled:\n"
        "            try:\n"
        "                return action()\n"
        "            except TimeoutError:\n"
        "                pass\n"
    )
    res2 = analyzer.analyze(nested_retry, file_path="nested_retry.py")
    retries2 = [f for f in res2["findings"] if f["rule_id"] == "PY_UNBOUNDED_RETRY"]
    assert len(retries2) == 1
    assert retries2[0]["line_number"] == 2

    # 3. Flag-guarded retry loop where flag is never updated on error
    flag_retry = (
        "def deliver_event(sender):\n"
        "    delivered = False\n"
        "    while not delivered:\n"
        "        try:\n"
        "            sender.send()\n"
        "            delivered = True\n"
        "        except Exception:\n"
        "            pass\n"
    )
    res3 = analyzer.analyze(flag_retry, file_path="flag_retry.py")
    retries3 = [f for f in res3["findings"] if f["rule_id"] == "PY_UNBOUNDED_RETRY"]
    assert len(retries3) == 1
    assert retries3[0]["line_number"] == 3


def test_unawaited_coroutine_discarded_aliases_nested_and_instances():
    analyzer = PythonCodeAnalyzer()

    # 1. Discarded unawaited coroutine inside for-loop
    code_discard = (
        "async def load_entity(entity_key):\n"
        "    return entity_key\n\n"
        "def run_batch(keys):\n"
        "    for k in keys:\n"
        "        load_entity(k)\n"
    )
    res1 = analyzer.analyze(code_discard, file_path="batch.py")
    f1 = [f for f in res1["findings"] if f["rule_id"] == "PY_UNAWAITED_COROUTINE"]
    assert len(f1) == 1
    assert f1[0]["line_number"] == 6
    assert "load_entity" in f1[0]["title"]

    # 2. Aliased async function (module alias + chained local alias)
    code_alias = (
        "async def pull_metric(metric_id):\n"
        "    return metric_id\n\n"
        "metric_loader = pull_metric\n\n"
        "def dispatch(ids):\n"
        "    fn = metric_loader\n"
        "    for mid in ids:\n"
        "        fn(mid)\n"
    )
    res2 = analyzer.analyze(code_alias, file_path="aliases.py")
    f2 = [f for f in res2["findings"] if f["rule_id"] == "PY_UNAWAITED_COROUTINE"]
    assert len(f2) == 1
    assert f2[0]["line_number"] == 9
    assert "pull_metric" in f2[0]["title"]

    # 3. Nested scope async function + class instance method call without await
    code_nested_and_inst = (
        "class DataGateway:\n"
        "    async def query_row(self, row_id):\n"
        "        return row_id\n\n"
        "def orchestrate(row_ids):\n"
        "    gw = DataGateway()\n"
        "    async def inner_step(val):\n"
        "        return val * 2\n"
        "    for rid in row_ids:\n"
        "        gw.query_row(rid)\n"
        "        inner_step(rid)\n"
    )
    res3 = analyzer.analyze(code_nested_and_inst, file_path="nested.py")
    f3 = [f for f in res3["findings"] if f["rule_id"] == "PY_UNAWAITED_COROUTINE"]
    assert len(f3) == 2
    assert {f["line_number"] for f in f3} == {10, 11}


def test_intentional_coroutine_return_and_create_task_no_false_positive():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import asyncio\n"
        "from asyncio import create_task\n\n"
        "async def fetch_entry(entry_id):\n"
        "    return {'id': entry_id}\n\n"
        "alias_fetch = fetch_entry\n\n"
        "def make_entry_coro(entry_id):\n"
        "    normalized = str(entry_id).strip()\n"
        "    return fetch_entry(normalized)\n\n"
        "async def schedule_all(entries):\n"
        "    t1 = asyncio.create_task(fetch_entry(1))\n"
        "    t2 = create_task(alias_fetch(2))\n"
        "    v3 = await alias_fetch(3)\n"
        "    return await t1, await t2, v3\n"
    )
    res = analyzer.analyze(code, file_path="valid_async.py")
    assert res["findings"] == []


def test_clean_analysis_causes_endpoint_and_db_isolation(client):
    clean_src = (
        "def normalize_scores(values):\n"
        "    total = sum(values)\n"
        "    if total == 0:\n"
        "        return []\n"
        "    return [v / total for v in values]\n"
    )
    resp = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Clean Causes Endpoint Check", "code": clean_src, "language": "python", "file_name": "norm.py"},
    )
    assert resp.status_code == 200
    data = resp.json()
    aid = data["id"]
    assert data["findings"] == []
    assert data["root_causes"] == []
    assert data["recommendations"] == []
    assert data["overall_score"] == 100.0

    # Verify dedicated /causes endpoint also returns empty list from SQLite
    causes_resp = client.get(f"/api/v1/analyses/{aid}/causes")
    assert causes_resp.status_code == 200
    assert causes_resp.json() == []
