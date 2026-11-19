import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.analyzers.logical.ast_semantic import ASTSemanticAnalyzer
from backend.app.analyzers.logical.runner import IsolatedCodeRunner
from backend.app.analyzers.logical.test_synthesizer import TestSynthesizer
from backend.app.analyzers.logical.verifier import LogicalVerifier
from backend.app.analyzers.logical.detector import LogicalErrorDetector

client = TestClient(app)

STUDENT_EXAMPLE_CODE = """
students = {
    "Aman": [85, 90, 78],
    "Rahul": [45, 55, 60],
    "Priya": [95, 98, 92]
}

def calculate_average(marks):
    total = 0
    for mark in marks:
        total += mark
    return total / (len(marks) + 1)

def find_topper(students):
    topper = ""
    highest = 0

    for name, marks in students.items():
        average = calculate_average(marks)

        if average < highest:
            highest = average
            topper = name

    return topper

def count_passed(students):
    passed = 0

    for name, marks in students.items():
        average = calculate_average(marks)

        if average < 40:
            passed += 1

    return passed

print("Topper:", find_topper(students))
print("Passed:", count_passed(students))
"""


def test_student_example_logical_error_detection():
    findings, _ = LogicalErrorDetector.detect(STUDENT_EXAMPLE_CODE, "service.py")
    assert len(findings) == 3

    rule_ids = {f["rule_id"] for f in findings}
    assert "PY_LOGICAL_CALCULATION" in rule_ids
    assert "PY_LOGICAL_COMPARISON" in rule_ids
    assert "PY_LOGICAL_CONDITION" in rule_ids

    # All three should be confirmed by automated test case execution
    assert all(f["is_confirmed"] is True for f in findings)
    assert all(f["category"] == "Logical Error" for f in findings)

    # Check that evidence includes actual vs expected output
    calc_finding = next(f for f in findings if f["rule_id"] == "PY_LOGICAL_CALCULATION")
    assert "84.33" in calc_finding["evidence"]
    assert "63.25" in calc_finding["evidence"]

    topper_finding = next(f for f in findings if f["rule_id"] == "PY_LOGICAL_COMPARISON")
    assert "Priya" in topper_finding["evidence"]

    passed_finding = next(f for f in findings if f["rule_id"] == "PY_LOGICAL_CONDITION")
    assert "3" in passed_finding["evidence"]
    assert "0" in passed_finding["evidence"]


def test_student_example_end_to_end_api_and_autofix_cycle():
    # 1. Initial Analysis
    res = client.post(
        "/api/v1/analyses/paste",
        json={
            "title": "Student Example Test",
            "code": STUDENT_EXAMPLE_CODE,
            "language": "python",
            "file_name": "service.py",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["findings"]) == 3
    assert len(data["recommendations"]) == 3
    assert data["overall_score"] < 100.0

    curr_id = data["id"]

    # 2. Successively apply all 3 recommendations
    for _ in range(3):
        rec_res = client.get(f"/api/v1/analyses/{curr_id}")
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        if not rec_data["recommendations"]:
            break
        target_rec = rec_data["recommendations"][0]

        apply_res = client.post(
            f"/api/v1/analyses/{curr_id}/fixes/apply",
            json={"recommendation_id": target_rec["id"]},
        )
        assert apply_res.status_code == 200
        apply_data = apply_res.json()
        assert "analysis" in apply_data
        curr_id = apply_data["analysis"]["id"]

    # 3. Final verification of corrected code
    final_res = client.get(f"/api/v1/analyses/{curr_id}")
    final_data = final_res.json()
    assert len(final_data["findings"]) == 0
    assert final_data["overall_score"] == 100.0

    # Execute the final source code to verify expected results
    src_res = client.get(f"/api/v1/analyses/{curr_id}/source")
    assert src_res.status_code == 200
    fixed_code = src_res.json()["files"]["service.py"]["content"]
    run_res = IsolatedCodeRunner.run_code(fixed_code)
    assert run_res["success"] is True
    out = run_res["stdout"]
    assert "Topper: Priya" in out
    assert "Passed: 3" in out


def test_correct_code_has_zero_false_positives():
    correct_code = """
def calculate_average(nums):
    if not nums:
        return 0.0
    return sum(nums) / len(nums)

def find_highest(items):
    best = None
    for x in items:
        if best is None or x > best:
            best = x
    return best

def count_passed(scores, passing_score=40):
    count = 0
    for s in scores:
        if s >= passing_score:
            count += 1
    return count
"""
    findings = ASTSemanticAnalyzer.analyze(correct_code)
    assert len(findings) == 0


def test_isolated_runner_timeout_safety():
    infinite_loop_code = "while True:\n    pass\n"
    res = IsolatedCodeRunner.run_code(infinite_loop_code, timeout=0.5)
    assert res["success"] is False
    assert res["timed_out"] is True
    assert "timed out" in res["stderr"]
