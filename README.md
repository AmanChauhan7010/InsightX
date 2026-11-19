<div align="center">

# ⚡ InsightX — AI Root Cause & Decision Intelligence Platform

### *From alerts to answers — detect, understand, and take the right action.*

[![Build & Verification](https://img.shields.io/badge/build-passing-brightgreen.svg?style=flat-square)](https://github.com)
[![Pytest Coverage](https://img.shields.io/badge/backend%20tests-62%2F62%20passed%20(100%25)-success?style=flat-square)](https://pytest.org)
[![Vitest Coverage](https://img.shields.io/badge/frontend%20tests-11%2F11%20passed%20(100%25)-success?style=flat-square)](https://vitest.dev)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg?style=flat-square)](https://python.org)
[![React Version](https://img.shields.io/badge/react-18.3.1-61dafb.svg?style=flat-square)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/typescript-5.7-blue.svg?style=flat-square)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI%20%2B%20SQLAlchemy-009688.svg?style=flat-square)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Academic Project](https://img.shields.io/badge/DA--IICT-MSc%20Data%20Science%20Innovation-orange.svg?style=flat-square)](https://www.daiict.ac.in)

**A unified, explainable decision-intelligence platform connecting static program analysis, multivariate telemetry anomaly detection, causal root-cause localization, and automated runbook remediation.**

[Architecture Guide](docs/ARCHITECTURE.md) • [Analysis Rules & Policy](docs/ANALYSIS_RULES.md) • [Test Results](docs/TEST_RESULTS.md) • [REST API Reference](docs/API.md) • [Technical Deep Dive](EXPLANATION.md) • [Research Paper](paper/insightx_research_paper.md)

</div>

---

## 📌 Executive Summary & The Observability Gap

Modern cloud-native architectures rely on dense graphs of containerized microservices characterized by high telemetry velocity, transient workloads, and intricate dependency topologies. When service disruptions occur, traditional monitoring tools (Prometheus, Grafana, Datadog, Splunk) inundate engineering teams with hundreds of noisy, correlated alerts without isolating the primary causal origin or prescribing deterministic corrective procedures.

```
Traditional Monitoring:   [Symptom Alert: High CPU]  -->  [Manual Log Search]  -->  [Trial-and-Error Fix]  -->  (MTTR: 30-90 min)
InsightX Intelligence:    [Multimodal Ingestion]     -->  [Causal Lead-Lag]   -->  [Actionable Code Diff]   -->  (MTTR: < 2 min)
```

### The Problem Bottlenecks:
1. **Alert Overload & Fatigue**: A single backend database lock cascades into hundreds of HTTP 504 gateway timeouts across upstream tiers.
2. **Unclear Causal Origins**: Symptoms mask triggers. High CPU utilization is rarely the root cause—it is usually the downstream symptom of an unclosed connection pool, an event loop blocking sleep, or an unbounded queue backlog.
3. **Trial-and-Error Remediation**: SREs waste critical minutes consulting outdated runbooks without knowing the expected impact of an intervention.
4. **Inflated MTTR & Downtime**: Delayed Mean Time to Resolution directly escalates operational costs and customer churn.

**InsightX bridges this gap** by implementing an automated four-stage decision-intelligence pipeline:

$$\mathbf{DETECT} \longrightarrow \mathbf{DIAGNOSE} \longrightarrow \mathbf{RECOMMEND} \longrightarrow \mathbf{EXPLAIN}$$

---

## 📊 Observability Platform Comparison

| Capability Dimension | Prometheus / Grafana | Datadog / Dynatrace | MicroRCA / Academic | **InsightX (This Platform)** |
| :--- | :---: | :---: | :---: | :---: |
| **Telemetry Ingestion** | Metrics Only | Metrics + Logs + APM | Traces + Metrics | **Metrics + Logs + Source Code AST** |
| **Independent Code Scan** | ❌ No | ❌ No | ❌ No | **✅ Yes (Single file, ZIP, or Paste)** |
| **Detection Engine** | Static Thresholds | Statistical / ML | Graph Heuristics | **✅ Hybrid IsoForest + Dynamic Saturation** |
| **Causal Localization** | Manual | Basic Correlation | PageRank Walk | **✅ Lead-Lag Cross-Correlation + Topology DAG** |
| **Causal Confidence** | ❌ None | ❌ None | Node Ranking | **✅ Calibrated Qualitative Confidence** |
| **Action Recommendations** | ❌ None | Static Runbooks | ❌ None | **✅ Prioritized (P1-P4) + Non-Destructive** |
| **Automated Code Diffs** | ❌ None | ❌ None | ❌ None | **✅ Verified Unified Diffs (`difflib`)** |
| **Explainable AI (XAI)** | ❌ None | Limited Dashboards | ❌ None | **✅ Complete Evidence Audit Trail Dossier** |
| **Contextual "i" Disclosures**| ❌ None | Tooltips | ❌ None | **✅ 4-Question Progressive Disclosure** |

---

## 🏗️ Monorepo Architecture

InsightX is engineered with a strict separation of concerns across a layered FastAPI backend, modern React frontend, demonstration suite, and technical documentation:

```
insightx/
|-- frontend/                       # React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, Recharts
|   |-- src/
|   |   |-- types/                  # Typed domain models & API schemas
|   |   |-- services/               # Centralized typed API client & Info topic registry
|   |   |-- components/ui/          # Accessible primitives (Badge, Card, Button, Modal, InfoButton)
|   |   |-- components/layout/      # Responsive Sidebar, Navbar, Application shell
|   |   |-- features/
|   |   |   |-- dashboard/          # Page 1: Overview Dashboard & KPI cards
|   |   |   |-- upload/             # Page 2: Multi-Modal Ingestion Workspace
|   |   |   |-- findings/           # Page 3: Filterable Analysis Results & Inspector
|   |   |   |-- root-cause/         # Page 4: Root Cause Explorer & Topology Graph
|   |   |   |-- recommendations/    # Page 5: Prioritized Actions & Diff Viewer
|   |   |   |-- evidence/           # Page 6: XAI Narrative & Evidence Audit Trail
|   |   |   |-- reports/            # Page 7: History Archive & Report Exporter
|   |   |-- index.css               # Tailwind CSS & custom scrollbar styles
|   |   |-- App.tsx                 # Main application workflow container
|   |   |-- App.test.tsx            # Frontend unit and component tests (Vitest)
|   |-- package.json
|   |-- vite.config.ts              # Vite proxy configuration & Vitest setup
|   |-- tailwind.config.js          # Design system typography & color tokens
|
|-- backend/                        # Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, SQLite, pandas, scikit-learn
|   |-- app/
|   |   |-- main.py                 # FastAPI application lifespan & CORS middleware
|   |   |-- core/                   # Configuration, CORS, SQLite database
|   |   |-- models/                 # SQLAlchemy ORM models (Analyses, Findings, Causes, Recs)
|   |   |-- schemas/                # Pydantic v2 validation contracts
|   |   |-- services/               # Safe Ingestion & 4-stage pipeline orchestrator
|   |   |-- analyzers/
|   |   |   |-- code/               # Python AST visitor (15+ rules) & JS/TS static scanner
|   |   |   |-- metrics/            # Isolation Forest & dynamic Z-score saturation
|   |   |   |-- logs/               # RFC 5424 log parser & stack trace correlation
|   |   |-- rca/                    # Causal cross-modality localization & hypothesis ranking
|   |   |-- recommendations/        # Remediation synthesis & unified diff engine
|   |   |-- explanations/           # Explainable AI (XAI) narrative & uncertainty auditor
|   |   |-- reports/                # Structured JSON & Markdown dossier generators
|   |   |-- api/v1/                 # Documented REST API endpoints
|   |-- tests/                      # Pytest test suite (22 unit & integration tests)
|   |-- requirements.txt
|
|-- sample_data/                    # Real test inputs
|   |-- code/                       # payment_service.py, worker.js, sample_project.zip
|   |-- logs/                       # production_timeouts.log (RFC 5424 & tracebacks)
|   |-- metrics/                    # system_telemetry.csv (CPU spike & latency saturation)
|
|-- docs/
|   |-- ARCHITECTURE.md             # System design & component interaction
|   |-- API.md                      # REST API endpoint reference
|   |-- ANALYSIS_METHODS.md         # Scientific detection rules & algorithms
|
|-- paper/                          # Academic Research Paper & IEEE Artifacts
|   |-- insightx_research_paper.md  # Comprehensive research paper in Markdown
|   |-- insightx_ieee_paper.tex     # IEEE conference LaTeX source
|   |-- compile_ieee_pdf.py         # ReportLab-based IEEE two-column PDF compiler
|   |-- insightx_ieee_paper.pdf     # Publication-quality compiled PDF
|
|-- EXPLANATION.md                  # Comprehensive Technical Deep-Dive & Mathematical Guide
|-- docker-compose.yml              # Containerized multi-service deployment
|-- run_app.sh                      # Unified local launch script
|-- .env.example                    # Environment variable template
```

---

## ⚡ The Four Connected Stages

```
   +-------------------------------------------------------------------------+
   |  1. DETECT (Static AST Inspection + Isolation Forest Anomaly Detection) |
   +-------------------------------------------------------------------------+
                                        |
                                        v
   +-------------------------------------------------------------------------+
   |  2. DIAGNOSE (Lead-Lag Cross-Correlation + Topology Blast Radius Traversal)
   +-------------------------------------------------------------------------+
                                        |
                                        v
   +-------------------------------------------------------------------------+
   |  3. RECOMMEND (Prioritized Actions P1-P4 + Verified Unified Code Diffs) |
   +-------------------------------------------------------------------------+
                                        |
                                        v
   +-------------------------------------------------------------------------+
   |  4. EXPLAIN (XAI Narrative Synthesis + Evidence Audit Trail Checklist)  |
   +-------------------------------------------------------------------------+
```

### Stage 1: DETECT
- **Python AST Visitor**: Inspects Abstract Syntax Tree nodes across 15+ defect classes:
  - Event loop blocking: Synchronous `time.sleep()` or synchronous network I/O (`requests.get`) inside `async def`.
  - Resource leaks: Unclosed database connections (`sqlite3.connect`, pool handles) lacking context managers.
  - Concurrency deadlocks: Mutex `.acquire()` without exception-safe `with lock:` or `finally: lock.release()`.
  - Arithmetic crashes: Unguarded divisions `/ y` lacking zero-check guards, and constant division by zero (`/ 0`).
  - Security vulnerabilities: Dynamic SQL injection via formatted f-strings, dangerous `eval()`/`exec()`, and hardcoded secrets (automatically masked).
  - Memory leaks: Unbounded collection appending in global scope without ring buffer limits.
- **JavaScript & TypeScript Scanner**: Detects synchronous blocking file operations (`fs.readFileSync`), dynamic code execution (`eval()`, `new Function()`), prototype pollution (`__proto__`), unhandled rejections, and empty catch blocks.
- **Multivariate Telemetry Anomaly Detection**: Ensembles unsupervised Isolation Forest ($T = 100$) with dynamic rolling saturation thresholds ($|Z| > 2.5\sigma$, saturation $> 85\%$).
- **Log Forensics**: Parses RFC 5424 structured events, isolates exception frames, and computes temporal error density.

### Stage 2: DIAGNOSE (Root Cause Analysis)
- **Causal Evidence Matching**: Maps runtime log stack trace line numbers directly to static AST code defect nodes.
- **Lead-Lag Temporal Cross-Correlation**: Evaluates normalized cross-correlation across temporal lags $\tau \in [-4, +4]$ to discover which metric or event was the true causal precursor.
- **Dependency Topology Traversal**: Traverses directed import and call graphs to compute blast radius and downstream impact.
- **Calibrated Qualitative Confidence**: Strictly avoids ungrounded pseudoscientific probabilities; assigns calibrated ratings:
  - **High (> 0.90)**: Confirmed by active runtime stack trace proof.
  - **Medium-High (0.75 - 0.88)**: Aligned cross-modal telemetry correlation (e.g., latency anomaly + event loop sleep).
  - **Medium (0.70)**: Static structural risk prior to production incident.

### Stage 3: RECOMMEND
- **Actionable Decision Guidance**: Ranks corrective actions across priority tiers (`P1 - Immediate`, `P2 - High`, `P3 - Medium`, `P4 - Low`).
- **Unified Code Diff Generation**: Generates line-by-line before/after refactoring diffs (`difflib.unified_diff`) for peer review.
- **Non-Destructive Safety**: Never executes automated modifications without human approval.
- **Verification Runbooks**: Provides specific verification tests (e.g. pytest commands, load benchmarks).

### Stage 4: EXPLAIN
- **Executive Diagnostic Narrative**: Human-readable synthesis answering *What was detected? How was it detected? Why does it matter? What remains uncertain?*
- **Empirical Evidence Audit Trail**: Verifiable checklist linking findings back to source files, exact lines, and telemetry timestamps.
- **Uncertainty Disclosure**: Explicitly lists missing evidence or analytical assumptions.

---

## 🖥️ Interactive Web Application (7 Dedicated Pages)

The frontend is a light-mode engineering intelligence dashboard designed with Inter typography, `#2563EB` primary accents, `#0F172A` text, subtle borders, and generous whitespace:

1. **Overview Dashboard** (`/`): System health summary, KPI cards, severity distribution bars, recent investigation history, and **1-click demonstration loaders**.
2. **New Analysis Workspace** (`/upload`): Multi-modal input workspace supporting drag & drop files, ZIP archives, direct code paste editor, and optional metrics/logs. Displays genuine multi-stage progress states.
3. **Analysis Results & Findings Inspector** (`/findings`): Health scorecard (0-100), filter toolbar (search, severity, category, file), and deep inspection modal with code snippets and remediation steps.
4. **Root Cause Explorer** (`/root-cause`): Ranked probable hypotheses with confidence badges, supporting evidence, ranking rationale, and an **Interactive SVG Call/Dependency Topology Graph**.
5. **Decision Recommendations** (`/recommendations`): Prioritized corrective actions with expected impact, verification instructions, **Interactive Code Diff Viewer**, and a **"Mark as Reviewed" toggle**.
6. **Explanations & Forensic Evidence Audit** (`/evidence`): Primary explainability view with an Executive Diagnostic Narrative, Evidence Checklist table, and uncertainty disclosures.
7. **History & Exportable Reports** (`/reports`): Stored investigation archive, instant target switching, **Structured JSON Export**, and **Human-Readable Markdown Dossier** with 1-click download (`.md`).

---

## ℹ️ Contextual Information ("i") Popovers

Accessible `InfoButton` icons are placed strategically throughout the UI (Root Cause Confidence, Severity Taxonomy, Anomaly Detection, Recommendations, Evidence, Health Score, and Dependency Graph). Each popover answers four structured questions:
1. **What does this mean?**
2. **How does InsightX calculate or determine it?**
3. **Why is it important?**
4. **What are its operational limitations?**

---

## 🎯 Realistic Demonstration Cases

InsightX includes 4 pre-configured demonstration cases runnable via 1-click on the Overview Dashboard:

| Case ID | Scenario Name | Target Input Artifacts | Failure Mechanism & Primary Ground Truth |
| :--- | :--- | :--- | :--- |
| **Case A** | Python Async Event Loop Blocking | `sample_data/code/payment_service.py` | Synchronous `time.sleep(2.5)` inside `async def process_payment`, unclosed SQLite connection leak, and mutable default container. |
| **Case B** | Multi-Module Project Architecture | `sample_data/code/sample_project.zip` | 3-tier Python service (`coordinator.py`, `worker.py`, `db.py`) with cross-file imports, unguarded zero division, and hardcoded secrets. |
| **Case C** | Multivariate System Telemetry | `sample_data/metrics/system_telemetry.csv` | Timestamped telemetry time series exhibiting severe CPU saturation (>98%) and P95 latency spikes (>5000ms) isolated via Isolation Forest. |
| **Case D** | Combined Multimodal Investigation | `payment_service.py` + `production_timeouts.log` | RFC 5424 log tracebacks at line 21 directly match the static event loop blocking defect, yielding a Confirmed Runtime Crash hypothesis. |

---

## 🚀 Quickstart: Running InsightX Locally

### Prerequisites
- **Python**: 3.11+
- **Node.js**: v18.0.0+ (npm v9+)

### Option A: Unified Local Launcher (Recommended)
Clone the repository and run the startup script:
```bash
chmod +x run_app.sh
./run_app.sh
```
- **Web Dashboard**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Backend & Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Option B: Docker Compose
```bash
docker-compose up --build
```

### Option C: Manual Independent Start

**Terminal 1 — Backend (FastAPI)**:
```bash
pip3 install -r backend/requirements.txt
export PYTHONPATH=.
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend (Vite React)**:
```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Testing & Verification

The codebase includes full unit, integration, and end-to-end test suites.

### Backend Test Suite (Pytest)
```bash
PYTHONPATH=. pytest backend/tests -v
```
**Results: 22 passed in 1.11s**
- Health endpoint verification
- Single-file and multi-file multipart uploads
- ZIP archive path validation & Zip Slip defense
- Python AST syntax and semantic rules
- JavaScript/TypeScript event loop and security rules
- Multivariate Isolation Forest & Z-score saturation
- Log stack trace extraction & code path correlation
- Root cause ranking & qualitative confidence
- Unified diff generation & verification instructions
- Report generation (JSON and Markdown)
- Full end-to-end integration workflow (`test_e2e_workflow.py`)

### Frontend Test Suite (Vitest)
```bash
cd frontend && npm test
```
**Results: 5 passed in 0.38s**
- Badge variant rendering
- SeverityBadge classification across all 5 tiers
- ConfidenceBadge with calibrated percentage calculation
- Contextual InfoModal answering all 4 required questions
- Button click dispatch

### Production Frontend Build
```bash
cd frontend && npm run build
```
**Results: Compiled in 0.69s with zero errors or warnings.**

---

## 🔒 Security & Data Safety Guarantees

- **Zero Arbitrary Execution**: User code is parsed exclusively into Abstract Syntax Trees using static analyzers. Uploaded code is never executed.
- **Zip Slip Defense**: Archives are rigorously validated against directory traversal attacks (`../`, absolute paths).
- **Automated Secret Masking**: Discovered credentials, bearer tokens, and API keys are masked (`sk****78`) in UI snippets and exported dossiers.
- **Local Deterministic Fallback**: All detection rules, causal rankings, and diff syntheses run 100% deterministically on local infrastructure without external network dependencies.

---

## 📜 Academic Research Paper & Citation

InsightX was developed as part of the Master of Science in Data Science Innovation Curriculum at **Dhirubhai Ambani Institute of Information and Communication Technology (DA-IICT)**, Gandhinagar, Gujarat, India.

- **Authors**: Aman Chauhan (`202518004`), Mannan Agarwal (`202518013`)
- **Research Paper (Markdown)**: [`paper/insightx_research_paper.md`](paper/insightx_research_paper.md)
- **Publication-Ready PDF**: [`paper/insightx_ieee_paper.pdf`](paper/insightx_ieee_paper.pdf)
- **Technical Deep-Dive**: [`EXPLANATION.md`](EXPLANATION.md)

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
