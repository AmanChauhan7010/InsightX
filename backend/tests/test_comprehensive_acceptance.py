import io
import json
import zipfile
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.analyzers.code.python_analyzer import PythonCodeAnalyzer
from backend.app.analyzers.code.rule_registry import RuleRegistry
from backend.app.analyzers.metrics.anomaly_analyzer import MetricAnomalyAnalyzer
from backend.app.analyzers.logs.log_analyzer import LogAnalyzer
from backend.app.services.scoring import EvidenceCategory


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def client():
    return TestClient(app)


# ==============================================================================
# RULE REGISTRY & API INTROSPECTION
# ==============================================================================
def test_rule_registry_and_rules_endpoint(client):
    resp = client.get("/api/v1/rules")
    assert resp.status_code == 200
    payload = resp.json()
    assert set(["python", "javascript", "typescript"]).issubset(set(payload["supported_languages"]))
    rule_ids = {r["rule_id"] for r in payload["rules"]}
    assert {
        "PY_ASYNC_BLOCKING_SLEEP",
        "PY_UNBOUNDED_RETRY",
        "PY_UNAWAITED_COROUTINE",
        "PY_UNSAFE_DESERIALIZATION",
        "PY_SUBPROCESS_SHELL",
        "PY_MISSING_TIMEOUT",
    }.issubset(rule_ids)
    # Filter by language
    py_only = client.get("/api/v1/rules?language=python").json()["rules"]
    assert all("python" in r["languages"] for r in py_only)


# ==============================================================================
# GROUP D: POSITIVE & NEGATIVE FALSE-POSITIVE CONTROLS (TIMEOUT, RESOURCE, MEMORY, SECURITY)
# ==============================================================================
def test_group_d_safe_vs_unsafe_controls():
    analyzer = PythonCodeAnalyzer()

    # Safe code: timeout present, context-managed file, bounded collection, yaml.safe_load, subprocess shell=False
    safe_code = (
        "import requests\n"
        "import yaml\n"
        "import subprocess\n"
        "from collections import deque\n\n"
        "recent_items = deque(maxlen=500)\n"
        "evicted_list = []\n\n"
        "def safe_pipeline(url, cfg_path, raw_yaml):\n"
        "    resp = requests.get(url, timeout=(3.0, 10.0))\n"
        "    with open(cfg_path, 'r', encoding='utf-8') as fh:\n"
        "        _ = fh.read()\n"
        "    parsed = yaml.safe_load(raw_yaml)\n"
        "    subprocess.run(['echo', 'ok'], shell=False, check=True)\n"
        "    recent_items.append(resp.status_code)\n"
        "    evicted_list.append(parsed)\n"
        "    if len(evicted_list) > 100:\n"
        "        evicted_list.pop(0)\n"
        "    return parsed\n"
    )
    res_safe = analyzer.analyze(safe_code, file_path="safe_controls.py")
    assert res_safe["findings"] == [], f"Unexpected false positives: {res_safe['findings']}"

    # Unsafe security patterns: pickle.loads, yaml.load without SafeLoader, subprocess shell=True, os.system
    unsafe_sec = (
        "import pickle\n"
        "import yaml\n"
        "import subprocess\n"
        "import os\n\n"
        "def risky_loader(blob, text, cmd):\n"
        "    obj = pickle.loads(blob)\n"
        "    cfg = yaml.load(text)\n"
        "    subprocess.run(cmd, shell=True)\n"
        "    os.system(cmd)\n"
        "    return obj, cfg\n"
    )
    res_sec = analyzer.analyze(unsafe_sec, file_path="risky_sec.py")
    sec_rules = {f["rule_id"] for f in res_sec["findings"]}
    assert "PY_UNSAFE_DESERIALIZATION" in sec_rules
    assert "PY_SUBPROCESS_SHELL" in sec_rules
    assert len([f for f in res_sec["findings"] if f["rule_id"] == "PY_UNSAFE_DESERIALIZATION"]) == 2
    assert len([f for f in res_sec["findings"] if f["rule_id"] == "PY_SUBPROCESS_SHELL"]) == 2


