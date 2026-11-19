import json
import re
from typing import Dict, Any, Optional
from backend.app.analyzers.logical.runner import IsolatedCodeRunner
from backend.app.analyzers.logical.test_synthesizer import TestSynthesizer


class LogicalVerifier:
    """
    Executes code against synthesized test cases in an isolated subprocess,
    evaluating actual output against expected output to confirm logical errors
    and verify that candidate patches resolve them without regression.
    """

    @classmethod
    def verify_code(cls, source_code: str) -> Dict[str, Any]:
        harness = TestSynthesizer.generate_harness(source_code)
        run_res = IsolatedCodeRunner.run_code(harness, timeout=3.0)

        if not run_res["success"] and not run_res.get("stdout"):
            return {
                "verified": False,
                "error": run_res.get("stderr") or "Subprocess execution failed during test verification.",
                "module_output": "",
                "functions": {},
            }

        stdout = run_res.get("stdout", "")
        m = re.search(r"__INSIGHTX_JSON_START__\s*(.*?)\s*__INSIGHTX_JSON_END__", stdout, re.DOTALL)
        if not m:
            return {
                "verified": False,
                "error": "Failed to extract test verification payload.",
                "module_output": stdout.strip(),
                "functions": {},
            }

        try:
            payload = json.loads(m.group(1))
            return {
                "verified": True,
                "error": None,
                "module_output": payload.get("module_output", "").strip(),
                "functions": payload.get("functions", {}),
            }
        except Exception as ex:
            return {
                "verified": False,
                "error": f"JSON parse error in test verification: {ex}",
                "module_output": stdout.strip(),
                "functions": {},
            }

    @classmethod
    def verify_patch(
        cls,
        original_code: str,
        patched_code: str,
        target_function: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs automated test verification against the patched code and confirms
        that the target logical error was resolved and no regressions occurred.
        """
        patch_eval = cls.verify_code(patched_code)
        if not patch_eval["verified"]:
            return {
                "passed": False,
                "error": patch_eval.get("error") or "Patched code failed execution.",
                "module_output": patch_eval.get("module_output", ""),
            }

        fn_res = patch_eval.get("functions", {})
        if target_function and target_function in fn_res:
            target_passed = fn_res[target_function].get("passed", False)
            return {
                "passed": target_passed,
                "target_function": target_function,
                "function_result": fn_res[target_function],
                "all_functions": fn_res,
                "module_output": patch_eval.get("module_output", ""),
            }

        # If no specific function target, check overall test pass status
        all_passed = all(f.get("passed", False) for f in fn_res.values()) if fn_res else True
        return {
            "passed": all_passed,
            "all_functions": fn_res,
            "module_output": patch_eval.get("module_output", ""),
        }
