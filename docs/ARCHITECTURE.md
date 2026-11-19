# InsightX System Architecture

## 1. Overview & Vision
InsightX is an explainable AI Root Cause & Decision Intelligence Platform connecting static source-code analysis, time-series metric anomaly detection, and application log forensics into one unified four-stage workflow:

$$\text{DETECT} \longrightarrow \text{DIAGNOSE} \longrightarrow \text{RECOMMEND} \longrightarrow \text{EXPLAIN}$$

The platform supports three independent and combinable analysis modes:
1. **Source Code Analysis** (single file, multiple files, ZIP repository, or direct paste; requires zero telemetry).
2. **System / Log Analysis** (CSV/JSON time-series metrics and structured JSON-lines or plain-text/RFC 5424 logs).
3. **Combined Root Cause Analysis** (correlating code findings, runtime stack traces, log errors, and metric anomalies).

---

## 2. Monorepo Organization

```text
insightx/
|-- frontend/                       # React 18, TypeScript, Vite, Tailwind CSS, Recharts
|   |-- src/
|   |   |-- types/                  # Typed domain models & EvidenceCategory definitions
|   |   |-- services/               # Typed REST API client & 4-question InfoButton registry
|   |   |-- components/ui/          # Badge, SeverityBadge, ConfidenceBadge, EvidenceBadge, InfoButton, Modal
|   |   |-- components/layout/      # Sidebar, Navbar, Page shell
|   |   |-- features/
|   |   |   |-- dashboard/          # Overview Dashboard, KPIs & 1-click sample cases
|   |   |   |-- upload/             # Multi-modal New Analysis Workspace
|   |   |   |-- findings/           # Filterable Analysis Results, Recharts Metrics Chart, Log Events & Modal
|   |   |   |-- root-cause/         # Ranked Hypotheses, Linked Findings & Interactive Dependency Graph
|   |   |   |-- recommendations/    # Prioritized Actions (P1-P4) & Unified Diff Viewer
|   |   |   |-- evidence/           # XAI Narrative, Score Breakdown & Evidence Audit Trail
|   |   |   |-- reports/            # History Archive, JSON & Markdown Export
|   |   |-- App.tsx                 # Analysis-keyed tab container preventing stale state
|   |   |-- App.test.tsx            # Vitest + Testing Library frontend test suite (11 tests)
|
|-- backend/                        # FastAPI, Pydantic v2, SQLAlchemy, SQLite, pandas, scikit-learn
|   |-- app/
|   |   |-- main.py                 # FastAPI entrypoint, CORS & startup lifespan
|   |   |-- core/                   # Settings & SQLite DB with safe schema migration + placeholder cleanup
|   |   |-- models/                 # SQLAlchemy ORM models (Analysis, Finding, RootCause, Recommendation, etc.)
|   |   |-- schemas/                # Pydantic v2 response & request contracts
|   |   |-- services/
|   |   |   |-- ingestion.py        # Safe file/ZIP ingestion (Zip Slip, ZIP bomb, extension & binary checks)
|   |   |   |-- scoring.py          # EvidenceCategory, SeverityPolicy & HealthScoreCalculator
|   |   |   |-- orchestrator.py     # 4-stage pipeline, cross-file async prescan & evidence invariants
|   |   |-- analyzers/
|   |   |   |-- code/
|   |   |   |   |-- rule_registry.py    # Centralized RuleDefinition registry exposed via /api/v1/rules
|   |   |   |   |-- python_analyzer.py  # Multi-pass Python AST, symbol/alias, control-flow & data-flow analyzer
|   |   |   |   |-- js_analyzer.py      # JavaScript & TypeScript static structural analyzer
|   |   |   |-- metrics/            # Robust Z-score/MAD/saturation + variance-guarded Isolation Forest
|   |   |   |-- logs/               # JSON-lines, RFC 5424 & plain-text log + stack-trace parser
|   |   |-- rca/                    # Evidence-grounded causal localization & six-part hypothesis ranking
|   |   |-- recommendations/        # Rule-ID routed remediation synthesis & unified diff engine
|   |   |-- explanations/           # Deterministic XAI narrative, evidence checklist & uncertainty audit
|   |   |-- reports/                # Structured JSON & Markdown diagnostic dossier generators
|   |   |-- api/v1/                 # REST endpoints (/health, /rules, /analyses, /report, /sample-cases)
|   |-- tests/                      # Pytest unit, regression, adversarial & acceptance suite (52 tests)
|
|-- docs/
|   |-- ARCHITECTURE.md             # System architecture & data flow
|   |-- ANALYSIS_RULES.md           # Implemented rules, severity policy, evidence categories & scoring
|   |-- TEST_RESULTS.md             # Executed verification & acceptance test report
|   |-- API.md                      # REST API contract documentation
|   |-- ANALYSIS_METHODS.md         # Algorithmic methodology
|-- run_app.sh                      # Unified launcher (FastAPI with --reload :8000 + Vite :5173)
```

---

## 3. End-to-End Data Flow

```text
Input (Paste / Files / ZIP / CSV / JSON / Logs)
  -> IngestionService (Extension, binary, size, Zip Slip & ZIP-bomb validation; zero code execution)
  -> Cross-File Prescan (Multi-file Python async export extraction)
  -> Stage 1: DETECT (PythonCodeAnalyzer, JavaScriptCodeAnalyzer, MetricAnomalyAnalyzer, LogAnalyzer)
  -> UUID Assignment (Findings receive real DB UUIDs before correlation)
  -> Stage 2: DIAGNOSE (RootCauseEngine + orchestrator evidence-backing invariant; 0 issues -> 0 causes)
  -> Stage 3: RECOMMEND (Rule-ID routed RecommendationEngine linked to Finding & RootCause IDs)
  -> Stage 4: EXPLAIN & SCORE (HealthScoreCalculator + ExplanationEngine categorized audit trail)
  -> Persistence (SQLite via SQLAlchemy) -> REST API -> React UI (keyed by analysis.id) -> JSON/MD Export
```

---

## 4. Key Architectural Invariants

- **Zero Arbitrary Execution**: Uploaded source files are parsed with `ast.parse()` / lexical inspection and never executed or imported.
- **Explicit Evidence Separation**: Every finding and root cause is labeled strictly as `Static Code Evidence`, `Log Evidence`, `Metrics Evidence`, `Runtime Evidence`, or `Correlated Evidence`. Static code findings are never labeled as confirmed runtime proof.
- **Clean-State Consistency**: Zero findings and zero incident signals produce `0` root causes, `0` recommendations, and a clean UI state—never placeholder hypotheses.
- **Qualitative Confidence**: Root-cause hypotheses report qualitative confidence (`High`, `Medium`, `Low`) rather than unsupported numerical probabilities.
- **Session Isolation**: Every persisted entity is scoped to `analysis_id`, and React feature views reset state on `analysis.id` transitions.