# ==============================================================================
# GROUP C: ADDITIONAL RETRY NEGATIVE CONTROLS (MEANINGFUL BREAK & CONTROLLED RE-RAISE)
# ==============================================================================
def test_group_c_retry_negative_controls():
    analyzer = PythonCodeAnalyzer()
    safe_loops = (
        "import asyncio\n\n"
        "def controlled_retry(op):\n"
        "    while True:\n"
        "        try:\n"
        "            return op()\n"
        "        except RuntimeError:\n"
        "            raise\n\n"
        "def stream_reader(stream):\n"
        "    while True:\n"
        "        chunk = stream.read(1024)\n"
        "        if not chunk:\n"
        "            break\n\n"
        "async def controlled_worker(stop_evt, queue):\n"
        "    while not stop_evt.is_set():\n"
        "        msg = await queue.get()\n"
        "        if msg is None:\n"
        "            break\n"
    )
    res = analyzer.analyze(safe_loops, file_path="safe_loops.py")
    assert res["findings"] == []


# ==============================================================================
# GROUP G: METRICS & LOGS (NORMAL METRICS, MISSING TS, DUPLICATE/UNORDERED, MALFORMED, JSON LOGS)
# ==============================================================================
def test_group_g_metrics_normal_vs_anomalous_and_edge_cases():
    analyzer = MetricAnomalyAnalyzer()

    # 1. Normal steady-state metrics -> MUST produce 0 false anomalies!
    normal_rows = ["timestamp,cpu_utilization,memory_mb,latency_ms"]
    for i in range(25):
        normal_rows.append(f"2026-11-18T10:{i:02d}:00Z,{30.0 + (i % 3) * 0.5},{512.0 + (i % 2)},{42.0 + (i % 4) * 0.5}")
    normal_res = analyzer.analyze("\n".join(normal_rows), file_name="normal.csv")
    assert normal_res["valid"] is True
    assert normal_res["anomaly_count"] == 0
    assert normal_res["anomalous_intervals"] == []
    assert len(normal_res["time_series"]) == 25

    # 2. Out-of-order + duplicate timestamps + missing values + real anomaly interval
    messy_rows = [
        "timestamp,cpu_utilization,p95_latency_ms",
        "2026-11-18T10:05:00Z,28.0,45.0",
        "2026-11-18T10:01:00Z,27.0,44.0",
        "2026-11-18T10:01:00Z,29.0,46.0",  # duplicate timestamp
        "2026-11-18T10:02:00Z,,45.0",      # missing value
        "2026-11-18T10:03:00Z,28.0,44.0",
        "2026-11-18T10:04:00Z,27.5,45.5",
        "2026-11-18T10:06:00Z,28.5,46.0",
        "2026-11-18T10:07:00Z,28.0,45.0",
        "2026-11-18T10:08:00Z,27.5,44.5",
        "2026-11-18T10:09:00Z,28.0,45.0",
        "2026-11-18T10:10:00Z,97.5,3900.0",  # anomalous interval start
        "2026-11-18T10:11:00Z,98.2,4100.0",  # anomalous interval end
        "2026-11-18T10:12:00Z,28.0,45.0",
    ]
    messy_res = analyzer.analyze("\n".join(messy_rows), file_name="messy.csv")
    assert messy_res["valid"] is True
    assert messy_res["data_quality"]["out_of_order_sorted"] is True
    assert messy_res["data_quality"]["duplicate_timestamps_merged"] == 1
    assert messy_res["data_quality"]["missing_values_imputed"] >= 1
    assert messy_res["anomaly_count"] >= 2
    assert len(messy_res["anomalous_intervals"]) >= 1

    # 3. Missing timestamps -> synthesized cleanly
    no_ts = "cpu_pct,latency_ms\n20,40\n21,41\n20,40\n22,42\n21,40\n98,4200\n20,41\n"
    no_ts_res = analyzer.analyze(no_ts, file_name="no_ts.csv")
    assert no_ts_res["valid"] is True
    assert no_ts_res["data_quality"]["timestamp_status"] == "missing_timestamps_synthesized"
    assert no_ts_res["anomaly_count"] >= 1

    # 4. Malformed non-numeric metrics -> valid=False
    bad_res = analyzer.analyze("col_a,col_b\nfoo,bar\nbaz,qux\nhello,world\n", file_name="bad.csv")
    assert bad_res["valid"] is False
    assert bad_res["validation_error"] is not None


