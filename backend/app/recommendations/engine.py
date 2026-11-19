import difflib
import re
from typing import List, Dict, Any, Optional
from backend.app.services.fix_engine import SafeFixEngine


SIMPLE_EXPLANATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "PY_LOGICAL_CALCULATION": {
        "what_is_wrong": "The calculation formula uses an incorrect denominator or arithmetic expression (such as dividing by length + 1).",
        "why_problem": "Adding extra numbers to the denominator reduces the calculated average below the true mathematical mean.",
        "what_to_change": "Divide directly by the collection length (e.g., total / len(items)).",
        "how_it_helps": "Restores correct mathematical calculation and accurate reporting metrics.",
    },
    "PY_LOGICAL_COMPARISON": {
        "what_is_wrong": "The comparison operator is inverted (using '<' instead of '>') when searching for the highest value or topper.",
        "why_problem": "Because the tracking variable starts at 0, checking '<' never triggers for positive scores, leaving the result empty.",
        "what_to_change": "Change the comparison operator from '<' to '>' to find the maximum value.",
        "how_it_helps": "Correctly identifies the highest-scoring candidate (e.g. Topper: Priya).",
    },
    "PY_LOGICAL_CONDITION": {
        "what_is_wrong": "The if-condition tests '< 40', which counts failing students instead of passing students.",
        "why_problem": "Students meeting or exceeding the passing threshold are ignored, resulting in an incorrect count of 0.",
        "what_to_change": "Change the condition to '>= 40' (score at least 40) to count students who passed.",
        "how_it_helps": "Correctly counts all passing students (e.g. Passed: 3).",
    },
    "PY_LOGICAL_OFF_BY_ONE": {
        "what_is_wrong": "A loop or indexing boundary is off by one, skipping valid elements or accessing past the end.",
        "why_problem": "Causes missing elements in aggregation or potential index boundary defects.",
        "what_to_change": "Adjust the loop range or index bounds to cover the complete collection.",
        "how_it_helps": "Ensures every element is inspected correctly without skipping data.",
    },
    "PY_LOGICAL_LOOP_BOUND": {
        "what_is_wrong": "The loop contains an unconditional return on the first iteration.",
        "why_problem": "The function returns prematurely without processing remaining elements.",
        "what_to_change": "Move the return statement outside the loop body or wrap it in a termination condition.",
        "how_it_helps": "Allows the loop to complete processing across the full collection.",
    },
    "PY_LOGICAL_ERROR": {
        "what_is_wrong": "The function compiles and executes without exceptions, but produces logically incorrect output values.",
        "why_problem": "Algorithmic mistakes produce corrupt results, invalid reports, or misleading decisions.",
        "what_to_change": "Apply the verified code correction to align the logic with the intended specification.",
        "how_it_helps": "Ensures the function outputs the expected, accurate results.",
    },
    "PY_ASYNC_BLOCKING_SLEEP": {
        "what_is_wrong": "The program pauses using a blocking wait inside an async task.",
        "why_problem": "While this function pauses, every other waiting user or task is frozen too.",
        "what_to_change": "Switch time.sleep(...) to await asyncio.sleep(...) and make sure asyncio is imported.",
        "how_it_helps": "Other tasks can keep running smoothly while this function waits.",
    },
    "PY_ASYNC_BLOCKING_HTTP": {
        "what_is_wrong": "This async function makes a regular web request that waits until the whole response returns.",
        "why_problem": "The rest of the app cannot handle other requests until that slow network call finishes.",
        "what_to_change": "Use an async web client like httpx.AsyncClient or aiohttp instead of requests.",
        "how_it_helps": "Your app stays fast and responsive even when external websites respond slowly.",
    },
    "PY_UNBOUNDED_RETRY": {
        "what_is_wrong": "A loop keeps retrying forever if an error happens and hides the error.",
        "why_problem": "If the external service stays down, the program can hang forever and waste CPU or flood the server.",
        "what_to_change": "Limit retries to a small number (such as 3), wait longer between tries, log the error, and stop if all tries fail.",
        "how_it_helps": "Temporary glitches still recover, while permanent failures stop cleanly and show clear logs.",
    },
    "PY_UNBOUNDED_RETRY_INSPECT": {
        "what_is_wrong": "This retry loop has no maximum number of attempts.",
        "why_problem": "If a permanent error occurs, the loop may keep retrying without ever finishing.",
        "what_to_change": "Add a clear retry limit or only retry temporary errors.",
        "how_it_helps": "Prevents background work from getting stuck indefinitely.",
    },
    "PY_UNCONTROLLED_LOOP": {
        "what_is_wrong": "There is a 'while True' loop with no clear way to stop or pause.",
        "why_problem": "Once the program enters this loop, it can spin at 100% CPU and freeze.",
        "what_to_change": "Add a clear stopping condition or exit check inside the loop.",
        "how_it_helps": "Prevents the program from locking up and wasting processor resources.",
    },
    "PY_UNAWAITED_COROUTINE": {
        "what_is_wrong": "An async function is called without waiting for it to actually run.",
        "why_problem": "In Python, calling an async function without 'await' does not execute the work—it only creates an unfinished task object.",
        "what_to_change": "Add 'await' before the call inside an async function, or run it with asyncio.run() / asyncio.gather().",
        "how_it_helps": "Ensures the task actually executes and gives you the real result instead of an unrun coroutine object.",
    },
    "PY_UNAWAITED_COROUTINE_RETURN": {
        "what_is_wrong": "A regular function sometimes returns an unfinished async task instead of a finished value.",
        "why_problem": "Callers expecting normal data can fail unexpectedly when they receive an unrun task object.",
        "what_to_change": "Make the function async and use 'await', or return consistent types across all branches.",
        "how_it_helps": "Callers reliably get the expected data every time.",
    },
    "PY_UNBOUNDED_COLLECTION": {
        "what_is_wrong": "A shared list keeps adding new items without ever removing old ones.",
        "why_problem": "If the app runs for a long time, memory usage can keep growing until the app crashes.",
        "what_to_change": "Use a size-limited container like collections.deque(maxlen=1000) or clear old entries regularly.",
        "how_it_helps": "Keeps memory usage steady and predictable over long runs.",
    },
    "PY_UNCLOSED_RESOURCE": {
        "what_is_wrong": "A file or database connection is opened without making sure it always closes.",
        "why_problem": "If an error happens before closing, the system can run out of available files or database connections.",
        "what_to_change": "Open the file or connection using a 'with ... as ...:' block.",
        "how_it_helps": "Python automatically closes the file or connection even if an error happens.",
    },
    "PY_UNSAFE_LOCK": {
        "what_is_wrong": "A thread lock is grabbed manually without guaranteeing it will be released.",
        "why_problem": "If an error occurs before unlocking, every other thread waiting for that lock will freeze forever.",
        "what_to_change": "Use 'with lock:' instead of calling lock.acquire() manually.",
        "how_it_helps": "Automatically unlocks even when errors occur, preventing freezes.",
    },
    "PY_SQL_INJECTION": {
        "what_is_wrong": "User data is pasted directly into a database query string.",
        "why_problem": "Crafted input could change the meaning of the database query and expose or damage data.",
        "what_to_change": "Use query placeholders (like ? or %s) and pass values separately.",
        "how_it_helps": "Keeps user inputs safely separated from database commands.",
    },
    "PY_DANGEROUS_EVAL": {
        "what_is_wrong": "The program runs raw text as executable Python code using eval() or exec().",
        "why_problem": "If untrusted text reaches this line, someone could run harmful commands on your computer.",
        "what_to_change": "Use safer data parsers like json.loads() or ast.literal_eval().",
        "how_it_helps": "Reads data safely without allowing arbitrary code to run.",
    },
    "PY_UNSAFE_DESERIALIZATION": {
        "what_is_wrong": "The program loads data using a format parser that can accidentally execute hidden code.",
        "why_problem": "Tampered input files could run unwanted code when loaded.",
        "what_to_change": "Use yaml.safe_load() or JSON instead of unsafe loaders.",
        "how_it_helps": "Loads configuration or data safely without risking code execution.",
    },
    "PY_SUBPROCESS_SHELL": {
        "what_is_wrong": "A system command is run through the command shell as a combined text string.",
        "why_problem": "Special characters in input values could trigger extra unintended system commands.",
        "what_to_change": "Pass the command and arguments as a Python list with shell=False.",
        "how_it_helps": "Runs only the intended command without shell interpretation risks.",
    },
    "PY_CONST_ZERO_DIV": {
        "what_is_wrong": "The code divides directly by zero.",
        "why_problem": "Dividing by zero immediately crashes the program whenever this line runs.",
        "what_to_change": "Replace the zero divisor with a valid non-zero value or check the formula.",
        "how_it_helps": "Eliminates a guaranteed crash.",
    },
    "PY_UNGUARDED_DIV": {
        "what_is_wrong": "The code divides by a variable without checking if it is zero first.",
        "why_problem": "If the value ever happens to be zero, the program will crash with an error.",
        "what_to_change": "Add a quick 'if value == 0:' check before dividing.",
        "how_it_helps": "Handles zero inputs gracefully instead of crashing.",
    },
    "PY_MUTABLE_DEFAULT": {
        "what_is_wrong": "A function uses an empty list or dictionary directly as a default argument.",
        "why_problem": "Python reuses that same list across calls, so old data unexpectedly shows up in later calls.",
        "what_to_change": "Set the default to None and create a fresh list inside the function.",
        "how_it_helps": "Gives every function call its own clean, independent data.",
    },
    "PY_MISSING_TIMEOUT": {
        "what_is_wrong": "An outgoing web request has no time limit.",
        "why_problem": "If the remote server stops responding, this request could wait forever.",
        "what_to_change": "Add a timeout setting (for example, timeout=10) to the request.",
        "how_it_helps": "Ensures stuck network calls stop after a reasonable wait.",
    },
    "PY_SILENT_EXCEPT": {
        "what_is_wrong": "An error handler catches problems and ignores them completely with 'pass'.",
        "why_problem": "When something breaks, there is no error message or log to help you find out why.",
        "what_to_change": "Log the error message or handle specific expected errors explicitly.",
        "how_it_helps": "Makes bugs visible immediately instead of failing silently.",
    },
    "PY_BARE_EXCEPT": {
        "what_is_wrong": "A bare 'except:' catches every possible error, even system stop signals.",
        "why_problem": "It can hide serious bugs and make the program hard to stop cleanly with Ctrl+C.",
        "what_to_change": "Change 'except:' to catch 'Exception' (or a specific error) and log it.",
        "how_it_helps": "Allows clean program shutdown while still handling real errors safely.",
    },
    "PY_HARDCODED_SECRET": {
        "what_is_wrong": "A password or API key is written directly inside the source code.",
        "why_problem": "Anyone who sees the code or repository history can steal the key.",
        "what_to_change": "Read the secret from an environment variable using os.environ.get(...).",
        "how_it_helps": "Keeps sensitive keys out of source code and easy to rotate safely.",
    },
    "PY_SYNTAX_ERROR": {
        "what_is_wrong": "There is a syntax mistake that Python cannot understand.",
        "why_problem": "The file cannot run or be fully checked until the syntax mistake is fixed.",
        "what_to_change": "Fix the punctuation, indentation, or missing bracket near the highlighted line.",
        "how_it_helps": "Allows Python to run the file and InsightX to scan the rest of your code.",
    },
    "PY_UNDEFINED_NAME": {
        "what_is_wrong": "A function or variable name is used without being defined or imported.",
        "why_problem": "Calling an undefined name raises a NameError crash as soon as that line executes.",
        "what_to_change": "If you wrote printf(), change it to print(). Otherwise, define or import the missing variable.",
        "how_it_helps": "Prevents runtime NameError crashes and uses the correct language built-ins.",
    },
    "PY_MISSING_ARGUMENT": {
        "what_is_wrong": "A function was called without all of the required arguments it needs.",
        "why_problem": "Python will raise a TypeError immediately when the function is invoked.",
        "what_to_change": "Pass all required parameters defined in the function signature.",
        "how_it_helps": "Satisfies the function contract and ensures calculations run properly.",
    },
    "JS_UNDEFINED_NAME": {
        "what_is_wrong": "A variable or function is referenced without being declared in JavaScript.",
        "why_problem": "Undeclared identifiers trigger ReferenceError crashes in strict JavaScript.",
        "what_to_change": "Declare the variable with const/let, or import it from the appropriate module.",
        "how_it_helps": "Ensures variable scope is defined and avoids runtime crashes.",
    },
    "TS_TYPE_MISMATCH": {
        "what_is_wrong": "A value of an incompatible type was assigned to a typed TypeScript variable.",
        "why_problem": "Violating declared types causes TypeScript compiler failure and unexpected runtime behavior.",
        "what_to_change": "Assign a value matching the declared type, or update the type annotation.",
        "how_it_helps": "Restores type safety and prevents unexpected type coercion bugs.",
    },
    "C_UNDECLARED_IDENTIFIER": {
        "what_is_wrong": "An identifier is used in C without being declared or having its header included.",
        "why_problem": "The C compiler cannot produce an executable object file with undeclared identifiers.",
        "what_to_change": "Include the necessary header file (e.g. #include <stdio.h>) or declare the variable.",
        "how_it_helps": "Allows the C compiler to verify symbol signatures and compile cleanly.",
    },
    "JS_BLOCKING_FS": {
        "what_is_wrong": "A synchronous file read or write pauses the whole JavaScript server.",
        "why_problem": "Other incoming requests have to wait until the disk finishes reading or writing.",
        "what_to_change": "Use async file methods such as await fs.promises.readFile(...).",
        "how_it_helps": "Keeps the server responsive for other users during disk operations.",
    },
    "JS_MISSING_TIMEOUT": {
        "what_is_wrong": "A network request has no timeout configured.",
        "why_problem": "If the external server hangs, the request can stay stuck indefinitely.",
        "what_to_change": "Add a timeout option or AbortSignal.timeout(5000).",
        "how_it_helps": "Fails cleanly after a set wait instead of hanging forever.",
    },
}


