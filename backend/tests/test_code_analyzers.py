import pytest
from backend.app.analyzers.code.python_analyzer import PythonCodeAnalyzer
from backend.app.analyzers.code.js_analyzer import JavaScriptCodeAnalyzer

def test_python_syntax_error():
    analyzer = PythonCodeAnalyzer()
    bad_code = "def broken_fn(\n    print('missing paren'"
    res = analyzer.analyze(bad_code, file_path="broken.py")
    assert res["ast_parsed"] is False
    assert len(res["findings"]) == 1
    assert res["findings"][0]["severity"] == "Critical"
    assert "Syntax Error" in res["findings"][0]["title"]

def test_python_async_blocking_sleep():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import asyncio\n"
        "import time\n\n"
        "async def handle():\n"
        "    time.sleep(2.0)\n"
    )
    res = analyzer.analyze(code, file_path="app.py")
    titles = [f["title"] for f in res["findings"]]
    assert any("Blocking Synchronous Call" in t for t in titles)
    finding = next(f for f in res["findings"] if "Blocking" in f["title"])
    assert finding["severity"] == "High"
    assert finding["evidence_category"] == "Static Code Evidence"
    assert finding["is_confirmed"] is False
    assert finding["line_number"] == 5

def test_python_mutable_defaults():
    analyzer = PythonCodeAnalyzer()
    code = (
        "def append_item(x, target=[]):\n"
        "    target.append(x)\n"
        "    return target\n"
    )
    res = analyzer.analyze(code, file_path="app.py")
    titles = [f["title"] for f in res["findings"]]
    assert any("Mutable Default" in t for t in titles)
    f = next(f for f in res["findings"] if "Mutable Default" in f["title"])
    assert f["line_number"] == 1
    assert f["severity"] == "High"

def test_python_resource_leak_and_deadlock():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import threading\n"
        "import sqlite3\n\n"
        "lock = threading.Lock()\n\n"
        "def process():\n"
        "    lock.acquire()\n"
        "    conn = sqlite3.connect('test.db')\n"
        "    return conn\n"
    )
    res = analyzer.analyze(code, file_path="srv.py")
    titles = [f["title"] for f in res["findings"]]
    assert any("Deadlock" in t for t in titles)
    assert any("Resource" in t for t in titles)

def test_python_sql_injection_and_secret_masking():
    analyzer = PythonCodeAnalyzer()
    code = (
        "API_KEY = 'sk_live_99881237612345678'\n\n"
        "def search_user(cursor, user_input):\n"
        "    cursor.execute(f'SELECT * FROM users WHERE name = {user_input}')\n"
    )
    res = analyzer.analyze(code, file_path="db.py")
    titles = [f["title"] for f in res["findings"]]
    assert any("SQL Injection" in t for t in titles)
    assert any("Credential" in t or "Secret" in t for t in titles)
    secret_f = next(f for f in res["findings"] if "Secret" in f["title"] or "Credential" in f["title"])
    # Verify masked secret
    assert "sk****78" in secret_f["code_snippet"] or "****" in secret_f["code_snippet"]
    assert "sk_live_99881237612345678" not in secret_f["code_snippet"]

def test_js_blocking_sync_and_eval():
    analyzer = JavaScriptCodeAnalyzer()
    code = (
        "const fs = require('fs');\n"
        "async function readFileData() {\n"
        "    const data = fs.readFileSync('/tmp/data.txt');\n"
        "    eval(data);\n"
        "    return data;\n"
        "}\n"
    )
    res = analyzer.analyze(code, file_path="index.js")
    titles = [f["title"] for f in res["findings"]]
    assert any("Blocking Synchronous I/O" in t for t in titles)
    assert any("Dynamic Code Injection" in t for t in titles)
    assert len(res["relationships"]) >= 1