def test_group_g_logs_json_repeated_and_unparseable():
    log_analyzer = LogAnalyzer()

    # 1. JSON-lines structured logs with repeated errors
    json_logs = "\n".join([
        json.dumps({"timestamp": "2026-11-18T10:00:01Z", "level": "INFO", "service": "orders", "message": "Started"}),
        json.dumps({"timestamp": "2026-11-18T10:00:05Z", "level": "ERROR", "service": "orders", "message": "Upstream timeout on /pay"}),
        json.dumps({"timestamp": "2026-11-18T10:00:08Z", "level": "ERROR", "service": "orders", "message": "Upstream timeout on /pay"}),
        json.dumps({"timestamp": "2026-11-18T10:00:12Z", "level": "ERROR", "service": "orders", "message": "Upstream timeout on /pay"}),
    ])
    res_json = log_analyzer.analyze(json_logs, file_name="orders.log")
    assert res_json["valid"] is True
    assert len(res_json["issues"]) == 1
    assert res_json["issues"][0]["count"] == 3
    assert len(res_json["repeated_patterns"]) == 1

    # 2. Unparseable random text -> valid=False with honest limitation (no fake results)
    res_bad = log_analyzer.analyze("lorem ipsum dolor sit amet\nconsectetur adipiscing elit\n", file_name="random.txt")
    assert res_bad["valid"] is False
    assert res_bad["limitation"] is not None
    assert res_bad["issues"] == []