class RecommendationEngine:
    """
    Actionable Decision Intelligence & Remediation Engine.

    Generates rule-accurate, prioritized corrective actions connected to real
    detected findings and root causes, with context-aware before/after diffs
    and concrete verification instructions. Never applies changes automatically.
    """

    def generate_recommendations(
        self,
        findings: List[Dict[str, Any]],
        files_map: Dict[str, str] = None,
        root_causes: List[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        files_map = files_map or {}
        root_causes = root_causes or []
        recommendations: List[Dict[str, Any]] = []

        # Build finding_id -> list of root_cause_ids map
        finding_to_causes: Dict[str, List[str]] = {}
        for rc in root_causes:
            rc_id = rc.get("id")
            if not rc_id:
                continue
            for fid in rc.get("related_finding_ids", []):
                finding_to_causes.setdefault(fid, []).append(rc_id)

        # Group findings by (rule_key, file_path) so duplicate occurrences in the same file
        # produce one consolidated recommendation referencing ALL matching finding IDs
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for f in findings:
            rkey = self._resolve_rule_key(f)
            f_file = f.get("file_path", "")
            grouped.setdefault((rkey, f_file), []).append(f)

        for (rkey, f_file), group_findings in grouped.items():
            primary = group_findings[0]
            f_ids = [f.get("id") or f.get("title", "") for f in group_findings]
            cause_ids = sorted({cid for fid in f_ids for cid in finding_to_causes.get(fid, [])})
            code_text = files_map.get(f_file, "")

            rec = self._build_recommendation(rkey, primary, group_findings, f_file, code_text, f_ids, cause_ids)
            if rec:
                # Enrich with rule_id, real auto-fixability check against actual file, and two-mode explanations
                rec["rule_id"] = rkey
                target_lines = [f.get("line_number") for f in group_findings if f.get("line_number")]
                if code_text:
                    preview = SafeFixEngine.preview_patch(
                        rule_id=rkey,
                        file_path=f_file,
                        original_code=code_text,
                        target_lines=target_lines,
                        original_snippet=primary.get("code_snippet") or "",
                    )
                    rec["auto_fixable"] = preview["auto_fixable"]
                    rec["manual_fix_reason"] = preview["manual_fix_reason"]
                    if preview["auto_fixable"] and preview.get("diff"):
                        rec["diff"] = preview["diff"]
                        if preview.get("patched_code"):
                            rec["refactored_code"] = preview["patched_code"]
                else:
                    can_auto, reason = SafeFixEngine.is_rule_potentially_auto_fixable(
                        rkey, primary.get("code_snippet") or ""
                    )
                    rec["auto_fixable"] = can_auto
                    rec["manual_fix_reason"] = reason

                rec["simple_explanation"] = self._build_simple_explanation(rkey, rec, primary)
                rec["technical_explanation"] = self._build_technical_explanation(rkey, rec, primary, group_findings)
                recommendations.append(rec)

        priority_order = {"P1 - Immediate": 1, "P2 - High": 2, "P3 - Medium": 3, "P4 - Low": 4}
        recommendations.sort(key=lambda r: (priority_order.get(r["priority"], 9), r["title"]))
        return recommendations

    def _resolve_rule_key(self, finding: Dict[str, Any]) -> str:
        rule_id = finding.get("rule_id")
        if rule_id:
            return rule_id
        # Fallback for findings constructed directly in unit tests without rule_id
        title = finding.get("title", "")
        cat = finding.get("category", "")
        if "Syntax" in title or "Delimiter" in title:
            return "PY_SYNTAX_ERROR"
        if "Logical" in cat or "logical" in title.lower() or (rule_id and rule_id.startswith("PY_LOGICAL_")):
            return rule_id or "PY_LOGICAL_ERROR"
        if "Synchronous Network Call" in title:
            return "PY_ASYNC_BLOCKING_HTTP"
        if "Blocking Synchronous I/O" in title:
            return "JS_BLOCKING_FS"
        if "Blocking Synchronous Call" in title or "Event Loop" in cat:
            return "PY_ASYNC_BLOCKING_SLEEP"
        if "Retry" in title:
            return "PY_UNBOUNDED_RETRY"
        if "Infinite Loop" in title:
            return "PY_UNCONTROLLED_LOOP"
        if "Coroutine" in title or "Coroutine" in cat:
            return "PY_UNAWAITED_COROUTINE"
        if "Collection Growth" in title or "Memory Management" in cat:
            return "PY_UNBOUNDED_COLLECTION"
        if "Deadlock" in title or "Lock" in title:
            return "PY_UNSAFE_LOCK"
        if "Unclosed" in title or "Resource" in cat:
            return "PY_UNCLOSED_RESOURCE"
        if "SQL" in title or "Injection" in title:
            return "PY_SQL_INJECTION"
        if "eval" in title.lower() or "Dynamic Code" in title:
            return "PY_DANGEROUS_EVAL"
        if "Mutable Default" in title:
            return "PY_MUTABLE_DEFAULT"
        if "Timeout" in title:
            return "PY_MISSING_TIMEOUT"
        if "Secret" in title or "Credential" in title:
            return "PY_HARDCODED_SECRET"
        if "Prototype" in title:
            return "JS_PROTOTYPE_POLLUTION"
        if "Division" in title or "Arithmetic" in cat:
            return "PY_UNGUARDED_DIV"
        if "except" in title.lower() or "Catch" in title or "Error Handling" in cat:
            return "PY_SILENT_EXCEPT"
        return "GENERIC"

    def _format_lines(self, group_findings: List[Dict[str, Any]]) -> str:
        parts = []
        for f in group_findings[:4]:
            ln = f.get("line_number")
            le = f.get("line_end")
            if ln and le and le > ln:
                parts.append(f"lines {ln}-{le}")
            elif ln:
                parts.append(f"line {ln}")
        return ", ".join(parts) if parts else "module scope"

    def _build_recommendation(
        self,
        rkey: str,
        primary: Dict[str, Any],
        group_findings: List[Dict[str, Any]],
        f_file: str,
        code_text: str,
        f_ids: List[str],
        cause_ids: List[str],
    ) -> Optional[Dict[str, Any]]:
        loc = self._format_lines(group_findings)
        orig_snippet = (primary.get("code_snippet") or "").strip()
        sev = primary.get("severity", "Medium")
        default_prio = (
            "P1 - Immediate" if sev == "Critical"
            else "P2 - High" if sev == "High"
            else "P3 - Medium" if sev == "Medium"
            else "P4 - Low"
        )

        # 1. Blocking time.sleep() inside async function
        if rkey == "PY_ASYNC_BLOCKING_SLEEP":
            orig = orig_snippet or "time.sleep(5)"
            m_arg = re.search(r"(?:time\.)?sleep\s*\(([^)]*)\)", orig)
            arg_val = m_arg.group(1).strip() if m_arg and m_arg.group(1).strip() else "delay_seconds"
            has_asyncio_import = bool(re.search(r"^\s*(?:import\s+asyncio|from\s+asyncio\s+import)", code_text, re.MULTILINE))
            if has_asyncio_import:
                refactored = f"await asyncio.sleep({arg_val})"
                import_note = "'asyncio' is already imported in this file."
            else:
                refactored = f"import asyncio  # add at module top-level\nawait asyncio.sleep({arg_val})"
                import_note = "Ensure 'import asyncio' is added at the top of the module."

            return self._pack(
                priority="P1 - Immediate" if sev == "Critical" else "P2 - High",
                title="Replace Blocking time.sleep() with Non-Blocking await asyncio.sleep()",
                problem_addressed=f"Synchronous sleep call at {loc} in {f_file} blocks the asyncio event loop thread.",
                why_recommended=(
                    "Asyncio runs concurrent coroutines cooperatively on a single event-loop thread. "
                    "Calling time.sleep() pauses the entire OS thread instead of yielding control, preventing other tasks from executing. "
                    f"Replacing it with 'await asyncio.sleep({arg_val})' suspends only the current coroutine and yields control back to the event loop. {import_note}"
                ),
                expected_benefit="Eliminates event-loop stalls during delays and restores concurrency for parallel requests.",
                verification_instructions=(
                    f"Verify 'import asyncio' is present, replace the blocking call with 'await asyncio.sleep({arg_val})', "
                    "and run two concurrent invocations via asyncio.gather() to confirm total runtime equals one interval rather than their sum."
                ),
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 2. Synchronous HTTP request inside async function
        if rkey == "PY_ASYNC_BLOCKING_HTTP":
            orig = orig_snippet or "response = requests.get(url)"
            m_method = re.search(r"requests\.(get|post|put|delete|patch)\s*\(([^)]*)\)", orig)
            method = m_method.group(1) if m_method else "get"
            args_str = m_method.group(2).strip() if m_method and m_method.group(2).strip() else "url"
            if "timeout" not in args_str:
                args_with_timeout = f"{args_str}, timeout=10.0"
            else:
                args_with_timeout = args_str
            refactored = (
                "async with httpx.AsyncClient(timeout=10.0) as client:\n"
                f"    response = await client.{method}({args_with_timeout})"
            )
            return self._pack(
                priority="P1 - Immediate" if sev == "Critical" else "P2 - High",
                title="Replace Synchronous HTTP Calls in Async Functions with an Async Client",
                problem_addressed=f"Blocking HTTP call at {loc} in {f_file} stalls the event loop while waiting on network I/O.",
                why_recommended=(
                    "The synchronous 'requests' or 'urllib' library blocks the current thread until socket I/O finishes, "
                    "freezing all other coroutines on the asyncio event loop. An async HTTP client (httpx.AsyncClient or aiohttp) "
                    "yields control while awaiting network responses."
                ),
                expected_benefit="Preserves async concurrency under high I/O latency and prevents P99 response spikes.",
                verification_instructions=(
                    "Add 'httpx' (or 'aiohttp') to dependencies, reuse a shared AsyncClient session where appropriate, "
                    "and benchmark concurrent async requests against a simulated slow endpoint."
                ),
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 3. Unbounded Infinite Retry Loop
        if rkey in ("PY_UNBOUNDED_RETRY", "PY_UNBOUNDED_RETRY_INSPECT"):
            orig = orig_snippet or "while True:\n    try:\n        return await request_data()\n    except Exception:\n        pass"
            is_async_ctx = "await " in orig or "async def" in code_text
            sleep_stmt = "await asyncio.sleep(min(2 ** attempt, 30))" if is_async_ctx else "time.sleep(min(2 ** attempt, 30))"
            refactored = (
                "max_retries = 3\n"
                "for attempt in range(max_retries):\n"
                "    try:\n"
                "        return await request_data()  # replace with your operation\n"
                "    except (TimeoutError, ConnectionError) as err:\n"
                "        logger.warning('Attempt %d/%d failed: %s', attempt + 1, max_retries, err)\n"
                "        if attempt == max_retries - 1:\n"
                "            raise\n"
                f"        {sleep_stmt}"
            )
            return self._pack(
                priority="P2 - High" if rkey == "PY_UNBOUNDED_RETRY" else "P3 - Medium",
                title="Bound Retry Loops with Max Attempts, Exponential Backoff, and Error Logging",
                problem_addressed=f"Unbounded retry loop at {loc} in {f_file} can loop indefinitely when errors persist.",
                why_recommended=(
                    "Retrying forever on broad exceptions without an attempt limit or backoff causes hung tasks, "
                    "CPU spin, and retry storms that amplify downstream outages. Bounding attempts with exponential backoff "
                    "and structured logging ensures controlled termination and observability."
                ),
                expected_benefit="Prevents indefinite hangs and retry storms while retaining resilience against transient failures.",
                verification_instructions=(
                    "Unit-test with a mock dependency that always raises an exception; verify the loop executes exactly "
                    "'max_retries' times, sleeps between retries, logs each attempt, and raises the error upon exhaustion."
                ),
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 4. Uncontrolled Infinite Loop (Non-retry)
        if rkey == "PY_UNCONTROLLED_LOOP":
            orig = orig_snippet or "while True:\n    ..."
            refactored = (
                "while not stop_event.is_set():\n"
                "    # perform bounded work unit\n"
                "    if done_condition:\n"
                "        break"
            )
            return self._pack(
                priority="P2 - High",
                title="Add Deterministic Termination or Cancellation Check to Infinite Loop",
                problem_addressed=f"Uncontrolled while True loop at {loc} in {f_file} has no exit, yield, or throttle.",
                why_recommended="A tight infinite loop without an exit guard or cooperative sleep/await pins a CPU core at 100% indefinitely.",
                expected_benefit="Prevents CPU starvation and allows graceful shutdown or cancellation.",
                verification_instructions="Test loop execution with a stop condition or timeout to confirm clean exit.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 5. Unawaited Coroutine Creation
        if rkey in ("PY_UNAWAITED_COROUTINE", "PY_UNAWAITED_COROUTINE_RETURN"):
            orig = orig_snippet or "results.append(fetch_user(user))"
            m_fn = re.search(r"'([a-zA-Z0-9_.]+)\(\)'", primary.get("title", ""))
            callee = m_fn.group(1) if m_fn else "async_func"
            if ".append(" in orig or "Collection" in primary.get("title", ""):
                refactored = (
                    "async def process_items(items):\n"
                    f"    tasks = [{callee}(item) for item in items]\n"
                    "    return await asyncio.gather(*tasks)"
                )
            elif rkey == "PY_UNAWAITED_COROUTINE_RETURN":
                refactored = (
                    "# Option A: Make enclosing function async and await:\n"
                    f"return await {callee}(...)\n"
                    "# Option B (sync entrypoint): return asyncio.run(" + f"{callee}(...))"
                )
            else:
                refactored = f"result = await {orig}" if "=" not in orig else re.sub(r"=\s*", "= await ", orig, count=1)

            return self._pack(
                priority="P2 - High" if rkey == "PY_UNAWAITED_COROUTINE" else "P3 - Medium",
                title=f"Await or Schedule Coroutine Returned by '{callee}()'",
                problem_addressed=f"Async function '{callee}()' is invoked at {loc} in {f_file} without awaiting or scheduling.",
                why_recommended=(
                    f"Calling an 'async def' function like '{callee}()' creates a coroutine object without executing its body. "
                    "Unless awaited ('await ...'), gathered ('await asyncio.gather(...)'), scheduled ('asyncio.create_task(...)'), "
                    "or run via 'asyncio.run(...)', the async logic never executes and callers receive raw coroutine objects."
                ),
                expected_benefit="Ensures asynchronous operations actually run and return resolved data instead of coroutine objects.",
                verification_instructions=(
                    f"Run tests with warnings treated as errors ('pytest -W error::RuntimeWarning') and verify "
                    f"resolved values are returned rather than '<coroutine object {callee}>'."
                ),
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 6. Unbounded In-Memory Collection Growth
        if rkey == "PY_UNBOUNDED_COLLECTION":
            orig = orig_snippet or "items.append(record)"
            m_var = re.search(r"\b([a-zA-Z0-9_]+)\s*\.", orig)
            var_name = m_var.group(1) if m_var else "items"
            refactored = (
                "from collections import deque\n"
                f"{var_name} = deque(maxlen=1000)  # bounded ring buffer\n"
                f"{orig}"
            )
            return self._pack(
                priority="P2 - High",
                title=f"Bound In-Memory Collection '{var_name}' with Maximum Capacity or Eviction",
                problem_addressed=f"Module-level collection '{var_name}' at {loc} in {f_file} grows unbounded across executions.",
                why_recommended=(
                    f"Appending indefinitely to global collection '{var_name}' without maxlen, TTL, or eviction causes "
                    "continuous heap expansion until the process hits Out-Of-Memory (OOM) limits."
                ),
                expected_benefit="Caps resident memory usage deterministically and prevents long-uptime OOM crashes.",
                verification_instructions=(
                    f"Invoke the mutating function more than maxlen times in a test and assert len({var_name}) <= maxlen."
                ),
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 7. Unclosed File / Connection Resource Leak
        if rkey == "PY_UNCLOSED_RESOURCE":
            orig = orig_snippet or "conn = sqlite3.connect('app.db')"
            if "open(" in orig:
                m_open = re.search(r"([a-zA-Z0-9_]+)\s*=\s*(open\([^)]*\))", orig)
                if m_open:
                    refactored = f"with {m_open.group(2)} as {m_open.group(1)}:\n    # operate on {m_open.group(1)}; automatically closed on exit"
                else:
                    refactored = "with open(path, mode) as handle:\n    # operate on handle; automatically closed on exit"
            else:
                m_conn = re.search(r"([a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_.]*connect\([^)]*\))", orig)
                if m_conn:
                    refactored = (
                        f"with {m_conn.group(2)} as {m_conn.group(1)}:\n"
                        f"    # execute queries using {m_conn.group(1)}\n"
                        "# Ensure explicit close() or contextlib.closing() if connection __exit__ only commits"
                    )
                else:
                    refactored = "with contextlib.closing(db.connect(...)) as conn:\n    # execute operations safely"
            return self._pack(
                priority="P2 - High",
                title="Manage File/Connection Lifecycle Using Context Managers ('with')",
                problem_addressed=f"Resource opened at {loc} in {f_file} lacks context-manager or try...finally closure.",
                why_recommended="Without a 'with' statement or 'finally: close()', exceptions leak open file descriptors or database connections.",
                expected_benefit="Prevents file descriptor exhaustion and connection pool starvation.",
                verification_instructions="Run tests under ResourceWarning enabled ('python3 -W default') and simulate an exception mid-operation to verify descriptor closure.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 8. Unsafe Lock Acquisition / Threading Deadlock
        if rkey == "PY_UNSAFE_LOCK":
            orig = orig_snippet or "lock.acquire()"
            m_lock = re.search(r"([a-zA-Z0-9_.]+)\.acquire\s*\(", orig)
            lock_name = m_lock.group(1) if m_lock else "lock"
            refactored = f"with {lock_name}:\n    # protected critical section; released automatically even on exception"
            return self._pack(
                priority="P1 - Immediate",
                title="Enforce Exception-Safe Mutex Acquisition Using 'with'",
                problem_addressed=f"Explicit '{lock_name}.acquire()' at {loc} in {f_file} lacks guaranteed release on exception.",
                why_recommended="If an exception or early return occurs before .release(), the lock remains permanently held and deadlocks waiting threads.",
                expected_benefit="Eliminates mutex leak deadlocks across concurrent threads.",
                verification_instructions=f"Raise a mock exception inside the critical section and verify a subsequent thread can acquire '{lock_name}' without hanging.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 9. SQL Injection
        if rkey in ("PY_SQL_INJECTION", "JS_SQL_INJECTION"):
            orig = orig_snippet or "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')"
            if rkey == "JS_SQL_INJECTION":
                refactored = "await db.query('SELECT * FROM users WHERE id = $1', [userId]);"
            else:
                refactored = "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"
            return self._pack(
                priority="P1 - Immediate",
                title="Replace Dynamic SQL String Interpolation with Parameterized Queries",
                problem_addressed=f"Dynamic SQL query construction at {loc} in {f_file} is vulnerable to SQL injection.",
                why_recommended="Interpolating variables directly into SQL text allows untrusted inputs to modify query syntax and access or corrupt unauthorized rows.",
                expected_benefit="Neutralizes SQL injection vulnerabilities in accordance with OWASP guidelines.",
                verification_instructions="Test with input containing SQL metacharacters (e.g., \"' OR '1'='1\") and confirm it is treated strictly as a literal value.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 10. Dangerous eval / exec
        if rkey in ("PY_DANGEROUS_EVAL", "JS_DANGEROUS_EVAL"):
            orig = orig_snippet or "eval(payload)"
            refactored = (
                "const parsed = JSON.parse(payload);"
                if rkey == "JS_DANGEROUS_EVAL"
                else "import ast\nresult = ast.literal_eval(payload)  # safe literal parsing only"
            )
            return self._pack(
                priority="P1 - Immediate",
                title="Eliminate Dynamic Code Execution (eval / exec / new Function)",
                problem_addressed=f"Dynamic execution primitive at {loc} in {f_file} creates a Remote Code Execution surface.",
                why_recommended="Evaluating arbitrary strings as code allows attackers to run arbitrary commands with the application's OS privileges.",
                expected_benefit="Closes critical arbitrary-code-execution vectors.",
                verification_instructions="Verify all inputs parse strictly as typed data (JSON or Python literals) and reject executable expressions.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 10b. Unsafe Deserialization
        if rkey == "PY_UNSAFE_DESERIALIZATION":
            orig = orig_snippet or "data = pickle.loads(payload)"
            if "yaml.load" in orig:
                refactored = orig.replace("yaml.load", "yaml.safe_load")
            else:
                refactored = "import json\ndata = json.loads(payload)  # avoid pickle/marshal on untrusted inputs"
            return self._pack(
                priority="P2 - High",
                title="Replace Unsafe Deserialization with Safe Format Parsing",
                problem_addressed=f"Unsafe deserialization call at {loc} in {f_file}.",
                why_recommended="pickle/marshal and unrestricted yaml.load() can instantiate arbitrary Python objects and execute code when given untrusted data.",
                expected_benefit="Eliminates arbitrary-code-execution risks during payload parsing.",
                verification_instructions="Confirm deserialization works with JSON or yaml.safe_load() and rejects arbitrary Python object tags.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 10c. Suspicious Subprocess Shell Execution
        if rkey == "PY_SUBPROCESS_SHELL":
            orig = orig_snippet or "subprocess.run(cmd, shell=True)"
            refactored = "subprocess.run(['/usr/bin/env', 'cmd', arg], shell=False, check=True)  # pass explicit argument list"
            return self._pack(
                priority="P2 - High",
                title="Avoid Shell Interpolation in Subprocess Calls (Use Argument List with shell=False)",
                problem_addressed=f"Shell-interpreted OS command execution at {loc} in {f_file}.",
                why_recommended="Invoking a shell (shell=True or os.system) allows shell metacharacters in dynamic arguments to execute unintended commands.",
                expected_benefit="Prevents command injection and improves cross-platform argument escaping reliability.",
                verification_instructions="Pass command tokens as a list with shell=False and test with input containing shell metacharacters (e.g., ';', '&&').",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 11. Constant or Unguarded Division by Zero
        if rkey in ("PY_CONST_ZERO_DIV", "PY_UNGUARDED_DIV"):
            orig = orig_snippet or "val = numerator / denominator"
            m_div = re.search(r"/\s*([a-zA-Z0-9_]+)", orig)
            denom = m_div.group(1) if m_div and not m_div.group(1).isdigit() else "denominator"
            refactored = (
                f"if {denom} == 0:\n"
                f"    raise ValueError('{denom} must be non-zero')\n"
                f"{orig}"
            )
            return self._pack(
                priority="P1 - Immediate" if rkey == "PY_CONST_ZERO_DIV" else "P3 - Medium",
                title="Add Pre-Division Zero-Guard Validation",
                problem_addressed=f"Division operation at {loc} in {f_file} lacks protection against a zero divisor.",
                why_recommended="Dividing by zero raises an unhandled ZeroDivisionError that aborts execution.",
                expected_benefit="Replaces unexpected runtime crashes with explicit, handled validation errors.",
                verification_instructions=f"Add unit tests passing {denom}=0 and verify a controlled ValueError or safe fallback is returned.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 12. Mutable Default Argument
        if rkey == "PY_MUTABLE_DEFAULT":
            orig = orig_snippet or "def process_data(items=[]):"
            refactored = re.sub(r"=\s*(\[\]|\{\}|set\(\))", "=None", orig)
            refactored += "\n    if param is None:\n        param = []  # initialize fresh container per call"
            return self._pack(
                priority="P2 - High",
                title="Use Immutable 'None' Sentinel for Mutable Default Arguments",
                problem_addressed=f"Mutable default parameter at {loc} in {f_file} shares state across independent invocations.",
                why_recommended="Python evaluates default argument values once at function definition time, so mutations persist across future calls.",
                expected_benefit="Prevents subtle cross-request data contamination.",
                verification_instructions="Call the function twice consecutively without passing the optional parameter and assert independent results.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 13. Missing Network Request Timeout
        if rkey in ("PY_MISSING_TIMEOUT", "JS_MISSING_TIMEOUT"):
            orig = orig_snippet or ("fetch(url)" if rkey == "JS_MISSING_TIMEOUT" else "requests.get(url)")
            if rkey == "JS_MISSING_TIMEOUT":
                refactored = (
                    re.sub(r"\)\s*;?$", ", { signal: AbortSignal.timeout(5000) });", orig)
                    if "fetch(" in orig
                    else re.sub(r"\)\s*;?$", ", { timeout: 5000 });", orig)
                )
            else:
                refactored = re.sub(r"\)\s*$", ", timeout=(3.05, 10.0))", orig)
            return self._pack(
                priority="P3 - Medium",
                title="Configure Explicit Connect and Read Timeouts on Outbound HTTP Calls",
                problem_addressed=f"Outbound HTTP request at {loc} in {f_file} omits an explicit timeout.",
                why_recommended="Without a timeout, a stalled remote host holds client sockets and worker threads open indefinitely.",
                expected_benefit="Bounds worst-case wait latency and prevents thread/socket exhaustion during upstream stalls.",
                verification_instructions="Point the request at a test endpoint that delays responses beyond the configured timeout and verify a timeout exception is raised promptly.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 14. Bare Except / Silent Exception Suppression / Empty Catch
        if rkey in ("PY_BARE_EXCEPT", "PY_SILENT_EXCEPT", "JS_EMPTY_CATCH"):
            orig = orig_snippet or ("catch (err) {}" if rkey == "JS_EMPTY_CATCH" else "except Exception:\n    pass")
            if rkey == "JS_EMPTY_CATCH":
                refactored = "catch (err) {\n    logger.error('Operation failed', { err });\n    throw err;\n}"
            else:
                refactored = (
                    "except SpecificError as err:\n"
                    "    logger.exception('Operation failed: %s', err)\n"
                    "    raise"
                )
            return self._pack(
                priority="P3 - Medium",
                title="Handle Specific Exception Types and Record Structured Error Logs",
                problem_addressed=f"Broad or silent exception handling at {loc} in {f_file} conceals failures.",
                why_recommended="Swallowing broad exceptions masks bugs, suppresses system exit signals (for bare except), and eliminates diagnostic context.",
                expected_benefit="Restores failure visibility and speeds up root-cause triage.",
                verification_instructions="Trigger a simulated error in a unit test and verify that the exception is logged or propagated as designed.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 15. Hardcoded Credentials
        if rkey in ("PY_HARDCODED_SECRET", "JS_HARDCODED_SECRET"):
            orig = orig_snippet or "API_KEY = '******'"
            m_var = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[:=]", orig)
            var_name = m_var.group(1) if m_var else "API_KEY"
            env_name = var_name.upper()
            refactored = (
                f"const {var_name} = process.env.{env_name};"
                if rkey == "JS_HARDCODED_SECRET"
                else f"{var_name} = os.environ.get('{env_name}', '')"
            )
            return self._pack(
                priority="P2 - High",
                title="Move Hardcoded Credentials to Environment Variables or a Secrets Manager",
                problem_addressed=f"Plaintext credential assigned to '{var_name}' at {loc} in {f_file}.",
                why_recommended="Hardcoded secrets committed to version control can be exposed via repository history, logs, or build artifacts.",
                expected_benefit="Prevents credential leakage and enables safe key rotation without code deployments.",
                verification_instructions=f"Rotate the exposed key, configure '{env_name}' in runtime environment secrets, and confirm no literal keys remain in source control.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 16. Node.js Blocking Synchronous File I/O
        if rkey == "JS_BLOCKING_FS":
            orig = orig_snippet or "const data = fs.readFileSync(filePath);"
            refactored = orig.replace("readFileSync", "promises.readFile").replace("writeFileSync", "promises.writeFile")
            if "await " not in refactored:
                refactored = re.sub(r"=\s*", "= await ", refactored, count=1)
            return self._pack(
                priority="P2 - High",
                title="Replace Synchronous Node.js fs.*Sync Calls with Async fs.promises",
                problem_addressed=f"Synchronous filesystem call at {loc} in {f_file} blocks the Node.js event loop.",
                why_recommended="Synchronous disk I/O pauses all incoming HTTP requests on the single-threaded Node.js event loop.",
                expected_benefit="Prevents event-loop latency spikes during file reads/writes.",
                verification_instructions="Verify enclosing function is async and benchmark concurrent requests while file I/O executes.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 17. JS Prototype Pollution
        if rkey == "JS_PROTOTYPE_POLLUTION":
            orig = orig_snippet or "obj['__proto__'].polluted = true;"
            refactored = "const safeMap = Object.create(null); // or use new Map() for untrusted keys"
            return self._pack(
                priority="P2 - High",
                title="Prevent Prototype Pollution Using Null-Prototype Objects or Map",
                problem_addressed=f"Prototype property access/mutation at {loc} in {f_file}.",
                why_recommended="Mutating __proto__ or constructor.prototype alters properties across all JavaScript objects in the runtime.",
                expected_benefit="Eliminates prototype-pollution DoS and authorization-bypass risks.",
                verification_instructions="Test with keys '__proto__' and 'constructor' and verify Object.prototype remains unmodified.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 18. Syntax Error / Unbalanced Delimiters
        if rkey in ("PY_SYNTAX_ERROR", "JS_UNBALANCED_DELIMITERS"):
            orig = orig_snippet or "<syntax error>"
            refactored = "# Fix syntax / closing delimiter around the reported line and re-run analysis"
            return self._pack(
                priority="P1 - Immediate",
                title="Resolve Source Syntax Error Preventing Compilation",
                problem_addressed=f"Unparseable syntax at {loc} in {f_file}.",
                why_recommended="Syntax errors prevent the module from loading and block deeper static analysis.",
                expected_benefit="Restores valid syntax so the module can compile, run, and be fully analyzed.",
                verification_instructions=f"Run 'python3 -m py_compile {f_file}' (or TypeScript/Node syntax check) and confirm exit code 0.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 19. Undefined Function or Variable Name (Python)
        if rkey == "PY_UNDEFINED_NAME":
            orig = orig_snippet or "printf('Hello World')"
            if any(k in orig.lower() for k in ("printf", "printdf", "println", "echo")):
                refactored = re.sub(r"\b(?:printf|printdf|println|echo)\b", "print", orig)
                rec_title = "Replace Undefined 'printf' with Standard Python 'print()'"
                why = (
                    "In Python, standard console output is provided by the built-in function 'print()'. "
                    "'printf' is not a standard Python built-in and will raise an unhandled NameError at runtime. "
                    "Replacing it with 'print()' ensures the statement executes correctly without crashing."
                )
            else:
                refactored = f"# Define or import the missing identifier before line {loc}\n{orig}"
                rec_title = f"Define or Import Undeclared Name: {primary.get('title', 'Undefined Symbol')}"
                why = (
                    "Referencing an undefined identifier raises a NameError at runtime. "
                    "Ensure the variable is initialized or the required module is imported before usage."
                )
            return self._pack(
                priority="P2 - High",
                title=rec_title,
                problem_addressed=f"Undeclared or undefined identifier at {loc} in {f_file}.",
                why_recommended=why,
                expected_benefit="Eliminates runtime NameError crash and satisfies Python symbol resolution.",
                verification_instructions="Re-run static analysis to confirm zero undefined-name diagnostics.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=refactored,
            )

        # 20. Missing Function Argument (Python)
        if rkey == "PY_MISSING_ARGUMENT":
            orig = orig_snippet or "func()"
            return self._pack(
                priority="P2 - High",
                title="Supply Missing Required Argument to Function Call",
                problem_addressed=f"Function call at {loc} in {f_file} lacks required positional arguments.",
                why_recommended=(
                    "The function signature defines mandatory positional arguments without default values. "
                    "Calling the function without these arguments raises a TypeError immediately upon execution."
                ),
                expected_benefit="Restores contract adherence and avoids TypeError crashes.",
                verification_instructions="Provide the required parameter value at the call site and verify test passes.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=f"{orig}  # Pass required parameters",
            )

        # 21. Undefined Identifier in JavaScript
        if rkey == "JS_UNDEFINED_NAME":
            orig = orig_snippet or "console.log(message)"
            return self._pack(
                priority="P2 - High",
                title="Declare or Import Undefined JavaScript Identifier",
                problem_addressed=f"Undeclared identifier at {loc} in {f_file}.",
                why_recommended="Using undeclared variables causes a runtime ReferenceError in strict mode.",
                expected_benefit="Ensures deterministic symbol scoping and prevents ReferenceError crashes.",
                verification_instructions="Declare variable with 'const' or 'let' or import from the appropriate module.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=f"const {orig} // declare with appropriate value",
            )

        # 22. TypeScript Type Mismatch
        if rkey == "TS_TYPE_MISMATCH":
            orig = orig_snippet or "let age: number = 'twenty';"
            return self._pack(
                priority="P2 - High",
                title="Resolve TypeScript Type Incompatibility",
                problem_addressed=f"Type contract violation at {loc} in {f_file}.",
                why_recommended="Assigning incompatible types violates compile-time type safety guarantees and triggers build failures.",
                expected_benefit="Restores type safety and enables clean TypeScript compilation without emit errors.",
                verification_instructions="Run 'npx tsc --noEmit' and confirm zero type diagnostics.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=f"{orig} // Align value type with declared type",
            )

        # 23. C Undeclared Identifier
        if rkey == "C_UNDECLARED_IDENTIFIER":
            orig = orig_snippet or "printf(\"Hello\\n\");"
            return self._pack(
                priority="P2 - High",
                title="Include Required Header or Declare C Identifier",
                problem_addressed=f"Undeclared identifier at {loc} in {f_file}.",
                why_recommended="C compilers require identifiers and functions to be declared or included via headers before invocation.",
                expected_benefit="Allows the C/C++ compiler to produce an executable object file.",
                verification_instructions="Add #include <stdio.h> or relevant header and re-run compilation.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig,
                refactored=f"#include <stdio.h>\n{orig}",
            )

        # 24. Logical Errors (Calculation, Comparison, Condition)
        if rkey.startswith("PY_LOGICAL_") or rkey == "PY_LOGICAL_ERROR":
            fn_label = primary.get("function_name") or "Function"
            if rkey == "PY_LOGICAL_CALCULATION":
                rec_title = f"Correct Calculation Formula / Denominator in '{fn_label}'"
                why = (
                    f"In calculating an average or mean in '{fn_label}', dividing by 'len(...) + 1' causes an off-by-one error "
                    "in the denominator that deflates the calculated result below the true mathematical mean. "
                    "Dividing by the exact collection length restores complete mathematical correctness."
                )
                benefit = "Restores accurate calculation results and expected arithmetic averages."
                refactored = re.sub(r"len\s*\(([^)]+)\)\s*\+\s*\d+", r"len(\1)", orig_snippet)
            elif rkey == "PY_LOGICAL_COMPARISON":
                rec_title = f"Invert Comparison Operator to Select Maximum/Topper in '{fn_label}'"
                why = (
                    f"Finding a maximum or topper in '{fn_label}' requires updating the tracking variable when the current element is greater "
                    "than the highest seen so far ('>'). Using '<' prevents tracking positive values and leaves the topper empty."
                )
                benefit = "Correctly identifies and returns the true topper/maximum candidate (e.g. Priya)."
                refactored = re.sub(r"\b<\b", ">", orig_snippet)
            elif rkey == "PY_LOGICAL_CONDITION":
                rec_title = f"Correct Threshold Condition in '{fn_label}'"
                why = (
                    f"When counting students who passed in '{fn_label}', the condition should check whether their score meets or exceeds "
                    "the threshold ('>='). Checking '<' counts failing students instead of passing students."
                )
                benefit = "Accurately counts all passing students meeting the passing criteria (e.g. 3 students)."
                refactored = re.sub(r"\b<\b", ">=", orig_snippet)
            else:
                rec_title = primary.get("title", "Resolve Algorithmic Logical Error")
                why = primary.get("description", "Resolves algorithmic defect identified by semantic analysis.")
                benefit = "Ensures the code produces correct outputs across all test cases."
                refactored = primary.get("suggested_next_step", "")

            return self._pack(
                priority="P2 - High",
                title=rec_title,
                problem_addressed=f"Algorithmic logic defect at {loc} in {f_file}.",
                why_recommended=why,
                expected_benefit=benefit,
                verification_instructions="Run automated test case verification to confirm actual outputs match expected results.",
                f_ids=f_ids,
                cause_ids=cause_ids,
                f_file=f_file,
                orig=orig_snippet,
                refactored=refactored,
            )

        # Fallback for any other genuine finding
        return self._pack(
            priority=default_prio,
            title=f"Remediate: {primary.get('title', 'Detected Issue')}",
            problem_addressed=f"{primary.get('description', 'Detected issue')} ({f_file}, {loc}).",
            why_recommended=primary.get("potential_consequences") or "Resolving this finding improves system reliability.",
            expected_benefit="Reduces operational risk identified by static analysis.",
            verification_instructions=primary.get("suggested_next_step") or "Verify fix with targeted unit tests.",
            f_ids=f_ids,
            cause_ids=cause_ids,
            f_file=f_file,
            orig=orig_snippet,
            refactored=primary.get("suggested_next_step") or "",
        )

    def _pack(
        self,
        priority: str,
        title: str,
        problem_addressed: str,
        why_recommended: str,
        expected_benefit: str,
        verification_instructions: str,
        f_ids: List[str],
        cause_ids: List[str],
        f_file: str,
        orig: str,
        refactored: str,
    ) -> Dict[str, Any]:
        diff = self._create_snippet_diff(orig, refactored, f_file) if orig and refactored else None
        return {
            "priority": priority,
            "title": title,
            "problem_addressed": problem_addressed,
            "why_recommended": why_recommended,
            "expected_benefit": expected_benefit,
            "verification_instructions": verification_instructions,
            "related_finding_ids": f_ids,
            "related_cause_ids": cause_ids,
            "file_path": f_file,
            "original_code": orig,
            "refactored_code": refactored,
            "diff": diff,
            "reviewed": False,
        }

    def _build_simple_explanation(
        self,
        rkey: str,
        rec: Dict[str, Any],
        primary: Dict[str, Any],
    ) -> Dict[str, str]:
        tpl = SIMPLE_EXPLANATION_TEMPLATES.get(rkey)
        if tpl:
            return dict(tpl)
        return {
            "what_is_wrong": primary.get("title") or rec["problem_addressed"],
            "why_problem": primary.get("potential_consequences") or "This pattern can make the application unreliable or slower.",
            "what_to_change": primary.get("suggested_next_step") or rec["title"],
            "how_it_helps": rec["expected_benefit"],
        }

    def _build_technical_explanation(
        self,
        rkey: str,
        rec: Dict[str, Any],
        primary: Dict[str, Any],
        group_findings: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        f_file = primary.get("file_path") or rec.get("file_path") or "unknown"
        loc = self._format_lines(group_findings)
        ev_cat = primary.get("evidence_category") or "Static Code Evidence"
        return {
            "problem_description": primary.get("description") or rec["problem_addressed"],
            "location": f"{f_file} ({loc})",
            "detection_method": primary.get("detection_method") or "Static AST Analysis",
            "root_cause_reasoning": rec["why_recommended"],
            "supporting_evidence": f"[{ev_cat}] {primary.get('evidence') or rec['problem_addressed']}",
            "impact": primary.get("potential_consequences") or rec["expected_benefit"],
            "implementation_details": primary.get("suggested_next_step") or rec["title"],
            "verification_instructions": rec.get("verification_instructions") or "Re-run static analysis and unit tests after applying the fix.",
            "uncertainty": (
                "Derived from static source inspection; runtime occurrence frequency depends on actual execution traffic and caller paths."
                if ev_cat == "Static Code Evidence"
                else "Corroborated with uploaded telemetry/log observations; verify end-to-end behavior in staging."
            ),
        }

    def _create_snippet_diff(self, original: str, refactored: str, file_path: str) -> str:
        orig_lines = [l if l.endswith("\n") else l + "\n" for l in original.splitlines(keepends=True)]
        ref_lines = [l if l.endswith("\n") else l + "\n" for l in refactored.splitlines(keepends=True)]
        diff = difflib.unified_diff(
            orig_lines,
            ref_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
        return "".join(diff)
