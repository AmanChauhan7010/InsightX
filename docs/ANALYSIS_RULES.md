# InsightX — Analysis Rules, Severity Policy & Root-Cause Methodology

This document is the authoritative engineering specification for InsightX's static code rules, control-flow/data-flow detection methods, deterministic severity assignment policy, explicit evidence categories, explainable health score formula, and root-cause ranking methodology.

---

## 1. Supported Languages

InsightX only advertises languages for which real analyzers are implemented:

| Language | File Extensions | Primary Analyzer | Technique |
| :--- | :--- | :--- | :--- |
| **Python** | `.py` | `PythonCodeAnalyzer` | Multi-pass Python `ast` parser, parent-annotated AST traversal, symbol tables, loop/exception control-flow analysis, and intra-procedural data-flow tracking |
| **JavaScript** | `.js`, `.jsx`, `.mjs`, `.cjs` | `JavaScriptCodeAnalyzer` | Delimiter balance check, comment-aware lexical/structural pattern analysis, and CommonJS/ESModule import extraction |
| **TypeScript** | `.ts`, `.tsx` | `JavaScriptCodeAnalyzer` | Same static structural analysis and module relationship extraction tailored for TypeScript syntax |

Auxiliary telemetry analyzers:
- **System Metrics** (`.csv`, `.json`): `MetricAnomalyAnalyzer` (Z-score $\ge 2.5\sigma$, utilization saturation $> 85\%$, and multivariate Isolation Forest when $N \ge 10$ and $D \ge 2$).
- **Application Logs** (`.log`, `.txt`): `LogAnalyzer` (RFC 5424 / unstructured log severity extraction, Python traceback file/line/function frame parsing, and message consolidation).

---

## 2. Implemented Static Code Rules

### 2.1 Python Rules (`PythonCodeAnalyzer`)

