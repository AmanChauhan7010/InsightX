<div align="center">

# ⚡ InsightX v2.0 — AI Root Cause & Decision Intelligence Platform

### *From alerts and bugs to verifiable solutions — detect, diagnose, auto-fix, and explain.*

[![Build & Verification](https://img.shields.io/badge/build-passing-brightgreen.svg?style=flat-square)](https://github.com)
[![Pytest Coverage](https://img.shields.io/badge/backend%20tests-104%2F104%20passed%20(100%25)-success?style=flat-square)](https://pytest.org)
[![Vitest Coverage](https://img.shields.io/badge/frontend%20tests-11%2F11%20passed%20(100%25)-success?style=flat-square)](https://vitest.dev)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg?style=flat-square)](https://python.org)
[![React Version](https://img.shields.io/badge/react-18.3.1-61dafb.svg?style=flat-square)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/typescript-5.7-blue.svg?style=flat-square)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI%20%2B%20SQLAlchemy-009688.svg?style=flat-square)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Academic Project](https://img.shields.io/badge/DA--IICT-MSc%20Data%20Science%20Innovation-orange.svg?style=flat-square)](https://www.daiict.ac.in)

**A unified, explainable decision-intelligence platform combining multi-layer static program analysis, intelligent logical error detection, sandbox test verification, multivariate telemetry anomaly detection, causal root-cause localization, and automated code remediation.**

[Architecture Guide](docs/ARCHITECTURE.md) • [Analysis Rules & Policy](docs/ANALYSIS_RULES.md) • [Test Results](docs/TEST_RESULTS.md) • [REST API Reference](docs/API.md) • [Technical Deep Dive](EXPLANATION.md) • [Research Paper](paper/insightx_research_paper.md)

</div>

---

## 📌 Executive Summary

Modern software systems suffer from two major operational and engineering challenges:
1. **Production Incidents (The Observability Gap)**: Distributed microservices flood on-call engineers with hundreds of noisy symptom alerts (high CPU, HTTP 504 timeouts, dropped requests). Traditional APMs detect that *something is broken*, but cannot determine *which line of code broke it* or *how to fix it*.
2. **Silent Logical Errors & Complex Code Defect Remediation**: Code frequently passes syntax checks, linters, and executes cleanly with exit code `0`, yet produces incorrect business results due to off-by-one errors, inverted conditional logic, incorrect comparison operators, or faulty formulas. When defects are discovered, developers are left to manually patch and re-verify without automated guidance.

```
Traditional Workflow: [Symptom Alert / Bug] --> [Manual Log Digging] --> [Guesswork Patch] --> (MTTR: 30-90 min)
InsightX v2.0:        [Multimodal Ingestion] --> [AST + Logical Test]  --> [1-Click Auto-Fix] --> (MTTR: < 2 min)
```

**InsightX bridges this gap** by combining:
- **Multi-Layer Static Code Analysis** (Python AST, Ruff linter diagnostics, JS/TS, C/C++)
- **Intelligent Logical Error Detection & Sandbox Verification** (detects code that runs cleanly but gives wrong answers)
- **Automated Test Synthesizer** (generates edge, boundary, and normal test cases to empirically confirm bugs)
- **Multivariate Telemetry Anomaly Detection** (Isolation Forest + dynamic Z-score saturation)
- **Causal Root Cause Analysis (RCA)** (lead-lag cross-correlation + topology blast radius mapping)
- **Real Automatic Code Remediation (Auto-Fix Engine)** (generates surgical patches, applies them to working copies, verifies with re-analysis, and persists revision history)
- **Explainable AI (XAI)** (executive forensic narratives, evidence audit checklists, and contextual progressive disclosures)

---

## 📊 Platform Capabilities Matrix

| Capability Dimension | Prometheus / Grafana | Datadog / Dynatrace | Traditional Linters | **InsightX v2.0** |
| :--- | :---: | :---: | :---: | :---: |
| **Telemetry Ingestion** | Metrics Only | Metrics + Logs + APM | None | **Metrics + Logs + Multi-Language Code** |
| **Independent Code Scan** | ❌ No | ❌ No | ✅ Single files | **✅ Single File, ZIP Repo, or Pasted Snippet** |
| **Basic Linter & Undefined Symbol Catch** | ❌ No | ❌ No | ✅ Yes | **✅ Multi-Layer (AST + Ruff + Symbols)** |
| **Logical Error Detection (Exit 0 Bugs)** | ❌ No | ❌ No | ❌ No | **✅ Detects Wrong Math, Inverted `<` / `>`, Loop Offsets** |
| **Automated Sandbox Test Verification** | ❌ No | ❌ No | ❌ No | **✅ Subprocess Sandbox + Actual vs Expected Output** |
| **Causal Root-Cause Localization** | Manual | Basic Correlation | ❌ None | **✅ Stack Trace Correlation + Lead-Lag Precursors** |
| **Automated Code Remediation** | ❌ None | ❌ None | Limited / Rule-only | **✅ Surgical AST Auto-Fix with Unified Diffs** |
| **Persistent Revision Tracking** | ❌ None | ❌ None | ❌ None | **✅ Immutable Revisions (v1 -> v2 -> v3) with Deltas** |
| **Explainable AI (XAI) & Audit Trail** | ❌ None | Limited Dashboards | ❌ None | **✅ Evidence Audit Trail + 4-Question Disclosures** |

---

## 🏗️ System Architecture

InsightX v2.0 is built as a modular monorepo featuring a high-performance **FastAPI backend** and a modern **React 18 + TypeScript frontend**:

```
Creative/
|-- frontend/                       # React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, Recharts
|   |-- src/
|   |   |-- types/                  # Typed schemas (Analysis, Finding, RootCause, Recommendation, etc.)
|   |   |-- services/               # Centralized typed API client & 4-Question Info registry
|   |   |-- components/ui/          # Accessible primitives (Badge, Card, Button, Modal, InfoButton, CodeEditor)
|   |   |-- components/layout/      # Responsive Sidebar, Navbar, Application Shell
|   |   |-- features/
|   |   |   |-- dashboard/          # Page 1: Overview Dashboard, KPI cards & Recent Diagnoses
|   |   |   |-- upload/             # Page 2: New Analysis Workspace (Files, ZIPs, Pasted Snippet)
|   |   |   |-- findings/           # Page 3: Filterable Analysis Results & Inspector with Test Details
|   |   |   |-- root-cause/         # Page 4: Root Cause Explorer & Topology Graph
|   |   |   |-- recommendations/    # Page 5: Recommendations, Auto-Fix, Apply Fix & Diff Viewer
|   |   |   |-- evidence/           # Page 6: XAI Narrative & Evidence Audit Trail
|   |   |   |-- reports/            # Page 7: History Archive & Report Exporter (Markdown/JSON)
|   |   |-- App.tsx                 # Main application state container
|   |   |-- App.test.tsx            # Vitest suite (11 comprehensive tests)
|   |-- vite.config.ts              # Vite proxy & test config
|   |-- tailwind.config.js          # Design system color tokens & typography
|
|-- backend/                        # Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, SQLite, Ruff, scikit-learn
|   |-- app/
|   |   |-- main.py                 # FastAPI application lifespan & CORS middleware
|   |   |-- core/                   # App configuration & SQLite database engine
|   |   |-- models/                 # SQLAlchemy ORM models (Analysis, Finding, RootCause, Recommendation)
|   |   |-- schemas/                # Pydantic v2 request/response contracts
|   |   |-- services/               # Ingestion, Scoring, and AnalysisOrchestrator
|   |   |-- analyzers/
|   |   |   |-- code/               # Python AST (20+ rules), Ruff linter, JS/TS & C/C++ analyzers
|   |   |   |-- logical/            # Logical Error Detector, Test Synthesizer, Runner & Verifier
|   |   |   |-- metrics/            # Isolation Forest & dynamic Z-score saturation
|   |   |   |-- logs/               # RFC 5424 log parser & stack-trace correlator
|   |   |-- autofix/                # Modular remediation engine (Registry, Patch Generator, Applier, Reanalyzer)
|   |   |-- rca/                    # Causal cross-modality localization & hypothesis ranking
|   |   |-- recommendations/        # Action prioritization (P1-P4) & unified diff engine
|   |   |-- explanations/           # Explainable AI (XAI) narrative & uncertainty auditor
|   |   |-- reports/                # Structured JSON & Markdown dossier generators
|   |   |-- api/v1/                 # Documented REST API endpoints
|   |-- tests/                      # Pytest suite (104 unit, integration, and E2E tests)
|   |-- requirements.txt
|
|-- sample_data/                    # Real-world test artifacts
|   |-- code/                       # payment_service.py, worker.js, sample_project.zip
|   |-- logs/                       # production_timeouts.log (RFC 5424 logs & tracebacks)
|   |-- metrics/                    # system_telemetry.csv (CPU spike & latency saturation)
|
|-- docs/                           # Architecture, API, rules, and test documentation
|-- paper/                          # Academic IEEE conference research paper & LaTeX sources
|-- run_app.sh                      # Unified local launch script
|-- docker-compose.yml              # Containerized multi-service deployment
```

---

## ⚡ The 5-Stage Decision Intelligence Pipeline

```
  +---------------------------------------------------------------------------------------------------+
  | 1. MULTI-LAYER INGESTION & DETECTION                                                               |
  |    • Multi-Language AST Analysis (Python, JS/TS, C/C++)                                           |
  |    • Ruff Linter & Symbol Scope Analysis (undefined functions, name errors, syntax traps)          |
  |    • Intelligent Logical Error Detection (calculation bugs, inverted conditions, off-by-one)     |
  |    • Isolation Forest Metric Anomaly Detection & RFC 5424 Log Stack-Trace Ingestion               |
  +-------------------------------------------------+-------------------------------------------------+
                                                    |
                                                    v
  +---------------------------------------------------------------------------------------------------+
  | 2. AUTOMATED SANDBOX TEST VERIFICATION                                                            |
  |    • Synthesizes normal, edge-case, and boundary test harnesses                                   |
  |    • Executes code in an isolated subprocess sandbox (`IsolatedCodeRunner`) with 2.0s timeout     |
  |    • Compares Actual Output vs Expected Output to confirm defect presence before flagging         |
  +-------------------------------------------------+-------------------------------------------------+
                                                    |
                                                    v
  +---------------------------------------------------------------------------------------------------+
  | 3. CAUSAL ROOT CAUSE ANALYSIS (RCA)                                                               |
  |    • Maps runtime stack-traces directly to AST code nodes                                         |
  |    • Temporal Lead-Lag Cross-Correlation discovers true causal precursors                         |
  |    • Ranks root-cause hypotheses with calibrated qualitative confidence (High, Med-High, Medium)  |
  +-------------------------------------------------+-------------------------------------------------+
                                                    |
                                                    v
  +---------------------------------------------------------------------------------------------------+
  | 4. DECISION RECOMMENDATIONS & AUTO-FIX REMEDIATION                                                |
  |    • Prioritizes actions across severity tiers (P1 Immediate to P4 Low)                           |
  |    • Generates AST-aware surgical patches and unified diffs (`difflib`)                           |
  |    • 1-Click "Auto Fix" applies patches to working copies, re-analyzes, and saves revision (v2)   |
  |    • Runs re-analyzed code through automated test harnesses to verify test passes and delta       |
  +-------------------------------------------------+-------------------------------------------------+
                                                    |
                                                    v
  +---------------------------------------------------------------------------------------------------+
  | 5. EXPLAINABLE AI (XAI) & AUDIT DOSSIER                                                           |
  |    • Executive Diagnostic Narrative (What happened? Why does it matter? What to do?)              |
  |    • Verifiable Evidence Audit Trail linking findings to line numbers and timestamps              |
  |    • Interactive "i" popovers answering 4 core progressive disclosure questions                   |
  +---------------------------------------------------------------------------------------------------+
```

---

## 🔍 Key Detection Engines Explained

### 1. Multi-Layer Static Code Analyzer
- **Syntax & Language Validation**: Rejects malformed files cleanly, giving exact line numbers and syntax explanations.
- **Ruff Linting & Symbol Resolution**: Detects undefined variables, invalid built-ins (e.g. `printf("hello")` instead of `print`), missing imports, and unused symbols.
- **Python AST Visitor (20+ rules)**:
  - *Event Loop Blocking*: Synchronous `time.sleep()` or synchronous network I/O (`requests.get`) inside `async def`.
  - *Unclosed Resources*: File handles or SQLite connections opened without context managers (`with`).
  - *Concurrency Deadlocks*: Mutex `.acquire()` calls lacking safe `with lock:` or `finally: lock.release()`.
  - *Unchecked Division / ZeroDivisionError*: Unguarded divisions without denominator validation.
  - *Security Deficiencies*: Dynamic SQL injection via f-strings, dangerous `eval()`/`exec()`, hardcoded secrets (automatically masked).
  - *Infinite Retry Loops*: `while True` blocks with swallowed exceptions and missing delay or exit condition.
- **C / C++ Static Scanner**: Identifies dangerous buffer operations (`strcpy`, `sprintf`, `gets`), unfree'd `malloc` allocations, format string vulnerabilities, and missing returns.
- **JavaScript & TypeScript Scanner**: Detects synchronous blocking file operations (`fs.readFileSync`), dynamic code execution, prototype pollution (`__proto__`), unhandled Promise rejections, and empty catch blocks.

### 2. Intelligent Logical Error Detector & Verifier
Unlike linters that only inspect syntax, InsightX detects **semantic and algorithmic defects** where code runs with exit code `0` but produces incorrect outputs:
- **Calculation Errors**: Incorrect arithmetic operations and wrong denominators (e.g. `sum(marks) / (len(marks) + 1)`).
- **Comparison Operator Inversions**: Accumulator conditions inverted (e.g. `if average < highest: highest = average` when searching for maximums).
- **Threshold / Boundary Logic Inversions**: Inverted filter conditions (e.g. `if average < 40: count += 1` inside a function named `count_passed`).
- **Off-by-One & Loop Boundary Errors**: Loop ranges excluding or overshooting boundary items.
- **Automated Sandbox Execution**: Runs the code in an isolated Python process using `IsolatedCodeRunner` with strict execution timeouts (2.0s) and memory protection.
- **Empirical Output Verification**: Verifies the code against synthesized test cases, proving the mismatch between **Actual Output** and **Expected Output** before raising a finding.

### 3. Multivariate Anomaly & Telemetry Engine
- **Isolation Forest ($T = 100$)**: Evaluates multidimensional numeric telemetry (CPU, RAM, latency, connection pools) to isolate anomalous vectors without requiring labeled training data.
- **Dynamic Z-Score Saturation ($|Z| > 2.5\sigma$, saturation $> 85\%$)**: Identifies sharp saturation knees and persistent threshold violations.

### 4. Causal Root Cause Engine (RCA)
- **Cross-Modal Traceback Mapping**: Correlates runtime exception frames extracted from RFC 5424 log streams directly with static AST defect nodes in the source files.
- **Lead-Lag Temporal Cross-Correlation**: Calculates normalized cross-correlation across temporal lags $\tau \in [-4, +4]$ to determine whether high CPU caused latency or an unclosed connection caused database timeouts.
- **Dependency Topology Traversal**: Traverses module import graphs to compute blast radius and downstream impact across upstream callers.

---

## 🛠️ The Real Automatic Code Remediation Engine

InsightX does **not** simulate fixes by hiding findings or artificially boosting scores. It performs real source-code remediation:

1. **Rule-Based & AST-Aware Patch Generation**: The patch generator (`backend/app/autofix/patch_generator.py`) generates surgical line-level code replacements preserving surrounding indentation, imports, and comments.
2. **Unified Diff Preview**: Users can inspect exact side-by-side unified diffs (`difflib.unified_diff`) before applying.
3. **1-Click Application**: Clicking **"Auto Fix"** or **"Apply Fix & Re-analyze"**:
   - Applies the patch to an isolated working copy of the code.
   - Re-runs the full backend analyzer on the updated code.
   - Automatically re-runs test verification to confirm tests pass.
   - Re-calculates the health score and resolves fixed findings.
   - Chains the new analysis into persistent revision history (`v1 -> v2 -> v3`).
   - Displays before-and-after score deltas (e.g., `+18 points improvement`).

---

## 🎯 Benchmark Demonstration: Student Grading System

InsightX includes out-of-the-box validation on classic logical error scenarios:

```python
students = {
    "Aman": [85, 90, 78],
    "Priya": [92, 88, 95],
    "Rohit": [70, 65, 80]
}

def calculate_average(marks):
    return sum(marks) / (len(marks) + 1)  # Defect 1: len + 1 denominator

def find_topper(students):
    highest = 0
    topper = ""
    for name, marks in students.items():
        average = calculate_average(marks)
        if average < highest:             # Defect 2: Inverted comparison (< instead of >)
            highest = average
            topper = name
    return topper

def count_passed(students):
    count = 0
    for marks in students.values():
        average = calculate_average(marks)
        if average < 40:                  # Defect 3: Inverted threshold (< 40 counts failures)
            count += 1
    return count

print("Topper:", find_topper(students))
print("Passed:", count_passed(students))
print("Aman average:", round(calculate_average(students["Aman"]), 2))
```

### Initial Run (Before Fix):
```text
Topper: 
Passed: 0
Aman average: 63.25
```

### InsightX Detection & Verification:
1. **`calculate_average`**: Flags `PY_LOGICAL_CALCULATION`. Verifies `calculate_average([85, 90, 78])` returns `63.25` instead of `84.33`.
2. **`find_topper`**: Flags `PY_LOGICAL_COMPARISON`. Verifies `find_topper(students)` returns `""` instead of `"Priya"`.
3. **`count_passed`**: Flags `PY_LOGICAL_CONDITION`. Verifies `count_passed(students)` returns `0` instead of `3`.

### After Applying Auto-Fixes (Revision 4):
```text
Topper: Priya
Passed: 3
Aman average: 84.33
```
- **Health Score**: Improves from `68/100` $\rightarrow$ `100/100`.
- **Findings**: 0 remaining.
- **Audit History**: All 4 revisions preserved with before/after diffs in the History tab.

---

## 🖥️ Interactive Web UI (7 Specialized Modules)

The frontend features a clean, accessible interface with zero visual clutter:

1. **Overview Dashboard** (`/`): System health scorecard, KPI statistics, severity breakdown, recent diagnoses list, and 1-click sample cases.
2. **New Analysis Workspace** (`/upload`): Multi-modal input center supporting file drag-and-drop, ZIP repository uploads, interactive syntax-highlighted code editor (Tab indentation, format, clear), and optional metrics/logs.
3. **Analysis Results & Findings Inspector** (`/findings`): Searchable and filterable findings table, category tags, severity badges, and deep inspection modal with verified test case results.
4. **Root Cause Explorer** (`/root-cause`): Ranked causal hypotheses, confidence ratings, and an **interactive SVG call & dependency graph**.
5. **Decision Recommendations** (`/recommendations`): Prioritized action cards (P1-P4), Simple vs Technical explanations, unified diff viewer, and 1-click **"Auto Fix"** / **"Apply Fix & Re-analyze"**.
6. **Explanations & Forensic Evidence** (`/evidence`): Plain-language executive summary, score deduction breakdown, and empirical evidence checklist table.
7. **History & Exportable Reports** (`/reports`): Revision archive with one-click export to **Structured JSON** or **Comprehensive Markdown Dossier (`.md`)**.

---

## 🚀 Quickstart: Running InsightX Locally

### Prerequisites
- **Python**: 3.11+
- **Node.js**: v18+ (npm v9+)

### Option A: Unified Local Script (Recommended)
```bash
chmod +x run_app.sh
./run_app.sh
```
- **Frontend UI**: [http://localhost:5173](http://localhost:5173)
- **Backend API & Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Option B: Docker Compose
```bash
docker-compose up --build
```

### Option C: Manual Start in Separate Terminals

**Terminal 1 — Backend (FastAPI)**:
```bash
pip3 install -r backend/requirements.txt
export PYTHONPATH=.
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend (Vite + React)**:
```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Testing & Verification

InsightX includes rigorous automated test coverage across both backend and frontend:

### Backend Test Suite (Pytest)
```bash
PYTHONPATH=. python3 -m pytest backend/tests/ tests/ -v
```
**Results: 104 passed in 7.85s (100% Pass Rate)**
- Multi-layer syntax and lexical validation
- Ruff undefined symbol and linting integration
- Python AST structural rules & security scanning
- C / C++ buffer and memory safety checks
- JavaScript/TypeScript static analysis
- Logical error detection & calculation verifications
- Subprocess sandbox code runner (`IsolatedCodeRunner`)
- Test case synthesis and empirical output validation
- Isolation Forest anomaly detection & Z-score saturation
- RFC 5424 log parsing and stack-trace correlation
- Root cause ranking & qualitative confidence calibration
- Auto-Fix patch generation, validation, application, and persistence
- End-to-end multi-revision analysis workflows

### Frontend Test Suite (Vitest)
```bash
cd frontend && npm test -- --run
```
**Results: 11 passed in 0.67s (100% Pass Rate)**
- High-contrast syntax code editor rendering & Tab indentation
- Multi-tab navigation & synchronized badge counts
- Contextual InfoModal answering all 4 core questions
- Recommendations view with Simple/Technical toggle and Auto Fix buttons
- Overview Dashboard recent diagnoses interaction and 1-click loading

### Production Frontend Build
```bash
cd frontend && npm run build
```
**Results: Compiled successfully in 1.22s with zero TypeScript or bundling errors.**

---

## 🔒 Security & Data Safety Guarantees

- **Subprocess Sandbox Isolation**: Code execution for test verification runs in isolated subprocesses with strict memory, environment, and 2.0s wall-clock timeouts.
- **Zip Slip Defense**: Uploaded archives are strictly checked against directory traversal vulnerabilities (`../`, absolute paths).
- **Automated Secret Masking**: Credentials, private keys, bearer tokens, and API secrets are automatically masked (`sk****78`) in UI views and reports.
- **Zero External Network Leaks**: All static rules, causal algorithms, and test synthesizers run completely on local infrastructure without sending code to external servers.

---

## 📜 Academic Research Paper & Citation

InsightX was developed as part of the Master of Science in Data Science Innovation Curriculum at **Dhirubhai Ambani Institute of Information and Communication Technology (DA-IICT)**, Gandhinagar, Gujarat, India.

- **Authors**: Aman Chauhan (`202518004`), Mannan Agarwal (`202518013`)

### BibTeX Citation:
```bibtex
@inproceedings{chauhan2026insightx,
  title     = {InsightX: An Explainable AI Decision-Intelligence Framework for Multimodal Anomaly Detection and Causal Root-Cause Localization in Distributed Microservices},
  author    = {Aman Chauhan, Mannan Agarwal},
  booktitle = {DA-IICT MSc Data Science Innovation Conference},
  year      = {2026},
  address   = {Gandhinagar, Gujarat, India}
}
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