# ==============================================================================
# GROUP H & ACCEPTANCE SCENARIO 4: MULTI-FILE ZIP + CROSS-FILE ASYNC + ZIP SLIP REJECTION
# ==============================================================================
def test_acceptance_scenario_4_multifile_zip_and_unsafe_rejection(client):
    # 1. Valid multi-file ZIP with cross-file async import called without await!
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "pkg/repo.py",
            "async def fetch_account(acct_id: int):\n"
            "    return {'id': acct_id}\n",
        )
        zf.writestr(
            "pkg/handler.py",
            "from pkg.repo import fetch_account\n\n"
            "def run_sync(ids):\n"
            "    for i in ids:\n"
            "        fetch_account(i)\n",
        )
        zf.writestr("__pycache__/ignored.pyc", b"\x00\x01\x02")
    buf.seek(0)

    resp = client.post(
        "/api/v1/analyses",
        data={"title": "Multi-File Cross-Module ZIP", "mode": "code"},
        files=[("files", ("project.zip", buf, "application/zip"))],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_count"] == 2
    assert any(
        f["file_path"] == "pkg/handler.py" and f["rule_id"] == "PY_UNAWAITED_COROUTINE" and f["line_number"] == 5
        for f in data["findings"]
    )
    assert len(data["relationships"]) >= 1

    # Report check
    rep = client.get(f"/api/v1/analyses/{data['id']}/report")
    assert rep.status_code == 200
    assert "pkg/handler.py" in rep.json()["markdown_report"]

    # 2. Unsafe Zip Slip archive MUST be rejected with HTTP 400
    bad_zip = io.BytesIO()
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../../etc/evil.py", "print('escape')\n")
    bad_zip.seek(0)
    resp_slip = client.post(
        "/api/v1/analyses",
        data={"title": "Zip Slip Test", "mode": "code"},
        files=[("files", ("evil.zip", bad_zip, "application/zip"))],
    )
    assert resp_slip.status_code == 400
    assert "path traversal" in resp_slip.json()["detail"].lower()


# ==============================================================================
# ACCEPTANCE SCENARIO 5 & 6: METRICS-ONLY & COMBINED CODE + LOGS + METRICS
# ==============================================================================
def test_acceptance_scenarios_5_and_6_metrics_and_combined(client):
    # Scenario 5: Timestamped metrics with known anomalous interval
    rows = ["timestamp,cpu_utilization,p95_latency_ms"]
    for i in range(20):
        t = f"2026-11-18T11:{i:02d}:00Z"
        if 10 <= i <= 13:
            rows.append(f"{t},96.5,3800.0")
        else:
            rows.append(f"{t},{24.0 + (i % 3)},{40.0 + (i % 4)}")
    csv_bytes = "\n".join(rows).encode("utf-8")

    r_metrics = client.post(
        "/api/v1/analyses",
        data={"title": "Metrics Anomaly Scenario", "mode": "metrics_logs"},
        files=[("metrics_file", ("telemetry.csv", io.BytesIO(csv_bytes), "text/csv"))],
    )
    assert r_metrics.status_code == 200
    mdata = r_metrics.json()
    assert len(mdata["metric_anomalies"]) >= 4
    assert len(mdata["meta_info"]["metrics_series"]) == 20
    assert len(mdata["meta_info"]["metrics_intervals"]) >= 1
    assert len(mdata["root_causes"]) >= 1
    assert mdata["root_causes"][0]["evidence_category"] == EvidenceCategory.METRICS

    # Scenario 6: Combined Code + Logs + Metrics
    code_bytes = (
        b"import time\n\n"
        b"async def settle_invoice(inv_id):\n"
        b"    time.sleep(3.5)\n"
        b"    return inv_id\n"
    )
    log_bytes = (
        b"2026-11-18 11:10:05 [billing-api] ERROR 504 Gateway Timeout waiting for settle_invoice\n"
        b"2026-11-18 11:10:12 [billing-api] CRITICAL Traceback (most recent call last):\n"
        b'  File "billing.py", line 4, in settle_invoice\n'
        b"    time.sleep(3.5)\n"
        b"TimeoutError: Exceeded 3.0s request budget\n"
    )
    r_comb = client.post(
        "/api/v1/analyses",
        data={"title": "Combined Multimodal Scenario", "mode": "combined"},
        files=[
            ("files", ("billing.py", io.BytesIO(code_bytes), "text/x-python")),
            ("logs_file", ("billing.log", io.BytesIO(log_bytes), "text/plain")),
            ("metrics_file", ("telemetry.csv", io.BytesIO(csv_bytes), "text/csv")),
        ],
    )
    assert r_comb.status_code == 200
    cdata = r_comb.json()
    assert cdata["findings"][0]["evidence_category"] == EvidenceCategory.CORRELATED
    assert cdata["findings"][0]["severity"] == "Critical"  # Elevated by confirmed runtime traceback
    assert cdata["root_causes"][0]["evidence_category"] == EvidenceCategory.CORRELATED
    assert cdata["root_causes"][0]["cause_type"] == "Confirmed Runtime Incident"
    assert len(cdata["recommendations"]) == 1


# ==============================================================================
# ACCEPTANCE SCENARIO 7: SEQUENTIAL SESSION ISOLATION (FAULTY -> CLEAN -> FAULTY -> CLEAN)
# ==============================================================================
def test_acceptance_scenario_7_sequential_session_isolation(client):
    seq = [
        ("Faulty 1", "import time\nasync def f1():\n    time.sleep(2)\n", "f1.py", 1, 1),
        ("Clean 1", "def ok1(x: int) -> int:\n    return x + 1\n", "c1.py", 0, 0),
        (
            "Faulty 2",
            "def f2(op):\n    while True:\n        try:\n            return op()\n        except Exception:\n            pass\n",
            "f2.py",
            2,  # PY_UNBOUNDED_RETRY + PY_SILENT_EXCEPT
            2,
        ),
        ("Clean 2", "async def ok2():\n    return 42\n", "c2.py", 0, 0),
    ]
    seen_ids = []
    for title, code, fname, exp_findings, exp_causes in seq:
        resp = client.post(
            "/api/v1/analyses/paste",
            json={"title": title, "code": code, "language": "python", "file_name": fname},
        )
        assert resp.status_code == 200
        d = resp.json()
        seen_ids.append((d["id"], fname, exp_findings, exp_causes))
        assert len(d["findings"]) == exp_findings
        assert len(d["root_causes"]) == exp_causes
        if exp_findings == 0:
            assert d["recommendations"] == []
            assert d["overall_score"] == 100.0
        else:
            assert all(f["file_path"] == fname for f in d["findings"])
            assert all(rc["analysis_id"] == d["id"] for rc in d["root_causes"])

    # Re-read every stored analysis & report to confirm zero cross-contamination
    for aid, fname, exp_findings, exp_causes in seen_ids:
        detail = client.get(f"/api/v1/analyses/{aid}").json()
        assert len(detail["findings"]) == exp_findings
        assert len(detail["root_causes"]) == exp_causes
        rep = client.get(f"/api/v1/analyses/{aid}/report").json()
        assert rep["analysis_id"] == aid
        assert len(rep["json_data"]["findings"]) == exp_findings


# ==============================================================================
# ACCEPTANCE SCENARIO 8: ERROR HANDLING & UNSUPPORTED INPUT REJECTION
# ==============================================================================
def test_acceptance_scenario_8_error_handling(client):
    # 1. Unsupported code extension (.exe)
    r1 = client.post(
        "/api/v1/analyses",
        data={"title": "Bad Ext", "mode": "code"},
        files=[("files", ("binary.exe", io.BytesIO(b"MZ\x00\x01"), "application/octet-stream"))],
    )
    assert r1.status_code == 400

    # 2. Unsupported language in paste endpoint
    r2 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Rust Test", "code": "fn main() {}", "language": "rust", "file_name": "main.rs"},
    )
    assert r2.status_code == 400
    assert "Unsupported language" in r2.json()["detail"]

    # 3. Malformed metrics-only upload
    r3 = client.post(
        "/api/v1/analyses",
        data={"title": "Bad Metrics", "mode": "metrics_logs"},
        files=[("metrics_file", ("broken.csv", io.BytesIO(b"a,b\nx,y\np,q\nr,s\n"), "text/csv"))],
    )
    assert r3.status_code == 400

    # 4. Syntax error in Python file -> NEVER gets 100/100 and marks incomplete_parse
    r4 = client.post(
        "/api/v1/analyses/paste",
        json={"title": "Syntax Error Test", "code": "def broken(:\n    pass\n", "language": "python", "file_name": "bad.py"},
    )
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["overall_score"] < 100.0
    assert d4["meta_info"]["score_breakdown"]["analysis_complete"] is False
    assert "bad.py" in d4["meta_info"]["incomplete_files"]