| Rule ID | Title / Defect Pattern | Detection Approach | Default Severity |
| :--- | :--- | :--- | :--- |
| `PY_SYNTAX_ERROR` | Syntax Error / Parsing Failure | `ast.parse()` exception location & message | **Critical** |
| `PY_CONST_ZERO_DIV` | Constant Division by Zero | AST `BinOp` (`Div`/`FloorDiv`/`Mod`) with literal `0` divisor | **Critical** |
| `PY_SQL_INJECTION` | SQL Injection Vulnerability | AST `Call` to `execute`/`executemany`/`raw_query` with `JoinedStr` (f-string), `BinOp` (`+`/`%`), or `.format()` | **Critical** |
| `PY_DANGEROUS_EVAL` | Dangerous Dynamic Code Execution (`eval`/`exec`) | AST `Call` to builtin `eval()` / `exec()` | **Critical** |
| `PY_UNSAFE_LOCK` | Unsafe Lock Acquisition / Deadlock Hazard | AST `Call` to `*.acquire()` outside `with` and without `try...finally: *.release()` in scope | **Critical** |
| `PY_ASYNC_BLOCKING_SLEEP` | Blocking Synchronous Sleep in `async def` | AST `Call` to `time.sleep()` or unawaited non-`asyncio` `sleep()` directly inside `AsyncFunctionDef` (excludes nested sync `def` and `await asyncio.sleep()`) | **High** |
| `PY_ASYNC_BLOCKING_HTTP` | Synchronous Network Call in `async def` | AST `Call` to `requests.*` or `urllib.request.urlopen` directly inside `AsyncFunctionDef` | **High** |
| `PY_UNBOUNDED_RETRY` | Potential Infinite Retry Loop Without Bound or Backoff | AST `While` control-flow analysis across `while True:` and flag-guarded retry loops (`while not done:`), including `try` nested inside `if`/`with`, detecting broad or silently swallowed exception handlers with no retry counter/deadline exit or backoff | **High** |
| `PY_UNBOUNDED_RETRY_INSPECT` | Unbounded Retry Loop Lacking Maximum Attempt Limit | AST `While` broad-exception retry loop that includes logging and backoff but has no explicit attempt cap (flagged for inspection) | **Medium** |
| `PY_UNCONTROLLED_LOOP` | Uncontrolled Infinite Loop (`while True` without exit or throttle) | AST `While(True)` lacking `break`, `return`, `raise`, `yield`, `await`, or blocking consumer/throttle calls | **High** |
| `PY_UNAWAITED_COROUTINE` | Unawaited Coroutine Call / Collection / Assignment | Two-pass AST symbol table of local/class/nested `async def`, async aliases (`fn = async_fn`), local class instance methods (`svc = Service(); svc.async_op()`), and stdlib async funcs + intra-procedural data-flow tracking of `await` and scheduling APIs (`create_task`, `gather`, `wait`, `wait_for`, `run`, `ensure_future`, `shield`, `as_completed`) | **High** |
| `PY_UNAWAITED_COROUTINE_RETURN` | Unawaited Coroutine Returned from Synchronous Function | Multi-statement sync `def` returning a confirmed async call without `Coroutine`/`Awaitable` return annotation | **Medium** |
| `PY_UNCLOSED_RESOURCE` | Unclosed Resource Descriptor / Connection Leak | AST `Call` to `open()` or `*connect()` outside `with`/`async with` without `try...finally: *.close()` in scope | **High** |
| `PY_UNBOUNDED_COLLECTION` | Unbounded In-Memory Collection Growth | AST module-level `[]`/`{}`/`set()` mutated via `.append`/`.extend`/`.add`/`.update` with no `pop`/`clear`/`del`/slice eviction anywhere in module | **High** |
| `PY_UNSAFE_DESERIALIZATION` | Potential Unsafe Deserialization (`pickle` / `marshal` / unsafe `yaml.load`) | AST `Call` inspecting `pickle.load(s)`, `marshal.load(s)`, and `yaml.load()` without `SafeLoader`/`CSafeLoader` (does not flag `yaml.safe_load`) | **High** |
| `PY_SUBPROCESS_SHELL` | Suspicious Shell Command Execution (`shell=True` / `os.system`) | AST `Call` inspecting `subprocess.*(..., shell=True)` and `os.system()` (does not flag `shell=False`) | **High** |
| `PY_HARDCODED_SECRET` | Hardcoded Credential / Secret Exposure | AST `Assign`/`AnnAssign` matching credential identifiers assigned a plaintext string literal ($\ge 8$ chars, non-placeholder); masked in output | **High** |
| `PY_MUTABLE_DEFAULT` | Mutable Default Argument in Function Definition | AST `FunctionDef`/`AsyncFunctionDef` default parameter inspecting `ast.List`, `ast.Dict`, or `ast.Set` | **High** |
| `PY_SILENT_EXCEPT` | Silent Exception Suppression (`except Exception: pass`) | AST `ExceptHandler` catching `Exception`/`BaseException` whose body is solely `[ast.Pass]` | **Medium** |
| `PY_BARE_EXCEPT` | Bare `except:` Clause Masks System Failures | AST `ExceptHandler` with `type is None` | **Medium** |
| `PY_MISSING_TIMEOUT` | Missing Network Request Timeout | AST `Call` to `requests.*` / `http_client.*` omitting `timeout` keyword argument | **Medium** |
| `PY_UNGUARDED_DIV` | Unguarded Division by Variable | AST `BinOp` division by a variable without an intra-procedural zero check (`if`/`assert`), non-zero constant binding, or `try...except ZeroDivisionError` | **Medium** |

### 2.2 JavaScript & TypeScript Rules (`JavaScriptCodeAnalyzer`)

