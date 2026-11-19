# InsightX REST API Reference

InsightX exposes a typed, documented REST API under `/api/v1`. Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## 1. System Health

### `GET /api/v1/health`
Returns system status, active version, SQLite database status, and initialized analyzer modules.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "database": "sqlite_connected",
  "supported_languages": ["python", "javascript", "typescript", "sql"],
  "analyzers_active": [
    "PythonCodeAnalyzer",
    "JavaScriptCodeAnalyzer",
    "MetricAnomalyAnalyzer",
    "LogAnalyzer",
    "RootCauseEngine",
    "RecommendationEngine",
    "ExplanationEngine"
  ]
}
```

---

## 2. Analyses & Investigations

### `POST /api/v1/analyses`
Primary multi-part upload endpoint supporting single files, multiple files, project ZIP archives, metrics CSVs, and application logs.

**Form Parameters**:
- `title` *(string, optional)*: Analysis title (default: "New Analysis").
- `mode` *(string, optional)*: `"code"`, `"metrics_logs"`, or `"combined"`.
- `files` *(files, optional)*: One or more source code files or a `.zip` archive.
- `metrics_file` *(file, optional)*: Time-series telemetry CSV or JSON.
- `logs_file` *(file, optional)*: Application logs file (.log, .txt).
- `error_trace` *(string, optional)*: Raw stack trace string.

**Response `200 OK`**: Full `AnalysisDetailResponse` JSON.

---

### `POST /api/v1/analyses/paste`
Analyzes directly pasted source code snippet.

**Request Body**:
```json
{
  "title": "Payment Processor Check",
  "code": "async def process():\n    time.sleep(2.0)\n",
  "language": "python",
  "file_name": "payment.py",
  "error_trace": null
}
```

**Response `200 OK`**: Full `AnalysisDetailResponse` JSON.

---

### `GET /api/v1/analyses`
Lists previous analyses stored in SQLite with severity breakdowns.

**Query Parameters**:
- `limit` *(integer, optional, default: 25)*: Max records to return.

**Response `200 OK`**: Array of `AnalysisSummaryResponse`.

---

### `GET /api/v1/analyses/{analysis_id}`
Retrieves complete analysis record with all findings, root causes, recommendations, relationships, anomalies, and logs.

---

### `GET /api/v1/analyses/{analysis_id}/findings`
Returns findings filtered by severity, category, or file path.

**Query Parameters**:
- `severity` *(string, optional)*: Filter by Critical, High, Medium, Low, Informational.
- `category` *(string, optional)*: Filter by category (e.g. "Concurrency Hazard").
- `file_path` *(string, optional)*: Filter by file.

---

### `GET /api/v1/analyses/{analysis_id}/causes`
Returns ranked probable root-cause hypotheses with confidence ratings and rationales.

---

### `GET /api/v1/analyses/{analysis_id}/recommendations`
Returns prioritized corrective interventions with unified code diffs.

---

### `PATCH /api/v1/analyses/{analysis_id}/recommendations/{rec_id}`
Toggles review status of a recommendation.

**Request Body**:
```json
{
  "reviewed": true
}
```

---

### `GET /api/v1/analyses/{analysis_id}/evidence`
Returns the verified evidence checklist, uncertainty disclosures, and methodology audit trail.

---

### `GET /api/v1/analyses/{analysis_id}/report`
Returns structured JSON data and formatted Markdown report.

---

### `GET /api/v1/analyses/{analysis_id}/report/download`
Downloads the human-readable Markdown incident dossier as an attachment (`.md`).

---

## 3. Demonstration Cases

### `GET /api/v1/sample-cases`
Lists pre-configured demonstration cases (Case A: Async Blocking, Case B: Multi-File Project, Case C: System Anomaly, Case D: Combined RCA).

### `POST /api/v1/sample-cases/{case_id}/load`
Instantly executes and loads a demonstration case.
