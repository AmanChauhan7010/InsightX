import os
import re
import json
import shutil
import subprocess
from typing import List, Dict, Any
from backend.app.services.ingestion import IngestionService
from backend.app.services.scoring import EvidenceCategory, SeverityPolicy


class JavaScriptCodeAnalyzer:
    """
    Static analyzer for JavaScript and TypeScript source files.
    Detects event loop blocking, security injection, credential leaks,
    missing timeouts, empty catches, prototype pollution, and dependency relationships.
    """

    def analyze(self, code: str, file_path: str = "app.js") -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        lines = code.splitlines()
        lang = "typescript" if file_path.endswith((".ts", ".tsx")) else "javascript"

        def emit(
            rule_id: str,
            title: str,
            category: str,
            line_number: int,
            line_end: int,
            code_snippet: str,
            description: str,
            evidence: str,
            detection_method: str,
            potential_consequences: str,
            suggested_next_step: str,
            default_severity: str = "Medium",
        ) -> None:
            severity, rationale = SeverityPolicy.classify(rule_id, default_severity=default_severity)
            findings.append({
                "rule_id": rule_id,
                "title": title,
                "category": category,
                "severity": severity,
                "severity_rationale": rationale,
                "file_path": file_path,
                "line_number": line_number,
                "line_end": line_end,
                "code_snippet": code_snippet,
                "description": description,
                "evidence": evidence,
                "evidence_category": EvidenceCategory.STATIC_CODE,
                "detection_method": detection_method,
                "potential_consequences": potential_consequences,
                "suggested_next_step": suggested_next_step,
                "is_confirmed": False,
                "language": lang,
            })

        # 1. External Linter & Compiler Diagnostics (ESLint & TypeScript compiler API)
        self._run_external_diagnostics(code, file_path, lines, emit)

        # 2. Syntax & structure check: basic delimiter balance
        open_braces = code.count("{") - code.count("}")
        open_parens = code.count("(") - code.count(")")

        if abs(open_braces) > 3 or abs(open_parens) > 3:
            emit(
                rule_id="JS_UNBALANCED_DELIMITERS",
                title=f"Unbalanced Syntax Delimiters ({lang.upper()})",
                category="Syntax & Parsing",
                line_number=1,
                line_end=max(1, len(lines)),
                code_snippet=lines[0].strip() if lines else "",
                description=f"File contains unbalanced structural delimiters (braces diff: {open_braces}, parens diff: {open_parens}). This will fail compilation or bundling.",
                evidence=f"Delimiter balance check in {file_path}: braces_diff={open_braces}, parens_diff={open_parens}.",
                detection_method="Static Delimiter Parser",
                potential_consequences="SyntaxError / Compilation failure on startup or bundle time.",
                suggested_next_step="Verify matching braces and parentheses in source file.",
            )

        # 2. Line-by-line inspection (skipping single-line comments)
        in_async_fn = False
        async_fn_name = ""

        for idx, line in enumerate(lines, 1):
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("//") or clean_line.startswith("*"):
                continue

            # Track async context
            if re.search(r"\basync\s+(?:function\s+([a-zA-Z0-9_]+)|\(?\w*\)?\s*=>)", clean_line):
                in_async_fn = True
                m_fn = re.search(r"async\s+function\s+([a-zA-Z0-9_]+)", clean_line)
                async_fn_name = m_fn.group(1) if m_fn else "anonymous"

            if in_async_fn and clean_line.endswith("}"):
                in_async_fn = False

            # Rule: Synchronous blocking I/O (fs.readFileSync / writeFileSync)
            if re.search(r"\bfs\.(?:readFileSync|writeFileSync|existsSync)\b", clean_line):
                emit(
                    rule_id="JS_BLOCKING_FS",
                    title="Blocking Synchronous I/O in Node.js Event Loop",
                    category="Async / Event Loop Blocking",
                    line_number=idx,
                    line_end=idx,
                    code_snippet=clean_line,
                    description=f"Synchronous file operation '{clean_line.split('(')[0]}' blocks the Node.js single-threaded event loop while disk I/O completes.",
                    evidence=f"Static match of synchronous fs method at {file_path}:{idx}.",
                    detection_method="Static Node.js Event Loop Rule",
                    potential_consequences="Latency spikes, delayed concurrent HTTP requests, and health check timeouts.",
                    suggested_next_step="Use 'await fs.promises.readFile(...)' or streaming pipelines.",
                )

            # Rule: Dangerous eval / new Function
            if re.search(r"\beval\s*\(|new\s+Function\s*\(", clean_line):
                emit(
                    rule_id="JS_DANGEROUS_EVAL",
                    title="Dynamic Code Injection via eval() / new Function()",
                    category="Security Vulnerability",
                    line_number=idx,
                    line_end=idx,
                    code_snippet=clean_line,
                    description="Dynamic execution of code strings using eval() or Function constructor creates Remote Code Execution (RCE) vulnerabilities.",
                    evidence=f"Static invocation of dynamic execution primitive at {file_path}:{idx}.",
                    detection_method="Static Security Taint Analysis",
                    potential_consequences="Arbitrary JavaScript execution within the Node.js runtime process.",
                    suggested_next_step="Replace eval() with JSON.parse() or structured logic dispatch.",
                )

            # Rule: SQL / NoSQL Injection in dynamic query concatenation
            if re.search(r"\.(?:query|raw|execute)\s*\(\s*[`'\"].*\$\{", clean_line) or re.search(
                r"\.(?:query|execute)\s*\([^,]+\s*\+", clean_line
            ):
                emit(
                    rule_id="JS_SQL_INJECTION",
                    title="SQL / Query Injection via String Concatenation",
                    category="Security Vulnerability",
                    line_number=idx,
                    line_end=idx,
                    code_snippet=clean_line,
                    description="Database query constructed via template literal interpolation (${...}) or string concatenation without parameterization.",
                    evidence=f"Unsanitized query interpolation/concatenation at {file_path}:{idx}.",
                    detection_method="Static Query Taint Analysis",
                    potential_consequences="Unauthorized data retrieval, database manipulation, or authentication bypass.",
                    suggested_next_step="Use parameterized queries, e.g. db.query('SELECT * FROM users WHERE id = $1', [userId]).",
                )

            # Rule: Hardcoded Secret / Token Exposure
            secret_match = re.search(
                r"\b(api_?key|jwt_?secret|token|private_?key|password)\s*[:=]\s*[\"']([a-zA-Z0-9_\-\.]{8,})[\"']",
                clean_line,
                re.IGNORECASE,
            )
            if secret_match:
                emit(
                    rule_id="JS_HARDCODED_SECRET",
                    title="Hardcoded Secret / Token Exposure",
                    category="Security Vulnerability",
                    line_number=idx,
                    line_end=idx,
                    code_snippet=IngestionService.mask_credentials(clean_line),
                    description=f"Plaintext secret credential '{secret_match.group(1)}' committed directly into source code.",
                    evidence=f"Static string assignment to credential variable '{secret_match.group(1)}' at {file_path}:{idx}.",
                    detection_method="Secret Pattern Inspection",
                    potential_consequences="Credential leakage, unauthorized API access, and identity spoofing.",
                    suggested_next_step="Load secret from process.env using dotenv or a secret manager.",
                )

            # Rule: Missing Request Timeout on fetch / axios
            if re.search(r"\b(?:fetch|axios\.get|axios\.post)\s*\(", clean_line):
                has_timeout = (
                    "signal" in clean_line
                    or "timeout" in clean_line
                    or any("timeout" in l for l in lines[max(0, idx - 3) : min(len(lines), idx + 3)])
                )
                if not has_timeout:
                    emit(
                        rule_id="JS_MISSING_TIMEOUT",
                        title="Unbounded HTTP Request Without Timeout (fetch / axios)",
                        category="Network & Resiliency",
                        line_number=idx,
                        line_end=idx,
                        code_snippet=clean_line,
                        description="HTTP request initiated without an explicit timeout or AbortSignal. A slow upstream server can keep sockets open indefinitely.",
                        evidence=f"HTTP call at {file_path}:{idx} lacks AbortSignal.timeout or timeout option.",
                        detection_method="Static Network Call Inspection",
                        potential_consequences="Socket starvation and hanging promises degrading service responsiveness.",
                        suggested_next_step="Add 'signal: AbortSignal.timeout(5000)' or configure axios timeout.",
                    )

            # Rule: Silent Empty Catch Block
            if re.search(r"catch\s*\([^\)]*\)\s*\{\s*\}", clean_line) or (
                clean_line.startswith("catch") and idx < len(lines) and lines[idx].strip() == "}"
            ):
                emit(
                    rule_id="JS_EMPTY_CATCH",
                    title="Silent Error Suppression in Empty Catch Block",
                    category="Error Handling Anti-Pattern",
                    line_number=idx,
                    line_end=idx,
                    code_snippet=clean_line,
                    description="Empty catch block silently swallows runtime rejections or errors without logging, alerting, or rethrowing.",
                    evidence=f"Empty catch block detected at {file_path}:{idx}.",
                    detection_method="Static Catch Block Inspection",
                    potential_consequences="Unexplained silent failures, hidden state corruption, and difficult post-incident forensics.",
                    suggested_next_step="Log the error using logger.error(err) or rethrow to caller.",
                )

            # Rule: Prototype Pollution Risk
            if re.search(r"\[[\"'](?:__proto__|constructor|prototype)[\"']\]", clean_line) or "__proto__" in clean_line:
                emit(
                    rule_id="JS_PROTOTYPE_POLLUTION",
                    title="Prototype Pollution Hazard",
                    category="Security Vulnerability",
                    line_number=idx,
                    line_end=idx,
                    code_snippet=clean_line,
                    description="Direct mutation of object prototype via __proto__ or constructor.prototype allows modifying object inheritance globally.",
                    evidence=f"Prototype accessor token detected at {file_path}:{idx}.",
                    detection_method="Static Prototype Pollution Pattern",
                    potential_consequences="Global application instability or property injection bypassing validation checks.",
                    suggested_next_step="Use Object.create(null) or Map instead of raw prototype property assignment.",
                )

            # Extract Import / Require relationships
            req_match = re.search(r"require\s*\(\s*[\"']([^\"']+)[\"']\s*\)", clean_line)
            if req_match:
                target = req_match.group(1)
                relationships.append({
                    "source": file_path,
                    "target": target,
                    "relationship_type": "imports",
                    "details": f"CommonJS require('{target}')",
                })

            imp_match = re.search(r"import\s+.*from\s+[\"']([^\"']+)[\"']", clean_line)
            if imp_match:
                target = imp_match.group(1)
                relationships.append({
                    "source": file_path,
                    "target": target,
                    "relationship_type": "imports",
                    "details": f"ESModule import from '{target}'",
                })

        return {
            "findings": findings,
            "relationships": relationships,
            "functions": [async_fn_name] if async_fn_name else [],
            "imports": [r["target"] for r in relationships],
            "ast_parsed": True,
        }

    def _run_external_diagnostics(self, code: str, file_path: str, lines: List[str], emit) -> None:
        node_bin = shutil.which("node")
        if not node_bin:
            return
        runner_path = os.path.join(os.path.dirname(__file__), "js_ts_runner.js")
        if not os.path.exists(runner_path):
            return
        try:
            env = dict(os.environ, SOURCE_CODE=code, FILE_PATH=file_path)
            proc = subprocess.run([node_bin, runner_path], env=env, capture_output=True, text=True, timeout=8)
            if not proc.stdout:
                return
            diags = json.loads(proc.stdout)
            for d in diags:
                tool = d.get("tool", "tool")
                rule_id = d.get("rule_id", "")
                msg = d.get("message", "")
                ln = d.get("line", 1)
                col = d.get("column", 1)
                cat = d.get("category", "General")
                snippet = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""

                if rule_id == "no-undef" or cat == "Undefined Names / Symbol Errors" or rule_id in ("TS2304", "TS2552"):
                    emit(
                        rule_id="JS_UNDEFINED_NAME",
                        title=f"Undefined Identifier in {('TypeScript' if file_path.endswith(('.ts', '.tsx')) else 'JavaScript')}",
                        category="Undefined Names / Symbol Errors",
                        line_number=ln,
                        line_end=ln,
                        code_snippet=snippet,
                        description=f"Identifier is referenced without being declared or imported: {msg}",
                        evidence=f"{tool.upper()} diagnostic ({rule_id}) at {file_path}:{ln}:{col}: {msg}",
                        detection_method=f"{tool.upper()} Diagnostic Runner ({rule_id})",
                        potential_consequences="Raises runtime ReferenceError in strict mode or fails bundle compilation.",
                        suggested_next_step="Declare the variable with 'const' or 'let', or import it from the appropriate module.",
                        default_severity="High",
                    )
                elif rule_id.startswith("TS") or cat == "Type Errors":
                    emit(
                        rule_id="TS_TYPE_MISMATCH",
                        title=f"TypeScript Type Incompatibility ({rule_id})",
                        category="Type & Argument Errors",
                        line_number=ln,
                        line_end=ln,
                        code_snippet=snippet,
                        description=f"TypeScript compiler detected a type contract mismatch: {msg}",
                        evidence=f"TypeScript Compiler API (ts.getPreEmitDiagnostics) at {file_path}:{ln}:{col}: {msg}",
                        detection_method=f"TypeScript Compiler API ({rule_id})",
                        potential_consequences="Type contract violation leads to build failure and unexpected runtime coercion errors.",
                        suggested_next_step="Align the assigned value type with the declared variable or parameter type.",
                        default_severity="High",
                    )
                elif "syntax" in cat.lower() or rule_id == "JS_SYNTAX_ERROR":
                    emit(
                        rule_id="JS_UNBALANCED_DELIMITERS",
                        title=f"Syntax Error in {file_path}",
                        category="Syntax & Parsing",
                        line_number=ln,
                        line_end=ln,
                        code_snippet=snippet,
                        description=f"Parser failed with syntax error: {msg}",
                        evidence=f"{tool.upper()} diagnostic at {file_path}:{ln}:{col}: {msg}",
                        detection_method=f"{tool.upper()} Syntax Parser",
                        potential_consequences="Prevents script execution or compilation.",
                        suggested_next_step="Correct the syntax defect around the reported line.",
                        default_severity="Critical",
                    )
        except Exception:
            pass
