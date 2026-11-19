from typing import List, Dict, Any, Tuple
from backend.app.analyzers.logical.ast_semantic import ASTSemanticAnalyzer
from backend.app.analyzers.logical.llm_semantic import LLMSemanticAnalyzer
from backend.app.analyzers.logical.verifier import LogicalVerifier
from backend.app.services.scoring import EvidenceCategory


class LogicalErrorDetector:
    """
    Main orchestrator for detecting, verifying, and explaining logical errors in Python code.
    Executes AST semantic evaluation and automated test-case verification in an isolated sandbox.
    """

    @classmethod
    def detect(cls, code: str, file_path: str = "service.py") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        findings: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        # 1. Semantic AST Analysis
        ast_candidates = ASTSemanticAnalyzer.analyze(code, file_path=file_path)

        # 2. Optional LLM Semantic Analysis (only runs when API keys are configured)
        llm_candidates = LLMSemanticAnalyzer.analyze(code, file_path=file_path)
        combined_candidates = ast_candidates + [
            c for c in llm_candidates
            if not any(a.get("line_number") == c.get("line_number") for a in ast_candidates)
        ]

        if not combined_candidates:
            return [], []

        # 3. Automated Test Case Verification in Isolated Sandbox
        test_verification = LogicalVerifier.verify_code(code)
        fn_results = test_verification.get("functions", {})

        for cand in combined_candidates:
            fn_name = cand.get("function_name")
            fn_eval = fn_results.get(fn_name) if fn_name else None

            # Determine whether this error is confirmed by real test execution
            if fn_eval and not fn_eval.get("passed", True):
                cand["is_confirmed"] = True
                cand["evidence_category"] = EvidenceCategory.RUNTIME
                exp = fn_eval.get("expected")
                act = fn_eval.get("actual")
                t_name = fn_eval.get("test_name", "Automated Test Case")
                cand["evidence"] = (
                    f"[Test Verification] Confirmed Logical Error on '{t_name}':\n"
                    f"• Expected Output: {exp}\n"
                    f"• Actual Output: {act}\n"
                    f"• Verification: Failed expected reference behavior in isolated sandbox."
                )
            else:
                # Suspected error reported separately when no reliable test oracle confirms it
                cand["is_confirmed"] = False
                cand["evidence_category"] = EvidenceCategory.STATIC_CODE
                cand["evidence"] = (
                    f"[Semantic Pattern Analysis] Suspected Logical Error in '{fn_name or 'module'}':\n"
                    f"• Detected AST semantic anomaly at line {cand.get('line_number')}.\n"
                    f"• Verification: Suspected pattern detected; manual confirmation or specification required."
                )

            cand["detection_method"] = "Semantic AST Analysis & Isolated Test Verification"
            cand["severity_rationale"] = (
                "Logical errors execute cleanly with exit code 0 but produce incorrect outputs, "
                "silently corrupting application logic, reporting metrics, or decision intelligence."
            )
            cand["potential_consequences"] = (
                "Causes incorrect calculation results, wrong filtering or selection, and silent data corruption."
            )
            cand["language"] = "python"
            findings.append(cand)

        return findings, relationships