| Rule ID | Title / Defect Pattern | Default Severity |
| :--- | :--- | :--- |
| `JS_UNBALANCED_DELIMITERS` | Unbalanced Structural Delimiters | **Critical** |
| `JS_DANGEROUS_EVAL` | Dynamic Code Injection (`eval()` / `new Function()`) | **Critical** |
| `JS_SQL_INJECTION` | SQL / Query Injection via Template Interpolation or Concatenation | **Critical** |
| `JS_BLOCKING_FS` | Blocking Synchronous Filesystem I/O (`fs.*Sync`) | **High** |
| `JS_HARDCODED_SECRET` | Hardcoded Secret / Token Exposure (masked) | **High** |
| `JS_PROTOTYPE_POLLUTION` | Prototype Pollution Hazard (`__proto__` / `constructor.prototype`) | **High** |
| `JS_EMPTY_CATCH` | Silent Error Suppression in Empty Catch Block | **Medium** |
| `JS_MISSING_TIMEOUT` | Unbounded HTTP Request Without Timeout / `AbortSignal` | **Medium** |

---

## 3. Deterministic Severity Policy

Severity is assigned deterministically by `SeverityPolicy` (`backend/app/services/scoring.py`) and paired with a human-readable `severity_rationale` on every finding:

- **Critical**: Reserved strictly for:
  1. Unconditional parse or execution failure (`PY_SYNTAX_ERROR`, `JS_UNBALANCED_DELIMITERS`, `PY_CONST_ZERO_DIV`).
  2. Directly exploitable high-impact security flaws (`PY_SQL_INJECTION`, `JS_SQL_INJECTION`, `PY_DANGEROUS_EVAL`, `JS_DANGEROUS_EVAL`).
  3. Exception-unsafe mutex lock deadlock hazards (`PY_UNSAFE_LOCK`).
  4. **Dynamic Elevation**: A `High` or `Medium` static defect that is directly corroborated by an uploaded runtime crash traceback in Combined Mode is elevated to `Critical` with an explicit audit note.
- **High**: Significant concurrency, retry-hang, coroutine-execution, resource-leak, memory-growth, or credential-exposure defects detected statically (including `time.sleep()` inside `async def` by default in code-only mode).
- **Medium**: Moderate resiliency or error-visibility risks whose runtime impact depends on external network conditions or caller input validation (missing HTTP timeouts, silent/bare `except`, unguarded variable division, logged+backoff unbounded retries).
- **Low / Informational**: Maintainability warnings and contextual inspection notes.

---

## 4. Explicit Evidence Categories

Every finding, root cause, and audit checklist item carries one of five explicit evidence categories—never conflating static inspection with runtime proof:

1. **`Static Code Evidence`**: Derived exclusively from parsing and static inspection of uploaded source files. Does not prove the issue executed in production.
2. **`Log Evidence`**: Derived from error, warning, or critical entries present in uploaded application log files.
3. **`Metrics Evidence`**: Derived from statistical Z-score or Isolation Forest deviations in uploaded CSV/JSON system telemetry.
4. **`Runtime Evidence`**: Derived from genuine execution stack traces/tracebacks present in uploaded runtime logs.
5. **`Correlated Evidence`**: Assigned only when two or more independent evidence sources converge (e.g., an AST finding matched to a runtime traceback frame, or async blocking aligned with latency metric spikes / timeout logs).

---

## 5. Root-Cause Ranking & Consistency Method

`RootCauseEngine` (`backend/app/rca/engine.py`) adheres to strict analytical invariants:

1. **Zero-Finding Clean State**: When an analysis detects 0 code findings, 0 metric anomalies, 0 actionable (`ERROR`/`CRITICAL`) log events, and 0 stack traces, InsightX returns **0 root causes** and **0 recommendations**. No generic placeholder hypotheses are generated.
2. **Evidence-Grounded Linkage**: Every code-backed root cause references real active-analysis Finding UUIDs; every recommendation references both active Finding UUIDs and active Root Cause UUIDs.
3. **Structured Six-Part Explanation**: Each hypothesis explains:
   - What was detected and why it can happen (`description`)
   - Classification (`Static Potential Cause`, `Deterministic Static Defect`, `Correlated Potential Cause`, `Confirmed Runtime Incident`, `Observed Runtime Incident`, `Metric Observation Hypothesis`, or `Observed Log Incident`)
   - Supporting evidence (`evidence_summary` + `evidence_category`)
   - Potential consequences (`consequences`)
   - Missing evidence and alternative explanations (`missing_evidence`, `alternative_explanations`)
   - Corrective action direction (`recommended_actions_summary`)
