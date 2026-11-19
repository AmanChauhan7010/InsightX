import ast
import re
import json
import shutil
import subprocess
import builtins
from typing import List, Dict, Any, Optional, Set, Tuple
from backend.app.services.ingestion import IngestionService
from backend.app.services.scoring import EvidenceCategory, SeverityPolicy


SCHEDULING_FUNCS = {
    "create_task",
    "ensure_future",
    "gather",
    "wait",
    "wait_for",
    "shield",
    "run",
    "run_until_complete",
    "as_completed",
    "add_task",
    "start_soon",
}

KNOWN_ASYNC_STDLIB = {
    "asyncio.sleep",
    "asyncio.open_connection",
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
    "asyncio.start_server",
}

BACKOFF_OR_SLEEP_NAMES = {"sleep", "backoff", "wait"}

LEGITIMATE_LOOP_BLOCKING_CALLS = {
    "sleep",
    "wait",
    "accept",
    "recv",
    "recvfrom",
    "get",
    "poll",
    "select",
    "input",
    "readline",
    "read",
    "serve_forever",
    "run_forever",
    "consume",
    "pop",
}

LOGGING_CALL_NAMES = {
    "debug",
    "info",
    "warning",
    "warn",
    "error",
    "exception",
    "critical",
    "log",
    "print",
}

SECRET_VAR_RE = re.compile(
    r"^(?:.*_)?(api_key|password|passwd|secret_key|auth_token|access_token|private_key|api_token|jwt_secret)$",
    re.IGNORECASE,
)


def _annotation_contains_coroutine(ann: Optional[ast.AST]) -> bool:
    if ann is None:
        return False
    for node in ast.walk(ann):
        if isinstance(node, ast.Name) and node.id in ("Coroutine", "Awaitable", "Future", "Task"):
            return True
        if isinstance(node, ast.Attribute) and node.attr in ("Coroutine", "Awaitable", "Future", "Task"):
            return True
    return False


def _call_name_parts(call: ast.Call) -> Tuple[str, str]:
    """Returns (root_or_obj_name, attr_or_func_name)."""
    if isinstance(call.func, ast.Name):
        return "", call.func.id
    if isinstance(call.func, ast.Attribute):
        root = _expr_dotted_name(call.func.value)
        return root, call.func.attr
    return "", ""


def _expr_dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _iter_scope_nodes(root: ast.AST):
    """Yields AST nodes within the same function/class scope without descending into nested defs/classes."""
    stack = list(ast.iter_child_nodes(root))
    while stack:
        current = stack.pop()
        yield current
        if not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(current))


def _iter_loop_nodes(loop_node: ast.While):
    """Yields AST nodes inside a loop body without descending into nested loops or nested function/class defs."""
    stack = list(loop_node.body)
    while stack:
        current = stack.pop()
        yield current
        if not isinstance(current, (ast.While, ast.For, ast.AsyncFor, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(current))


class PythonCodeAnalyzer:
    """
    AST-driven static, control-flow, and intra-procedural data-flow analyzer for Python.
    Produces parser-accurate file/line locations, deterministic severities, and explicit
    Static Code Evidence classifications without matching hardcoded examples.
    """

    def analyze(
        self,
        code: str,
        file_path: str = "main.py",
        external_async_symbols: Optional[Dict[str, Set[str]]] = None,
    ) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        code_lines = code.splitlines()

        # 1. Parse AST and validate executable compilation
        try:
            tree = ast.parse(code, filename=file_path)
            compile(code, filename=file_path, mode="exec")
        except SyntaxError as e:
            line_no = e.lineno or 1
            snippet = code_lines[line_no - 1].strip() if 0 < line_no <= len(code_lines) else ""
            sev, rationale = SeverityPolicy.classify("PY_SYNTAX_ERROR")
            findings.append({
                "rule_id": "PY_SYNTAX_ERROR",
                "title": "Syntax Error / Parsing Failure",
                "category": "Syntax & Parsing",
                "severity": sev,
                "severity_rationale": rationale,
                "file_path": file_path,
                "line_number": line_no,
                "line_end": line_no,
                "code_snippet": snippet,
                "description": f"Code parsing failed with SyntaxError: {e.msg} at line {line_no}, col {e.offset}.",
                "evidence": f"Python ast.parse raised SyntaxError at {file_path}:{line_no}: {e.msg}",
                "evidence_category": EvidenceCategory.STATIC_CODE,
                "detection_method": "Python AST Parser (ast.parse)",
                "potential_consequences": "Application module cannot compile or start; immediate failure on import or execution.",
                "suggested_next_step": f"Fix syntax structure around line {line_no}.",
                "is_confirmed": False,
                "language": "python",
            })
            return {
                "findings": findings,
                "relationships": [],
                "functions": [],
                "async_functions": [],
                "imports": [],
                "ast_parsed": False,
            }

        # 2. Run Ruff Linter & Symbol/Scope Analysis for Undefined Names (F821)
        ruff_available = bool(shutil.which("ruff"))
        if ruff_available:
            ruff_findings = self._run_ruff(code, file_path, code_lines)
            findings.extend(ruff_findings)
        else:
            # Fallback to AST Symbol Table Scope Analysis if Ruff is not installed
            ast_undef_findings = self._check_ast_undefined_names(tree, code_lines, file_path)
            findings.extend(ast_undef_findings)

        # 4. Run multi-pass AST + control/data-flow analyzer
        visitor = PythonASTVisitor(tree, code_lines, file_path, external_async_symbols=external_async_symbols)
        visitor.run()
        findings.extend(visitor.findings)
        relationships.extend(visitor.relationships)

        # Deduplicate identical (rule_id, file_path, line_number) findings and sort deterministically
        deduped: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple[str, str, int]] = set()
        for f in sorted(findings, key=lambda x: (x.get("line_number") or 0, x.get("rule_id") or "")):
            k = (f.get("rule_id") or f.get("title", ""), f.get("file_path", ""), f.get("line_number") or 0)
            if k not in seen_keys:
                seen_keys.add(k)
                deduped.append(f)

        return {
            "findings": deduped,
            "relationships": relationships,
            "functions": visitor.discovered_functions,
            "async_functions": sorted(set(visitor.module_async_funcs.values())),
            "imports": visitor.discovered_imports,
            "ast_parsed": True,
        }

    def _run_ruff(self, code: str, file_path: str, code_lines: List[str]) -> List[Dict[str, Any]]:
        ruff_bin = shutil.which("ruff")
        if not ruff_bin:
            return []
        try:
            cmd = [ruff_bin, "check", "--output-format=json", "--isolated", "-"]
            proc = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=5)
            if not proc.stdout:
                return []
            diags = json.loads(proc.stdout)
            findings = []
            sev, rationale = SeverityPolicy.classify("PY_UNDEFINED_NAME", default_severity="High")
            for item in diags:
                code_str = item.get("code")
                if code_str == "F821":
                    loc = item.get("location", {})
                    row = loc.get("row", 1)
                    col = loc.get("column", 1)
                    msg = item.get("message", "")
                    snippet = code_lines[row - 1].strip() if 0 < row <= len(code_lines) else ""
                    m_name = re.search(r"Undefined name `([^`]+)`", msg)
                    name = m_name.group(1) if m_name else "identifier"

                    if name in ("printf", "printdf", "println", "echo"):
                        suggested = f"Replace undefined '{name}(...)' with Python built-in 'print(...)', or define '{name}' before calling it."
                    else:
                        suggested = f"Define or import '{name}' before using it at line {row}."

                    findings.append({
                        "rule_id": "PY_UNDEFINED_NAME",
                        "title": f"Undefined Name '{name}'",
                        "category": "Undefined Names / Symbol Errors",
                        "severity": sev,
                        "severity_rationale": rationale,
                        "file_path": file_path,
                        "line_number": row,
                        "line_end": row,
                        "column_number": col,
                        "code_snippet": snippet,
                        "description": f"Name '{name}' is referenced but not defined or imported in this scope.",
                        "evidence": f"Ruff diagnostic F821 at {file_path}:{row}:{col}: {msg}",
                        "evidence_category": EvidenceCategory.STATIC_CODE,
                        "detection_method": "Ruff Linter & AST Symbol Scope Analysis (F821)",
                        "potential_consequences": f"Referencing undefined name '{name}' raises an unhandled NameError at runtime.",
                        "suggested_next_step": suggested,
                        "is_confirmed": False,
                        "language": "python",
                    })
            return findings
        except Exception:
            return []

    def _check_ast_undefined_names(self, tree: ast.Module, code_lines: List[str], file_path: str) -> List[Dict[str, Any]]:
        builtin_names = set(dir(builtins))
        builtin_names.update({"__file__", "__name__", "__doc__", "__package__", "__annotations__", "__builtins__"})
        defined_symbols = set()
        loaded_names: List[Tuple[str, int, int]] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined_symbols.add(node.name)
                for a in getattr(node.args, "posonlyargs", []):
                    defined_symbols.add(a.arg)
                for a in node.args.args:
                    defined_symbols.add(a.arg)
                for a in getattr(node.args, "kwonlyargs", []):
                    defined_symbols.add(a.arg)
                if node.args.vararg:
                    defined_symbols.add(node.args.vararg.arg)
                if node.args.kwarg:
                    defined_symbols.add(node.args.kwarg.arg)
            elif isinstance(node, ast.ClassDef):
                defined_symbols.add(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined_symbols.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined_symbols.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, (ast.Store, ast.Param)):
                    defined_symbols.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    loaded_names.append((node.id, getattr(node, "lineno", 1), getattr(node, "col_offset", 0)))
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for gen in node.generators:
                    if isinstance(gen.target, ast.Name):
                        defined_symbols.add(gen.target.id)
            elif isinstance(node, ast.ExceptHandler):
                if node.name:
                    defined_symbols.add(node.name)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                if isinstance(node.target, ast.Name):
                    defined_symbols.add(node.target.id)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if isinstance(item.optional_vars, ast.Name):
                        defined_symbols.add(item.optional_vars.id)

        findings = []
        sev, rationale = SeverityPolicy.classify("PY_UNDEFINED_NAME", default_severity="High")
        for name, ln, col in loaded_names:
            if name not in builtin_names and name not in defined_symbols:
                snippet = code_lines[ln - 1].strip() if 0 < ln <= len(code_lines) else ""
                if name in ("printf", "printdf", "println", "echo"):
                    suggested = f"Replace undefined '{name}(...)' with Python built-in 'print(...)', or define '{name}' before calling it."
                else:
                    suggested = f"Define or import '{name}' before using it at line {ln}."
                findings.append({
                    "rule_id": "PY_UNDEFINED_NAME",
                    "title": f"Undefined Name '{name}'",
                    "category": "Undefined Names / Symbol Errors",
                    "severity": sev,
                    "severity_rationale": rationale,
                    "file_path": file_path,
                    "line_number": ln,
                    "line_end": ln,
                    "column_number": col,
                    "code_snippet": snippet,
                    "description": f"Name '{name}' is referenced but not defined or imported in this scope.",
                    "evidence": f"AST symbol resolution at {file_path}:{ln}:{col}: '{name}' is not in scope or builtins.",
                    "evidence_category": EvidenceCategory.STATIC_CODE,
                    "detection_method": "Python AST Symbol Table & Scope Resolution",
                    "potential_consequences": f"Referencing undefined name '{name}' raises an unhandled NameError at runtime.",
                    "suggested_next_step": suggested,
                    "is_confirmed": False,
                    "language": "python",
                })
        return findings


