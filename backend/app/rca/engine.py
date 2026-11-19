import os
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from backend.app.services.scoring import EvidenceCategory, SeverityPolicy


class RootCauseEngine:
    """
    Multimodal Causal Root Cause Localization Engine.

    Correlates static AST findings, runtime stack traces, application log errors,
    and time-series metric anomalies to formulate ranked, evidence-backed hypotheses.

    Strict guarantees:
    - Zero findings and zero telemetry/log incidents produce ZERO root causes (no placeholders).
    - Every hypothesis references genuine findings, log events, or metric anomalies.
    - Explicitly distinguishes Static Potential Causes from Correlated/Confirmed Runtime Causes.
    - Answers: What was detected, Why it can happen, Supporting evidence, Consequences,
      Alternative explanations, Missing evidence, and Corrective action direction.
    """

    def diagnose(
        self,
        findings: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        metric_anomalies: List[Dict[str, Any]] = None,
        log_issues: List[Dict[str, Any]] = None,
        stack_traces: List[Dict[str, Any]] = None,
        mode: str = "code",
    ) -> List[Dict[str, Any]]:
        metric_anomalies = metric_anomalies or []
        log_issues = log_issues or []
        stack_traces = stack_traces or []

        # Early clean exit: no defects and no telemetry/log incident evidence -> 0 root causes
        actionable_log_issues = [
            l for l in log_issues if (l.get("level") or "").upper() in ("CRITICAL", "ERROR")
        ]
        if not findings and not metric_anomalies and not actionable_log_issues and not stack_traces:
            return []

        hypotheses: List[Dict[str, Any]] = []
        matched_finding_ids: Set[str] = set()

        # Helper to extract function name hints from findings or relationships
        def extract_functions(f_list: List[Dict[str, Any]]) -> List[str]:
            fns: List[str] = []
            for f in f_list:
                # Check title for quoted function name, e.g. Async Function 'foo'
                m = re.search(r"Function '([a-zA-Z0-9_]+)'", f.get("title", ""))
                if m and m.group(1) not in fns:
                    fns.append(m.group(1))
                # Check description for `async def foo` or `function 'foo'`
                m2 = re.search(r"(?:async def|function) '?([a-zA-Z0-9_]+)'?", f.get("description", ""))
                if m2 and m2.group(1) not in fns:
                    fns.append(m2.group(1))
            return fns

        def fmt_lines(f_list: List[Dict[str, Any]]) -> str:
            parts = []
            for f in f_list[:4]:
                ln = f.get("line_number")
                le = f.get("line_end")
                if ln and le and le > ln:
                    parts.append(f"L{ln}-L{le}")
                elif ln:
                    parts.append(f"L{ln}")
            return ", ".join(parts) if parts else "module scope"

        # ------------------------------------------------------------------
        # 1. Correlate Runtime Stack Traces with Static Code Findings (Highest Rank)
        # ------------------------------------------------------------------
        matched_traces: Set[int] = set()
        for t_idx, trace in enumerate(stack_traces):
            trace_file = os.path.basename(trace.get("file_path") or "")
            trace_line = trace.get("line_number")
            trace_exc = trace.get("exception_type", "RuntimeError")
            trace_msg = trace.get("message", "")
            trace_fn = trace.get("function_name")

            matched = []
            for f in findings:
                f_file = os.path.basename(f.get("file_path") or "")
                f_line = f.get("line_number")
                if f_file and f_file == trace_file and (
                    trace_line is None or f_line is None or abs(f_line - trace_line) <= 5
                ):
                    matched.append(f)

            if matched:
                matched_traces.add(t_idx)
                primary = matched[0]
                for m_f in matched:
                    fid = m_f.get("id") or m_f.get("title", "")
                    matched_finding_ids.add(fid)
                    # Upgrade matched finding's evidence category & runtime confirmation!
                    m_f["evidence_category"] = EvidenceCategory.CORRELATED
                    m_f["is_confirmed"] = True
                    new_sev, new_rat = SeverityPolicy.elevate_for_runtime_confirmation(
                        m_f.get("severity", "High"),
                        m_f.get("severity_rationale") or "",
                        trace_exc,
                    )
                    m_f["severity"] = new_sev
                    m_f["severity_rationale"] = new_rat

                affected_fns = [trace_fn] if trace_fn else extract_functions(matched)
                hypotheses.append({
                    "title": f"Confirmed Runtime Crash: {trace_exc} Correlated with Static Defect in {trace_file}",
                    "description": (
                        f"Uploaded runtime traceback recorded '{trace_exc}: {trace_msg}' at {trace_file}:{trace_line or primary.get('line_number')}. "
                        f"This aligns directly with the statically detected flaw '{primary['title']}', explaining why execution failed on this path."
                    ),
                    "confidence": "High",
                    "confidence_score": 0.96,
                    "evidence_category": EvidenceCategory.CORRELATED,
                    "cause_type": "Confirmed Runtime Incident",
                    "affected_files": sorted({m["file_path"] for m in matched}),
                    "affected_functions": affected_fns,
                    "related_finding_ids": [m.get("id") or m.get("title", "") for m in matched],
                    "evidence_summary": (
                        f"Correlated Evidence: Runtime stack frame ({trace_file}:{trace_line}) matches static AST finding "
                        f"'{primary['title']}' ({primary['file_path']}:{primary.get('line_number')})."
                    ),
                    "ranking_rationale": (
                        "Ranked highest because two independent evidence sources—uploaded runtime stack trace and static AST "
                        "inspection—converge on the exact same file and line."
                    ),
                    "consequences": primary.get("potential_consequences") or f"Active {trace_exc} crash disrupting request execution.",
                    "recommended_actions_summary": primary.get("suggested_next_step") or "Remediate the correlated code defect and add regression tests.",
                    "missing_evidence": "Distributed request context or full traffic volume to quantify total impacted users.",
                    "alternative_explanations": "Upstream invalid payload or environmental timeout may have triggered this defective code branch.",
                })

        # ------------------------------------------------------------------
        # 2. Correlate Code Findings with Metrics / Logs or Synthesize Static Causal Mechanisms
        # ------------------------------------------------------------------
        has_latency_anomaly = any(
            "latency" in a.get("metric_name", "").lower() or "response" in a.get("metric_name", "").lower()
            for a in metric_anomalies
        )
        has_cpu_anomaly = any("cpu" in a.get("metric_name", "").lower() for a in metric_anomalies)
        has_mem_anomaly = any("mem" in a.get("metric_name", "").lower() for a in metric_anomalies)
        has_conn_anomaly = any(
            "db" in a.get("metric_name", "").lower() or "connection" in a.get("metric_name", "").lower()
            for a in metric_anomalies
        )
        has_timeout_logs = any(
            "timeout" in (l.get("message") or "").lower() or "504" in (l.get("message") or "")
            for l in log_issues
        )
        has_conn_logs = any(
            "pool" in (l.get("message") or "").lower() or "connection" in (l.get("message") or "").lower()
            for l in log_issues
        )

        # Group remaining findings by (causal_bucket, file_path) so explanations synthesize root mechanisms
        # instead of merely repeating each finding's title.
        def causal_bucket(f: Dict[str, Any]) -> str:
            rule = f.get("rule_id") or ""
            cat = f.get("category") or ""
            if rule in ("PY_ASYNC_BLOCKING_SLEEP", "PY_ASYNC_BLOCKING_HTTP", "JS_BLOCKING_FS") or "Event Loop" in cat:
                return "event_loop_blocking"
            if rule in ("PY_UNAWAITED_COROUTINE", "PY_UNAWAITED_COROUTINE_RETURN") or "Coroutine" in cat:
                return "unawaited_coroutine"
            if rule in ("PY_UNBOUNDED_RETRY", "PY_UNBOUNDED_RETRY_INSPECT", "PY_UNCONTROLLED_LOOP") or "Control Flow" in cat:
                return "unbounded_retry_or_loop"
            if rule in ("PY_UNCLOSED_RESOURCE", "PY_UNSAFE_LOCK") or "Resource" in cat or "Concurrency" in cat:
                return "resource_or_lock_lifecycle"
            if rule in ("PY_UNBOUNDED_COLLECTION", "PY_MUTABLE_DEFAULT") or "Memory" in cat:
                return "memory_state_growth"
            if rule in ("PY_SQL_INJECTION", "PY_DANGEROUS_EVAL", "PY_HARDCODED_SECRET", "JS_DANGEROUS_EVAL", "JS_SQL_INJECTION", "JS_HARDCODED_SECRET", "JS_PROTOTYPE_POLLUTION") or "Security" in cat:
                return "security_exposure"
            if rule in ("PY_MISSING_TIMEOUT", "JS_MISSING_TIMEOUT") or "Network" in cat:
                return "network_resiliency"
            if rule in ("PY_BARE_EXCEPT", "PY_SILENT_EXCEPT", "JS_EMPTY_CATCH") or "Error Handling" in cat:
                return "error_suppression"
            if rule in (
                "PY_SYNTAX_ERROR", "JS_UNBALANCED_DELIMITERS", "PY_CONST_ZERO_DIV", "PY_UNGUARDED_DIV",
                "PY_UNDEFINED_NAME", "PY_MISSING_ARGUMENT", "JS_UNDEFINED_NAME", "TS_TYPE_MISMATCH",
                "C_UNDECLARED_IDENTIFIER", "C_COMPILER_ERROR",
            ) or "Syntax" in cat or "Arithmetic" in cat or "Undefined" in cat or "Type" in cat:
                return "execution_failure"
            return "general_static_defect"

        buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for f in findings:
            fid = f.get("id") or f.get("title", "")
            if fid in matched_finding_ids:
                continue
            key = (causal_bucket(f), f.get("file_path", "unknown"))
            buckets.setdefault(key, []).append(f)

        for (bucket, f_path), b_findings in buckets.items():
            base_file = os.path.basename(f_path)
            f_ids = [f.get("id") or f.get("title", "") for f in b_findings]
            lines_str = fmt_lines(b_findings)
            fns = extract_functions(b_findings)
            sev_set = {f.get("severity", "Medium") for f in b_findings}

            if bucket == "event_loop_blocking":
                correlated = has_latency_anomaly or has_timeout_logs
                if correlated:
                    for f in b_findings:
                        f["evidence_category"] = EvidenceCategory.CORRELATED
                ev_cat = EvidenceCategory.CORRELATED if correlated else EvidenceCategory.STATIC_CODE
                cause_type = "Correlated Potential Cause" if correlated else "Static Potential Cause"
                conf = "High" if correlated else "Medium"
                score = 0.88 if correlated else 0.72
                hypotheses.append({
                    "title": f"Event-Loop Starvation Risk from Synchronous Blocking in {base_file}",
                    "description": (
                        f"Synchronous blocking calls ({', '.join(sorted({f['title'] for f in b_findings}))}) were detected inside "
                        f"asynchronous execution paths at {base_file} ({lines_str}). Because an async event loop cooperatively "
                        "multiplexes all tasks on a single thread, blocking calls pause scheduling for every concurrent request "
                        "until the synchronous operation finishes."
                    ),
                    "confidence": conf,
                    "confidence_score": score,
                    "evidence_category": ev_cat,
                    "cause_type": cause_type,
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": (
                        f"Static Code Evidence at {f_path} ({lines_str})"
                        + (
                            f" corroborated by {'latency metric spikes' if has_latency_anomaly else 'timeout log errors'}."
                            if correlated
                            else ". No runtime logs or latency metrics were provided to confirm production occurrence."
                        )
                    ),
                    "ranking_rationale": (
                        "Elevated because static event-loop blocking aligns with observed latency/timeout telemetry."
                        if correlated
                        else "Ranked by high structural concurrency impact; static analysis alone indicates a potential cause rather than a confirmed runtime outage."
                    ),
                    "consequences": "Escalating request queue depth, P99 latency spikes, and cascading gateway timeouts under concurrent traffic.",
                    "recommended_actions_summary": "Replace blocking calls with non-blocking async equivalents (e.g., await asyncio.sleep(), httpx.AsyncClient, or fs.promises).",
                    "missing_evidence": (
                        "Per-request APM event-loop lag traces to measure exact blocking duration in production."
                        if not correlated
                        else "Distributed trace spans linking specific caller endpoints to the blocking call."
                    ),
                    "alternative_explanations": "Observed latency (if any) could also stem from upstream database slowness, network congestion, or host CPU throttling; in low-concurrency scripts, blocking impact may remain minimal.",
                })

            elif bucket == "unbounded_retry_or_loop":
                correlated = has_cpu_anomaly or has_timeout_logs
                if correlated:
                    for f in b_findings:
                        f["evidence_category"] = EvidenceCategory.CORRELATED
                ev_cat = EvidenceCategory.CORRELATED if correlated else EvidenceCategory.STATIC_CODE
                cause_type = "Correlated Potential Cause" if correlated else "Static Potential Cause"
                conf = "High" if correlated else "Medium"
                score = 0.86 if correlated else 0.71
                hypotheses.append({
                    "title": f"Non-Terminating Retry / Loop Execution Hazard in {base_file}",
                    "description": (
                        f"Loop control-flow analysis in {base_file} ({lines_str}) identified an unbounded loop without a retry cap "
                        "or deterministic termination guard. When an underlying dependency fails persistently or an exception is "
                        "silently swallowed without backoff, control flow repeats indefinitely instead of failing fast."
                    ),
                    "confidence": conf,
                    "confidence_score": score,
                    "evidence_category": ev_cat,
                    "cause_type": cause_type,
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": (
                        f"Static control-flow evidence in {f_path} ({lines_str}): unbounded 'while True' loop lacking attempt limit/backoff"
                        + (" correlated with CPU/timeout telemetry." if correlated else ".")
                    ),
                    "ranking_rationale": (
                        "Correlated with elevated CPU or timeout telemetry indicating loop saturation."
                        if correlated
                        else "Ranked for high operational hang risk; persistent errors in this loop prevent graceful recovery."
                    ),
                    "consequences": "Indefinite task hang, worker exhaustion, 100% CPU core spin, or retry storms amplifying downstream outages.",
                    "recommended_actions_summary": "Enforce a bounded retry limit, exponential backoff with jitter, structured error logging, and exception propagation after max retries.",
                    "missing_evidence": "Runtime execution traces or loop iteration telemetry confirming whether failures actually recur on this path.",
                    "alternative_explanations": "The loop may be intended as a long-lived background worker if external cancellation or process supervision terminates it.",
                })

            elif bucket == "unawaited_coroutine":
                hypotheses.append({
                    "title": f"Skipped Async Execution Due to Unawaited Coroutine Objects in {base_file}",
                    "description": (
                        f"AST symbol and data-flow analysis in {base_file} ({lines_str}) detected calls to confirmed 'async def' "
                        "functions whose returned coroutine objects are neither awaited nor passed to a scheduler (such as "
                        "asyncio.create_task() or asyncio.gather()). In Python, invoking an async function merely constructs a "
                        "coroutine object without running its body."
                    ),
                    "confidence": "Medium",
                    "confidence_score": 0.70,
                    "evidence_category": EvidenceCategory.STATIC_CODE,
                    "cause_type": "Static Potential Cause",
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": f"Static Code Evidence at {f_path} ({lines_str}): confirmed async callee invoked without await or scheduling API.",
                    "ranking_rationale": "High likelihood of silent functional bug because unawaited coroutines never execute their underlying logic.",
                    "consequences": "Operations are silently skipped, collections contain raw coroutine objects instead of resolved data, and Python emits RuntimeWarning.",
                    "recommended_actions_summary": "Await the coroutine inside an 'async def' function, aggregate via 'await asyncio.gather(*tasks)', or execute via 'asyncio.run()' at a sync boundary.",
                    "missing_evidence": "Runtime execution logs or unit test output confirming whether callers outside this file await the returned objects.",
                    "alternative_explanations": "External callers in another module not included in this analysis could intentionally await the returned coroutine collection.",
                })

            elif bucket == "resource_or_lock_lifecycle":
                correlated = has_conn_anomaly or has_conn_logs
                if correlated:
                    for f in b_findings:
                        f["evidence_category"] = EvidenceCategory.CORRELATED
                ev_cat = EvidenceCategory.CORRELATED if correlated else EvidenceCategory.STATIC_CODE
                cause_type = "Correlated Potential Cause" if correlated else "Static Potential Cause"
                conf = "High" if correlated else "Medium"
                score = 0.85 if correlated else 0.69
                hypotheses.append({
                    "title": f"Resource Descriptor Leak or Lock Contention Risk in {base_file}",
                    "description": (
                        f"Resource or synchronization primitives in {base_file} ({lines_str}) are acquired without context managers "
                        "('with') or guaranteed 'finally' cleanup. If an exception or early return occurs before explicit cleanup, "
                        "handles or mutex locks remain held."
                    ),
                    "confidence": conf,
                    "confidence_score": score,
                    "evidence_category": ev_cat,
                    "cause_type": cause_type,
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": (
                        f"Static Code Evidence at {f_path} ({lines_str})"
                        + (" correlated with connection/pool telemetry." if correlated else " showing unguarded resource/lock lifecycle.")
                    ),
                    "ranking_rationale": (
                        "Correlated with active connection exhaustion telemetry."
                        if correlated
                        else "Resource leaks and unsafe mutex acquisition compound over process uptime and cause cascading exhaustion."
                    ),
                    "consequences": "File descriptor exhaustion ('Too many open files'), database connection pool starvation, or thread deadlock.",
                    "recommended_actions_summary": "Use Python context managers ('with open(...)', 'with conn:', 'with lock:') to guarantee deterministic cleanup on all exit paths.",
                    "missing_evidence": "OS file descriptor metrics (lsof/ulimit) or connection-pool saturation telemetry over sustained uptime.",
                    "alternative_explanations": "Callers in another module may close returned handles via a wrapper, or CPython reference counting may mask leaks under low error rates.",
                })

            elif bucket == "memory_state_growth":
                correlated = has_mem_anomaly
                if correlated:
                    for f in b_findings:
                        f["evidence_category"] = EvidenceCategory.CORRELATED
                ev_cat = EvidenceCategory.CORRELATED if correlated else EvidenceCategory.STATIC_CODE
                cause_type = "Correlated Potential Cause" if correlated else "Static Potential Cause"
                conf = "High" if correlated else "Medium"
                score = 0.84 if correlated else 0.67
                hypotheses.append({
                    "title": f"Progressive Memory / Shared State Accumulation in {base_file}",
                    "description": (
                        f"State-retention hazards in {base_file} ({lines_str})—such as unbounded module-level collections or "
                        "mutable default arguments—allow data to accumulate indefinitely across calls without eviction or isolation."
                    ),
                    "confidence": conf,
                    "confidence_score": score,
                    "evidence_category": ev_cat,
                    "cause_type": cause_type,
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": f"Static Code Evidence at {f_path} ({lines_str}) indicating unbounded state growth or shared mutable defaults.",
                    "ranking_rationale": "Unbounded heap growth and cross-request state retention degrade stability over long-running service lifetimes.",
                    "consequences": "Steadily climbing RAM consumption, garbage-collection pauses, Out-Of-Memory (OOM) kills, or cross-request data leakage.",
                    "recommended_actions_summary": "Use bounded collections (collections.deque(maxlen=N) / LRU cache) and immutable None sentinel defaults.",
                    "missing_evidence": "Longitudinal heap/RSS memory telemetry or memory profiler snapshots (tracemalloc).",
                    "alternative_explanations": "If the process is short-lived (e.g., a batch CLI script), memory accumulation may exit before causing OOM.",
                })

            elif bucket == "security_exposure":
                is_crit = "Critical" in sev_set
                hypotheses.append({
                    "title": f"Security Injection or Credential Exposure Surface in {base_file}",
                    "description": (
                        f"Static security inspection of {base_file} ({lines_str}) identified high-risk security patterns "
                        f"({', '.join(sorted({f['title'] for f in b_findings}))}). Dynamically constructed queries/code or "
                        "embedded plaintext secrets widen the application's attack surface."
                    ),
                    "confidence": "High" if is_crit else "Medium",
                    "confidence_score": 0.80 if is_crit else 0.68,
                    "evidence_category": EvidenceCategory.STATIC_CODE,
                    "cause_type": "Static Potential Cause",
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": f"Static Code Evidence at {f_path} ({lines_str}): {len(b_findings)} security finding(s) detected via AST/pattern inspection.",
                    "ranking_rationale": "Prioritized due to severe confidentiality/integrity impact if untrusted input or repository access occurs.",
                    "consequences": "Unauthorized data access, SQL injection, arbitrary code execution, or leaked credentials.",
                    "recommended_actions_summary": "Switch to parameterized queries, eliminate eval/exec, and move credentials to environment variables or a secrets manager.",
                    "missing_evidence": "Data-flow reachability from external HTTP/user inputs and runtime access logs to confirm exploitability.",
                    "alternative_explanations": "Inputs reaching these calls may be strictly internal or pre-sanitized by an upstream layer not visible in the uploaded files.",
                })

            elif bucket == "execution_failure":
                is_deterministic = any(
                    f.get("rule_id") in (
                        "PY_SYNTAX_ERROR", "PY_CONST_ZERO_DIV", "JS_UNBALANCED_DELIMITERS",
                        "PY_UNDEFINED_NAME", "PY_MISSING_ARGUMENT", "JS_UNDEFINED_NAME",
                        "TS_TYPE_MISMATCH", "C_UNDECLARED_IDENTIFIER", "C_COMPILER_ERROR",
                    )
                    for f in b_findings
                )
                hypotheses.append({
                    "title": f"{'Deterministic Parse/Execution Failure' if is_deterministic else 'Potential Runtime Arithmetic Exception'} in {base_file}",
                    "description": (
                        f"Static analysis of {base_file} ({lines_str}) detected "
                        f"{', '.join(sorted({f['title'] for f in b_findings}))}. "
                        + (
                            "This structural defect fails unconditionally when parsed or executed."
                            if is_deterministic
                            else "Without explicit input validation guards, zero or invalid inputs will trigger unhandled runtime exceptions."
                        )
                    ),
                    "confidence": "High" if is_deterministic else "Medium",
                    "confidence_score": 0.82 if is_deterministic else 0.60,
                    "evidence_category": EvidenceCategory.STATIC_CODE,
                    "cause_type": "Deterministic Static Defect" if is_deterministic else "Static Potential Cause",
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": f"Static Code Evidence at {f_path} ({lines_str}) directly from parser/AST inspection.",
                    "ranking_rationale": (
                        "Ranked high because parser/constant-folding guarantees failure when reached."
                        if is_deterministic
                        else "Potential exception path lacking local defensive validation."
                    ),
                    "consequences": "Immediate startup failure or unhandled runtime exception aborting the operation.",
                    "recommended_actions_summary": "Resolve syntax errors or add explicit zero/input validation guards before division.",
                    "missing_evidence": "Runtime execution traces confirming whether zero values can actually be supplied by callers.",
                    "alternative_explanations": "Callers or database constraints may guarantee non-zero denominators outside the inspected function." if not is_deterministic else "None for syntax/literal zero defects.",
                })

            elif bucket in ("network_resiliency", "error_suppression", "general_static_defect"):
                correlated = (bucket == "network_resiliency" and (has_timeout_logs or has_latency_anomaly))
                if correlated:
                    for f in b_findings:
                        f["evidence_category"] = EvidenceCategory.CORRELATED
                ev_cat = EvidenceCategory.CORRELATED if correlated else EvidenceCategory.STATIC_CODE
                cause_type = "Correlated Potential Cause" if correlated else "Static Potential Cause"
                title_map = {
                    "network_resiliency": f"Unbounded Network Wait / Timeout Resiliency Gap in {base_file}",
                    "error_suppression": f"Error Observability Loss from Suppressed Exceptions in {base_file}",
                    "general_static_defect": f"Static Reliability Defect Cluster in {base_file}",
                }
                desc_map = {
                    "network_resiliency": f"Outbound HTTP calls in {base_file} ({lines_str}) omit explicit timeout bounds, allowing hung upstream peers to stall sockets indefinitely.",
                    "error_suppression": f"Exception handlers in {base_file} ({lines_str}) catch broadly and discard errors silently, obscuring runtime failure signals.",
                    "general_static_defect": f"Static inspection identified {len(b_findings)} reliability issue(s) in {base_file} ({lines_str}).",
                }
                hypotheses.append({
                    "title": title_map[bucket],
                    "description": desc_map[bucket],
                    "confidence": "High" if correlated else "Low",
                    "confidence_score": 0.80 if correlated else 0.55,
                    "evidence_category": ev_cat,
                    "cause_type": cause_type,
                    "affected_files": [f_path],
                    "affected_functions": fns,
                    "related_finding_ids": f_ids,
                    "evidence_summary": f"{ev_cat} at {f_path} ({lines_str}): {', '.join(f['title'] for f in b_findings[:3])}.",
                    "ranking_rationale": (
                        "Correlated with uploaded timeout/latency incident evidence."
                        if correlated
                        else "Ranked below critical/high defects because impact depends on external network behavior or fault frequency."
                    ),
                    "consequences": (
                        "Worker thread lockup and socket exhaustion when external APIs become unresponsive."
                        if bucket == "network_resiliency"
                        else "Hidden runtime failures, silent data corruption, and prolonged incident diagnosis."
                    ),
                    "recommended_actions_summary": b_findings[0].get("suggested_next_step") or "Apply defensive resiliency and structured error logging.",
                    "missing_evidence": "Production network latency logs or error telemetry confirming active impact.",
                    "alternative_explanations": "Default transport timeouts configured at a proxy/session layer, or intentional best-effort fallback logic.",
                })

        # ------------------------------------------------------------------
        # 3. Unmatched Runtime Stack Traces (Log/Runtime Evidence Without Matching Code Finding)
        # ------------------------------------------------------------------
        for t_idx, trace in enumerate(stack_traces):
            if t_idx in matched_traces:
                continue
            t_file = trace.get("file_path") or "unknown"
            t_line = trace.get("line_number")
            t_exc = trace.get("exception_type", "RuntimeError")
            t_msg = trace.get("message", "")
            hypotheses.append({
                "title": f"Observed Runtime Exception: {t_exc} in {os.path.basename(t_file)}",
                "description": (
                    f"Uploaded logs contain an explicit runtime traceback for '{t_exc}: {t_msg}' at {t_file}:{t_line or '?'}. "
                    "No matching static AST finding was found at that line (source file may not have been uploaded or the failure is data-dependent)."
                ),
                "confidence": "High",
                "confidence_score": 0.90,
                "evidence_category": EvidenceCategory.RUNTIME,
                "cause_type": "Observed Runtime Incident",
                "affected_files": [t_file] if t_file != "unknown" else [],
                "affected_functions": [trace.get("function_name")] if trace.get("function_name") else [],
                "related_finding_ids": [],
                "evidence_summary": f"Runtime Evidence: Traceback frame at {t_file}:{t_line or '?'} raising {t_exc}.",
                "ranking_rationale": "Direct runtime exception recorded in uploaded logs.",
                "consequences": f"Active {t_exc} interrupting request/job completion.",
                "recommended_actions_summary": "Inspect the referenced file and line with full input context and add defensive validation or error handling.",
                "missing_evidence": "Matching source file contents for static code correlation.",
                "alternative_explanations": "External environment, schema mismatch, or transient runtime data corruption.",
            })

        # ------------------------------------------------------------------
        # 4. Metric-Only or Log-Only RCA (When Telemetry/Logs Show Real Anomalies Without Code Hypotheses)
        # ------------------------------------------------------------------
        if not hypotheses and metric_anomalies:
            anom_counts: Dict[str, int] = {}
            for a in metric_anomalies:
                m_name = a["metric_name"].split(" ")[0]
                anom_counts[m_name] = anom_counts.get(m_name, 0) + 1
            top_metric = max(anom_counts, key=anom_counts.get)
            hypotheses.append({
                "title": f"Telemetry Saturation Anomaly ({top_metric})",
                "description": (
                    f"Statistical and multivariate anomaly detection flagged {len(metric_anomalies)} anomalous observations "
                    f"across uploaded metrics, concentrated in '{top_metric}' ({anom_counts[top_metric]} events)."
                ),
                "confidence": "Medium",
                "confidence_score": 0.76,
                "evidence_category": EvidenceCategory.METRICS,
                "cause_type": "Metric Observation Hypothesis",
                "affected_files": [],
                "affected_functions": [],
                "related_finding_ids": [],
                "evidence_summary": f"Metrics Evidence: {anom_counts[top_metric]} abnormal observations in '{top_metric}' (Z-score >= 2.5 or Isolation Forest outlier).",
                "ranking_rationale": "Dominant anomalous dimension across uploaded time-series metrics.",
                "consequences": "Service degradation, queuing delays, or resource saturation during the anomaly window.",
                "recommended_actions_summary": "Correlate the anomaly timestamps with application source code, deployment events, and service logs.",
                "missing_evidence": "Application source code and error logs to localize the code-level cause of the metric spike.",
                "alternative_explanations": "External traffic surge, scheduled batch workload, or infrastructure scaling event.",
            })

        if not hypotheses and actionable_log_issues:
            top_log = max(actionable_log_issues, key=lambda l: l.get("count", 1))
            hypotheses.append({
                "title": f"Recurring Operational Log Failure ({top_log.get('level', 'ERROR')})",
                "description": (
                    f"Uploaded logs contain {len(actionable_log_issues)} distinct error/critical event groups, "
                    f"led by '{top_log['message'][:120]}' (observed {top_log.get('count', 1)} time(s))."
                ),
                "confidence": "Medium",
                "confidence_score": 0.72,
                "evidence_category": EvidenceCategory.LOG,
                "cause_type": "Observed Log Incident",
                "affected_files": [top_log["file_path"]] if top_log.get("file_path") else [],
                "affected_functions": [],
                "related_finding_ids": [],
                "evidence_summary": f"Log Evidence: [{top_log.get('level')}] repeated {top_log.get('count', 1)} time(s) in service '{top_log.get('service') or 'app'}'.",
                "ranking_rationale": "Highest frequency severe log event observed in uploaded logs.",
                "consequences": "Degraded service reliability or failed customer requests.",
                "recommended_actions_summary": "Upload the corresponding source code and metrics to correlate these log failures to specific functions.",
                "missing_evidence": "Source code files and infrastructure metrics to isolate the underlying code defect.",
                "alternative_explanations": "Transient third-party dependency failure or network blip.",
            })

        # Sort hypotheses deterministically by ranking score descending, then title
        hypotheses.sort(key=lambda x: (-x["confidence_score"], x["title"]))

        for idx, h in enumerate(hypotheses, 1):
            h["rank"] = idx

        return hypotheses
