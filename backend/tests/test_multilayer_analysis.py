import pytest
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.analyzers.code.python_analyzer import PythonCodeAnalyzer
from backend.app.analyzers.code.js_analyzer import JavaScriptCodeAnalyzer
from backend.app.analyzers.code.c_analyzer import CCodeAnalyzer
from backend.app.autofix.patch_generator import PatchGenerator


@pytest.fixture
def client():
    return TestClient(app)


def test_python_test_a_undefined_printf():
    analyzer = PythonCodeAnalyzer()
    res = analyzer.analyze('printf("Hello")\n', file_path="main.py")
    assert any(f["rule_id"] == "PY_UNDEFINED_NAME" and "printf" in f["title"] for f in res["findings"])


def test_python_test_b_valid_print_clean():
    analyzer = PythonCodeAnalyzer()
    res = analyzer.analyze('print("Hello")\n', file_path="main.py")
    assert len(res["findings"]) == 0


def test_python_test_c_scoped_defined_printf():
    analyzer = PythonCodeAnalyzer()
    code = (
        "def printf(message):\n"
        "    print(message)\n\n"
        "printf('Hello')\n"
    )
    res = analyzer.analyze(code, file_path="main.py")
    assert len(res["findings"]) == 0


def test_python_test_d_undefined_variable():
    analyzer = PythonCodeAnalyzer()
    code = "x = 10\nprint(y)\n"
    res = analyzer.analyze(code, file_path="main.py")
    assert any(f["rule_id"] == "PY_UNDEFINED_NAME" and "y" in f["title"] for f in res["findings"])


def test_python_test_e_missing_function_argument():
    analyzer = PythonCodeAnalyzer()
    code = (
        "def add(a, b):\n"
        "    return a + b\n\n"
        "print(add(5))\n"
    )
    res = analyzer.analyze(code, file_path="main.py")
    assert any(f["rule_id"] == "PY_MISSING_ARGUMENT" and "b" in f["title"] for f in res["findings"])


def test_python_test_f_syntax_error():
    analyzer = PythonCodeAnalyzer()
    code = "def hello()\n    print('Hello')\n"
    res = analyzer.analyze(code, file_path="main.py")
    assert any(f["rule_id"] == "PY_SYNTAX_ERROR" for f in res["findings"])


def test_python_test_g_async_blocking_sleep():
    analyzer = PythonCodeAnalyzer()
    code = (
        "import time\n"
        "async def task():\n"
        "    time.sleep(2)\n"
    )
    res = analyzer.analyze(code, file_path="main.py")
    assert any(f["rule_id"] == "PY_ASYNC_BLOCKING_SLEEP" for f in res["findings"])


def test_python_test_h_constant_division_by_zero():
    analyzer = PythonCodeAnalyzer()
    code = "result = 10 / 0\n"
    res = analyzer.analyze(code, file_path="main.py")
    assert any(f["rule_id"] == "PY_CONST_ZERO_DIV" for f in res["findings"])


def test_javascript_test_undefined_identifier():
    analyzer = JavaScriptCodeAnalyzer()
    code = "function main() { console.log(unknownVariable); } main();"
    res = analyzer.analyze(code, file_path="app.js")
    assert any(f["rule_id"] == "JS_UNDEFINED_NAME" for f in res["findings"])


def test_typescript_test_type_mismatch():
    analyzer = JavaScriptCodeAnalyzer()
    code = 'let age: number = "twenty";'
    res = analyzer.analyze(code, file_path="app.ts")
    assert any(f["rule_id"] == "TS_TYPE_MISMATCH" for f in res["findings"])


def test_c_test_valid_printf():
    analyzer = CCodeAnalyzer()
    if not analyzer.is_operational():
        pytest.skip("Clang not available")
    code = (
        "#include <stdio.h>\n"
        "int main(void) {\n"
        '    printf("Hello\\n");\n'
        "    return 0;\n"
        "}\n"
    )
    res = analyzer.analyze(code, file_path="main.c")
    assert len(res["findings"]) == 0


def test_c_test_undeclared_identifier():
    analyzer = CCodeAnalyzer()
    if not analyzer.is_operational():
        pytest.skip("Clang not available")
    code = (
        "int main(void) {\n"
        "    int x = unknown_identifier;\n"
        "    return 0;\n"
        "}\n"
    )
    res = analyzer.analyze(code, file_path="main.c")
    assert any(f["rule_id"] == "C_UNDECLARED_IDENTIFIER" for f in res["findings"])


def test_e2e_printf_autofix_and_execution_output(client):
    res = client.post(
        "/api/v1/analyses/paste",
        json={
            "title": "Printf Auto Fix Test",
            "code": 'printf("Hello World")\n',
            "file_name": "service.py",
            "language": "python",
        },
    )
    assert res.status_code == 200
    data = res.json()
    orig_id = data["id"]
    assert any(f["rule_id"] == "PY_UNDEFINED_NAME" for f in data["findings"])

    rec = next(r for r in data["recommendations"] if r["rule_id"] == "PY_UNDEFINED_NAME")
    assert rec["auto_fixable"] is True
    assert "print" in rec["diff"]

    apply_res = client.post(
        f"/api/v1/analyses/{orig_id}/fixes/apply",
        json={"recommendation_id": rec["id"]},
    )
    assert apply_res.status_code == 200
    applied_data = apply_res.json()
    assert applied_data["applied_file_path"] == "service.py"
    assert 'print("Hello World")' in applied_data["fixed_code"]
    assert applied_data["analysis"]["overall_score"] == 100.0
    assert applied_data["analysis"]["findings"] == []
    assert "Hello World" in (applied_data.get("execution_output") or "")
