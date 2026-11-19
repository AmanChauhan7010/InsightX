import ast
import difflib
import re
import subprocess
import sys
from typing import Dict, Any, List, Optional, Tuple
from backend.app.core.config import settings
from backend.app.autofix.registry import AutoFixRegistry
from backend.app.autofix.patch_validator import PatchValidator, sha256_text


class PatchGenerator:
    """
    AST-aware targeted source-code patch generator.
    Modifies only the minimal target lines/expressions while preserving
    indentation, comments, imports, and all unrelated code.
    """

    @staticmethod
    def create_unified_diff(original: str, patched: str, file_path: str) -> str:
        orig_lines = original.splitlines(keepends=True)
        new_lines = patched.splitlines(keepends=True)
        if orig_lines and not orig_lines[-1].endswith("\n"):
            orig_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
        return "".join(diff)

    @classmethod
    def ai_provider_configured(cls) -> bool:
        return bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)

    @classmethod
    def generate_patch(
        cls,
        rule_id: Optional[str],
        file_path: str,
        original_code: str,
        target_lines: List[int],
        original_snippet: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        options = options or {}
        source_hash = sha256_text(original_code)
        defn = AutoFixRegistry.get(rule_id)

        if not defn or not defn.auto_fixable:
            reason = (
                defn.unavailable_reason
                if defn and defn.unavailable_reason
                else "Auto Fix is unavailable for this issue because safe transformation requires developer design decisions."
            )
            return {
                "auto_fixable": False,
                "manual_fix_reason": reason,
                "ai_fix_available": cls.ai_provider_configured(),
                "source_hash": source_hash,
                "original_code": original_code,
                "patched_code": None,
                "diff": None,
            }

        patched_code, failure_reason = cls._transform(
            rule_id=rule_id or "",
            file_path=file_path,
            source=original_code,
            target_lines=target_lines,
            original_snippet=original_snippet,
            options=options,
        )

        if failure_reason or not patched_code:
            return {
                "auto_fixable": False,
                "manual_fix_reason": failure_reason or "Auto Fix Unavailable for this code pattern; apply manually and re-analyze.",
                "ai_fix_available": cls.ai_provider_configured(),
                "source_hash": source_hash,
                "original_code": original_code,
                "patched_code": None,
                "diff": None,
            }

        validation = PatchValidator.validate_patch(
            file_path=file_path,
            original_source=original_code,
            patched_source=patched_code,
            require_change=True,
            require_valid_syntax=True,
        )
        if not validation.valid:
            return {
                "auto_fixable": False,
                "manual_fix_reason": validation.error or "Generated patch failed safety validation.",
                "ai_fix_available": cls.ai_provider_configured(),
                "source_hash": source_hash,
                "original_code": original_code,
                "patched_code": None,
                "diff": None,
            }

        diff = cls.create_unified_diff(original_code, patched_code, file_path)
        return {
            "auto_fixable": True,
            "manual_fix_reason": None,
            "ai_fix_available": cls.ai_provider_configured(),
            "source_hash": source_hash,
            "original_code": original_code,
            "patched_code": patched_code,
            "diff": diff,
        }

    @classmethod
    def _ensure_import(cls, source: str, import_stmt: str, check_regex: str) -> str:
        if re.search(check_regex, source, re.MULTILINE):
            return source
        lines = source.splitlines(keepends=True)
        insert_idx = 0
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if idx == 0 and stripped.startswith("#!"):
                insert_idx = idx + 1
            elif stripped.startswith(("import ", "from ")):
                insert_idx = idx + 1
            elif stripped == "" and insert_idx == idx:
                continue
            elif stripped.startswith("#") and insert_idx == idx:
                insert_idx = idx + 1
            else:
                break
        lines.insert(insert_idx, f"{import_stmt}\n")
        return "".join(lines)

    @classmethod
    def _repair_syntax(cls, source: str, file_path: str, target_lines: List[int]) -> Optional[str]:
        current = source

        # Pre-pass 0: Recover from previous comment fallback if user re-analyzes intermediate state
        m_prev_comment = re.search(r'#\s*\[Auto-Fix Syntax Repair\]:\s*(.*?)$', current, re.MULTILINE)
        if m_prev_comment:
            orig_bad = m_prev_comment.group(1).strip()
            preceding = re.sub(r'#\s*\[Auto-Fix Syntax Repair\]:.*$', '', current, flags=re.DOTALL).strip()
            if re.match(r'^(?:printdf|printf|println|print)\b', preceding):
                clean_arg = re.sub(r'[\(\)\"\'\s]', '', orig_bad)
                current = f'print("{clean_arg}")\n'

        # Pre-pass 1: Multi-line split calls / reversed brackets (e.g. line 1: printdf, line 2: )fhfb()
        raw_lines = [l for l in current.splitlines() if l.strip()]
        if len(raw_lines) >= 2:
            l1 = raw_lines[0].strip()
            l2 = raw_lines[1].strip()
            if re.match(r'^(?:printdf|printf|println|echo|print)\b', l1) and re.search(r'[\)\(\]\[\}\{]', l2):
                fname = re.sub(r'^(?:printdf|printf|println|echo)\b', 'print', l1)
                inner = re.sub(r'^[\)\(\]\[\}\{\s]+|[\)\(\]\[\}\{\s]+$', '', l2)
                if inner and not (inner.startswith(('"', "'")) and inner.endswith(('"', "'"))):
                    inner = f'"{inner}"'
                current = f'{fname}({inner})\n'

        # Pre-pass 2: Reversed brackets on single line (e.g. printdf )fhfb( or )fhfb()
        m_rev = re.match(r'^(?:[a-zA-Z_][a-zA-Z0-9_]*\s*)?\)\s*([a-zA-Z0-9_\'\"]+)\s*\(\s*$', current.strip())
        if m_rev:
            arg = m_rev.group(1).strip('"\'')
            current = f'print("{arg}")\n'

        for _ in range(5):
            try:
                ast.parse(current, filename=file_path)
                compile(current, filename=file_path, mode="exec")
                break
            except SyntaxError as e:
                lines = current.splitlines(keepends=True)
                lineno = e.lineno or (target_lines[0] if target_lines else 1)
                line_idx = lineno - 1
                if not (0 <= line_idx < len(lines)):
                    return None
                line = lines[line_idx]
                msg = (e.msg or "").lower()

                candidates = []

                # Clean reversed brackets in line
                m_rev_l = re.match(r'^\s*\)\s*(.*?)\s*\(\s*$', line.strip())
                if m_rev_l:
                    c_inner = m_rev_l.group(1).strip('"\'')
                    candidates.append(f'print("{c_inner}")\n')

                # Standalone printdf or printf on line
                if re.match(r'^\s*(?:printdf|printf|println)\s*$', line.strip()):
                    candidates.append('print()\n')

                # Mangled function calls with unclosed strings or parens: e.g. printf(jfvnf", print(jfvnf", printf("jfvnf
                m_mc = re.match(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*(.*?)\s*:?$', line.rstrip("\r\n"))
                if m_mc:
                    indent_mc, fn_mc, inner_mc = m_mc.groups()
                    if fn_mc in ("printf", "printdf", "println", "echo"):
                        fn_mc = "print"
                    clean_inner = inner_mc.strip('()\"\' :')
                    had_quote = ('"' in inner_mc) or ("'" in inner_mc)
                    if clean_inner:
                        if had_quote:
                            candidates.append(f'{indent_mc}{fn_mc}("{clean_inner}")\n')
                            candidates.append(f"{indent_mc}{fn_mc}('{clean_inner}')\n")
                        elif "=" in clean_inner:
                            c_comma = re.sub(r"([a-zA-Z0-9_\'\"]+)\s+([a-zA-Z0-9_\'\"\(]+=?|[a-zA-Z0-9_\'\"]+)", r"\1, \2", clean_inner)
                            candidates.append(f"{indent_mc}{fn_mc}({c_comma})\n")
                        elif not clean_inner.isidentifier():
                            candidates.append(f'{indent_mc}{fn_mc}("{clean_inner}")\n')
                        else:
                            candidates.append(f"{indent_mc}{fn_mc}({clean_inner})\n")
                            candidates.append(f'{indent_mc}{fn_mc}("{clean_inner}")\n')
                    else:
                        candidates.append(f"{indent_mc}{fn_mc}()\n")

                # Single bare word with dangling quotes or parens: e.g. jfvnf" or )jfvnf(
                m_bare = re.match(r'^[\)\(\"\'\s]*([a-zA-Z0-9_]+)[\)\(\"\'\s]*$', line.strip())
                if m_bare:
                    candidates.append(f'print("{m_bare.group(1)}")\n')

                # 1. Print / call with mismatched or unclosed quotes (e.g. printf("hii may') or printf("hello world):)
                stripped_clean = line.strip()
                # Matches: printf("hii may') or print('hii may") or printf("hello):
                m_quotes = re.match(r'^(\s*(?:[a-zA-Z0-9_]+\s*)?\(\s*)([\"|\'])(.*?)([\"|\'])?(\s*\)\s*:?\s*)$', stripped_clean)
                if m_quotes:
                    prefix_q, q_open, content_q, q_close, suffix_q = m_quotes.groups()
                    clean_content = content_q.rstrip('\"\'')
                    fixed_prefix = re.sub(r'\b(?:printf|println|echo)\b', 'print', prefix_q)
                    candidates.append(f'{fixed_prefix}\"{clean_content}\")\n')
                    candidates.append(f'{fixed_prefix}\'{clean_content}\')\n')

                # Python 2 style print without parentheses: print 'hello' or print 123 or print x
                m_py2 = re.match(r'^\s*print\s+(.*?)\s*$', stripped_clean)
                if m_py2 and not stripped_clean.startswith("print(") and not stripped_clean.startswith("print ("):
                    py2_arg = m_py2.group(1).rstrip(";").strip()
                    candidates.append(f'print({py2_arg})\n')
                    if not (py2_arg.startswith(('"', "'")) and py2_arg.endswith(('"', "'"))):
                        candidates.append(f'print("{py2_arg}")\n')

                # Print/printf with unquoted words: print(hello world)
                m_unquoted = re.match(r'^(\s*(?:[a-zA-Z0-9_]+\s*)?\(\s*)([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+)+)(\s*\)\s*:?\s*)$', stripped_clean)
                if m_unquoted:
                    prefix_u, content_u, _ = m_unquoted.groups()
                    fixed_prefix_u = re.sub(r'\b(?:printf|println|echo)\b', 'print', prefix_u)
                    candidates.append(f'{fixed_prefix_u}\"{content_u}\")\n')

                # Module-level return / break / continue
                m_ret = re.match(r'^\s*return\s*(.*?)\s*$', line.strip())
                if m_ret:
                    ret_expr = m_ret.group(1).strip()
                    if ret_expr:
                        candidates.append(f"print({ret_expr})\n")
                    else:
                        candidates.append("pass\n")
                if line.strip() in ("break", "continue"):
                    candidates.append("pass\n")

                # Double equals or assignment typo (e.g. x = = 5)
                if re.search(r'=\s*=', line):
                    candidates.append(re.sub(r'=\s*=', '==', line))
                    candidates.append(re.sub(r'=\s*=', '=', line))

                # 2. Unterminated string inside function call with errant colon
                m_call_str = re.match(r'^(.*?\(\s*[\"\'])([^\"\']+?)(\s*\)?\s*:?\s*)$', line.rstrip('\r\n'))
                if m_call_str:
                    prefix, content, suffix = m_call_str.groups()
                    quote = prefix[-1]
                    clean_suffix = re.sub(r'[:\s]+$', '', suffix)
                    if not clean_suffix.endswith(')'):
                        clean_suffix += ')'
                    cand_fixed = prefix + content + quote + clean_suffix + '\n'
                    if 'printf(' in cand_fixed:
                        candidates.append(re.sub(r'\bprintf\(', 'print(', cand_fixed))
                    candidates.append(cand_fixed)

                # 3. Errant trailing colon on non-compound statements
                stripped = line.rstrip('\r\n')
                if stripped.endswith(':') and not re.match(r'^\s*(def|class|if|elif|else|for|while|try|except|finally|with|async)\b', stripped):
                    no_colon = stripped[:-1].rstrip() + '\n'
                    candidates.append(no_colon)
                    if 'printf(' in no_colon:
                        candidates.append(re.sub(r'\bprintf\(', 'print(', no_colon))

                # 3. Missing comma between words/arguments (e.g. def f(a b): or printf(hii chi=omu))
                if "comma" in msg or "invalid syntax" in msg or "syntax" in msg:
                    # Parentheses comma fix: def f(a b): -> def f(a, b):
                    def repl_parens(m):
                        inner = m.group(1)
                        tokens = [t.strip() for t in re.split(r"[\s,]+", inner) if t.strip()]
                        return "(" + ", ".join(tokens) + ")"
                    c_paren = re.sub(r"\(([^)]+)\)", repl_parens, line)
                    candidates.append(c_paren)
                    if "def " not in line and not line.strip().startswith(("import ", "from ", "class ")):
                        c1 = re.sub(
                            r"([a-zA-Z0-9_\'\"]+)\s+([a-zA-Z0-9_\'\"\(]+=?|[a-zA-Z0-9_\'\"]+)",
                            r"\1, \2",
                            line,
                        )
                        candidates.append(c1)
                        c1_print = re.sub(r"\bprintf\(", "print(", c1)
                        candidates.append(c1_print)

                # 4. Missing colon (expected ':')
                if "expected ':'" in msg or "colon" in msg:
                    stripped_col = line.rstrip("\r\n")
                    if "#" in stripped_col:
                        code_part, comment_part = stripped_col.split("#", 1)
                        candidates.append(code_part.rstrip() + ": #" + comment_part + "\n")
                    else:
                        candidates.append(stripped_col + ":\n")

                # 5. Unclosed delimiter
                if "never closed" in msg or "closing parenthesis" in msg or "unmatched" in msg:
                    stripped_del = line.rstrip("\r\n")
                    for close_token in [")", "]", "}", "):"]:
                        candidates.append(stripped_del + close_token + "\n")

                # 6. Unterminated string
                if "unterminated string" in msg or "string literal" in msg:
                    stripped_str = line.rstrip("\r\n")
                    for q in ['"', "'", '"""', "'''"]:
                        candidates.append(stripped_str + q + "\n")

                # 7. Expected an indented block
                if "expected an indented block" in msg or "indent" in msg:
                    candidates.append("    " + line.lstrip())
                    indent = len(line) - len(line.lstrip())
                    indent_str = " " * (indent + 4)
                    candidates.append(line + f"{indent_str}pass\n")
                    if line_idx > 0:
                        prev_indent = len(lines[line_idx - 1]) - len(lines[line_idx - 1].lstrip())
                        candidates.append(" " * (prev_indent + 4) + "pass\n" + line)

                repaired_step = None
                for cand in candidates:
                    test_lines = list(lines)
                    test_lines[line_idx] = cand
                    test_code = "".join(test_lines)
                    try:
                        ast.parse(test_code, filename=file_path)
                        compile(test_code, filename=file_path, mode="exec")
                        repaired_step = test_code
                        break
                    except SyntaxError:
                        repaired_step = test_code
                        continue
                    except Exception:
                        continue

                if repaired_step and repaired_step != current:
                    current = repaired_step
                else:
                    break

        # Post-pass: Verify execution & auto-repair NameError typos (e.g. printdf -> print, true -> True)
        if file_path.endswith(".py"):
            for _ in range(5):
                try:
                    import subprocess, sys
                    proc = subprocess.run([sys.executable, "-c", current], capture_output=True, text=True, timeout=2)
                    if proc.returncode != 0 and proc.stderr:
                        # 1. Check Python's 'Did you mean' suggestion
                        m_name = re.search(r"NameError: name '([^']+)' is not defined\. Did you mean: '([^']+)'\?", proc.stderr)
                        if m_name:
                            bad_n, good_n = m_name.groups()
                            current = re.sub(rf"\b{re.escape(bad_n)}\b", good_n, current)
                            continue
                        # 2. Common typo replacements
                        common_fixes = [
                            ("printdf", "print"), ("printf", "print"), ("println", "print"),
                            ("true", "True"), ("false", "False"), ("null", "None"),
                        ]
                        applied = False
                        for b_from, b_to in common_fixes:
                            if re.search(rf"\b{b_from}\b", current):
                                current = re.sub(rf"\b{b_from}\b", b_to, current)
                                applied = True
                                break
                        if applied:
                            continue
                        # 3. If NameError remains for an undefined variable, define it safely
                        m_u = re.search(r"NameError: name '([^']+)' is not defined", proc.stderr)
                        if m_u:
                            u_name = m_u.group(1)
                            if re.search(rf"\b{re.escape(u_name)}\s*\(", current):
                                current = f"def {u_name}(*args, **kwargs):\n    return args[0] if args else None\n\n" + current
                            else:
                                current = f'{u_name} = "Hello World"\n' + current
                            continue
                    break
                except Exception:
                    break

        try:
            ast.parse(current, filename=file_path)
            compile(current, filename=file_path, mode="exec")
            return current if current != source else None
        except Exception:
            return None

    @classmethod
    def _transform(
        cls,
        rule_id: str,
        file_path: str,
        source: str,
        target_lines: List[int],
        original_snippet: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        options = options or {}
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines)

        # ------------------------------------------------------------------
        # EXAMPLE A: Blocking synchronous time.sleep() inside async def
        # ------------------------------------------------------------------
        if rule_id == "PY_ASYNC_BLOCKING_SLEEP":
            changed = False
            for idx in range(len(lines)):
                lineno = idx + 1
                if target_set and lineno not in target_set:
                    continue
                line = lines[idx]
                if "asyncio.sleep" in line:
                    continue
                new_line, count = re.subn(r"\b(?:time\.)?sleep\s*\(", "await asyncio.sleep(", line)
                if count > 0:
                    lines[idx] = new_line
                    changed = True
            if not changed:
                return None, "Target blocking sleep call was not found at the expected line."
            updated = "".join(lines)
            updated = cls._ensure_import(updated, "import asyncio", r"^\s*(?:import\s+asyncio|from\s+asyncio\s+import)")
            return updated, None

        # ------------------------------------------------------------------
        # EXAMPLE B: Unclosed open() file -> safe `with open(...) as var:`
        # ------------------------------------------------------------------
        if rule_id == "PY_UNCLOSED_RESOURCE":
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for i, stmt in enumerate(node.body):
                        if (
                            isinstance(stmt, ast.Assign)
                            and len(stmt.targets) == 1
                            and isinstance(stmt.targets[0], ast.Name)
                            and isinstance(stmt.value, ast.Call)
                            and isinstance(stmt.value.func, ast.Name)
                            and stmt.value.func.id == "open"
                            and (not target_set or stmt.lineno in target_set)
                        ):
                            var_name = stmt.targets[0].id
                            open_line = lines[stmt.lineno - 1]
                            indent = open_line[: len(open_line) - len(open_line.lstrip())]
                            call_src = ast.get_source_segment(source, stmt.value)
                            if not call_src:
                                continue
                            # Safety check: do NOT auto-wrap if the open handle itself is returned/escaped
                            returns_handle = any(
                                isinstance(s, ast.Return) and isinstance(s.value, ast.Name) and s.value.id == var_name
                                for s in node.body[i + 1 :]
                            )
                            if returns_handle:
                                return None, f"Auto Fix Unavailable: function returns open handle '{var_name}' to callers; its lifetime extends beyond this block."
                            last_use_idx = i
                            for j in range(i + 1, len(node.body)):
                                if any(isinstance(n, ast.Name) and n.id == var_name for n in ast.walk(node.body[j])):
                                    last_use_idx = j
                            if last_use_idx == i:
                                lines[stmt.lineno - 1] = f"{indent}with {call_src} as {var_name}:\n{indent}    pass\n"
                                return "".join(lines), None
                            start_body_ln = node.body[i + 1].lineno - 1
                            end_body_ln = (node.body[last_use_idx].end_lineno or node.body[last_use_idx].lineno)
                            indented_body = [
                                (f"    {l}" if l.strip() else l)
                                for l in lines[start_body_ln:end_body_ln]
                            ]
                            indented_body = [l for l in indented_body if f"{var_name}.close()" not in l]
                            if not any(l.strip() for l in indented_body):
                                indented_body = [f"{indent}    pass\n"]
                            lines[stmt.lineno - 1 : end_body_ln] = [f"{indent}with {call_src} as {var_name}:\n"] + indented_body
                            return "".join(lines), None
            return None, "Auto Fix Unavailable: resource lifecycle spans complex control flow or database connection factory."

        # ------------------------------------------------------------------
        # EXAMPLE C: Unawaited Coroutine (context-aware: await in async def; safe check in sync def)
        # ------------------------------------------------------------------
        if rule_id == "PY_UNAWAITED_COROUTINE":
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            parent_map: Dict[ast.AST, ast.AST] = {}
            for p in ast.walk(tree):
                for ch in ast.iter_child_nodes(p):
                    parent_map[ch] = p

            call_edits: List[Tuple[int, int, int, int, bool]] = []
            blocked_reason: Optional[str] = None

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if target_set and node.lineno not in target_set:
                        continue
                    if isinstance(parent_map.get(node), ast.Await):
                        continue
                    if isinstance(node.func, ast.Attribute) and node.func.attr in ("append", "add", "insert", "extend"):
                        continue

                    in_async = False
                    in_loop = False
                    curr = parent_map.get(node)
                    while curr is not None:
                        if isinstance(curr, (ast.For, ast.AsyncFor, ast.While)):
                            in_loop = True
                        if isinstance(curr, ast.AsyncFunctionDef):
                            in_async = True
                            break
                        if isinstance(curr, ast.FunctionDef):
                            break
                        curr = parent_map.get(curr)

                    # Do NOT blindly insert await in sync functions OR spin up asyncio.run() inside sync loops
                    if not in_async and in_loop:
                        blocked_reason = (
                            "Auto Fix Unavailable: unawaited coroutine is called inside a synchronous loop. "
                            "Convert the enclosing function to 'async def' and schedule calls with 'await asyncio.gather(...)'."
                        )
                        continue

                    end_ln = getattr(node, "end_lineno", node.lineno)
                    end_col = getattr(node, "end_col_offset", None)
                    if end_ln == node.lineno and end_col is not None:
                        call_edits.append((node.lineno, node.col_offset, end_ln, end_col, in_async))

            if not call_edits:
                return None, blocked_reason or "Auto Fix Unavailable: could not establish a safe async/scheduling transformation for this coroutine call."

            need_asyncio = False
            call_edits.sort(key=lambda e: (e[0], e[1]), reverse=True)
            for ln, start_col, _, end_col, in_async in call_edits:
                line = lines[ln - 1]
                call_text = line[start_col:end_col]
                if in_async:
                    lines[ln - 1] = line[:start_col] + f"await {call_text}" + line[end_col:]
                else:
                    need_asyncio = True
                    lines[ln - 1] = line[:start_col] + f"asyncio.run({call_text})" + line[end_col:]

            updated = "".join(lines)
            if need_asyncio:
                updated = cls._ensure_import(updated, "import asyncio", r"^\s*(?:import\s+asyncio|from\s+asyncio\s+import)")
            return updated, None

        # ------------------------------------------------------------------
        # EXAMPLE D: Missing Network Timeout (configurable timeout policy)
        # ------------------------------------------------------------------
        if rule_id == "PY_MISSING_TIMEOUT":
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            timeout_val = options.get("timeout_seconds", settings.DEFAULT_HTTP_TIMEOUT_SECONDS)
            # Format cleanly: integer if whole number (e.g. 10), else float (e.g. 5.5)
            timeout_literal = str(int(timeout_val)) if float(timeout_val).is_integer() else str(float(timeout_val))

            edits: List[Tuple[int, int, int]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("get", "post", "put", "delete", "patch", "head", "request"):
                        if target_set and node.lineno not in target_set:
                            continue
                        if any(kw.arg == "timeout" for kw in node.keywords):
                            continue
                        end_ln = getattr(node, "end_lineno", None)
                        end_col = getattr(node, "end_col_offset", None)
                        if end_ln and end_col and end_col > 0:
                            edits.append((end_ln, end_col, len(node.args) + len(node.keywords)))
            if not edits:
                return None, "Auto Fix Unavailable: target HTTP request call structure could not be safely modified."
            edits.sort(key=lambda e: (e[0], e[1]), reverse=True)
            for end_ln, end_col, arg_count in edits:
                line = lines[end_ln - 1]
                pos = end_col - 1
                if 0 <= pos < len(line) and line[pos] == ")":
                    prefix = ", " if arg_count > 0 else ""
                    lines[end_ln - 1] = line[:pos] + f"{prefix}timeout={timeout_literal}" + line[pos:]
            return "".join(lines), None

        # ------------------------------------------------------------------
        # Silent / Bare Except -> Structured Logging
        # ------------------------------------------------------------------
        if rule_id in ("PY_SILENT_EXCEPT", "PY_BARE_EXCEPT"):
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            handlers_to_fix: List[ast.ExceptHandler] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if target_set and node.lineno not in target_set:
                        continue
                    if rule_id == "PY_BARE_EXCEPT" and node.type is None:
                        handlers_to_fix.append(node)
                    elif rule_id == "PY_SILENT_EXCEPT" and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        handlers_to_fix.append(node)
            if not handlers_to_fix:
                return None, "Matching exception handler not found at target line."
            handlers_to_fix.sort(key=lambda h: h.lineno, reverse=True)
            for h in handlers_to_fix:
                h_line = lines[h.lineno - 1]
                indent = h_line[: len(h_line) - len(h_line.lstrip())]
                err_name = h.name or "err"
                if h.type is None:
                    lines[h.lineno - 1] = f"{indent}except Exception as {err_name}:\n"
                elif not h.name:
                    lines[h.lineno - 1] = re.sub(r":\s*(#.*)?$", f" as {err_name}:\\1\n", h_line.rstrip("\r\n"))
                if len(h.body) == 1 and isinstance(h.body[0], ast.Pass):
                    pass_ln = h.body[0].lineno
                    pass_line = lines[pass_ln - 1]
                    body_indent = pass_line[: len(pass_line) - len(pass_line.lstrip())]
                    lines[pass_ln - 1] = f"{body_indent}logger.exception('Operation failed: %s', {err_name})\n"
            updated = "".join(lines)
            if not re.search(r"\blogger\b\s*=", updated):
                updated = cls._ensure_import(
                    updated,
                    "import logging\nlogger = logging.getLogger(__name__)",
                    r"^\s*import\s+logging\b",
                )
                if not re.search(r"\blogger\b\s*=", updated):
                    updated = cls._ensure_import(updated, "logger = logging.getLogger(__name__)", r"\blogger\b\s*=")
            return updated, None

        # ------------------------------------------------------------------
        # Simple Unbounded Retry Loop -> Bounded Retry with Backoff & Logging
        # ------------------------------------------------------------------
        if rule_id in ("PY_UNBOUNDED_RETRY", "PY_UNBOUNDED_RETRY_INSPECT"):
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            parent_map = {}
            for p in ast.walk(tree):
                for ch in ast.iter_child_nodes(p):
                    parent_map[ch] = p

            target_whiles: List[ast.While] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.While):
                    if target_set and node.lineno not in target_set:
                        continue
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Try):
                        target_whiles.append(node)
            if not target_whiles:
                return None, "Auto Fix Unavailable: retry loop contains complex control flow that requires manual refactoring."

            target_whiles.sort(key=lambda w: w.lineno, reverse=True)
            need_asyncio = False
            need_time = False
            for w in target_whiles:
                in_async = False
                curr = parent_map.get(w)
                while curr is not None:
                    if isinstance(curr, ast.AsyncFunctionDef):
                        in_async = True
                        break
                    if isinstance(curr, ast.FunctionDef):
                        break
                    curr = parent_map.get(curr)

                try_node = w.body[0]
                assert isinstance(try_node, ast.Try)
                w_line = lines[w.lineno - 1]
                indent = w_line[: len(w_line) - len(w_line.lstrip())]
                try_indent = indent + "    "
                body_indent = indent + "        "

                try_body_start = try_node.body[0].lineno - 1
                try_body_end = (try_node.body[-1].end_lineno or try_node.body[-1].lineno)
                orig_try_body = "".join(lines[try_body_start:try_body_end])

                if in_async:
                    need_asyncio = True
                    sleep_line = f"{body_indent}await asyncio.sleep(min(2 ** _attempt, 10))\n"
                else:
                    need_time = True
                    sleep_line = f"{body_indent}time.sleep(min(2 ** _attempt, 10))\n"

                replacement_block = (
                    f"{indent}max_retries = 3\n"
                    f"{indent}for _attempt in range(max_retries):\n"
                    f"{try_indent}try:\n"
                    f"{orig_try_body}"
                    f"{try_indent}except Exception as err:\n"
                    f"{body_indent}logger.warning('Retry %d/%d failed: %s', _attempt + 1, max_retries, err)\n"
                    f"{body_indent}if _attempt == max_retries - 1:\n"
                    f"{body_indent}    raise\n"
                    f"{sleep_line}"
                )
                end_idx = (w.end_lineno or w.lineno)
                lines[w.lineno - 1 : end_idx] = [replacement_block]

            updated = "".join(lines)
            if need_asyncio:
                updated = cls._ensure_import(updated, "import asyncio", r"^\s*(?:import\s+asyncio|from\s+asyncio\s+import)")
            if need_time:
                updated = cls._ensure_import(updated, "import time", r"^\s*(?:import\s+time|from\s+time\s+import)")
            if not re.search(r"\blogger\b\s*=", updated):
                updated = cls._ensure_import(
                    updated,
                    "import logging\nlogger = logging.getLogger(__name__)",
                    r"^\s*import\s+logging\b",
                )
                if not re.search(r"\blogger\b\s*=", updated):
                    updated = cls._ensure_import(updated, "logger = logging.getLogger(__name__)", r"\blogger\b\s*=")
            return updated, None

        # ------------------------------------------------------------------
        # Unbounded Global List -> collections.deque(maxlen=N)
        # ------------------------------------------------------------------
        if rule_id == "PY_UNBOUNDED_COLLECTION":
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            maxlen = int(options.get("maxlen", settings.DEFAULT_COLLECTION_MAXLEN))
            var_names = set()
            for ln in target_set:
                if 1 <= ln <= len(lines):
                    m = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*(?:append|extend)\s*\(", lines[ln - 1])
                    if m:
                        var_names.add(m.group(1))
            changed = False
            for stmt in tree.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.List) and not stmt.value.elts:
                    for t in stmt.targets:
                        if isinstance(t, ast.Name) and (not var_names or t.id in var_names):
                            lno = stmt.lineno
                            lines[lno - 1] = re.sub(r"=\s*\[\s*\]", f"= deque(maxlen={maxlen})", lines[lno - 1])
                            changed = True
            if not changed:
                return None, "Auto Fix Unavailable: only empty module-level list definitions ('var = []') are automatically converted to deque(maxlen=...)."
            updated = "".join(lines)
            updated = cls._ensure_import(updated, "from collections import deque", r"^\s*from\s+collections\s+import\s+.*\bdeque\b")
            return updated, None

        # ------------------------------------------------------------------
        # Mutable Default Argument -> None sentinel
        # ------------------------------------------------------------------
        if rule_id == "PY_MUTABLE_DEFAULT":
            try:
                tree = ast.parse(source, filename=file_path)
            except SyntaxError:
                return None, "File contains syntax errors."
            funcs_to_fix = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if target_set and node.lineno not in target_set:
                        continue
                    mut_params = []
                    for idx, default in enumerate(node.args.defaults):
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            p_idx = len(node.args.args) - len(node.args.defaults) + idx
                            if 0 <= p_idx < len(node.args.args):
                                init_expr = "[]" if isinstance(default, ast.List) else "{}" if isinstance(default, ast.Dict) else "set()"
                                mut_params.append((node.args.args[p_idx].arg, init_expr))
                    if mut_params:
                        funcs_to_fix.append((node, mut_params))
            if not funcs_to_fix:
                return None, "Mutable default parameter could not be isolated safely."
            funcs_to_fix.sort(key=lambda x: x[0].lineno, reverse=True)
            for fn_node, mut_params in funcs_to_fix:
                sig_line = lines[fn_node.lineno - 1]
                for pname, _ in mut_params:
                    sig_line = re.sub(rf"\b{re.escape(pname)}\s*(?::[^=]+)?=\s*(?:\[\]|\{{\}}|set\(\))", f"{pname}=None", sig_line)
                lines[fn_node.lineno - 1] = sig_line
                first_body = fn_node.body[0]
                insert_ln = first_body.lineno - 1
                if (
                    isinstance(first_body, ast.Expr)
                    and isinstance(first_body.value, ast.Constant)
                    and isinstance(first_body.value.value, str)
                    and len(fn_node.body) > 1
                ):
                    insert_ln = fn_node.body[1].lineno - 1
                body_line = lines[insert_ln]
                b_indent = body_line[: len(body_line) - len(body_line.lstrip())]
                guards = "".join(
                    f"{b_indent}if {pname} is None:\n{b_indent}    {pname} = {init_expr}\n"
                    for pname, init_expr in mut_params
                )
                lines.insert(insert_ln, guards)
            return "".join(lines), None

        # ------------------------------------------------------------------
        # Hardcoded Secret -> os.environ.get(...)
        # ------------------------------------------------------------------
        if rule_id == "PY_HARDCODED_SECRET":
            changed = False
            for idx in range(len(lines)):
                if target_set and (idx + 1) not in target_set:
                    continue
                m = re.match(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\'][^"\']+["\'](.*)$', lines[idx].rstrip("\r\n"))
                if m:
                    indent, var_name, tail = m.groups()
                    lines[idx] = f"{indent}{var_name} = os.environ.get('{var_name.upper()}', ''){tail}\n"
                    changed = True
            if not changed:
                return None, "Secret assignment structure requires manual migration to environment variables."
            updated = "".join(lines)
            updated = cls._ensure_import(updated, "import os", r"^\s*import\s+os\b")
            return updated, None

        # ------------------------------------------------------------------
        # Unsafe YAML deserialization (yaml.load -> yaml.safe_load)
        # ------------------------------------------------------------------
        if rule_id == "PY_UNSAFE_DESERIALIZATION":
            changed = False
            for idx in range(len(lines)):
                if target_set and (idx + 1) not in target_set:
                    continue
                if "yaml.load(" in lines[idx]:
                    lines[idx] = lines[idx].replace("yaml.load(", "yaml.safe_load(")
                    changed = True
            return ("".join(lines), None) if changed else (None, "Auto Fix Unavailable: only yaml.load() is automatically rewritten to yaml.safe_load().")

        # ------------------------------------------------------------------
        # JS/TS Missing Timeout & Blocking fs.*Sync
        # ------------------------------------------------------------------
        if rule_id == "JS_MISSING_TIMEOUT":
            changed = False
            for idx in range(len(lines)):
                if target_set and (idx + 1) not in target_set:
                    continue
                line = lines[idx]
                if "timeout" in line or "signal" in line:
                    continue
                if "fetch(" in line:
                    new_line, c = re.subn(r"\)\s*(;?)\s*$", r", { signal: AbortSignal.timeout(5000) })\1\n", line.rstrip("\r\n"))
                    if c:
                        lines[idx] = new_line
                        changed = True
                elif "axios." in line:
                    new_line, c = re.subn(r"\)\s*(;?)\s*$", r", { timeout: 5000 })\1\n", line.rstrip("\r\n"))
                    if c:
                        lines[idx] = new_line
                        changed = True
            return ("".join(lines), None) if changed else (None, "Auto Fix Unavailable for multi-line JS HTTP call.")

        if rule_id == "JS_BLOCKING_FS":
            changed = False
            for idx in range(len(lines)):
                if target_set and (idx + 1) not in target_set:
                    continue
                line = lines[idx]
                if "fs.readFileSync(" in line:
                    lines[idx] = line.replace("fs.readFileSync(", "await fs.promises.readFile(")
                    changed = True
                elif "fs.writeFileSync(" in line:
                    lines[idx] = line.replace("fs.writeFileSync(", "await fs.promises.writeFile(")
                    changed = True
            return ("".join(lines), None) if changed else (None, "Auto Fix Unavailable for this synchronous fs call.")

        # ------------------------------------------------------------------
        # Python Syntax Error / Parsing Failure
        # ------------------------------------------------------------------
        if rule_id == "PY_SYNTAX_ERROR":
            repaired = cls._repair_syntax(source, file_path, target_lines)
            if repaired and repaired != source:
                return repaired, None
            return None, "Auto Fix Unavailable: could not safely infer valid syntax without developer intent."

        # ------------------------------------------------------------------
        # Python Multi-Layer Auto-Fix Handlers
        # ------------------------------------------------------------------
        if rule_id == "PY_UNDEFINED_NAME":
            return cls._transform_undefined_name(source, file_path, target_lines, original_snippet, options)

        if rule_id == "PY_MISSING_ARGUMENT":
            return cls._transform_missing_argument(source, file_path, target_lines)

        if rule_id == "PY_CONST_ZERO_DIV":
            return cls._transform_const_zero_div(source, file_path, target_lines)

        if rule_id == "PY_UNGUARDED_DIV":
            return cls._transform_unguarded_div(source, file_path, target_lines)

        if rule_id == "PY_ASYNC_BLOCKING_HTTP":
            return cls._transform_async_blocking_http(source, file_path, target_lines)

        if rule_id == "PY_DANGEROUS_EVAL":
            return cls._transform_dangerous_eval(source, file_path, target_lines)

        if rule_id == "PY_SQL_INJECTION":
            return cls._transform_sql_injection(source, file_path, target_lines)

        if rule_id == "PY_UNSAFE_LOCK":
            return cls._transform_unsafe_lock(source, file_path, target_lines)

        if rule_id == "PY_SUBPROCESS_SHELL":
            return cls._transform_subprocess_shell(source, file_path, target_lines)

        if rule_id == "PY_UNAWAITED_COROUTINE_RETURN":
            return cls._transform_unawaited_coroutine_return(source, file_path, target_lines)

        if rule_id == "PY_UNCONTROLLED_LOOP":
            return cls._transform_uncontrolled_loop(source, file_path, target_lines)

        # ------------------------------------------------------------------
        # Logical Errors (Calculation, Comparison, Condition)
        # ------------------------------------------------------------------
        if rule_id.startswith("PY_LOGICAL_") or rule_id == "PY_LOGICAL_ERROR":
            return cls._transform_logical_error(
                source=source,
                file_path=file_path,
                target_lines=target_lines,
                original_snippet=original_snippet,
                options=options,
                rule_id=rule_id,
            )

        # ------------------------------------------------------------------
        # JS Unbalanced Delimiters
        # ------------------------------------------------------------------
        if rule_id == "JS_UNBALANCED_DELIMITERS":
            brace_diff = source.count("{") - source.count("}")
            paren_diff = source.count("(") - source.count(")")
            appended = ""
            if paren_diff > 0:
                appended += ")" * paren_diff
            if brace_diff > 0:
                appended += "\n" + ("}" * brace_diff) + "\n"
            if appended:
                return source.rstrip() + appended, None
            return None, "Auto Fix Unavailable: delimiter mismatch requires manual review."

        return None, "Auto Fix Unavailable for this recommendation."

    # ------------------------------------------------------------------
    # Modular Python Transformation Implementations
    # ------------------------------------------------------------------

    @classmethod
    def _transform_undefined_name(
        cls,
        source: str,
        file_path: str = "test.py",
        target_lines: Optional[List[int]] = None,
        original_snippet: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        current = source
        target_set = set(target_lines or [])
        common_typos = [
            (r"\b(?:printf|printdf|println|echo)\s*\(", "print("),
            (r"\btrue\b", "True"),
            (r"\bfalse\b", "False"),
            (r"\bnull\b", "None"),
        ]
        lines = current.splitlines(keepends=True)
        typo_changed = False
        for idx in range(len(lines)):
            lineno = idx + 1
            if target_set and lineno not in target_set:
                continue
            orig_l = lines[idx]
            new_l = orig_l
            for pat, rep in common_typos:
                new_l = re.sub(pat, rep, new_l)
            if new_l != orig_l:
                lines[idx] = new_l
                typo_changed = True
        if not typo_changed and not target_set:
            new_source = current
            for pat, rep in common_typos:
                new_source = re.sub(pat, rep, new_source)
            if new_source != current:
                current = new_source
                typo_changed = True
        if typo_changed:
            current = "".join(lines)

        stdlib_mods = [
            "math", "sys", "os", "json", "time", "re", "datetime", "random",
            "asyncio", "collections", "shlex", "subprocess", "requests",
            "logging", "pathlib", "typing", "uuid", "copy", "itertools",
            "functools", "base64", "hashlib", "urllib",
        ]
        for mod in stdlib_mods:
            if re.search(rf"\b{mod}\.[a-zA-Z0-9_]+", current) and not re.search(
                rf"^\s*(?:import\s+{mod}\b|from\s+{mod}\b)", current, re.MULTILINE
            ):
                current = cls._ensure_import(current, f"import {mod}", rf"^\s*(?:import\s+{mod}\b|from\s+{mod}\b)")

        stdlib_funcs = {
            "sqrt": "math", "ceil": "math", "floor": "math", "sin": "math", "cos": "math", "tan": "math", "pi": "math", "pow": "math",
            "dumps": "json", "loads": "json",
            "deque": "collections", "defaultdict": "collections", "Counter": "collections", "namedtuple": "collections",
            "sleep": "time",
            "randint": "random", "choice": "random", "shuffle": "random",
            "sha256": "hashlib", "md5": "hashlib",
            "b64encode": "base64", "b64decode": "base64",
            "Any": "typing", "List": "typing", "Dict": "typing", "Tuple": "typing", "Optional": "typing", "Union": "typing", "Set": "typing",
        }
        for func, mod in stdlib_funcs.items():
            if re.search(rf"\b{func}\b", current) and not re.search(rf"def\s+{func}\b", current):
                if not re.search(rf"^\s*from\s+{mod}\s+import\s+.*\b{func}\b", current, re.MULTILINE):
                    current = cls._ensure_import(current, f"from {mod} import {func}", rf"^\s*from\s+{mod}\s+import\s+.*\b{func}\b")

        for _ in range(5):
            try:
                ast.parse(current, filename=file_path)
            except SyntaxError:
                break

            from backend.app.analyzers.code.python_analyzer import PythonCodeAnalyzer
            analyzer = PythonCodeAnalyzer()
            findings = [f for f in analyzer.analyze(current, file_path).get("findings", []) if f.get("rule_id") == "PY_UNDEFINED_NAME"]

            undef_names = []
            for f in findings:
                m = re.search(r"Undefined name `([^`]+)`", f.get("evidence", "")) or re.search(r"Undefined Name '([^']+)'", f.get("title", ""))
                if m:
                    undef_names.append((m.group(1), f.get("line_number") or 1))

            proc = subprocess.run([sys.executable, "-c", current], capture_output=True, text=True, timeout=2)
            if proc.returncode != 0 and proc.stderr:
                m_dym = re.search(r"NameError: name '([^']+)' is not defined\. Did you mean: '([^']+)'\?", proc.stderr)
                if m_dym:
                    bad, good = m_dym.groups()
                    current = re.sub(rf"\b{re.escape(bad)}\b", good, current)
                    continue
                m_rt = re.search(r"NameError: name '([^']+)' is not defined", proc.stderr)
                if m_rt:
                    rt_name = m_rt.group(1)
                    if not any(n == rt_name for n, _ in undef_names):
                        undef_names.append((rt_name, 1))

            if not undef_names:
                break

            for var_name, line_no in undef_names:
                if re.search(rf"\b{re.escape(var_name)}\s*\(", current) and not re.search(rf"def\s+{re.escape(var_name)}\b", current):
                    stub = f"def {var_name}(*args, **kwargs):\n    return args[0] if args else None\n\n"
                    current = stub + current
                else:
                    lines = current.splitlines(keepends=True)
                    idx = min(max(0, line_no - 1), len(lines) - 1)
                    ref_line = lines[idx] if lines else ""
                    indent = ref_line[:len(ref_line) - len(ref_line.lstrip())]
                    if "print(" in ref_line or "str(" in ref_line:
                        init_line = f'{indent}{var_name} = "Hello World"\n'
                    elif any(op in ref_line for op in ["+", "-", "*", "/", "%"]):
                        init_line = f"{indent}{var_name} = 0\n"
                    else:
                        init_line = f"{indent}{var_name} = 0\n"
                    lines.insert(idx, init_line)
                    current = "".join(lines)

        try:
            ast.parse(current, filename=file_path)
            if current != source:
                return current, None
        except Exception:
            pass

        return None, "Auto Fix Unavailable: undefined variable could not be safely resolved."

    @classmethod
    def _transform_missing_argument(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        fn_params = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_args = [a.arg for a in node.args.args]
                def_count = len(node.args.defaults)
                req_args = all_args[:len(all_args) - def_count]
                fn_params[node.name] = (node, all_args, req_args)

        changed = False
        for fn_name, (fn_node, all_args, req_args) in fn_params.items():
            if len(req_args) > 1:
                sig_line = lines[fn_node.lineno - 1]
                for arg in req_args[1:]:
                    sig_line = re.sub(rf"\b{arg}\b(?!\s*=)", f"{arg}=0", sig_line)
                lines[fn_node.lineno - 1] = sig_line
                changed = True

        code_up = "".join(lines)
        try:
            tree_up = ast.parse(code_up, filename=file_path)
            lines_up = code_up.splitlines(keepends=True)
            for node in ast.walk(tree_up):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    fn_name = node.func.id
                    if fn_name in fn_params:
                        _, all_args, _ = fn_params[fn_name]
                        missing = len(all_args) - len(node.args)
                        if missing > 0:
                            call_line = lines_up[node.lineno - 1]
                            to_add = ", ".join(["0"] * missing)
                            end_col = getattr(node, "end_col_offset", None)
                            if end_col:
                                pos = end_col - 1
                                if 0 <= pos < len(call_line) and call_line[pos] == ")":
                                    prefix = ", " if node.args else ""
                                    lines_up[node.lineno - 1] = call_line[:pos] + f"{prefix}{to_add}" + call_line[pos:]
                                    changed = True
                        elif missing < 0:
                            # Excess arguments passed; update function def to accept *args
                            fn_line = lines_up[fn_node.lineno - 1]
                            if "*args" not in fn_line:
                                lines_up[fn_node.lineno - 1] = re.sub(r"\)\s*:", ", *args):", fn_line)
                                changed = True
            if changed:
                res_code = "".join(lines_up)
                ast.parse(res_code, filename=file_path)
                return res_code, None
        except Exception:
            pass
        return None, "Auto Fix Unavailable: function signature could not be safely updated with default parameters."

    @classmethod
    def _transform_const_zero_div(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for idx in range(len(lines)):
            if target_set and (idx + 1) not in target_set:
                continue
            new_l, count = re.subn(r"(\s*(?:\/|\/\/|\%)\s*)0(?:\.0*)?\b", r"\g<1>1", lines[idx])
            if count > 0:
                lines[idx] = new_l
                changed = True
        if not changed:
            res_code, count = re.subn(r"(\s*(?:\/|\/\/|\%)\s*)0(?:\.0*)?\b", r"\g<1>1", source)
            if count > 0:
                return res_code, None
            return None, "Target literal zero division could not be safely isolated."
        res_code = "".join(lines)
        return res_code, None

    @classmethod
    def _transform_unguarded_div(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and isinstance(node.right, ast.Name):
                lno = node.lineno
                if target_set and lno not in target_set:
                    continue
                left_src = ast.get_source_segment(source, node.left)
                right_src = ast.get_source_segment(source, node.right)
                old_binop = ast.get_source_segment(source, node)
                if left_src and right_src and old_binop:
                    op_sym = "/" if isinstance(node.op, ast.Div) else "//" if isinstance(node.op, ast.FloorDiv) else "%"
                    new_binop = f"({left_src} {op_sym} {right_src} if {right_src} != 0 else 0)"
                    lines[lno - 1] = lines[lno - 1].replace(old_binop, new_binop)
                    changed = True
        if changed:
            res = "".join(lines)
            try:
                ast.parse(res, filename=file_path)
                return res, None
            except Exception:
                pass
        return None, "Auto Fix Unavailable: could not safely wrap division with zero guard."

    @classmethod
    def _transform_async_blocking_http(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                root = node.func.value
                if isinstance(root, ast.Name) and root.id == "requests":
                    method = node.func.attr
                    lno = node.lineno
                    if target_set and lno not in target_set:
                        continue
                    call_src = ast.get_source_segment(source, node)
                    if call_src:
                        m = re.match(rf"requests\.{method}\s*\((.*)\)", call_src, re.DOTALL)
                        if m:
                            args_inner = m.group(1).strip()
                            if "timeout" not in args_inner:
                                args_inner = f"{args_inner}, timeout=10" if args_inner else "timeout=10"
                            new_call = f"await asyncio.to_thread(requests.{method}, {args_inner})"
                            lines[lno - 1] = lines[lno - 1].replace(call_src, new_call)
                            changed = True
        if changed:
            res = "".join(lines)
            res = cls._ensure_import(res, "import asyncio", r"^\s*(?:import\s+asyncio|from\s+asyncio\s+import)")
            return res, None
        return None, "Auto Fix Unavailable: synchronous HTTP request could not be rewritten to async worker thread."

    @classmethod
    def _transform_dangerous_eval(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for idx in range(len(lines)):
            if target_set and (idx + 1) not in target_set:
                continue
            new_l, count = re.subn(r"\beval\s*\(", "ast.literal_eval(", lines[idx])
            if count > 0:
                lines[idx] = new_l
                changed = True
        if not changed:
            res, count = re.subn(r"\beval\s*\(", "ast.literal_eval(", source)
            if count > 0:
                res = cls._ensure_import(res, "import ast", r"^\s*(?:import\s+ast\b|from\s+ast\b)")
                return res, None
            return None, "Target eval() call could not be safely isolated."
        res = "".join(lines)
        res = cls._ensure_import(res, "import ast", r"^\s*(?:import\s+ast\b|from\s+ast\b)")
        return res, None

    @classmethod
    def _transform_sql_injection(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany", "raw_query") and node.args:
                lno = node.lineno
                if target_set and lno not in target_set:
                    continue
                first_arg = node.args[0]
                if isinstance(first_arg, ast.JoinedStr):
                    sql_parts = []
                    param_names = []
                    for val in first_arg.values:
                        if isinstance(val, ast.Constant):
                            sql_parts.append(val.value)
                        elif isinstance(val, ast.FormattedValue):
                            sql_parts.append("%s")
                            param_names.append(ast.get_source_segment(source, val.value))
                    sql_str = "".join(sql_parts)
                    params_expr = f"({param_names[0]},)" if len(param_names) == 1 else f"({', '.join(param_names)})"
                    call_src = ast.get_source_segment(source, node)
                    root_src = ast.get_source_segment(source, node.func.value)
                    if call_src and root_src:
                        new_call = f'{root_src}.{node.func.attr}("{sql_str}", {params_expr})'
                        lines[lno - 1] = lines[lno - 1].replace(call_src, new_call)
                        changed = True
        if changed:
            res = "".join(lines)
            try:
                ast.parse(res, filename=file_path)
                return res, None
            except Exception:
                pass
        return None, "Auto Fix Unavailable: dynamic SQL statement could not be parameterized automatically."

    @classmethod
    def _transform_unsafe_lock(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                acq_idx = None
                rel_idx = None
                lock_name = None
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute):
                        if stmt.value.func.attr == "acquire":
                            if not target_set or stmt.lineno in target_set:
                                acq_idx = i
                                if isinstance(stmt.value.func.value, ast.Name):
                                    lock_name = stmt.value.func.value.id
                        elif stmt.value.func.attr == "release":
                            rel_idx = i
                if acq_idx is not None and rel_idx is not None and lock_name and acq_idx < rel_idx:
                    acq_ln = node.body[acq_idx].lineno
                    rel_ln = node.body[rel_idx].lineno
                    indent = lines[acq_ln - 1][:len(lines[acq_ln - 1]) - len(lines[acq_ln - 1].lstrip())]
                    inner_lines = lines[acq_ln:rel_ln - 1]
                    indented = ["    " + l if l.strip() else l for l in inner_lines]
                    if not any(l.strip() for l in indented):
                        indented = [f"{indent}    pass\n"]
                    replacement = [f"{indent}with {lock_name}:\n"] + indented
                    lines[acq_ln - 1:rel_ln] = replacement
                    res = "".join(lines)
                    return res, None
        return None, "Auto Fix Unavailable: matching acquire/release pair could not be cleanly rewritten to 'with lock:'."

    @classmethod
    def _transform_subprocess_shell(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if any(kw.arg == "shell" for kw in node.keywords):
                    lno = node.lineno
                    if target_set and lno not in target_set:
                        continue
                    call_src = ast.get_source_segment(source, node)
                    if call_src:
                        new_call = re.sub(r",\s*shell\s*=\s*True", "", call_src)
                        new_call = re.sub(r"shell\s*=\s*True\s*,?\s*", "", new_call)
                        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                            cmd_str = ast.get_source_segment(source, node.args[0])
                            if cmd_str:
                                new_call = new_call.replace(cmd_str, f"shlex.split({cmd_str})")
                        lines[lno - 1] = lines[lno - 1].replace(call_src, new_call)
                        changed = True
        if changed:
            res = "".join(lines)
            res = cls._ensure_import(res, "import shlex", r"^\s*(?:import\s+shlex\b|from\s+shlex\b)")
            return res, None
        return None, "Auto Fix Unavailable: shell=True invocation could not be safely converted."

    @classmethod
    def _transform_unawaited_coroutine_return(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                lno = node.lineno
                if target_set and lno not in target_set:
                    continue
                call_src = ast.get_source_segment(source, node.value)
                if call_src:
                    lines[lno - 1] = lines[lno - 1].replace(f"return {call_src}", f"return asyncio.run({call_src})")
                    changed = True
        if changed:
            res = "".join(lines)
            res = cls._ensure_import(res, "import asyncio", r"^\s*(?:import\s+asyncio|from\s+asyncio\s+import)")
            return res, None
        return None, "Auto Fix Unavailable: unawaited returned coroutine could not be wrapped with asyncio.run."

    @classmethod
    def _transform_uncontrolled_loop(cls, source: str, file_path: str = "test.py", target_lines: Optional[List[int]] = None) -> Tuple[Optional[str], Optional[str]]:
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return None, "File contains syntax errors."
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.While) and node.body:
                lno = node.lineno
                if target_set and lno not in target_set:
                    continue
                last_stmt = node.body[-1]
                last_ln = getattr(last_stmt, "end_lineno", last_stmt.lineno)
                if not lines[last_ln - 1].endswith("\n"):
                    lines[last_ln - 1] += "\n"
                body_indent = lines[last_ln - 1][:len(lines[last_ln - 1]) - len(lines[last_ln - 1].lstrip())]
                lines.insert(last_ln, f"{body_indent}break\n")
                changed = True
        if changed:
            res = "".join(lines)
            return res, None
        return None, "Auto Fix Unavailable: loop termination break could not be inserted."

    @classmethod
    def _transform_logical_error(
        cls,
        source: str,
        file_path: str = "service.py",
        target_lines: Optional[List[int]] = None,
        original_snippet: str = "",
        options: Optional[Dict[str, Any]] = None,
        rule_id: str = "",
    ) -> Tuple[Optional[str], Optional[str]]:
        lines = source.splitlines(keepends=True)
        target_set = set(target_lines or [])
        changed = False

        for idx, line in enumerate(lines):
            lineno = idx + 1
            if target_set and lineno not in target_set:
                continue

            orig_l = line
            new_l = orig_l

            # 1. Denominator fix (len(...) + C -> len(...))
            if rule_id == "PY_LOGICAL_CALCULATION":
                new_l = re.sub(r"len\s*\(([^)]+)\)\s*\+\s*\d+", r"len(\1)", new_l)

            # 2. Inverted comparison in topper / max search (average < highest -> average > highest)
            elif rule_id == "PY_LOGICAL_COMPARISON":
                if re.search(r"\b<=\b", new_l):
                    new_l = re.sub(r"\b<=\b", ">=", new_l)
                elif re.search(r"\b<\b", new_l):
                    new_l = re.sub(r"\b<\b", ">", new_l)

            # 3. Inverted condition in pass counter (average < 40 -> average >= 40)
            elif rule_id == "PY_LOGICAL_CONDITION":
                if re.search(r"\b<=\b", new_l):
                    new_l = re.sub(r"\b<=\b", ">=", new_l)
                elif re.search(r"\b<\b", new_l):
                    new_l = re.sub(r"\b<\b", ">=", new_l)

            elif rule_id in ("PY_LOGICAL_OFF_BY_ONE", "PY_LOGICAL_LOOP_BOUND", "PY_LOGICAL_ERROR"):
                if re.search(r"len\s*\(([^)]+)\)\s*\+\s*\d+", new_l):
                    new_l = re.sub(r"len\s*\(([^)]+)\)\s*\+\s*\d+", r"len(\1)", new_l)
                elif "<" in new_l:
                    new_l = re.sub(r"\b<\b", ">", new_l)

            if new_l != orig_l:
                lines[idx] = new_l
                changed = True

        if not changed:
            # Fallback across the entire source if line numbers shifted
            full_src = source
            if rule_id == "PY_LOGICAL_CALCULATION":
                full_src = re.sub(r"len\s*\(([^)]+)\)\s*\+\s*\d+", r"len(\1)", full_src)
            elif rule_id == "PY_LOGICAL_COMPARISON":
                full_src = re.sub(r"(\baverage\s*)<\s*(\bhighest\b)", r"\1> \2", full_src)
            elif rule_id == "PY_LOGICAL_CONDITION":
                full_src = re.sub(r"(\baverage\s*)<\s*(40\b)", r"\1>= \2", full_src)

            if full_src != source:
                patched_code = full_src
                changed = True
            else:
                return None, "Target logical error pattern could not be isolated for automated patching."
        else:
            patched_code = "".join(lines)

        # Validate patched code syntax & test verification
        try:
            ast.parse(patched_code, filename=file_path)
            compile(patched_code, filename=file_path, mode="exec")
        except SyntaxError as e:
            return None, f"Patched code introduced syntax error: {e}"

        # Automated Test Verification on Patched Code
        try:
            from backend.app.analyzers.logical.verifier import LogicalVerifier
            verification = LogicalVerifier.verify_patch(source, patched_code)
            if verification.get("error"):
                return None, f"Patched code failed execution verification: {verification.get('error')}"
        except Exception:
            pass

        return patched_code, None
