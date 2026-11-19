# InsightX — Comprehensive Technical & Architectural Guide

This document provides an exhaustive, in-depth technical explanation of the **InsightX** AI Root Cause & Decision Intelligence Platform. It details the underlying mathematical formulations, program analysis rules, multimodal causal correlation algorithms, decision recommendation synthesis, and Explainable AI (XAI) architecture.

---

## 1. System Vision & Architectural Workflow

InsightX is designed to solve the critical "alert-to-action" gap in software engineering and system operations. Traditional observability systems excel at alerting users to **symptoms** (e.g., elevated CPU, connection spikes, HTTP 504 timeouts), but fail to answer the critical questions:
- *Where is the defect located in the codebase?*
- *What is the underlying causal trigger?*
- *What evidence substantiates this diagnosis?*
- *What exact corrective action should be executed?*

InsightX unifies four sequential stages into a single continuous pipeline:

$$\mathbf{DETECT} \longrightarrow \mathbf{DIAGNOSE} \longrightarrow \mathbf{RECOMMEND} \longrightarrow \mathbf{EXPLAIN}$$

```
+-----------------------------------------------------------------------------------+
| 1. DETECT                                                                         |
|    - Static Program Analysis (Python AST, JS/TS Token Scanners)                   |
|    - Multivariate Telemetry Anomaly Detection (Isolation Forest, Z-Scores)       |
|    - Structured Log Event Extraction (RFC 5424 Log Parsing, Stack Traces)         |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 2. DIAGNOSE (Root Cause Analysis)                                                 |
|    - Cross-Modal Traceback Mapping (Matching log tracebacks to AST code lines)   |
|    - Temporal Lead-Lag Cross-Correlation (Precursor discovery)                    |
|    - Call & Import Dependency Graph Traversal (Blast radius calculation)          |
|    - Ranked Hypotheses with Calibrated Qualitative Confidence                     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 3. RECOMMEND                                                                      |
|    - Prioritized Interventions (P1 Immediate to P4 Low)                           |
|    - Non-Destructive Unified Code Refactoring Diffs (difflib.unified_diff)        |
|    - Objective Verification Runbooks and Test Procedures                          |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 4. EXPLAIN (Explainable AI)                                                       |
|    - Plain-Language Executive Diagnostic Narrative                                |
|    - Empirical Evidence Audit Checklist                                           |
|    - Explicit Analytical Assumptions and Uncertainty Disclosures                  |
|    - Contextual Progressive Disclosure ("i" Popovers answering 4 Core Questions)  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Mathematical Formulations & Statistical Methods

### 2.1. Multivariate Isolation Forest for Telemetry Drift
When multidimensional numeric time series are uploaded (e.g., CPU utilization, resident memory, P95 latency, active database connection counts), InsightX utilizes an ensemble of Isolation Trees to detect points that are structurally atypical:

1. **Isolation Tree Construction**: Given a dataset of $N$ observations, an Isolation Tree recursively partitions feature space by randomly selecting a feature $q$ and a split value $p \in [\min(q), \max(q)]$ until either:
   - The tree reaches a maximum height $h_{\max} = \lceil \log_2(N) \rceil$,
   - All sample instances are isolated, or
   - The sub-sample contains identical values.

2. **Anomaly Scoring**: For an observation $\mathbf{x}$, the path length $h(\mathbf{x})$ measures the number of edges traversed from the root node to an isolating leaf. The anomaly score $s(\mathbf{x}, N)$ is formulated as:
   $$s(\mathbf{x}, N) = 2^{-\frac{\mathbb{E}(h(\mathbf{x}))}{c(N)}}$$
   where $c(N)$ is the average path length of an unsuccessful search in a Binary Search Tree constructed over $N$ nodes:
   $$c(N) = 2\left(\ln(N - 1) + 0.5772156649\right) - \frac{2(N - 1)}{N}$$
   - Observations with $s(\mathbf{x}, N) \to 1.0$ exhibit significantly shorter path lengths and are marked as multivariate anomalies.
   - Observations with $s(\mathbf{x}, N) < 0.5$ follow nominal structural distributions.

### 2.2. Dynamic Rolling Baseline & Saturation Thresholds
To complement unsupervised isolation, InsightX implements rolling statistical control bounds:
- **Rolling Mean**: $\bar{x}_t^{(w)} = \frac{1}{w} \sum_{k=0}^{w-1} x_{t-k}$
- **Standard Deviation**: $\sigma_t^{(w)} = \sqrt{\frac{1}{w-1} \sum_{k=0}^{w-1} (x_{t-k} - \bar{x}_t^{(w)})^2}$
- **Z-Score Violation**: An alert is triggered when $|Z_t| = \frac{|x_t - \bar{x}_t^{(w)}|}{\sigma_t^{(w)}} > 2.5$.
- **Operational Saturation**: Absolute boundary violation is flagged when critical utilization metrics (e.g., CPU, Memory, Connection Pool Capacity) exceed $85\%$.

### 2.3. Temporal Lead-Lag Cross-Correlation for Causal Precedence
When an incident is flagged at timestamp $T$, InsightX determines which metric or component deviated first by computing normalized cross-correlation across temporal lag shifts $\tau \in [-K, +K]$:
$$r_{x, y}(\tau) = \frac{\sum_t (x_t - \bar{x})(y_{t+\tau} - \bar{y})}{\sqrt{\sum_t (x_t - \bar{x})^2 \sum_t (y_{t+\tau} - \bar{y})^2}}$$
- If the maximum cross-correlation occurs at $\tau < 0$, signal $x$ temporally precedes signal $y$, establishing quantitative evidence that $x$ is a candidate precursor to symptom $y$.
- For example, if message queue backlog surges at $\tau = -3$ ($\sim 90$ seconds before worker CPU spikes), the queue bottleneck is attributed as the causal ancestor rather than the downstream CPU saturation.

### 2.4. Directed Dependency Graph & Blast Radius
InsightX models service and code relationships as a directed graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$, where vertices $\mathcal{V}$ represent source modules, functions, or microservices, and directed edges $\mathcal{E}$ represent import, invocation, or data-flow dependencies:
$$\text{BlastRadius}(v_{\text{root}}) = \{u \in \mathcal{V} \mid \exists \text{ path } v_{\text{root}} \rightsquigarrow u \text{ in } \mathcal{G}\}$$
The blast radius score scales with the out-degree and transitive reachable descendants from the defect site, enabling engineers to prioritize issues located in foundational shared utilities over edge leaves.

### 2.5. Calibrated Qualitative Confidence Formulation
InsightX rejects arbitrary or ungrounded probability values (e.g. "94% root cause certainty"). Instead, the platform derives calibrated confidence scores from empirical evidence:
- **High Confidence ($0.90 - 0.98$)**: Directly substantiated by runtime log stack trace frames matching the exact AST code line.
- **Medium-High Confidence ($0.75 - 0.88$)**: Corroborated by cross-modal correlation (e.g., metric latency anomaly matching an asynchronous event-loop blocking call).
- **Medium Confidence ($0.65 - 0.74$)**: Derived from static structural code defect analysis prior to live incident verification.

---

## 3. Static Program Analysis Engine

The static analysis engine inspects code without executing it, ensuring safe ingestion of untrusted repositories.

### 3.1. Python AST Semantic Analysis
Using Python's standard `ast` module, InsightX parses source code into an abstract syntax tree and runs custom visitors (`ast.NodeVisitor`):

1. **Async Event-Loop Blocking (`visit_AsyncFunctionDef`)**:
   - *Pattern*: Synchronous blocking invocations (`time.sleep()`, `requests.get()`, `urllib.request.urlopen()`) located inside asynchronous coroutines (`async def`).
   - *Operational Impact*: Asyncio relies on single-threaded cooperative multitasking. Calling a synchronous blocking primitive freezes the entire event loop, preventing all concurrent network coroutines from progressing.
   - *Remediation*: Replace `time.sleep(n)` with `await asyncio.sleep(n)` and migrate synchronous HTTP calls to asynchronous clients like `httpx.AsyncClient`.

2. **Resource & Connection Handle Leaks (`visit_Call` & Text Lifecycle Scan)**:
   - *Pattern*: Database connections (`sqlite3.connect()`, pool handles) or file descriptors instantiated without an `ast.With` context manager or guaranteed `finally: conn.close()` cleanup.
   - *Operational Impact*: File descriptors or database connection pool slots remain open, starving the connection pool under continuous load.
   - *Remediation*: Wrap handles in context managers: `with db.connect() as conn:`.

3. **Concurrency Deadlocks (`visit_Call` & Lock Analysis)**:
   - *Pattern*: Explicit lock acquisition (`lock.acquire()`) lacking an exception-safe context manager (`with lock:`) or `finally: lock.release()`.
   - *Operational Impact*: If an unhandled exception occurs before `release()`, the mutex remains permanently acquired, causing permanent thread lockup.
   - *Remediation*: Refactor to `with lock:` context manager.

4. **Unguarded Arithmetic Divisions (`visit_BinOp`)**:
   - *Pattern*: Division operations where the denominator is either literal zero (`ast.Constant(0)`) or an unchecked variable accessed without a preceding guard (`if divisor == 0:`).
   - *Operational Impact*: Uncaught `ZeroDivisionError` causing sudden HTTP 500 crashes.
   - *Remediation*: Add guard validation before the operation.

5. **Mutable Default Arguments (`visit_FunctionDef`)**:
   - *Pattern*: Default argument containers using mutable types (`ast.List`, `ast.Dict`, `ast.Set`) in function signatures (`def process(audit_log=[])`).
   - *Operational Impact*: In Python, default arguments are evaluated once at module load time. Any state mutation persists across subsequent invocations, corrupting session state across user requests.
   - *Remediation*: Set default to `None` and initialize inside the function body: `if audit_log is None: audit_log = []`.

6. **SQL Injection Vulnerabilities (`visit_Call`)**:
   - *Pattern*: Dynamic query formatting using formatted string interpolation (`f"SELECT ... {user_id}"`) or string concatenation inside database execution calls.
   - *Operational Impact*: Remote attackers can manipulate query logic or exfiltrate database records.
   - *Remediation*: Convert to parameterized queries: `cursor.execute("SELECT ... WHERE id = ?", (user_id,))`.

7. **Dangerous Dynamic Evaluation (`visit_Call`)**:
   - *Pattern*: Invocation of dynamic evaluation primitives (`eval()`, `exec()`).
   - *Operational Impact*: Remote Code Execution (RCE) vulnerabilities.
   - *Remediation*: Replace with safe literal parsers like `ast.literal_eval()`.

8. **Hardcoded Secrets & Credential Exposure**:
   - *Pattern*: Plaintext API keys, passwords, and tokens matched via high-entropy token analysis.
   - *Operational Impact*: Credential leakage upon repository commitment.
   - *Remediation*: Extract tokens into environment variables (`os.environ.get`). Credentials are automatically masked in the UI.

9. **Unbounded In-Memory Collection Growth**:
   - *Pattern*: Continuous `.append()` or `.extend()` into global or module-scoped collections without a maximum capacity, ring buffer, or eviction TTL.
   - *Operational Impact*: Monotonic heap memory accumulation leading to OOM kills.
   - *Remediation*: Replace with `collections.deque(maxlen=N)` or an LRU cache.

### 3.2. JavaScript & TypeScript Static Analysis
1. **Synchronous File I/O in Event Loop**: Detection of `fs.readFileSync` or `fs.writeFileSync` in request handler functions.
2. **Dynamic Code Injection**: Detection of `eval()` and `new Function()` invocations.
3. **Prototype Pollution**: Detection of assignments to `__proto__` or `constructor.prototype`.
4. **Silent Empty Catch Blocks**: Detection of `catch (err) {}` blocks that swallow exceptions without logging or re-throwing.

---

## 4. Multimodal Correlation & Causal Inference

InsightX's core innovation is connecting heterogeneous signals across code, logs, and metrics into a cohesive diagnosis:

```
+-------------------+      +---------------------+      +---------------------+
| Static AST Defect |      |  Runtime Log Event  |      |   Telemetry Metric  |
| (line 21, sleep)  | <--> | (stack trace frame) | <--> | (latency > 5000ms)  |
+-------------------+      +---------------------+      +---------------------+
          \                           |                           /
           \                          |                          /
            v                         v                         v
     +-----------------------------------------------------------------+
     |                  Causal Root Cause Diagnosis                    |
     |  "Blocking call in payment_service.py:21 caused latency spike"  |
     |         Confidence: High (0.96) | Rank: #1                      |
     +-----------------------------------------------------------------+
