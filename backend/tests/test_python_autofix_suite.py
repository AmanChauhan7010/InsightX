import pytest
from starlette.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_autofix_all_python_rules(client):
    """
    Comprehensive test ensuring that every single Python error detected by InsightX
    provides a valid, working, runnable code solution (auto_fixable=True),
    applies the patch cleanly, updates score and findings, and captures execution output.
    """
    rules_and_snippets = [
        (
            "PY_SYNTAX_ERROR",
            'printf("hello world"):',
            "service.py",
        ),
        (
            "PY_UNDEFINED_NAME",
            'printf("hello world")',
            "service.py",
        ),
        (
            "PY_UNDEFINED_NAME",
            "x = 10\nprint(y)\n",
            "service.py",
        ),
        (
            "PY_UNDEFINED_NAME",
            "print(math.sqrt(16))\n",
            "service.py",
        ),
        (
            "PY_CONST_ZERO_DIV",
            "x = 10 / 0\nprint(x)\n",
            "service.py",
        ),
        (
            "PY_UNGUARDED_DIV",
            "def div(a, b):\n    return a / b\nprint(div(10, 2))\n",
            "service.py",
        ),
        (
            "PY_MISSING_ARGUMENT",
            "def add(a, b):\n    return a + b\nadd(5)\n",
            "service.py",
        ),
        (
            "PY_ASYNC_BLOCKING_HTTP",
            "import requests\nasync def fetch():\n    return requests.get('https://example.com')\n",
            "service.py",
        ),
        (
            "PY_DANGEROUS_EVAL",
            "x = eval('\"hello\"')\nprint(x)\n",
            "service.py",
        ),
        (
            "PY_SQL_INJECTION",
            "def get_user(cursor, user_id):\n    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n",
            "service.py",
        ),
        (
            "PY_UNSAFE_LOCK",
            "import threading\nlock = threading.Lock()\ndef work():\n    lock.acquire()\n    print('safe')\n    lock.release()\n",
            "service.py",
        ),
        (
            "PY_SUBPROCESS_SHELL",
            "import subprocess\nsubprocess.run('ls -l', shell=True)\n",
            "service.py",
        ),
        (
            "PY_UNAWAITED_COROUTINE_RETURN",
            "import asyncio\nasync def g():\n    return 1\ndef f(flag):\n    if flag:\n        return 10\n    return g()\n",
            "service.py",
        ),
        (
            "PY_UNCONTROLLED_LOOP",
            "while True:\n    print('hi')\n",
            "service.py",
        ),
        (
            "PY_ASYNC_BLOCKING_SLEEP",
            "import time\nasync def worker():\n    time.sleep(1)\n",
            "service.py",
        ),
        (
            "PY_UNCLOSED_RESOURCE",
            "def read_file():\n    f = open('data.txt')\n    content = f.read()\n    return content\n",
            "service.py",
        ),
        (
            "PY_MISSING_TIMEOUT",
            "import requests\ndef fetch():\n    return requests.get('https://example.com')\n",
            "service.py",
        ),
        (
            "PY_SILENT_EXCEPT",
            "try:\n    int('abc')\nexcept Exception:\n    pass\n",
            "service.py",
        ),
        (
            "PY_BARE_EXCEPT",
            "try:\n    int('abc')\nexcept:\n    print('error')\n",
            "service.py",
        ),
        (
            "PY_MUTABLE_DEFAULT",
            "def append_item(val, items=[]):\n    items.append(val)\n    return items\n",
            "service.py",
        ),
        (
            "PY_HARDCODED_SECRET",
            'API_KEY = "sk-live-1234567890abcdef"\n',
            "service.py",
        ),
        (
            "PY_UNSAFE_DESERIALIZATION",
            "import yaml\ndef load_data(text):\n    return yaml.load(text)\n",
            "service.py",
        ),
    ]

    for expected_rule, code_snippet, filename in rules_and_snippets:
        # Step 1: Upload / paste code
        post_res = client.post(
            "/api/v1/analyses/paste",
            json={
                "title": f"Test {expected_rule}",
                "code": code_snippet,
                "file_name": filename,
                "language": "python",
            },
        )
        assert post_res.status_code == 200, f"Paste failed for {expected_rule}: {post_res.text}"
        data = post_res.json()
        analysis_id = data["id"]

        # Confirm the expected rule was detected
        finding_rule_ids = [f.get("rule_id") for f in data.get("findings", [])]
        assert expected_rule in finding_rule_ids, f"Expected {expected_rule} was not detected. Found: {finding_rule_ids}"

        # Step 2: Fetch recommendation for this rule
        recs = data.get("recommendations", [])
        rec = next((r for r in recs if r.get("rule_id") == expected_rule), None)
        assert rec is not None, f"No recommendation found for {expected_rule}"

        # MUST be marked auto-fixable!
        assert rec.get("auto_fixable") is True, f"{expected_rule} was marked auto_fixable=False! Reason: {rec.get('manual_fix_reason')}"
        assert rec.get("diff") is not None, f"{expected_rule} has no diff in recommendation"

        # Step 3: Preview fix endpoint
        preview_res = client.post(
            f"/api/v1/analyses/{analysis_id}/fixes/preview",
            json={"recommendation_id": rec["id"]},
        )
        assert preview_res.status_code == 200, f"Preview failed for {expected_rule}: {preview_res.text}"
        preview_data = preview_res.json()
        assert preview_data["auto_fixable"] is True
        assert preview_data["patched_code"] is not None
        assert preview_data["diff"] is not None

        # Step 4: Apply fix & re-analyze
        apply_res = client.post(
            f"/api/v1/analyses/{analysis_id}/fixes/apply",
            json={"recommendation_id": rec["id"]},
        )
        assert apply_res.status_code == 200, f"Apply failed for {expected_rule}: {apply_res.text}"
        apply_data = apply_res.json()

        # Step 5: Verify factual before/after comparison
        assert apply_data["applied_file_path"] == filename
        assert apply_data["fixed_code"] is not None
        assert apply_data["source_hash"] is not None

        new_analysis = apply_data["analysis"]
        remaining_rules = [f.get("rule_id") for f in new_analysis.get("findings", [])]
        assert expected_rule not in remaining_rules, f"Rule {expected_rule} still present after fix! Remaining: {remaining_rules}"

        comparison = apply_data["comparison"]
        assert len(comparison["resolved_findings"]) >= 1, f"No findings resolved for {expected_rule}"
        assert comparison["score_delta"] >= 0, f"Score regressed for {expected_rule}"
