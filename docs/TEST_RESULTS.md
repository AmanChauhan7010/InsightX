# InsightX — Automated Verification & Acceptance Test Results

**Verification Date**: 2026-11-18  
**Environment**: macOS, Python 3.14.2 (`pytest 9.2.0`), Node/Vite (`vitest 5.1.0`, TypeScript `tsc`, Vite `6.4.6`)

---

## 1. Executed Test Suites Summary

| Test Suite | Command Executed | Total | Passed | Failed | Duration |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Backend Unit, Regression, Auto-Fix, Persistence & Acceptance Suite** | `python3 -m pytest backend/tests -v` | 62 | **62** | 0 | ~1.7s |
| **Frontend Component, Editor, Auto-Fix & Dashboard Suite** | `cd frontend && npm test -- --run` | 11 | **11** | 0 | ~0.6s |
| **Frontend TypeScript & Production Build** | `cd frontend && npm run build` | Build | **PASS** | 0 | ~1.4s |
| **SQLite Legacy Placeholder Verification** | `SELECT COUNT(*) FROM root_causes WHERE title = 'Nominal Operational Baseline / No Causal Defect Isolated'` | 1 | **PASS (`0` rows)** | 0 | <0.1s |

---

## 2. Coverage Matrix by Test Group

| Test Group | Test File(s) | Key Verified Cases | Result |
| :--- | :--- | :--- | :---: |
| **A. Python AST & Locations** | `test_code_analyzers.py`, `test_regression_audit.py` | Valid parsing, `SyntaxError` incomplete-parse handling, leading blank lines, decorators, classes, nested defs, Windows CRLF & Unix LF exact line numbers | **PASS** |
| **B. Async & Coroutines** | `test_regression_audit.py`, `test_comprehensive_acceptance.py` | Blocking `time.sleep` (`High` static default), sync `requests.get`, unawaited local/discarded/collected/aliased/nested/instance/cross-file coroutines; safe `await`, `create_task`, `gather`, intentional coroutine return | **PASS** |
| **C. Infinite Retries & Loops** | `test_regression_audit.py`, `test_comprehensive_acceptance.py` | Sync/async `while True` with swallowed exceptions, nested `try` in `if`, flag-guarded `while not done`, specific-exception silent retry; safe bounded retries, `break`, `raise`, and queue workers | **PASS** |
| **D. Existing & Security Rules** | `test_code_analyzers.py`, `test_comprehensive_acceptance.py` | Missing timeout vs valid timeout, silent `except`, unclosed vs `with open()`, unbounded vs bounded (`deque`/`.pop()`), mutable defaults, SQLi, `eval`/`exec`, `pickle`/`yaml.load` vs `yaml.safe_load`, `subprocess shell=True` vs `shell=False`, masked secrets, deadlocks | **PASS** |
| **E. Root Cause Analysis** | `test_rca_and_recommendations.py`, `test_regression_audit.py`, `test_comprehensive_acceptance.py` | Stack-trace correlation elevating to `Critical` + `Correlated Evidence`, real finding-ID linking, clean scan producing `0` root causes, zero placeholder causes, cross-analysis isolation | **PASS** |
| **F. Recommendations** | `test_rca_and_recommendations.py`, `test_regression_audit.py` | Rule-ID routed fixes, exact sleep duration preservation, `import asyncio` check, unified diffs (`difflib`), review status toggle, `0` recommendations on clean scans | **PASS** |
| **G. Metrics & Logs** | `test_metrics_and_logs.py`, `test_comprehensive_acceptance.py` | Normal steady metrics (`0` false positives), anomalous interval extraction, out-of-order/duplicate timestamps, missing timestamps, malformed CSV rejection (HTTP 400), JSON-lines & RFC 5424 logs, repeated error consolidation, unparseable log limitation | **PASS** |
| **H. Multi-File & Security** | `test_api.py`, `test_comprehensive_acceptance.py` | Multi-file upload, nested ZIP repository, cross-file async import check, Zip Slip path traversal rejection (HTTP 400), binary & unsupported extension rejection (HTTP 400), unsupported paste language rejection (HTTP 400), `/api/v1/rules` introspection | **PASS** |
| **I. Frontend Integration** | `frontend/src/App.test.tsx` | Navigation & synced counts, upload/paste validation, clean empty state A vs filtered empty state B with Reset Filters, failed analysis banner, metrics/log panels, `RootCauseExplorer` linked findings & stale-state reset, `RecommendationsView`, `InfoButton` 4-question modal, zero `"Confirmed Runtime Proof"` on static findings | **PASS** |
| **J. Auto-Fix Engine & Persistence** | `test_fixes_and_revisions.py` | Modular `backend/app/autofix/` deterministic fixes (`time.sleep` -> `await asyncio.sleep`, safe `with open()`, escaped handle guard, async vs sync-loop coroutine safety, configurable HTTP timeout, infinite retry bound, silent `except`, sequential v1 -> v2 -> v3 revisions, stale hash rejection, revision compare endpoint, SQLite persistence across fresh sessions & clients) | **PASS** |
| **Adversarial & E2E Scenarios 1–8** | `test_e2e_workflow.py`, `test_comprehensive_acceptance.py` | Parameterized randomized function/variable names, sequential session isolation (`Faulty -> Clean -> Faulty -> Clean`), combined Code + Logs + Metrics multimodal RCA, Markdown & JSON report generation | **PASS** |

---

## 3. Commands to Re-Run Verification

```bash
# Backend test suite
cd /Users/amanchauhan/Creative
python3 -m pytest backend/tests -v

# Frontend test suite
cd /Users/amanchauhan/Creative/frontend
npm test -- --run

# Frontend TypeScript check & production build
cd /Users/amanchauhan/Creative/frontend
npm run build
```