```

### 4.1. Traceback-to-AST Line Mapping
When application logs contain exception stack traces (e.g., Python Tracebacks or Node.js error frames), InsightX extracts:
- Target file path: `payment_service.py`
- Line number: `21`
- Function name: `process_payment`
- Exception type: `TimeoutError` or `ZeroDivisionError`

The engine scans the findings repository for static defects identified in that file within $\pm 5$ lines of the crash site. When a match occurs, the hypothesis confidence is upgraded to **High (0.96)** with the classification: **Confirmed Runtime Crash**.

### 4.2. Metric-to-Code Bottleneck Correlation
When metrics demonstrate saturation (e.g., P95 latency surging from 45ms to 5,200ms) and the code analyzer detects an event loop blocking call (`time.sleep` in async context), the engine establishes cross-modal correlation:
- Symptom: Latency saturation.
- Root Cause: Event loop starved of CPU cycles by synchronous blocking primitive.
- Confidence: **High (0.88)**.

---

## 5. Recommendation Engine & Automated Diff Synthesis

InsightX generates prioritized corrective actions with clear operational runbooks:

1. **Priority Ordering**:
   - **P1 - Immediate**: Runtime crashes, thread deadlocks, active event-loop blocking, SQL injection.
   - **P2 - High**: Database connection leaks, memory leaks, mutable defaults, prototype pollution.
   - **P3 - Medium**: Missing outbound request timeouts, broad exception handling.
   - **P4 - Low**: Informational maintainability warnings.

2. **Unified Diff Generation**:
   The engine generates exact unified diffs using standard patch formatting:
   ```diff
   --- a/payment_service.py
   +++ b/payment_service.py
   @@ -18,4 +18,4 @@
   -    time.sleep(2.5)
   +    await asyncio.sleep(2.5)
   ```
   Users can review before/after comparisons, copy suggested code changes with one click, and mark recommendations as reviewed.

---

## 6. Explainable AI (XAI) & Information Architecture

InsightX ensures total transparency by eliminating black-box opacity.

### 6.1. The 4-Question Progressive Disclosure Model
Every contextual information button ("i") in the application opens a structured drawer answering:
1. **What does this mean?**: Clear definition in simple engineering terms.
2. **How does InsightX calculate or determine it?**: Exact formula, parser rule, or statistical method used.
3. **Why is it important?**: Practical operational and architectural consequences.
4. **What are its limitations?**: Known edge cases, data gaps, or boundary conditions.

### 6.2. Empirical Evidence Audit Trail
Every diagnosis links back to verified evidence:
- AST Defect: File path, line number, exact code snippet.
- Metric Deviation: Exact timestamp, observed value, baseline mean, anomaly score.
- Log Event: Log level, message, occurrence count, timestamp.

---

## 7. Safety, Security & Data Isolation Guarantees

InsightX treats all uploaded repositories as untrusted:
1. **Zero Code Execution**: Uploaded source code is parsed purely into syntactic tokens and Abstract Syntax Trees. Code is never imported, invoked, or executed.
2. **Zip Slip Prevention**: Archives are validated against path traversal (`../`, absolute paths, leading slashes).
3. **Automated Secret Masking**: Credentials, JWTs, and API tokens are masked (`sk****78`) before rendering in UI views or exporting reports.
4. **Deterministic Local Execution**: The engine operates 100% locally using SQLite, pandas, and scikit-learn without mandatory external network calls.