# ==============================================================================
# ADVERSARIAL RANDOMIZED IDENTIFIER GENERALIZATION (ZERO OVERFITTING CHECK)
# ==============================================================================
@pytest.mark.parametrize(
    "fn_a,fn_b,var_x,var_y",
    [
        ("alpha_sync", "beta_async", "records_pool", "item_key"),
        ("k9_runner", "q7_loader", "cache_bucket", "row_ref"),
        ("dispatch_orders", "hydrate_invoice", "global_ledger", "inv_num"),
    ],
)
def test_adversarial_identifier_generalization(fn_a, fn_b, var_x, var_y):
    analyzer = PythonCodeAnalyzer()
    code = (
        "import time\n"
        "import requests\n\n"
        f"{var_x} = []\n\n"
        f"async def {fn_b}({var_y}):\n"
        "    time.sleep(1.5)\n"
        f"    r = requests.get(f'https://example.internal/{{{var_y}}}')\n"
        f"    {var_x}.append(r.text)\n"
        "    while True:\n"
        "        try:\n"
        "            return r.status_code\n"
        "        except Exception:\n"
        "            pass\n\n"
        f"def {fn_a}(items):\n"
        "    for z in items:\n"
        f"        {fn_b}(z)\n"
    )
    res = analyzer.analyze(code, file_path=f"{fn_a}.py")
    rules = {f["rule_id"] for f in res["findings"]}
    assert {
        "PY_ASYNC_BLOCKING_SLEEP",
        "PY_ASYNC_BLOCKING_HTTP",
        "PY_MISSING_TIMEOUT",
        "PY_UNBOUNDED_COLLECTION",
        "PY_UNBOUNDED_RETRY",
        "PY_SILENT_EXCEPT",
        "PY_UNAWAITED_COROUTINE",
    }.issubset(rules)
