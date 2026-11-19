import { InfoTopic } from '../types';

export const INFO_TOPICS: Record<string, InfoTopic> = {
  confidence: {
    title: 'Qualitative Confidence Rating',
    whatItMeans:
      'Expresses the strength of supporting evidence behind a root-cause hypothesis using qualitative tiers (High, Medium, Low) rather than uncalibrated percentage probabilities.',
    howCalculated:
      'High: Multiple independent evidence sources converge (e.g., runtime stack trace matching a static AST defect) or a deterministic compile/syntax failure exists. Medium: Strong static structural/control-flow evidence or single-source telemetry anomaly without cross-modal confirmation. Low: Potential resiliency or hygiene risk whose runtime impact depends heavily on external context.',
    whyImportant:
      'Prevents false precision and clearly separates confirmed runtime incidents from potential static code hazards.',
    limitations:
      'Qualitative confidence reflects only the evidence uploaded to InsightX. External infrastructure or un-uploaded modules may introduce additional causes.'
  },
  severity: {
    title: 'Deterministic Issue Severity Policy',
    whatItMeans:
      'Classifies each detected finding into five operational risk tiers (Critical, High, Medium, Low, Informational) based on defect class, likely impact, and available evidence.',
    howCalculated:
      'Critical is reserved for unconditional parse/crash defects (SyntaxError, literal / 0), directly exploitable security injections (SQL injection, eval/exec), exception-unsafe mutex deadlocks, or High static defects confirmed by an uploaded runtime crash trace. High covers significant static concurrency, retry, coroutine, resource-leak, memory-growth, and secret-exposure risks (including synchronous time.sleep() inside async functions). Medium covers missing timeouts, broad/silent exception handlers, and unguarded variable divisions.',
    whyImportant:
      'Ensures triage teams focus first on deterministic crashes, security exposures, and confirmed incidents without inflating every static warning to Critical.',
    limitations:
      'Static severity estimates potential impact without runtime traffic context; a High static issue in unused code may have lower real impact than a Medium issue on a hot request path.'
  },
  anomaly_detection: {
    title: 'Hybrid Metric Anomaly Detection',
    whatItMeans:
      'Identifies abnormal multi-dimensional departures and saturation points across uploaded time-series infrastructure telemetry (CPU, memory, latency, connection counts).',
    howCalculated:
      'Combines univariate statistical bounds (Z-score >= 2.5 sigma and absolute saturation > 85% for utilization metrics) with unsupervised multivariate Isolation Forest when >= 10 observations and >= 2 dimensions are supplied.',
    whyImportant:
      'Isolates sudden spikes and multivariate anomalies without requiring manual threshold tuning or labeled historical training data.',
    limitations:
      'Requires at least 3 data points for statistical analysis and >= 10 points for Isolation Forest. Expected batch jobs or planned load tests may appear anomalous.'
  },
  rca_diagnosis: {
    title: 'Root Cause Causal Diagnosis',
    whatItMeans:
      'Synthesizes detected findings, logs, and metric anomalies into ranked hypotheses explaining what was detected, why it can occur, supporting evidence, consequences, and alternatives.',
    howCalculated:
      'Correlates static AST defect sites with uploaded stack trace frames, log error patterns, and time-series anomalies. Explicitly separates Static Potential Causes from Correlated or Confirmed Runtime Incidents. Produces zero root causes when no issues or incident signals exist.',
    whyImportant:
      'Moves beyond raw finding lists to explain the underlying failure mechanism and highlight missing evidence before remediation.',
    limitations:
      'In code-only mode, root causes represent plausible static mechanisms rather than proof that an outage occurred in production.'
  },
  recommendations: {
    title: 'Actionable Corrective Recommendations',
    whatItMeans:
      'Maps each detected finding class to concrete, reviewable remediation guidance, context-aware before/after diffs, and verification steps. Changes are never applied automatically.',
    howCalculated:
      'Each recommendation is linked directly to real finding IDs and root causes from the active analysis, preserving source context (e.g., sleep duration, variable names, import presence) and prioritizing P1 Immediate through P4 Low.',
    whyImportant:
      'Reduces Mean Time to Resolution (MTTR) by giving engineers accurate, testable refactoring guidance tailored to the detected defect.',
    limitations:
      'Suggested diffs illustrate the localized remediation pattern and must be reviewed and verified with your project test suite before merging.'
  },
  evidence: {
    title: 'Explicit Evidence Categories',
    whatItMeans:
      'Labels every finding and hypothesis with the exact kind of evidence supporting it: Static Code Evidence, Log Evidence, Metrics Evidence, Runtime Evidence, or Correlated Evidence.',
    howCalculated:
      'Static Code Evidence comes exclusively from source-code parsing/AST inspection. Log Evidence comes from uploaded log entries. Metrics Evidence comes from uploaded CSV/JSON metrics. Runtime Evidence comes from uploaded execution stack traces. Correlated Evidence is assigned only when multiple independent evidence sources align.',
    whyImportant:
      'Guarantees intellectual honesty: static code analysis is never misrepresented as confirmed runtime proof.',
    limitations:
      'Correlated Evidence requires uploading multiple modalities (e.g., source code plus logs or metrics) together.'
  },
  health_score: {
    title: 'Explainable Health Score (0–100)',
    whatItMeans:
      'A deterministic summary indicator of findings detected by the enabled rules. A score of 100/100 means "No issues detected by the enabled analysis rules"—it does NOT guarantee the software is bug-free.',
    howCalculated:
      'Starts at 100 and subtracts severity-weighted deductions: Critical (-18), High (-10), Medium (-5), Low (-2), Informational (0). Duplicate occurrences of the same rule within a file receive diminished marginal penalty (35%, capped at 3 duplicates). Multi-file repositories apply mild logarithmic normalization to non-Critical deductions while keeping Critical findings undiluted. Uploaded metric anomalies (capped -15) and severe log errors (capped -20) also contribute when present.',
    whyImportant:
      'Provides a consistent, reproducible benchmark across revisions without letting file count or repeated warnings distort the overall picture.',
    limitations:
      'Included: enabled Python/JS/TS static rules and uploaded logs/metrics. Not covered: runtime business logic correctness, external un-uploaded libraries, dynamic reflection, or full penetration testing.'
  },
  dependency_graph: {
    title: 'Call & Import Dependency Topology',
    whatItMeans:
      'A visual graph mapping file-level imports and function call relationships extracted via static AST parsing.',
    howCalculated:
      'Constructed from ast.Import, ast.ImportFrom, and ast.Call nodes (or JS import/require statements) across all uploaded files.',
    whyImportant:
      'Helps engineers trace module coupling and understand which callers or downstream components could be affected by a defect.',
    limitations:
      'Dynamic reflection (e.g., getattr/importlib) and runtime dependency injection cannot be resolved statically.'
  }
};