4. **Qualitative Confidence & Deterministic Ranking**:
   - Confidence is displayed strictly qualitatively (`High`, `Medium`, `Low`)—no fabricated root-cause probability percentages are presented.
   - Ranking priority order:
     1. Static finding + matching runtime stack trace (**Confirmed Runtime Incident**, `Correlated Evidence`, `High`)
     2. Unmatched runtime stack trace (**Observed Runtime Incident**, `Runtime Evidence`, `High`)
     3. Static finding corroborated by matching metric anomaly or timeout/pool logs (**Correlated Potential Cause**, `Correlated Evidence`, `High`)
     4. Deterministic static defects (syntax error, literal zero division) and critical security surfaces (`Static Code Evidence`, `High`)
     5. Static concurrency, unbounded retry, unawaited coroutine, resource leak, and memory growth hypotheses (`Static Code Evidence`, `Medium`)
     6. Metric-only or log-only anomalies (`Metrics Evidence` / `Log Evidence`, `Medium`)
     7. Standalone resiliency/error-handling static gaps (`Static Code Evidence`, `Low`)

---

## 6. Explainable Health Score Formula

`HealthScoreCalculator` (`backend/app/services/scoring.py`) computes a deterministic 0–100 score and stores the full breakdown in `analysis.meta_info.score_breakdown`:

- **Baseline**: `100.0`. A score of `100/100` explicitly means **"No issues detected by the enabled analysis rules"**—it does **not** certify the code is bug-free.
- **Severity Base Weights**: `Critical = 18`, `High = 10`, `Medium = 5`, `Low = 2`, `Informational = 0`.
- **Duplicate Diminishing Returns**: Findings are grouped by `(file_path, rule_id)`. The 1st occurrence applies `100%` weight; occurrences 2–4 apply `35%` weight; further duplicates in the same file apply `0%` marginal deduction.
- **Multi-File Scale Normalization**: For single-file uploads (`files_count == 1`), scale factor is `1.0`. For multi-file repositories (`files_count > 1`), non-Critical penalties are multiplied by $1 / (1 + 0.15 \cdot \log_2(\text{files\_count}))$, while `Critical` penalties are never diluted.
- **Telemetry & Log Penalties**: Deduplicated metric anomalies (capped at `-15`) and log severity groups (capped at `-20`) apply only when logs/metrics are provided.

---

## 7. Known Limitations

- **Intra-Procedural Scope for Unawaited Coroutines**: Coroutine tracking analyzes definitions within the same file (module-level functions, class methods, nested functions, and known `asyncio` stdlib functions). Imported third-party async functions defined in external packages not included in the upload cannot be confirmed as async without type stubs and are intentionally not guessed to prevent false positives.
- **Dynamic Control Flow & Reflection**: `getattr()`, dynamic imports (`importlib`), decorators that alter synchronous/asynchronous signatures at runtime, or external caller-side resource cleanup (`conn.close()` in a separate un-uploaded file) cannot be resolved purely statically.
- **JavaScript/TypeScript Parser Granularity**: The JS/TS analyzer currently uses comment-aware lexical/structural rules rather than a full TypeScript compiler AST, so complex multi-line JS control-flow constructs have lower precision than the Python AST engine.
- **Static Non-Execution Guarantee**: InsightX never executes user-submitted code; therefore, business logic correctness, runtime input distributions, and full security penetration testing are outside static coverage.
