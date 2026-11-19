import ast
import json
from typing import Dict, Any, List, Optional


class TestSynthesizer:
    """
    Synthesizes automated test cases (normal, boundary, and edge) and executes
    them through an isolated test harness to independently evaluate actual output
    against expected algorithmic output.
    """

    @classmethod
    def generate_harness(cls, source_code: str) -> str:
        """
        Creates a self-contained Python script that imports/executes the source code
        in an isolated scope, runs synthesized test cases, and outputs structured
        JSON comparison results to stdout.
        """
        harness = f'''
import sys
import json
import io

# Capture original top-level module output
stdout_capture = io.StringIO()
original_stdout = sys.stdout
sys.stdout = stdout_capture

module_env = {{}}
raw_code = {repr(source_code)}

try:
    exec(raw_code, module_env)
finally:
    sys.stdout = original_stdout

module_output = stdout_capture.getvalue()

results = {{
    "module_output": module_output,
    "functions": {{}},
    "errors": []
}}

# Inspect synthesized test cases for functions present in module_env
students_data = module_env.get("students")

# 1. Test calculate_average
if "calculate_average" in module_env and callable(module_env["calculate_average"]):
    fn = module_env["calculate_average"]
    test_cases = []
    if students_data and isinstance(students_data, dict) and "Aman" in students_data:
        test_cases.append(("Aman marks", students_data["Aman"], round(sum(students_data["Aman"]) / len(students_data["Aman"]), 2)))
    test_cases.append(("normal marks", [80, 90, 70], 80.0))
    test_cases.append(("boundary single", [100], 100.0))

    passed_all = True
    actual_val = None
    expected_val = None
    first_failure_test = None

    for t_name, inp, exp in test_cases:
        try:
            act = fn(inp)
            act_num = round(float(act), 2)
            if abs(act_num - exp) > 0.05:
                passed_all = False
                actual_val = act_num
                expected_val = exp
                first_failure_test = t_name
                break
        except Exception as e:
            passed_all = False
            actual_val = f"Exception: {{e}}"
            expected_val = exp
            first_failure_test = t_name
            break

    results["functions"]["calculate_average"] = {{
        "passed": passed_all,
        "actual": actual_val,
        "expected": expected_val,
        "test_name": first_failure_test,
    }}

# 2. Test find_topper
if "find_topper" in module_env and callable(module_env["find_topper"]):
    fn = module_env["find_topper"]
    test_cases = []
    if students_data and isinstance(students_data, dict):
        # Determine actual topper from data independently
        try:
            exp_topper = max(students_data.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))[0]
            test_cases.append(("students dataset", students_data, exp_topper))
        except Exception:
            pass
    test_cases.append(("two students", {{"Low": [40, 50], "High": [90, 95]}}, "High"))

    passed_all = True
    actual_val = None
    expected_val = None
    first_failure_test = None

    for t_name, inp, exp in test_cases:
        try:
            act = str(fn(inp)).strip()
            if act != exp:
                passed_all = False
                actual_val = act if act else '"" (empty string)'
                expected_val = exp
                first_failure_test = t_name
                break
        except Exception as e:
            passed_all = False
            actual_val = f"Exception: {{e}}"
            expected_val = exp
            first_failure_test = t_name
            break

    results["functions"]["find_topper"] = {{
        "passed": passed_all,
        "actual": actual_val,
        "expected": expected_val,
        "test_name": first_failure_test,
    }}

# 3. Test count_passed
if "count_passed" in module_env and callable(module_env["count_passed"]):
    fn = module_env["count_passed"]
    test_cases = []
    if students_data and isinstance(students_data, dict):
        try:
            # All 3 students have true average >= 40 (Aman ~84.33, Rahul 53.33, Priya 95)
            exp_count = sum(1 for m in students_data.values() if (sum(m)/len(m)) >= 40)
            test_cases.append(("students dataset (threshold 40)", students_data, exp_count))
        except Exception:
            pass
    test_cases.append(("split students", {{"Fail": [20, 30], "Pass": [50, 60]}}, 1))

    passed_all = True
    actual_val = None
    expected_val = None
    first_failure_test = None

    for t_name, inp, exp in test_cases:
        try:
            act = int(fn(inp))
            if act != exp:
                passed_all = False
                actual_val = act
                expected_val = exp
                first_failure_test = t_name
                break
        except Exception as e:
            passed_all = False
            actual_val = f"Exception: {{e}}"
            expected_val = exp
            first_failure_test = t_name
            break

    results["functions"]["count_passed"] = {{
        "passed": passed_all,
        "actual": actual_val,
        "expected": expected_val,
        "test_name": first_failure_test,
    }}

print("__INSIGHTX_JSON_START__")
print(json.dumps(results))
print("__INSIGHTX_JSON_END__")
'''
        return harness
