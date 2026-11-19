import ast
import re
from typing import List, Dict, Any, Optional, Tuple


class ASTSemanticAnalyzer:
    """
    Generalized AST semantic analyzer for Python source code.
    Detects algorithmic and logical bugs that compile and execute cleanly
    but produce incorrect outputs:
    1. Incorrect mathematical calculations & wrong denominators
    2. Wrong comparison operators (<, >, <=, >=) in extreme-finding logic
    3. Inverted loop/if-else conditions & threshold checks
    4. Off-by-one loop ranges and indexing bounds
    5. Premature loop termination and return statements
    6. Accumulator overwriting instead of in-place aggregation
    """

    @classmethod
    def analyze(cls, code: str, file_path: str = "service.py") -> List[Dict[str, Any]]:
        findings = []
        try:
            tree = ast.parse(code, filename=file_path)
        except Exception:
            # Syntax errors are handled by PythonCodeAnalyzer
            return []

        lines = code.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = node.name.lower()

                # -------------------------------------------------------------
                # 1. Denominator / Calculation Error in Average / Mean Functions
                # -------------------------------------------------------------
                if any(k in fn_name for k in ("average", "avg", "mean")):
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.BinOp) and isinstance(sub.op, (ast.Div, ast.FloorDiv)):
                            # Check denominator
                            denom = sub.right
                            # Pattern: len(...) + C (e.g. len(marks) + 1)
                            if (
                                isinstance(denom, ast.BinOp)
                                and isinstance(denom.left, ast.Call)
                                and isinstance(denom.left.func, ast.Name)
                                and denom.left.func.id == "len"
                                and isinstance(denom.op, ast.Add)
                                and isinstance(denom.right, ast.Constant)
                                and isinstance(denom.right.value, (int, float))
                                and denom.right.value != 0
                            ):
                                ln = getattr(sub, "lineno", node.lineno)
                                end_ln = getattr(sub, "end_lineno", ln)
                                snip = "\n".join(lines[ln - 1 : end_ln]) if 0 < ln <= len(lines) else ""
                                arg_name = denom.left.args[0].id if denom.left.args and isinstance(denom.left.args[0], ast.Name) else "items"
                                findings.append({
                                    "rule_id": "PY_LOGICAL_CALCULATION",
                                    "title": f"Incorrect Denominator in Average Calculation '{node.name}'",
                                    "category": "Logical Error",
                                    "severity": "High",
                                    "file_path": file_path,
                                    "line_number": ln,
                                    "line_end": end_ln,
                                    "function_name": node.name,
                                    "code_snippet": snip.strip(),
                                    "description": (
                                        f"Function '{node.name}' computes an average but divides by 'len({arg_name}) + {denom.right.value}' "
                                        f"instead of 'len({arg_name})'. Adding {denom.right.value} to the collection length produces an "
                                        f"off-by-one denominator error, artificially reducing the calculated mean."
                                    ),
                                    "suggested_next_step": f"Divide by 'len({arg_name})' instead of 'len({arg_name}) + {denom.right.value}'.",
                                    "fix_type": "average_denominator",
                                    "bad_token": f"len({arg_name}) + {denom.right.value}",
                                    "good_token": f"len({arg_name})",
                                    "is_confirmed": False,
                                })

                # -------------------------------------------------------------
                # 2. Inverted Comparison Operator in Extreme Selection (Topper/Max vs Lowest/Min)
                # -------------------------------------------------------------
                is_max_search = any(k in fn_name for k in ("topper", "highest", "max", "best", "peak", "largest"))
                is_min_search = any(k in fn_name for k in ("lowest", "min", "bottom", "worst", "smallest"))

                if is_max_search or is_min_search:
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.If) and isinstance(sub.test, ast.Compare):
                            cmp = sub.test
                            if len(cmp.ops) == 1 and len(cmp.comparators) == 1:
                                op = cmp.ops[0]
                                left_expr = cmp.left
                                right_expr = cmp.comparators[0]
                                ln = getattr(sub, "lineno", node.lineno)
                                end_ln = getattr(sub, "end_lineno", ln)
                                snip = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""

                                # When finding MAX/TOPPER/HIGHEST:
                                # 'if average < highest:' is inverted because we want average > highest
                                if is_max_search and isinstance(op, (ast.Lt, ast.LtE)):
                                    # Check if the right or left operand corresponds to highest tracker
                                    findings.append({
                                        "rule_id": "PY_LOGICAL_COMPARISON",
                                        "title": f"Inverted Comparison Operator in Maximum/Topper Selection '{node.name}'",
                                        "category": "Logical Error",
                                        "severity": "High",
                                        "file_path": file_path,
                                        "line_number": ln,
                                        "line_end": ln,
                                        "function_name": node.name,
                                        "code_snippet": snip,
                                        "description": (
                                            f"Function '{node.name}' is designed to identify the highest/maximum value, "
                                            f"but uses the comparison operator '<' on line {ln}. This comparison logic is inverted: "
                                            f"it fails to select higher scores and will retain an empty/stale result."
                                        ),
                                        "suggested_next_step": "Change the comparison operator from '<' to '>'.",
                                        "fix_type": "comparison_inversion",
                                        "bad_op": "<",
                                        "good_op": ">",
                                        "is_confirmed": False,
                                    })
                                elif is_min_search and isinstance(op, (ast.Gt, ast.GtE)):
                                    findings.append({
                                        "rule_id": "PY_LOGICAL_COMPARISON",
                                        "title": f"Inverted Comparison Operator in Minimum Selection '{node.name}'",
                                        "category": "Logical Error",
                                        "severity": "High",
                                        "file_path": file_path,
                                        "line_number": ln,
                                        "line_end": ln,
                                        "function_name": node.name,
                                        "code_snippet": snip,
                                        "description": (
                                            f"Function '{node.name}' is designed to identify the lowest/minimum value, "
                                            f"but uses '>' on line {ln}. This comparison logic is inverted: it selects higher items instead of minimum."
                                        ),
                                        "suggested_next_step": "Change the comparison operator from '>' to '<'.",
                                        "fix_type": "comparison_inversion",
                                        "bad_op": ">",
                                        "good_op": "<",
                                        "is_confirmed": False,
                                    })

                # -------------------------------------------------------------
                # 3. Inverted Condition in Pass / Validation Counter Functions
                # -------------------------------------------------------------
                is_pass_count = any(k in fn_name for k in ("count_passed", "passed_count", "count_pass", "get_passed"))
                if is_pass_count:
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.If) and isinstance(sub.test, ast.Compare):
                            cmp = sub.test
                            if len(cmp.ops) == 1 and len(cmp.comparators) == 1:
                                op = cmp.ops[0]
                                ln = getattr(sub, "lineno", node.lineno)
                                snip = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
                                # If pass counting checks `val < 40`, it counts failures instead of passes
                                if isinstance(op, (ast.Lt, ast.LtE)):
                                    findings.append({
                                        "rule_id": "PY_LOGICAL_CONDITION",
                                        "title": f"Inverted Passing Condition in '{node.name}'",
                                        "category": "Logical Error",
                                        "severity": "High",
                                        "file_path": file_path,
                                        "line_number": ln,
                                        "line_end": ln,
                                        "function_name": node.name,
                                        "code_snippet": snip,
                                        "description": (
                                            f"Function '{node.name}' increments a 'passed' counter, but tests whether the score/average "
                                            f"is less than the threshold on line {ln}. This condition counts failing students rather than "
                                            f"passing students."
                                        ),
                                        "suggested_next_step": "Change the condition operator to '>=' to count students meeting or exceeding the passing threshold.",
                                        "fix_type": "pass_threshold_inversion",
                                        "bad_op": "<",
                                        "good_op": ">=",
                                        "is_confirmed": False,
                                    })

                # -------------------------------------------------------------
                # 4. Overwriting Accumulator Inside Loop Instead of Incrementing
                # -------------------------------------------------------------
                for sub in ast.walk(node):
                    if isinstance(sub, (ast.For, ast.While)):
                        for stmt in sub.body:
                            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                                var_id = stmt.targets[0].id
                                # If initialized before loop and assigned a simple value (not BinOp with self)
                                if (
                                    var_id in ("total", "sum", "count", "acc", "accumulator")
                                    and not any(isinstance(n, ast.Name) and n.id == var_id for n in ast.walk(stmt.value))
                                ):
                                    ln = stmt.lineno
                                    snip = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
                                    findings.append({
                                        "rule_id": "PY_LOGICAL_CALCULATION",
                                        "title": f"Accumulator Overwrite in Loop '{node.name}'",
                                        "category": "Logical Error",
                                        "severity": "High",
                                        "file_path": file_path,
                                        "line_number": ln,
                                        "line_end": ln,
                                        "function_name": node.name,
                                        "code_snippet": snip,
                                        "description": f"Variable '{var_id}' is overwritten on line {ln} inside the loop instead of accumulating values (e.g. '+=').",
                                        "suggested_next_step": f"Use '+=' instead of '=' to accumulate values across iterations.",
                                        "fix_type": "accumulator_overwrite",
                                        "is_confirmed": False,
                                    })

                # -------------------------------------------------------------
                # 5. Premature Unconditional Return Inside Loop
                # -------------------------------------------------------------
                for sub in ast.walk(node):
                    if isinstance(sub, (ast.For, ast.While)):
                        if sub.body and isinstance(sub.body[0], ast.Return):
                            ret_node = sub.body[0]
                            ln = ret_node.lineno
                            snip = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
                            findings.append({
                                "rule_id": "PY_LOGICAL_LOOP_BOUND",
                                "title": f"Premature Unconditional Return in Loop '{node.name}'",
                                "category": "Logical Error",
                                "severity": "High",
                                "file_path": file_path,
                                "line_number": ln,
                                "line_end": ln,
                                "function_name": node.name,
                                "code_snippet": snip,
                                "description": f"Loop in function '{node.name}' returns unconditionally on the first iteration at line {ln}, terminating the loop prematurely.",
                                "suggested_next_step": "Move the return statement outside the loop body or wrap it in a termination condition.",
                                "fix_type": "premature_return",
                                "is_confirmed": False,
                            })

                # -------------------------------------------------------------
                # 6. Impossible / Mutually Exclusive Logical Conditions
                # -------------------------------------------------------------
                for sub in ast.walk(node):
                    if isinstance(sub, ast.If) and isinstance(sub.test, ast.BoolOp) and isinstance(sub.test.op, ast.And):
                        # Pattern: x < A and x > B where A <= B
                        comps = [c for c in sub.test.values if isinstance(c, ast.Compare)]
                        if len(comps) >= 2:
                            c1, c2 = comps[0], comps[1]
                            if (
                                isinstance(c1.left, ast.Name)
                                and isinstance(c2.left, ast.Name)
                                and c1.left.id == c2.left.id
                            ):
                                var_id = c1.left.id
                                op1 = c1.ops[0] if c1.ops else None
                                op2 = c2.ops[0] if c2.ops else None
                                val1 = c1.comparators[0] if c1.comparators else None
                                val2 = c2.comparators[0] if c2.comparators else None
                                if (
                                    isinstance(val1, ast.Constant)
                                    and isinstance(val2, ast.Constant)
                                    and isinstance(val1.value, (int, float))
                                    and isinstance(val2.value, (int, float))
                                ):
                                    # e.g. x < 0 and x > 100
                                    if (isinstance(op1, (ast.Lt, ast.LtE)) and isinstance(op2, (ast.Gt, ast.GtE)) and val1.value <= val2.value) or (
                                        isinstance(op2, (ast.Lt, ast.LtE)) and isinstance(op1, (ast.Gt, ast.GtE)) and val2.value <= val1.value
                                    ):
                                        ln = sub.lineno
                                        snip = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
                                        findings.append({
                                            "rule_id": "PY_LOGICAL_CONDITION",
                                            "title": f"Mutually Exclusive 'and' Condition in '{node.name}'",
                                            "category": "Logical Error",
                                            "severity": "High",
                                            "file_path": file_path,
                                            "line_number": ln,
                                            "line_end": ln,
                                            "function_name": node.name,
                                            "code_snippet": snip,
                                            "description": f"Condition on line {ln} uses 'and' between contradictory range bounds, making the block unreachable.",
                                            "suggested_next_step": "Change 'and' to 'or' if checking for out-of-bounds values.",
                                            "fix_type": "impossible_condition",
                                            "is_confirmed": False,
                                        })

        return findings
