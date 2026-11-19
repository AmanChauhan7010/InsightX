# InsightX Analysis Methodology & Detection Rules

InsightX implements deterministic, evidence-backed diagnostic intelligence. This document formalizes the algorithms, mathematical models, and static analysis rules powering the engine.

---

## 1. Multimodal Anomaly Detection (Time-Series Telemetry)

### Dynamic Statistical Threshold Saturation
For each time series metric $x_t \in \mathbf{x}_t$, the baseline mean $\mu$ and standard deviation $\sigma$ are calculated:
$$\mu = \frac{1}{N} \sum_{i=1}^N x_i, \quad \sigma = \sqrt{\frac{1}{N} \sum_{i=1}^N (x_i - \mu)^2}$$

An anomaly event is triggered if:
$$\left|\frac{x_t - \mu}{\sigma}\right| > 2.5 \quad \text{or} \quad x_t > \tau_{\text{sat}}$$
where $\tau_{\text{sat}} = 85\%$ for processor or memory utilization metrics.

### Multivariate Isolation Forest
When multi-dimensional metrics ($\ge 2$ numeric dimensions, $\ge 10$ observations) are uploaded:
1. Feature matrix $X \in \mathbb{R}^{N \times D}$ is cleaned and imputed.
2. An ensemble of 100 Isolation Trees is constructed using recursive random partitioning:
   $$s(x, n) = 2^{-\frac{\mathbb{E}(h(x))}{c(n)}}$$
   where $h(x)$ is path length and $c(n)$ is average path length of unsuccessful searches in a Binary Search Tree.
3. Points with $s(x, n) > 0.5$ (decision function $< 0$) are isolated as multidimensional anomaly events.

---

## 2. Static Code Analysis Engine

### Python AST Visitor Rules
1. **Async Event Loop Blocking**:
   - `time.sleep()` invoked within `ast.AsyncFunctionDef`.
   - Synchronous network I/O (`requests.get`, `urllib.request`) inside async coroutines.
2. **Resource Descriptor & Connection Leaks**:
   - `open()`, `sqlite3.connect()`, or database handles instantiated without an `ast.With` context manager or a guaranteed `finally: close()` block.
3. **Concurrency & Threading Deadlocks**:
   - Explicit `mutex.acquire()` invoked without exception-safe `with mutex:` or `finally: mutex.release()`.
4. **Arithmetic Crashes**:
   - Constant division by zero (`ast.Constant(0)` in `ast.BinOp`).
   - Division by variable `/ y` lacking preceding `if y == 0:` guard.
5. **State Retention / Mutable Default Arguments**:
   - `def fn(arg=[])` or `def fn(arg={})` evaluated once at module load time.
6. **SQL Injection Vulnerabilities**:
   - Dynamic query execution using formatted f-strings or string concatenation in cursor calls.
7. **Dangerous Code Execution**:
   - Dynamic execution of arbitrary strings via `eval()` or `exec()`.
8. **Hardcoded Secrets & Credential Exposure**:
   - Plaintext API keys, passwords, and tokens matched via entropy analysis and masked in all UI views.
9. **Unbounded In-Memory Collection Growth**:
   - Continuous `.append()` into global or module-scoped lists/dicts without ring buffer (`collections.deque(maxlen=N)`) or expiration TTL.
10. **Missing Network Request Timeouts**:
    - Outbound HTTP requests without explicit connect/read timeouts.
11. **Bare Except Clauses & Silent Error Suppression**:
    - `except:` or `except Exception: pass` concealing critical faults.

### JavaScript & TypeScript Static Rules
1. **Synchronous Blocking I/O**:
   - `fs.readFileSync` or `fs.writeFileSync` executed in Node.js event loop thread.
2. **Code Injection**:
   - Dynamic evaluation via `eval()` or `new Function()`.
3. **Prototype Pollution**:
   - Assignment to `__proto__` or `constructor.prototype`.
4. **SQL / Query Injection**:
   - Template string interpolation `${...}` in raw query execution.
5. **Silent Catch Blocks**:
   - Empty `catch (e) {}` blocks suppressing runtime errors.

---

## 3. Causal Root Cause Localization

The RCA engine ranks candidate causes by combining:
1. **Runtime Traceback Proof (Weight: 1.0, Confidence: High > 0.90)**:
   A runtime stack trace actively confirms the execution of an AST static defect.
2. **Cross-Modal Telemetry Correlation (Weight: 0.85, Confidence: High 0.75-0.88)**:
   A system metric anomaly (e.g. latency spike > 4000ms) aligns temporally with a code bottleneck (e.g. async event loop sleep).
3. **Static Structural Severity (Weight: 0.70, Confidence: Medium 0.70)**:
   Critical AST defect identified in source code prior to runtime incidents.
4. **Dependency Blast Radius**:
   Computes downstream caller modules impacted by the defect using the directed call graph.

---

## 4. Remediation & Unified Diff Generation
For every actionable finding, the engine:
1. Formulates the engineering rationale and expected benefit.
2. Synthesizes a refactored code replacement.
3. Generates a standard unified diff using `difflib.unified_diff`.
4. Specifies non-destructive verification instructions.