class PythonASTVisitor(ast.NodeVisitor):
    """Multi-pass AST visitor with symbol tables, alias tracking, parent pointers, and control/data-flow checks."""

    def __init__(
        self,
        tree: ast.Module,
        code_lines: List[str],
        file_path: str,
        external_async_symbols: Optional[Dict[str, Set[str]]] = None,
    ):
        self.tree = tree
        self.code_lines = code_lines
        self.file_path = file_path
        self.external_async_symbols = external_async_symbols or {}

        self.findings: List[Dict[str, Any]] = []
        self.relationships: List[Dict[str, Any]] = []
        self.discovered_functions: List[str] = []
        self.discovered_imports: List[str] = []

        # Parent pointers & symbol tables populated in pass 1
        self.parent_map: Dict[ast.AST, ast.AST] = {}
        self.imported_aliases: Dict[str, str] = {}
        self.module_async_funcs: Dict[str, str] = {}  # local_or_alias_name -> canonical_async_name
        self.class_async_methods: Dict[str, Set[str]] = {}
        self.module_var_classes: Dict[str, str] = {}  # var_name -> ClassName
        self.module_global_collections: Dict[str, int] = {}
        self.bounded_collections: Set[str] = set()
        self._reported_unbounded_collections: Set[str] = set()
        self.local_function_signatures: Dict[str, Tuple[int, int, List[str], List[str], bool, bool, int]] = {}

        # Dynamic scope stacks during pass 2
        self.current_function: Optional[str] = None
        self.current_class: Optional[str] = None
        self.in_async: bool = False
        self.async_scope_stack: List[Dict[str, str]] = []  # stack of {name -> canonical_async_name}
        self.var_class_stack: List[Dict[str, str]] = []    # stack of {var_name -> ClassName}
        self.current_func_node: Optional[ast.AST] = None
        self.current_scope_awaited_vars: Set[str] = set()
        self.current_scope_local_non_async_names: Set[str] = set()

    def run(self) -> None:
        self._build_parent_map()
        self._collect_module_symbols()
        self.async_scope_stack = [dict(self.module_async_funcs)]
        self.var_class_stack = [dict(self.module_var_classes)]
        self.current_scope_awaited_vars = self._collect_awaited_or_scheduled_vars(self.tree)
        self.visit(self.tree)

    # ------------------------------------------------------------------
    # Pass 1: Parent Map & Symbol / Alias / Module-Level Pre-Scan
    # ------------------------------------------------------------------

    def _build_parent_map(self) -> None:
        for parent in ast.walk(self.tree):
            for child in ast.iter_child_nodes(parent):
                self.parent_map[child] = parent

    def _collect_module_symbols(self) -> None:
        # 1a. Collect top-level imports, async functions, classes, and global collections
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    local = alias.asname or alias.name.split(".")[0]
                    self.imported_aliases[local] = alias.name
            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                mod_stem = mod.split(".")[-1] if mod else ""
                for alias in stmt.names:
                    local = alias.asname or alias.name
                    self.imported_aliases[local] = f"{mod}.{alias.name}" if mod else alias.name
                    # Cross-file async symbol import resolution (when multi-file project uploaded)
                    if mod in self.external_async_symbols and alias.name in self.external_async_symbols[mod]:
                        self.module_async_funcs[local] = f"{mod}.{alias.name}"
                    elif mod_stem in self.external_async_symbols and alias.name in self.external_async_symbols[mod_stem]:
                        self.module_async_funcs[local] = f"{mod_stem}.{alias.name}"
            elif isinstance(stmt, ast.AsyncFunctionDef):
                self.module_async_funcs[stmt.name] = stmt.name
            elif isinstance(stmt, ast.ClassDef):
                methods: Set[str] = set()
                for item in stmt.body:
                    if isinstance(item, ast.AsyncFunctionDef):
                        methods.add(item.name)
                if methods:
                    self.class_async_methods[stmt.name] = methods
            elif isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, (ast.List, ast.Dict, ast.Set)):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            self.module_global_collections[target.id] = stmt.lineno
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                if isinstance(stmt.value, (ast.List, ast.Dict, ast.Set)) and isinstance(stmt.target, ast.Name):
                    self.module_global_collections[stmt.target.id] = stmt.lineno

        # 1b. Collect module-level async aliases (e.g. `fetcher = retrieve_record`) & class instances (`store = Store()`)
        self._collect_scope_aliases_and_types(
            self.tree,
            async_map=self.module_async_funcs,
            var_class_map=self.module_var_classes,
            enclosing_asyncs={},
            enclosing_var_classes={},
        )

        # 1c. Collect local function signatures for argument count validation
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                pos_args = [a.arg for a in getattr(node.args, "posonlyargs", [])] + [a.arg for a in node.args.args]
                num_defaults = len(node.args.defaults)
                num_req = len(pos_args) - num_defaults
                req_names = pos_args[:num_req]
                has_vararg = bool(node.args.vararg)
                has_kwarg = bool(node.args.kwarg)
                self.local_function_signatures[node.name] = (
                    num_req,
                    len(pos_args),
                    pos_args,
                    req_names,
                    has_vararg,
                    has_kwarg,
                    node.lineno,
                )

        # 2. Detect whether any module-level collection has eviction / bounds anywhere in the module
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in self.module_global_collections:
                    if node.func.attr in ("pop", "popleft", "clear", "remove", "discard"):
                        self.bounded_collections.add(node.func.value.id)
            elif isinstance(node, ast.Delete):
                for t in node.targets:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                        self.bounded_collections.add(t.value.id)
                    elif isinstance(t, ast.Name):
                        self.bounded_collections.add(t.id)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in self.module_global_collections:
                        if isinstance(node.value, ast.Subscript) and isinstance(node.value.slice, ast.Slice):
                            self.bounded_collections.add(t.id)
                    elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and isinstance(t.slice, ast.Slice):
                        self.bounded_collections.add(t.value.id)

    def _collect_scope_aliases_and_types(
        self,
        scope_node: ast.AST,
        async_map: Dict[str, str],
        var_class_map: Dict[str, str],
        enclosing_asyncs: Dict[str, str],
        enclosing_var_classes: Dict[str, str],
        non_async_shadow: Optional[Set[str]] = None,
    ) -> None:
        """
        Tracks local async function aliases (e.g. `fn = retrieve_record`, `alias = fn`,
        `m = self.async_method`) and class instantiations (`svc = MyService()`).
        """
        # Iterate to fixed point (max 3 passes) to resolve chained aliases like `a = async_fn; b = a`
        for _ in range(3):
            changed = False
            combined_async = {**enclosing_asyncs, **async_map}
            combined_classes = {**enclosing_var_classes, **var_class_map}

            for stmt in _iter_scope_nodes(scope_node):
                val = None
                targets: List[str] = []
                if isinstance(stmt, ast.Assign):
                    val = stmt.value
                    targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                    val = stmt.value
                    targets = [stmt.target.id] if isinstance(stmt.target, ast.Name) else []
                if not targets or val is None:
                    continue

                # Case A: Alias to a known async function (`alias = retrieve_record`)
                if isinstance(val, ast.Name) and val.id in combined_async:
                    canonical = combined_async[val.id]
                    for tname in targets:
                        if async_map.get(tname) != canonical:
                            async_map[tname] = canonical
                            if non_async_shadow and tname in non_async_shadow:
                                non_async_shadow.discard(tname)
                            changed = True
                # Case B: Alias to an async method (`fn = self.pull_order` or `fn = store.pull_order`)
                elif isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name):
                    obj = val.value.id
                    cls_name = None
                    if obj in ("self", "cls") and self.current_class:
                        cls_name = self.current_class
                    elif obj in combined_classes:
                        cls_name = combined_classes[obj]
                    elif obj in self.class_async_methods:
                        cls_name = obj
                    if cls_name and val.attr in self.class_async_methods.get(cls_name, set()):
                        canonical = f"{cls_name}.{val.attr}"
                        for tname in targets:
                            if async_map.get(tname) != canonical:
                                async_map[tname] = canonical
                                if non_async_shadow and tname in non_async_shadow:
                                    non_async_shadow.discard(tname)
                                changed = True
                # Case C: Class instantiation (`store = RecordStore()`)
                elif isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                    if val.func.id in self.class_async_methods:
                        for tname in targets:
                            if var_class_map.get(tname) != val.func.id:
                                var_class_map[tname] = val.func.id
                                changed = True
                # Case D: Rebinding an outer async name to a non-async value
                else:
                    if non_async_shadow is not None:
                        for tname in targets:
                            if tname not in async_map and tname in enclosing_asyncs:
                                non_async_shadow.add(tname)
            if not changed:
                break

    # ------------------------------------------------------------------
    # Helpers: Source Snippets & Finding Builder
    # ------------------------------------------------------------------

    def _snippet(self, start_line: int, end_line: Optional[int] = None, max_lines: int = 1) -> str:
        if not self.code_lines or start_line < 1:
            return ""
        start_idx = max(0, start_line - 1)
        last_line = end_line if end_line and end_line >= start_line else start_line
        end_idx = min(len(self.code_lines), start_idx + max_lines, last_line)
        selected = self.code_lines[start_idx:end_idx]
        if len(selected) == 1:
            return selected[0].strip()
        non_empty = [l for l in selected if l.strip()]
        min_indent = min((len(l) - len(l.lstrip()) for l in non_empty), default=0)
        return "\n".join(l[min_indent:] if len(l) >= min_indent else l for l in selected)

    def _emit_finding(
        self,
        rule_id: str,
        title: str,
        category: str,
        line_number: int,
        line_end: Optional[int],
        code_snippet: str,
        description: str,
        evidence: str,
        detection_method: str,
        potential_consequences: str,
        suggested_next_step: str,
        default_severity: str = "Medium",
        context_note: str = "",
    ) -> None:
        severity, severity_rationale = SeverityPolicy.classify(
            rule_id, default_severity=default_severity, context_note=context_note
        )
        self.findings.append({
            "rule_id": rule_id,
            "title": title,
            "category": category,
            "severity": severity,
            "severity_rationale": severity_rationale,
            "file_path": self.file_path,
            "line_number": line_number,
            "line_end": line_end or line_number,
            "code_snippet": code_snippet,
            "description": description,
            "evidence": evidence,
            "evidence_category": EvidenceCategory.STATIC_CODE,
            "detection_method": detection_method,
            "potential_consequences": potential_consequences,
            "suggested_next_step": suggested_next_step,
            "is_confirmed": False,
            "language": "python",
        })

    def _resolve_canonical_call(self, node: ast.Call) -> str:
        """Resolves call target against import aliases, e.g. 't.sleep' -> 'time.sleep'."""
        root, attr = _call_name_parts(node)
        if not root:
            return self.imported_aliases.get(attr, attr)
        parts = root.split(".")
        resolved_head = self.imported_aliases.get(parts[0], parts[0])
        rest = ".".join(parts[1:] + [attr])
        return f"{resolved_head}.{rest}"

    def _is_inside_await(self, node: ast.AST) -> bool:
        return isinstance(self.parent_map.get(node), ast.Await)

    def _is_inside_with_context(self, node: ast.AST) -> bool:
        curr = self.parent_map.get(node)
        while curr is not None:
            if isinstance(curr, ast.withitem):
                return True
            if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                return False
            curr = self.parent_map.get(curr)
        return False

    def _is_inside_try_except(self, node: ast.AST, exception_names: Set[str]) -> bool:
        curr = self.parent_map.get(node)
        while curr is not None:
            if isinstance(curr, ast.Try):
                for h in curr.handlers:
                    if h.type is None:
                        return True
                    if isinstance(h.type, ast.Name) and h.type.id in exception_names:
                        return True
                    if isinstance(h.type, ast.Tuple):
                        for elt in h.type.elts:
                            if isinstance(elt, ast.Name) and elt.id in exception_names:
                                return True
            if isinstance(curr, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                return False
            curr = self.parent_map.get(curr)
        return False

    def _scope_has_finally_call(self, scope_node: Optional[ast.AST], method_name: str, after_line: int) -> bool:
        if scope_node is None:
            scope_node = self.tree
        for child in _iter_scope_nodes(scope_node):
            if isinstance(child, ast.Try) and child.finalbody:
                for fstmt in ast.walk(ast.Module(body=child.finalbody, type_ignores=[])):
                    if isinstance(fstmt, ast.Call) and isinstance(fstmt.func, ast.Attribute):
                        if fstmt.func.attr == method_name and getattr(fstmt, "lineno", 0) >= after_line:
                            return True
        return False

    # ------------------------------------------------------------------
    # Intra-Procedural Data-Flow for Coroutine Await/Scheduling Tracking
    # ------------------------------------------------------------------

    def _collect_awaited_or_scheduled_vars(self, scope_node: ast.AST) -> Set[str]:
        """Collects variable names in a scope that are awaited, iterated-and-awaited, or scheduled."""
        awaited: Set[str] = set()
        iter_loop_var_to_collection: Dict[str, str] = {}

        for node in _iter_scope_nodes(scope_node):
            if isinstance(node, ast.For):
                if isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Name):
                    iter_loop_var_to_collection[node.target.id] = node.iter.id

        for node in _iter_scope_nodes(scope_node):
            if isinstance(node, ast.Await):
                if isinstance(node.value, ast.Name):
                    awaited.add(node.value.id)
                elif isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Name):
                    awaited.add(node.value.value.id)
                elif isinstance(node.value, ast.Call):
                    self._add_scheduled_arg_names(node.value, awaited)

            elif isinstance(node, ast.Call):
                _, attr = _call_name_parts(node)
                if attr in SCHEDULING_FUNCS:
                    self._add_scheduled_arg_names(node, awaited)

        for loop_var, coll_var in iter_loop_var_to_collection.items():
            if loop_var in awaited:
                awaited.add(coll_var)

        return awaited

    def _add_scheduled_arg_names(self, call: ast.Call, out_set: Set[str]) -> None:
        for arg in call.args:
            if isinstance(arg, ast.Name):
                out_set.add(arg.id)
            elif isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
                out_set.add(arg.value.id)
            elif isinstance(arg, (ast.List, ast.Tuple, ast.Set)):
                for elt in arg.elts:
                    if isinstance(elt, ast.Name):
                        out_set.add(elt.id)
            elif isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
                for gen in arg.generators:
                    if isinstance(gen.iter, ast.Name):
                        out_set.add(gen.iter.id)
        for kw in call.keywords:
            if isinstance(kw.value, ast.Name):
                out_set.add(kw.value.id)

    def _is_passed_to_scheduler(self, call: ast.Call) -> bool:
        curr = self.parent_map.get(call)
        while isinstance(curr, (ast.Starred, ast.List, ast.Tuple, ast.Set, ast.ListComp, ast.GeneratorExp, ast.keyword)):
            curr = self.parent_map.get(curr)
        if isinstance(curr, ast.Call):
            _, attr = _call_name_parts(curr)
            if attr in SCHEDULING_FUNCS:
                return True
        return False

    def _lookup_var_class(self, var_name: str) -> Optional[str]:
        for scope_map in reversed(self.var_class_stack):
            if var_name in scope_map:
                return scope_map[var_name]
        return None

    def _is_known_async_call(self, node: ast.Call) -> Optional[str]:
        """
        Determines whether `node` definitively invokes an async function (directly,
        via an alias, via a nested scope, via `self`/`cls`, or via a known local class instance).
        Returns canonical callee name if confirmed async, otherwise None.
        """
        canonical = self._resolve_canonical_call(node)
        if canonical in KNOWN_ASYNC_STDLIB:
            return canonical

        if isinstance(node.func, ast.Name):
            fn_name = node.func.id
            if fn_name in self.current_scope_local_non_async_names:
                return None
            for scope_asyncs in reversed(self.async_scope_stack):
                if fn_name in scope_asyncs:
                    return scope_asyncs[fn_name]
            return None

        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                obj = node.func.value.id
                if obj in ("self", "cls") and self.current_class:
                    if node.func.attr in self.class_async_methods.get(self.current_class, set()):
                        return f"{self.current_class}.{node.func.attr}"
                if obj in self.class_async_methods and node.func.attr in self.class_async_methods[obj]:
                    return f"{obj}.{node.func.attr}"
                inst_cls = self._lookup_var_class(obj)
                if inst_cls and node.func.attr in self.class_async_methods.get(inst_cls, set()):
                    return f"{inst_cls}.{node.func.attr}"

        return None

    # ------------------------------------------------------------------
    # Visitors: Imports, Classes, Functions
    # ------------------------------------------------------------------

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.discovered_imports.append(alias.name)
            self.relationships.append({
                "source": self.file_path,
                "target": alias.name,
                "relationship_type": "imports",
                "details": f"Imports module {alias.name}",
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        self.discovered_imports.append(mod)
        for alias in node.names:
            self.relationships.append({
                "source": self.file_path,
                "target": f"{mod}.{alias.name}" if mod else alias.name,
                "relationship_type": "imports",
                "details": f"Imports {alias.name} from {mod}",
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def _enter_function(self, node, is_async: bool):
        prev_fn = self.current_function
        prev_async = self.in_async
        prev_fn_node = self.current_func_node
        prev_awaited = self.current_scope_awaited_vars
        prev_local_non_async = self.current_scope_local_non_async_names

        self.current_function = node.name
        self.in_async = is_async
        self.current_func_node = node
        self.discovered_functions.append(node.name)

        # Discover nested async functions anywhere in this function scope (including inside if/try)
        nested_asyncs: Dict[str, str] = {}
        local_var_classes: Dict[str, str] = {}
        local_non_async: Set[str] = {
            a.arg for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs
        }
        if node.args.vararg:
            local_non_async.add(node.args.vararg.arg)
        if node.args.kwarg:
            local_non_async.add(node.args.kwarg.arg)

        for stmt in _iter_scope_nodes(node):
            if isinstance(stmt, ast.AsyncFunctionDef):
                nested_asyncs[stmt.name] = stmt.name
            elif isinstance(stmt, ast.FunctionDef):
                local_non_async.add(stmt.name)

        # Merge enclosing asyncs and classes for alias & type resolution
        enclosing_asyncs: Dict[str, str] = {}
        for s in self.async_scope_stack:
            enclosing_asyncs.update(s)
        enclosing_classes: Dict[str, str] = {}
        for c in self.var_class_stack:
            enclosing_classes.update(c)

        self._collect_scope_aliases_and_types(
            node,
            async_map=nested_asyncs,
            var_class_map=local_var_classes,
            enclosing_asyncs=enclosing_asyncs,
            enclosing_var_classes=enclosing_classes,
            non_async_shadow=local_non_async,
        )

        self.async_scope_stack.append(nested_asyncs)
        self.var_class_stack.append(local_var_classes)
        self.current_scope_local_non_async_names = local_non_async
        self.current_scope_awaited_vars = self._collect_awaited_or_scheduled_vars(node)

        self._inspect_function_semantics(node)
        self.generic_visit(node)

        self.async_scope_stack.pop()
        self.var_class_stack.pop()
        self.current_function = prev_fn
        self.in_async = prev_async
        self.current_func_node = prev_fn_node
        self.current_scope_awaited_vars = prev_awaited
        self.current_scope_local_non_async_names = prev_local_non_async

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._enter_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._enter_function(node, is_async=True)

    def _inspect_function_semantics(self, node) -> None:
        # 1. Mutable Default Arguments
        for idx, arg in enumerate(node.args.defaults):
            if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                arg_name = "param"
                param_idx = len(node.args.args) - len(node.args.defaults) + idx
                if 0 <= param_idx < len(node.args.args):
                    arg_name = node.args.args[param_idx].arg

                self._emit_finding(
                    rule_id="PY_MUTABLE_DEFAULT",
                    title="Mutable Default Argument in Function Definition",
                    category="State Retention / Memory",
                    line_number=node.lineno,
                    line_end=node.lineno,
                    code_snippet=self._snippet(node.lineno),
                    description=(
                        f"Parameter '{arg_name}' in function '{node.name}' uses a mutable default container "
                        f"({type(arg).__name__}). Default arguments in Python are evaluated once at definition time, "
                        "persisting mutated state across subsequent calls."
                    ),
                    evidence=f"AST {type(node).__name__} '{node.name}' default[{idx}] at line {node.lineno} is {type(arg).__name__}.",
                    detection_method="AST Parameter Signature Inspection",
                    potential_consequences="Unintended data leakage between requests, non-deterministic behavior, and corrupted state.",
                    suggested_next_step=f"Use '{arg_name}=None' in the signature and initialize '{arg_name} = []' (or {{}}) inside the function body.",
                )

        # 2. Arithmetic Division Zero Checks (scoped to this function)
        zero_checked_vars: Set[str] = set()
        non_zero_const_vars: Set[str] = set()

        for stmt in _iter_scope_nodes(node):
            if isinstance(stmt, ast.If):
                for child in ast.walk(stmt.test):
                    if isinstance(child, ast.Name):
                        zero_checked_vars.add(child.id)
            elif isinstance(stmt, ast.IfExp):
                for child in ast.walk(stmt.test):
                    if isinstance(child, ast.Name):
                        zero_checked_vars.add(child.id)
            elif isinstance(stmt, ast.Assert):
                for child in ast.walk(stmt.test):
                    if isinstance(child, ast.Name):
                        zero_checked_vars.add(child.id)
            elif isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, (int, float)) and stmt.value.value != 0:
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            non_zero_const_vars.add(t.id)
                elif isinstance(stmt.value, ast.Call):
                    _, cname = _call_name_parts(stmt.value)
                    if cname == "max":
                        if any(isinstance(a, ast.Constant) and isinstance(a.value, (int, float)) and a.value > 0 for a in stmt.value.args):
                            for t in stmt.targets:
                                if isinstance(t, ast.Name):
                                    non_zero_const_vars.add(t.id)

        for stmt in _iter_scope_nodes(node):
            if isinstance(stmt, ast.BinOp) and isinstance(stmt.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                line_no = getattr(stmt, "lineno", node.lineno)
                end_no = getattr(stmt, "end_lineno", line_no)
                if isinstance(stmt.right, ast.Constant) and stmt.right.value == 0:
                    self._emit_finding(
                        rule_id="PY_CONST_ZERO_DIV",
                        title="Constant Division by Zero",
                        category="Arithmetic Crash",
                        line_number=line_no,
                        line_end=end_no,
                        code_snippet=self._snippet(line_no, end_no),
                        description="Explicit division or modulo by literal zero detected. Raises ZeroDivisionError unconditionally if executed.",
                        evidence=f"AST BinOp at {self.file_path}:{line_no} has literal divisor ast.Constant(value=0).",
                        detection_method="AST Constant Folding Analysis",
                        potential_consequences="Immediate unhandled ZeroDivisionError halting transaction processing.",
                        suggested_next_step="Validate the divisor value or remove the literal zero division.",
                    )
                elif isinstance(stmt.right, ast.Name):
                    var_name = stmt.right.id
                    if (
                        var_name not in zero_checked_vars
                        and var_name not in non_zero_const_vars
                        and not self._is_inside_try_except(stmt, {"ZeroDivisionError", "ArithmeticError", "Exception"})
                    ):
                        self._emit_finding(
                            rule_id="PY_UNGUARDED_DIV",
                            title=f"Unguarded Division by Variable '{var_name}'",
                            category="Arithmetic Crash",
                            line_number=line_no,
                            line_end=end_no,
                            code_snippet=self._snippet(line_no, end_no),
                            description=(
                                f"Division operation '/ {var_name}' at line {line_no} is executed without a visible zero guard "
                                f"('if {var_name} == 0:'). If callers pass 0, Python raises ZeroDivisionError."
                            ),
                            evidence=f"Divisor variable '{var_name}' at line {line_no} lacks an intra-procedural zero-check guard.",
                            detection_method="AST Control Flow Guard Analysis",
                            potential_consequences="Unhandled ZeroDivisionError exceptions when zero values reach this calculation.",
                            suggested_next_step=f"Add a guard clause: 'if {var_name} == 0: raise ValueError(...)' before dividing.",
                        )

    # ------------------------------------------------------------------
    # Visitors: Assignments (Hardcoded Secrets)
    # ------------------------------------------------------------------

    def _check_secret_assignment(self, target_name: str, value_node: ast.AST, lineno: int, end_lineno: Optional[int]) -> None:
        if not SECRET_VAR_RE.match(target_name):
            return
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            val = value_node.value.strip()
            if len(val) >= 8 and not val.lower().startswith(("your_", "example", "placeholder", "changeme", "<", "${")):
                raw_snippet = self._snippet(lineno, end_lineno)
                masked_snippet = IngestionService.mask_credentials(raw_snippet)
                self._emit_finding(
                    rule_id="PY_HARDCODED_SECRET",
                    title="Hardcoded Credential / Secret Exposure",
                    category="Security Vulnerability",
                    line_number=lineno,
                    line_end=end_lineno or lineno,
                    code_snippet=masked_snippet,
                    description=f"Hardcoded credential literal assigned to '{target_name}'. Secrets committed in source code risk leakage.",
                    evidence=f"AST assignment to credential identifier '{target_name}' at line {lineno} uses a plaintext string literal.",
                    detection_method="AST Secret Literal Inspection",
                    potential_consequences="Credential compromise, unauthorized API access, and compliance violations.",
                    suggested_next_step="Load credentials from environment variables (os.environ.get(...)) or a secrets manager.",
                )

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_secret_assignment(target.id, node.value, node.lineno, getattr(node, "end_lineno", node.lineno))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.target, ast.Name) and node.value is not None:
            self._check_secret_assignment(node.target.id, node.value, node.lineno, getattr(node, "end_lineno", node.lineno))
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Visitors: Try / Except Handlers
    # ------------------------------------------------------------------

    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            h_start = handler.lineno
            h_end = getattr(handler, "end_lineno", h_start) or h_start
            if handler.type is None:
                self._emit_finding(
                    rule_id="PY_BARE_EXCEPT",
                    title="Bare 'except:' Clause Masks System Failures",
                    category="Error Handling Anti-Pattern",
                    line_number=h_start,
                    line_end=h_end,
                    code_snippet=self._snippet(h_start, h_end, max_lines=3),
                    description="Bare 'except:' catches KeyboardInterrupt, SystemExit, and MemoryError, preventing clean shutdown and concealing critical failures.",
                    evidence=f"AST ExceptHandler at {self.file_path}:{h_start} has type=None.",
                    detection_method="AST Exception Handler Inspection",
                    potential_consequences="Silent error suppression, corrupted state, and inability to interrupt or gracefully terminate workers.",
                    suggested_next_step="Catch explicit exception classes (e.g., 'except (ValueError, IOError) as err:') and log failures.",
                )
            elif isinstance(handler.type, ast.Name) and handler.type.id in ("Exception", "BaseException"):
                if len(handler.body) == 1 and isinstance(handler.body[0], (ast.Pass,)):
                    self._emit_finding(
                        rule_id="PY_SILENT_EXCEPT",
                        title=f"Silent Exception Suppression ('except {handler.type.id}: pass')",
                        category="Error Handling Anti-Pattern",
                        line_number=h_start,
                        line_end=h_end,
                        code_snippet=self._snippet(h_start, h_end, max_lines=3),
                        description=f"Catching '{handler.type.id}' and executing 'pass' silently discards runtime failures without logging or recovery.",
                        evidence=f"AST ExceptHandler at {self.file_path}:{h_start} catches {handler.type.id} with body [ast.Pass].",
                        detection_method="AST Exception Handler Inspection",
                        potential_consequences="Silent data or transaction failures, hidden defects, and prolonged debugging time.",
                        suggested_next_step="Log the exception with traceback ('logger.exception(...)') or catch and handle specific error types.",
                    )
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Visitors: Calls (Async Blocking, Unawaited Coroutines, Security, Resources, Timeouts, Memory)
    # ------------------------------------------------------------------

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            line_no = getattr(node, "lineno", 1)
            end_no = getattr(node, "end_lineno", line_no) or line_no
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self._emit_finding(
                    rule_id="PY_CONST_ZERO_DIV",
                    title="Constant Division by Zero",
                    category="Arithmetic Crash",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=self._snippet(line_no, end_no),
                    description="Explicit division or modulo by literal zero detected. Raises ZeroDivisionError unconditionally if executed.",
                    evidence=f"AST BinOp at {self.file_path}:{line_no} has literal divisor ast.Constant(value=0).",
                    detection_method="AST Constant Folding Analysis",
                    potential_consequences="Immediate unhandled ZeroDivisionError halting execution.",
                    suggested_next_step="Validate the divisor value or remove the literal zero division.",
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        line_no = getattr(node, "lineno", 1)
        end_no = getattr(node, "end_lineno", line_no) or line_no
        root, attr = _call_name_parts(node)
        canonical = self._resolve_canonical_call(node)
        snippet = self._snippet(line_no, end_no)

        # 0. Inter-Procedural Argument Count Validation for Local Functions
        if isinstance(node.func, ast.Name) and node.func.id in self.local_function_signatures:
            fn_name = node.func.id
            num_req, total_pos, all_args, req_args, has_vararg, has_kwarg, def_line = self.local_function_signatures[fn_name]
            passed_pos = len(node.args)
            passed_kw = {k.arg for k in node.keywords if k.arg}
            missing = [arg for idx, arg in enumerate(req_args) if idx >= passed_pos and arg not in passed_kw]
            if missing:
                self._emit_finding(
                    rule_id="PY_MISSING_ARGUMENT",
                    title=f"Missing Required Argument '{missing[0]}' in Call to '{fn_name}'",
                    category="Type & Argument Errors",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=f"Call to '{fn_name}' is missing required positional argument '{missing[0]}' (expected at least {num_req}, received {passed_pos + len(passed_kw)}).",
                    evidence=f"Function '{fn_name}' defined at line {def_line} requires argument '{missing[0]}'.",
                    detection_method="AST Inter-Procedural Signature & Call Site Validation",
                    potential_consequences=f"Calling '{fn_name}' without required argument '{missing[0]}' raises a TypeError at runtime.",
                    suggested_next_step=f"Pass the missing argument '{missing[0]}' in the call to '{fn_name}'.",
                )
            elif passed_pos > total_pos and not has_vararg:
                self._emit_finding(
                    rule_id="PY_MISSING_ARGUMENT",
                    title=f"Too Many Arguments in Call to '{fn_name}'",
                    category="Type & Argument Errors",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=f"Call to '{fn_name}' passes {passed_pos} positional arguments, but function takes at most {total_pos}.",
                    evidence=f"Function '{fn_name}' defined at line {def_line} accepts {total_pos} positional parameters.",
                    detection_method="AST Inter-Procedural Signature & Call Site Validation",
                    potential_consequences=f"Calling '{fn_name}' with too many arguments raises TypeError at runtime.",
                    suggested_next_step=f"Remove excess arguments from the call to '{fn_name}' or update the function definition.",
                )

        # 1. Record Call Relationships
        if self.current_function:
            target_call = f"{root}.{attr}" if root else attr
            if target_call:
                self.relationships.append({
                    "source": f"{self.file_path}:{self.current_function}",
                    "target": target_call,
                    "relationship_type": "calls",
                    "details": f"Function {self.current_function} calls {target_call}",
                })

        # 2. Blocking calls inside async def (only when directly in an async function, NOT nested sync def)
        if self.in_async:
            is_blocking_sleep = (
                canonical == "time.sleep"
                or (root == "time" and attr == "sleep")
                or (not root and attr == "sleep" and canonical != "asyncio.sleep" and not self._is_inside_await(node))
            )
            if is_blocking_sleep:
                self._emit_finding(
                    rule_id="PY_ASYNC_BLOCKING_SLEEP",
                    title=f"Blocking Synchronous Call in Async Function '{self.current_function}'",
                    category="Async / Event Loop Blocking",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Synchronous blocking call '{canonical or attr}()' is invoked inside 'async def {self.current_function}'. "
                        "Blocking calls stall the asyncio event loop thread and prevent concurrent coroutines from progressing."
                    ),
                    evidence=f"AST Call to '{canonical or attr}' at {self.file_path}:{line_no} inside AsyncFunctionDef '{self.current_function}'.",
                    detection_method="AST Async Context Analysis",
                    potential_consequences="Event-loop latency spikes, delayed concurrent requests, and cascading request timeouts under load.",
                    suggested_next_step="Replace 'time.sleep(...)' with 'await asyncio.sleep(...)' (and ensure 'import asyncio' is present).",
                )

            if canonical in (
                "requests.get",
                "requests.post",
                "requests.put",
                "requests.delete",
                "requests.patch",
                "requests.head",
                "requests.request",
                "urllib.request.urlopen",
            ):
                self._emit_finding(
                    rule_id="PY_ASYNC_BLOCKING_HTTP",
                    title=f"Synchronous Network Call in Async Function '{self.current_function}'",
                    category="Async / Event Loop Blocking",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Synchronous HTTP call '{canonical}()' is invoked inside 'async def {self.current_function}'. "
                        "This blocks the event loop thread until the remote network I/O completes."
                    ),
                    evidence=f"AST Call to '{canonical}' at {self.file_path}:{line_no} within AsyncFunctionDef '{self.current_function}'.",
                    detection_method="AST Async Context Analysis",
                    potential_consequences="Degraded concurrency, high P99 latency spikes, and worker starvation during slow upstream responses.",
                    suggested_next_step="Use an asynchronous HTTP client such as httpx.AsyncClient or aiohttp.ClientSession with an explicit timeout.",
                )

        # 3. Unawaited Coroutine Detection
        async_callee = self._is_known_async_call(node)
        if async_callee is not None:
            self._check_unawaited_coroutine(node, async_callee, line_no, end_no, snippet)

        # 4. Missing Timeout on HTTP requests calls
        if (root in ("requests", "http_client") or canonical.startswith("requests.")) and attr in (
            "get", "post", "put", "delete", "patch", "head", "request"
        ):
            has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
            if not has_timeout:
                call_label = f"{root}.{attr}" if root else attr
                self._emit_finding(
                    rule_id="PY_MISSING_TIMEOUT",
                    title=f"Missing Network Request Timeout ({call_label})",
                    category="Network & Resiliency",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Outbound HTTP request '{call_label}()' at line {line_no} omits an explicit 'timeout' argument. "
                        "Requests without timeouts can block indefinitely if the upstream server stalls."
                    ),
                    evidence=f"AST Call to '{call_label}' at {self.file_path}:{line_no} has no 'timeout' keyword argument.",
                    detection_method="AST Network Call Parameter Inspection",
                    potential_consequences="Socket exhaustion and worker thread hang during upstream network partitions or slow peers.",
                    suggested_next_step="Pass an explicit timeout parameter, e.g. timeout=(3.05, 10.0).",
                )

        # 5. Unsafe Lock Acquisition (.acquire() without context manager or finally release)
        if attr == "acquire" and root:
            if not self._is_inside_with_context(node) and not self._scope_has_finally_call(self.current_func_node, "release", line_no):
                self._emit_finding(
                    rule_id="PY_UNSAFE_LOCK",
                    title="Unsafe Lock Acquisition / Thread Deadlock Hazard",
                    category="Concurrency Hazard",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Mutex '{root}.acquire()' at line {line_no} is called without a 'with {root}:' context manager "
                        f"or a guaranteed 'try...finally: {root}.release()'. An unhandled exception leaves the lock held."
                    ),
                    evidence=f"AST Call '{root}.acquire()' at {self.file_path}:{line_no} lacks exception-safe release in scope.",
                    detection_method="AST Concurrency Lifecycle Analysis",
                    potential_consequences="Permanent thread deadlock and complete service stall under concurrent execution.",
                    suggested_next_step=f"Refactor to use context manager syntax: 'with {root}:'.",
                )

        # 6. Unclosed File / Connection Resource Leak
        is_resource_open = (not root and attr == "open") or attr in ("connect", "create_connection")
        if is_resource_open and not self._is_inside_with_context(node):
            if not self._scope_has_finally_call(self.current_func_node, "close", line_no):
                self._emit_finding(
                    rule_id="PY_UNCLOSED_RESOURCE",
                    title="Unclosed Resource Descriptor / Connection Leak",
                    category="Resource Management",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Resource instantiated via '{f'{root}.{attr}' if root else attr}()' at line {line_no} "
                        "is not wrapped in a context manager ('with') and has no guaranteed 'finally: close()' cleanup."
                    ),
                    evidence=f"AST Call '{f'{root}.{attr}' if root else attr}()' at {self.file_path}:{line_no} outside With/AsyncWith without finally close.",
                    detection_method="AST Resource Lifecycle Analysis",
                    potential_consequences="File descriptor exhaustion or database connection pool starvation under sustained traffic.",
                    suggested_next_step="Wrap the resource in a 'with ... as handle:' block or ensure closure in a 'try...finally' block.",
                )

        # 7. SQL Injection via f-string / string concatenation / format
        if attr in ("execute", "executemany", "raw_query") and node.args:
            first_arg = node.args[0]
            is_dynamic_sql = (
                isinstance(first_arg, ast.JoinedStr)
                or (isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Add, ast.Mod)))
                or (
                    isinstance(first_arg, ast.Call)
                    and isinstance(first_arg.func, ast.Attribute)
                    and first_arg.func.attr == "format"
                )
            )
            if is_dynamic_sql:
                self._emit_finding(
                    rule_id="PY_SQL_INJECTION",
                    title="SQL Injection Vulnerability",
                    category="Security Vulnerability",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description="Dynamic SQL query constructed via f-string interpolation, string concatenation, or .format(). Untrusted input can alter SQL syntax.",
                    evidence=f"AST Call '{f'{root}.{attr}' if root else attr}()' at {self.file_path}:{line_no} receives dynamically formatted query string ({type(first_arg).__name__}).",
                    detection_method="AST SQL Taint Inspection",
                    potential_consequences="Data exfiltration, unauthorized database mutation, or full backend compromise.",
                    suggested_next_step="Use parameterized query placeholders, e.g. cursor.execute('SELECT ... WHERE id = ?', (user_id,)).",
                )

        # 8. Dangerous eval / exec Usage
        if not root and attr in ("eval", "exec"):
            self._emit_finding(
                rule_id="PY_DANGEROUS_EVAL",
                title="Dangerous Dynamic Code Execution (eval/exec)",
                category="Security Vulnerability",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=f"Dynamic code execution via '{attr}()' at line {line_no} can execute arbitrary code if untrusted data reaches this call.",
                evidence=f"AST Call to builtin '{attr}()' at {self.file_path}:{line_no}.",
                detection_method="AST Security Primitive Inspection",
                potential_consequences="Arbitrary Python code execution with the host process's privileges if input is attacker-controlled.",
                suggested_next_step="Replace eval()/exec() with ast.literal_eval() for data parsing or an explicit dispatch dictionary.",
            )

        # 8b. Unsafe Deserialization (pickle/marshal/unsafe yaml.load)
        is_unsafe_pickle = canonical in ("pickle.loads", "pickle.load", "marshal.loads", "marshal.load")
        is_unsafe_yaml = canonical == "yaml.load" and not any(
            kw.arg == "Loader"
            and (
                (isinstance(kw.value, ast.Name) and kw.value.id in ("SafeLoader", "CSafeLoader", "BaseLoader"))
                or (isinstance(kw.value, ast.Attribute) and kw.value.attr in ("SafeLoader", "CSafeLoader", "BaseLoader"))
            )
            for kw in node.keywords
        )
        if is_unsafe_pickle or is_unsafe_yaml:
            self._emit_finding(
                rule_id="PY_UNSAFE_DESERIALIZATION",
                title=f"Potential Unsafe Deserialization ({canonical})",
                category="Security Vulnerability",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=(
                    f"Call to '{canonical}()' at line {line_no} can execute arbitrary object constructors during deserialization "
                    "if untrusted payloads are processed."
                ),
                evidence=f"AST Call to '{canonical}' at {self.file_path}:{line_no} without safe loader restriction.",
                detection_method="AST Security Primitive Inspection",
                potential_consequences="Arbitrary code execution if untrusted or tampered input reaches this deserializer.",
                suggested_next_step=(
                    "Use 'yaml.safe_load(...)' instead of 'yaml.load(...)'."
                    if is_unsafe_yaml
                    else "Prefer JSON or validated schema serialization instead of pickle/marshal for untrusted data."
                ),
            )

        # 8c. Suspicious Subprocess Shell Execution (shell=True / os.system)
        is_os_system = canonical == "os.system"
        is_subprocess_shell = (
            canonical in ("subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output")
            and any(kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in node.keywords)
        )
        if is_os_system or is_subprocess_shell:
            self._emit_finding(
                rule_id="PY_SUBPROCESS_SHELL",
                title=f"Suspicious Shell Command Execution ({canonical})",
                category="Security Vulnerability",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=(
                    f"Executing OS commands via '{canonical}' with shell interpretation at line {line_no} introduces a "
                    "command-injection risk if any dynamic or external input is interpolated into the command string."
                ),
                evidence=f"AST Call '{canonical}' at {self.file_path}:{line_no} invokes the system shell.",
                detection_method="AST Security Primitive Inspection",
                potential_consequences="Potential OS command injection if untrusted arguments reach the command string.",
                suggested_next_step="Pass commands as an explicit argument list to subprocess.run([...], shell=False) without shell interpolation.",
            )

        # 9. Potential Unbounded In-Memory Global Collection Growth
        if (
            root in self.module_global_collections
            and attr in ("append", "extend", "add", "update")
            and root not in self.bounded_collections
            and root not in self._reported_unbounded_collections
        ):
            self._reported_unbounded_collections.add(root)
            self._emit_finding(
                rule_id="PY_UNBOUNDED_COLLECTION",
                title="Potential Unbounded In-Memory Collection Growth (Memory-Growth Risk)",
                category="Memory Management",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=(
                    f"Module-level collection '{root}' (defined at line {self.module_global_collections[root]}) "
                    f"grows via '.{attr}()' at line {line_no} with no visible capacity cap, eviction, pop, or clear mechanism. "
                    "Static analysis flags this as a potential memory-growth risk rather than a proven runtime leak."
                ),
                evidence=f"Global collection '{root}' mutated by '.{attr}()' at {self.file_path}:{line_no} without bounded eviction in module.",
                detection_method="AST Global Collection Growth Analysis",
                potential_consequences="Potential progressive heap growth, increasing GC pause latency, or OOM risk in long-lived processes.",
                suggested_next_step=f"Replace '{root} = []' with 'collections.deque(maxlen=1000)' or implement TTL/LRU eviction.",
            )

        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Unawaited Coroutine Context Analysis
    # ------------------------------------------------------------------

    def _check_unawaited_coroutine(
        self,
        call: ast.Call,
        callee_name: str,
        line_no: int,
        end_no: int,
        snippet: str,
    ) -> None:
        # 1. Directly awaited -> SAFE
        if self._is_inside_await(call):
            return

        # 2. Directly passed to a valid scheduling/execution API -> SAFE
        if self._is_passed_to_scheduler(call):
            return

        parent = self.parent_map.get(call)

        # 3. Discarded standalone expression: `retrieve_record(record_id)`
        if isinstance(parent, ast.Expr):
            self._emit_finding(
                rule_id="PY_UNAWAITED_COROUTINE",
                title=f"Unawaited Coroutine Call ('{callee_name}()')",
                category="Async / Coroutine Usage",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=(
                    f"Async function '{callee_name}()' is called at line {line_no} as a standalone statement without 'await' "
                    "or task scheduling. Calling an async function returns a coroutine object that never executes unless awaited."
                ),
                evidence=f"Confirmed async function '{callee_name}' invoked in ast.Expr at {self.file_path}:{line_no} without ast.Await or scheduling API.",
                detection_method="AST Async Symbol & Data-Flow Analysis",
                potential_consequences="The coroutine body never executes (silent logic drop) and Python emits RuntimeWarning: coroutine was never awaited.",
                suggested_next_step=(
                    f"Use 'await {callee_name}(...)' inside an async function, schedule via 'asyncio.create_task({callee_name}(...))', "
                    f"or execute from synchronous entrypoints via 'asyncio.run({callee_name}(...))'."
                ),
            )
            return

        # 4. Inserted into a collection via .append / .extend / .add / .insert
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute):
            if parent.func.attr in ("append", "add", "insert", "extend") and isinstance(parent.func.value, ast.Name):
                coll_var = parent.func.value.id
                if coll_var in self.current_scope_awaited_vars:
                    return
                self._emit_finding(
                    rule_id="PY_UNAWAITED_COROUTINE",
                    title=f"Unawaited Coroutine Inserted into Collection '{coll_var}' ('{callee_name}()')",
                    category="Async / Coroutine Usage",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Calling async function '{callee_name}()' inside '{coll_var}.{parent.func.attr}(...)' at line {line_no} "
                        f"appends unexecuted coroutine objects to '{coll_var}' rather than resolved values, and '{coll_var}' is never "
                        "awaited or passed to asyncio.gather()/asyncio.wait() in this scope."
                    ),
                    evidence=f"Confirmed async call '{callee_name}()' stored in '{coll_var}' at {self.file_path}:{line_no} with no subsequent await or gather on '{coll_var}'.",
                    detection_method="AST Async Symbol & Data-Flow Analysis",
                    potential_consequences="Callers receive raw coroutine objects instead of data, causing downstream TypeError/AttributeError or silent non-execution.",
                    suggested_next_step=(
                        f"Make the enclosing function 'async def' and use 'await {callee_name}(...)' (or collect tasks and return "
                        f"'await asyncio.gather(*{coll_var})'), or run synchronously via 'asyncio.run(...)'."
                    ),
                )
                return

        # 5. Inside a list/set/dict literal or comprehension
        container_parent = parent
        while isinstance(container_parent, (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp)):
            outer = self.parent_map.get(container_parent)
            if isinstance(outer, ast.Assign):
                target_names = [t.id for t in outer.targets if isinstance(t, ast.Name)]
                if any(tn in self.current_scope_awaited_vars for tn in target_names):
                    return
                var_label = target_names[0] if target_names else "collection"
                self._emit_finding(
                    rule_id="PY_UNAWAITED_COROUTINE",
                    title=f"Unawaited Coroutine Built in Collection '{var_label}' ('{callee_name}()')",
                    category="Async / Coroutine Usage",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Async function '{callee_name}()' is evaluated inside a collection assigned to '{var_label}' at line {line_no}, "
                        f"producing coroutine objects that are never awaited or passed to asyncio.gather()/asyncio.wait()."
                    ),
                    evidence=f"Confirmed async call '{callee_name}()' inside {type(container_parent).__name__} assigned to '{var_label}' at {self.file_path}:{line_no} without subsequent await/gather.",
                    detection_method="AST Async Symbol & Data-Flow Analysis",
                    potential_consequences="Collection holds unexecuted coroutine objects instead of resolved results.",
                    suggested_next_step=f"Pass '{var_label}' to 'await asyncio.gather(*{var_label})' inside an async function, or await each call.",
                )
                return
            elif isinstance(outer, ast.Return):
                if isinstance(self.current_func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _annotation_contains_coroutine(self.current_func_node.returns):
                        return
                self._emit_finding(
                    rule_id="PY_UNAWAITED_COROUTINE",
                    title=f"Unawaited Coroutine Collection Returned ('{callee_name}()')",
                    category="Async / Coroutine Usage",
                    line_number=line_no,
                    line_end=end_no,
                    code_snippet=snippet,
                    description=(
                        f"Returning a collection containing unawaited calls to async function '{callee_name}()' at line {line_no} "
                        "returns raw coroutine objects instead of resolved results."
                    ),
                    evidence=f"Confirmed async call '{callee_name}()' returned inside {type(container_parent).__name__} at {self.file_path}:{line_no}.",
                    detection_method="AST Async Symbol & Data-Flow Analysis",
                    potential_consequences="Callers receive unexecuted coroutine objects and async work never runs.",
                    suggested_next_step=f"Await with 'return await asyncio.gather(*[{callee_name}(...) ...])' in an async function.",
                )
                return
            container_parent = outer

        # 6. Assigned to a local variable: `res = retrieve_record(1)`
        if isinstance(parent, (ast.Assign, ast.AnnAssign)):
            if isinstance(parent, ast.Assign):
                target_names = [t.id for t in parent.targets if isinstance(t, ast.Name)]
                is_subscript = any(isinstance(t, ast.Subscript) for t in parent.targets)
                sub_coll = [t.value.id for t in parent.targets if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)]
            else:
                target_names = [parent.target.id] if isinstance(parent.target, ast.Name) else []
                is_subscript = isinstance(parent.target, ast.Subscript)
                sub_coll = [parent.target.value.id] if isinstance(parent.target, ast.Subscript) and isinstance(parent.target.value, ast.Name) else []

            if any(tn in self.current_scope_awaited_vars for tn in target_names):
                return
            if is_subscript and any(sc in self.current_scope_awaited_vars for sc in sub_coll):
                return

            if target_names and isinstance(self.current_func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _annotation_contains_coroutine(self.current_func_node.returns):
                    return

            var_label = target_names[0] if target_names else (sub_coll[0] if sub_coll else "variable")
            self._emit_finding(
                rule_id="PY_UNAWAITED_COROUTINE",
                title=f"Coroutine Assigned to '{var_label}' Without Await ('{callee_name}()')",
                category="Async / Coroutine Usage",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=(
                    f"Async function '{callee_name}()' is assigned to '{var_label}' at line {line_no} without 'await', "
                    f"and '{var_label}' is neither awaited nor scheduled via asyncio APIs in this scope."
                ),
                evidence=f"Confirmed async call '{callee_name}()' assigned to '{var_label}' at {self.file_path}:{line_no} with no await/create_task/gather usage.",
                detection_method="AST Async Symbol & Data-Flow Analysis",
                potential_consequences=f"'{var_label}' holds an unexecuted coroutine object rather than the resolved return value.",
                suggested_next_step=f"Await the coroutine ('{var_label} = await {callee_name}(...)') in an async function or schedule it with asyncio.create_task().",
            )
            return

        # 7. Returned directly: `return retrieve_record(1)`
        if isinstance(parent, ast.Return):
            if isinstance(self.current_func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _annotation_contains_coroutine(self.current_func_node.returns):
                    return
                if self.in_async:
                    self._emit_finding(
                        rule_id="PY_UNAWAITED_COROUTINE",
                        title=f"Unawaited Coroutine Returned Inside Async Function ('{callee_name}()')",
                        category="Async / Coroutine Usage",
                        line_number=line_no,
                        line_end=end_no,
                        code_snippet=snippet,
                        description=(
                            f"Async function '{self.current_function}' returns '{callee_name}()' at line {line_no} without 'await'. "
                            "Awaiting the outer function will yield an unexecuted inner coroutine object."
                        ),
                        evidence=f"Confirmed async call '{callee_name}()' returned without await inside AsyncFunctionDef '{self.current_function}' at {self.file_path}:{line_no}.",
                        detection_method="AST Async Symbol & Data-Flow Analysis",
                        potential_consequences="Callers awaiting this function receive a raw coroutine object instead of its resolved result.",
                        suggested_next_step=f"Change to 'return await {callee_name}(...)'.",
                    )
                    return
                else:
                    # Synchronous function returning a coroutine:
                    # Do NOT flag intentional coroutine factories/wrappers that consistently return a coroutine.
                    # Only flag if the function has inconsistent non-coroutine return paths (e.g., returning None/dict on one branch).
                    other_returns = [
                        n for n in _iter_scope_nodes(self.current_func_node)
                        if isinstance(n, ast.Return) and n is not parent
                    ]
                    has_non_coro_return = any(
                        r.value is None or not (isinstance(r.value, ast.Call) and self._is_known_async_call(r.value))
                        for r in other_returns
                    )
                    if has_non_coro_return:
                        self._emit_finding(
                            rule_id="PY_UNAWAITED_COROUTINE_RETURN",
                            title=f"Unawaited Coroutine Returned from Synchronous Function '{self.current_function}'",
                            category="Async / Coroutine Usage",
                            line_number=line_no,
                            line_end=end_no,
                            code_snippet=snippet,
                            description=(
                                f"Synchronous function '{self.current_function}' mixes regular return values with an unawaited "
                                f"call to async function '{callee_name}()' at line {line_no}."
                            ),
                            evidence=f"Confirmed async call '{callee_name}()' returned from sync def '{self.current_function}' at {self.file_path}:{line_no} alongside non-coroutine return paths.",
                            detection_method="AST Async Symbol & Data-Flow Analysis",
                            potential_consequences="Synchronous callers expecting a resolved value will unexpectedly receive a coroutine object.",
                            suggested_next_step=(
                                f"Convert '{self.current_function}' to 'async def' and use 'return await {callee_name}(...)', "
                                f"or execute via 'asyncio.run({callee_name}(...))'."
                            ),
                        )
                    return

        # 8. Used directly as a value inside an expression
        if isinstance(parent, (ast.Subscript, ast.Attribute, ast.BinOp, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.If, ast.FormattedValue, ast.Call)):
            self._emit_finding(
                rule_id="PY_UNAWAITED_COROUTINE",
                title=f"Unawaited Coroutine Used Directly as Value ('{callee_name}()')",
                category="Async / Coroutine Usage",
                line_number=line_no,
                line_end=end_no,
                code_snippet=snippet,
                description=(
                    f"Async function '{callee_name}()' is invoked at line {line_no} without 'await' and its returned coroutine object "
                    "is immediately used as a value."
                ),
                evidence=f"Confirmed async call '{callee_name}()' passed directly to {type(parent).__name__} at {self.file_path}:{line_no} without ast.Await.",
                detection_method="AST Async Symbol & Data-Flow Analysis",
                potential_consequences="Runtime TypeError/AttributeError or incorrect truthiness evaluation on coroutine object.",
                suggested_next_step=f"Await the call ('await {callee_name}(...)') before accessing or passing its result.",
            )

    # ------------------------------------------------------------------
    # Visitors: While Loops (Infinite Retry & Uncontrolled Loop Analysis)
    # ------------------------------------------------------------------

    def _is_unbounded_while_test(self, test: ast.AST) -> bool:
        if isinstance(test, ast.Constant) and test.value in (True, 1):
            return True
        return False

    def _flag_var_unmodified_in_handlers(self, test: ast.AST, handlers: List[ast.ExceptHandler]) -> Optional[str]:
        """Detects retry loops like `while not done:` where `done` is never updated in `except`."""
        flag_name: Optional[str] = None
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not) and isinstance(test.operand, ast.Name):
            flag_name = test.operand.id
        elif isinstance(test, ast.Name):
            flag_name = test.id
        if not flag_name:
            return None
        for h in handlers:
            for n in ast.walk(h):
                if isinstance(n, ast.Assign):
                    if any(isinstance(t, ast.Name) and t.id == flag_name for t in n.targets):
                        return None
        return flag_name

    def _has_bounded_retry_guard(self, while_node: ast.While) -> bool:
        """
        Determines whether a loop has a genuine bounded retry counter
        or time/deadline exit guard that breaks/returns/raises when exhausted.
        """
        mutated_vars: Set[str] = set()
        for child in _iter_loop_nodes(while_node):
            if isinstance(child, ast.AugAssign) and isinstance(child.target, ast.Name):
                if isinstance(child.op, (ast.Add, ast.Sub)):
                    mutated_vars.add(child.target.id)
            elif isinstance(child, ast.Assign):
                if isinstance(child.value, ast.BinOp) and isinstance(child.value.op, (ast.Add, ast.Sub)):
                    for t in child.targets:
                        if isinstance(t, ast.Name):
                            mutated_vars.add(t.id)

        for child in _iter_loop_nodes(while_node):
            if isinstance(child, ast.If):
                exits_in_branch = any(
                    isinstance(n, (ast.Break, ast.Return, ast.Raise))
                    for branch in (child.body, child.orelse)
                    for stmt in branch
                    for n in _iter_scope_nodes(stmt)
                ) or any(isinstance(s, (ast.Break, ast.Return, ast.Raise)) for s in child.body + child.orelse)

                if not exits_in_branch:
                    continue

                test_names = {n.id for n in ast.walk(child.test) if isinstance(n, ast.Name)}
                if test_names & mutated_vars:
                    return True

                test_attrs = {n.attr for n in ast.walk(child.test) if isinstance(n, ast.Attribute)}
                if test_attrs & {"monotonic", "time", "perf_counter"}:
                    return True
                if any(k in name.lower() for name in test_names for k in ("deadline", "timeout", "elapsed", "max_retries", "max_attempts", "limit")):
                    return True

        return False

    def _handler_unconditionally_exits(self, handler: ast.ExceptHandler) -> bool:
        for stmt in handler.body:
            if isinstance(stmt, (ast.Raise, ast.Break, ast.Return)):
                return True
        return False

    def _handler_is_silent(self, handler: ast.ExceptHandler) -> bool:
        meaningful = []
        for stmt in handler.body:
            if isinstance(stmt, (ast.Pass, ast.Continue)):
                continue
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue
            meaningful.append(stmt)
        return len(meaningful) == 0

    def _handler_has_backoff(self, handler: ast.ExceptHandler, while_node: ast.While) -> bool:
        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                _, attr = _call_name_parts(node)
                if attr in BACKOFF_OR_SLEEP_NAMES:
                    return True
        for stmt in while_node.body:
            if not isinstance(stmt, ast.Try):
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Call):
                        _, attr = _call_name_parts(node)
                        if attr in BACKOFF_OR_SLEEP_NAMES:
                            return True
        return False

    def _handler_has_logging(self, handler: ast.ExceptHandler) -> bool:
        for node in ast.walk(handler):
            if isinstance(node, ast.Call):
                _, attr = _call_name_parts(node)
                if attr in LOGGING_CALL_NAMES:
                    return True
        return False

    def _is_broad_exception_handler(self, handler: ast.ExceptHandler) -> bool:
        if handler.type is None:
            return True
        if isinstance(handler.type, ast.Name) and handler.type.id in ("Exception", "BaseException"):
            return True
        if isinstance(handler.type, ast.Tuple):
            return any(
                isinstance(e, ast.Name) and e.id in ("Exception", "BaseException")
                for e in handler.type.elts
            )
        return False

    def visit_While(self, node: ast.While):
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line) or start_line
        is_const_true = self._is_unbounded_while_test(node.test)

        # Collect all `try` statements in this loop scope (even nested inside `if` or `with`, excluding inner loops/defs)
        loop_tries = [n for n in _iter_loop_nodes(node) if isinstance(n, ast.Try)]
        retry_flagged = False

        if loop_tries and not self._has_bounded_retry_guard(node):
            for try_stmt in loop_tries:
                non_exiting_handlers = [
                    h for h in try_stmt.handlers if not self._handler_unconditionally_exits(h)
                ]
                if not non_exiting_handlers:
                    continue

                # Applicable when `while True:` OR `while not flag:` where `flag` is untouched in except handlers
                flag_var = None if is_const_true else self._flag_var_unmodified_in_handlers(node.test, non_exiting_handlers)
                if not is_const_true and not flag_var:
                    continue

                broad_non_exiting = [h for h in non_exiting_handlers if self._is_broad_exception_handler(h)]
                silent_non_exiting = [h for h in non_exiting_handlers if self._handler_is_silent(h)]

                if broad_non_exiting:
                    any_silent = any(self._handler_is_silent(h) for h in broad_non_exiting)
                    has_backoff = any(self._handler_has_backoff(h, node) for h in broad_non_exiting)
                    has_logging = any(self._handler_has_logging(h) for h in broad_non_exiting)

                    loop_desc = "'while True' loop" if is_const_true else f"flag-controlled retry loop ('{flag_var}' unchanged on error)"
                    factors = [f"unbounded {loop_desc}", "broad exception handler without termination", "no retry attempt limit"]
                    if any_silent:
                        factors.append("silently ignored exception")
                    if not has_backoff:
                        factors.append("missing retry backoff delay")

                    snippet = self._snippet(start_line, end_line, max_lines=8)

                    if any_silent or not has_backoff:
                        self._emit_finding(
                            rule_id="PY_UNBOUNDED_RETRY",
                            title="Potential Infinite Retry Loop Without Bound or Backoff",
                            category="Resiliency / Control Flow",
                            line_number=start_line,
                            line_end=end_line,
                            code_snippet=snippet,
                            description=(
                                f"The {loop_desc} spanning lines {start_line}-{end_line} catches broad exceptions "
                                f"without a maximum retry limit ({', '.join(factors)}). Persistent failures will cause "
                                "this loop to retry indefinitely."
                            ),
                            evidence=(
                                f"AST While at {self.file_path}:{start_line}-{end_line} wraps ast.Try with broad "
                                f"ExceptHandler(s), no bounded retry counter/deadline exit, "
                                f"silent_swallow={any_silent}, has_backoff={has_backoff}, has_logging={has_logging}."
                            ),
                            detection_method="AST Loop & Exception Control-Flow Analysis",
                            potential_consequences=(
                                "Indefinite request hang, tight CPU spin or retry storm amplifying downstream outages, "
                                "and hidden persistent failures."
                            ),
                            suggested_next_step=(
                                "Enforce a bounded retry limit (e.g. 'for attempt in range(max_retries):'), add exponential "
                                "backoff ('await asyncio.sleep(2 ** attempt)' or 'time.sleep(...)'), log failures, and re-raise on exhaustion."
                            ),
                        )
                    else:
                        self._emit_finding(
                            rule_id="PY_UNBOUNDED_RETRY_INSPECT",
                            title="Unbounded Retry Loop Lacking Maximum Attempt Limit",
                            category="Resiliency / Control Flow",
                            line_number=start_line,
                            line_end=end_line,
                            code_snippet=snippet,
                            description=(
                                f"The {loop_desc} at lines {start_line}-{end_line} includes backoff and logging, "
                                "but catches broad exceptions without an explicit retry cap or termination condition. "
                                "Verify whether indefinite retrying is intentional."
                            ),
                            evidence=(
                                f"AST While at {self.file_path}:{start_line}-{end_line} has broad exception retry "
                                "with backoff/logging but no retry limit or cancellation exit."
                            ),
                            detection_method="AST Loop & Exception Control-Flow Analysis",
                            potential_consequences="Task may never terminate on permanent errors if not bounded or cancellable.",
                            suggested_next_step="Add a maximum retry count or differentiate transient vs permanent exceptions before retrying.",
                        )
                    retry_flagged = True
                    break

                # Specific exception silently swallowed inside unbounded loop with NO backoff and NO retry limit
                if is_const_true and silent_non_exiting:
                    has_backoff = any(self._handler_has_backoff(h, node) for h in silent_non_exiting)
                    if not has_backoff:
                        self._emit_finding(
                            rule_id="PY_UNBOUNDED_RETRY",
                            title="Potential Infinite Retry Loop With Swallowed Exceptions",
                            category="Resiliency / Control Flow",
                            line_number=start_line,
                            line_end=end_line,
                            code_snippet=self._snippet(start_line, end_line, max_lines=8),
                            description=(
                                f"The 'while True' loop spanning lines {start_line}-{end_line} silently ignores caught exceptions "
                                "with no retry limit and no backoff delay. Repeated errors will spin indefinitely."
                            ),
                            evidence=(
                                f"AST While(True) at {self.file_path}:{start_line}-{end_line} has silent ExceptHandler(s) "
                                "without retry counter/deadline exit or backoff."
                            ),
                            detection_method="AST Loop & Exception Control-Flow Analysis",
                            potential_consequences="Indefinite tight retry loop, CPU spin, and downstream overload.",
                            suggested_next_step="Add a maximum retry count, exponential backoff delay, structured logging, and re-raise after exhaustion.",
                        )
                        retry_flagged = True
                        break

        # Non-retry uncontrolled busy spin loop (`while True:` with zero exit/yield/await/blocking consumer)
        if is_const_true and not retry_flagged:
            has_exit_or_yield = False
            for child in _iter_scope_nodes(node):
                if isinstance(child, (ast.Break, ast.Return, ast.Raise, ast.Yield, ast.YieldFrom, ast.Await)):
                    has_exit_or_yield = True
                    break
                if isinstance(child, ast.Call):
                    _, attr = _call_name_parts(child)
                    if attr in LEGITIMATE_LOOP_BLOCKING_CALLS:
                        has_exit_or_yield = True
                        break

            if not has_exit_or_yield:
                self._emit_finding(
                    rule_id="PY_UNCONTROLLED_LOOP",
                    title="Uncontrolled Infinite Loop (while True without exit or throttle)",
                    category="Resiliency / Control Flow",
                    line_number=start_line,
                    line_end=end_line,
                    code_snippet=self._snippet(start_line, end_line, max_lines=5),
                    description=(
                        f"Loop 'while True:' at lines {start_line}-{end_line} contains no break, return, raise, yield, await, "
                        "or blocking throttle call. Once entered, it executes a tight CPU spin indefinitely."
                    ),
                    evidence=f"AST While(True) at {self.file_path}:{start_line}-{end_line} has no exit, yield, await, or throttling primitive.",
                    detection_method="AST Loop Control-Flow Analysis",
                    potential_consequences="100% CPU core pinning, worker thread lockup, and denial of service.",
                    suggested_next_step="Add a deterministic exit condition, break guard, or cooperative throttling.",
                )

        self.generic_visit(node)
