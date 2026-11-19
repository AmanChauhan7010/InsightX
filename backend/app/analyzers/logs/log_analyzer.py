import json
import re
from typing import List, Dict, Any, Optional


class LogAnalyzer:
    """
    Log Intelligence Analyzer for JSON-lines, RFC 5424, and unstructured application logs.

    Extracts timestamps, severity levels, Python stack traces, consolidated error groups,
    recurring failure frequencies, and reports honest parsing limitations when input
    lacks recognizable log structure.
    """

    LOG_LEVEL_PATTERN = re.compile(r"\b(FATAL|CRITICAL|ERROR|WARN(?:ING)?|INFO|DEBUG)\b", re.IGNORECASE)
    TIMESTAMP_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b")
    TRACEBACK_FILE_PATTERN = re.compile(r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([a-zA-Z0-9_<>]+))?')
    EXCEPTION_PATTERN = re.compile(r"\b([A-Z][a-zA-Z0-9]*(?:Error|Exception|Crash|Fault|Failure|Timeout))\b(?::\s*(.*))?")

    def analyze(self, content_str: str, file_name: str = "app.log") -> Dict[str, Any]:
        if not content_str or not content_str.strip():
            return {
                "valid": False,
                "issues": [],
                "stack_traces": [],
                "summary": "Uploaded log input is empty.",
                "counts": {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0},
                "total_lines": 0,
                "parsed_lines": 0,
                "limitation": "Empty log file provided.",
                "repeated_patterns": [],
            }

        lines = content_str.splitlines()
        log_issues: List[Dict[str, Any]] = []
        stack_traces: List[Dict[str, Any]] = []
        error_counts_by_level = {"CRITICAL": 0, "ERROR": 0, "WARN": 0, "INFO": 0}
        parsed_lines = 0
        current_traceback: Optional[Dict[str, Any]] = None

        for idx, line in enumerate(lines, 1):
            clean_line = line.strip()
            if not clean_line:
                continue

            # 1. Try Structured JSON-Line Log Entry
            if clean_line.startswith("{") and clean_line.endswith("}"):
                try:
                    record = json.loads(clean_line)
                    if isinstance(record, dict):
                        parsed_lines += 1
                        raw_lvl = str(record.get("level") or record.get("severity") or record.get("lvl") or "INFO").upper()
                        level = self._normalize_level(raw_lvl)
                        if level in error_counts_by_level:
                            error_counts_by_level[level] += 1
                        msg = str(record.get("message") or record.get("msg") or record.get("error") or clean_line)
                        ts = str(record.get("timestamp") or record.get("time") or record.get("@timestamp") or "") or None
                        svc = str(record.get("service") or record.get("app") or record.get("logger") or "") or None
                        fpath = record.get("file_path") or record.get("file")
                        lno = record.get("line_number") or record.get("line")
                        if level in ("CRITICAL", "ERROR", "WARN"):
                            log_issues.append({
                                "timestamp": ts,
                                "level": level,
                                "message": msg,
                                "service": svc,
                                "file_path": str(fpath) if fpath else None,
                                "line_number": int(lno) if isinstance(lno, int) else None,
                                "count": 1,
                            })
                        continue
                except Exception:
                    pass  # Fall back to plain-text parsing

            # 2. Detect Stack Trace Frames
            tb_match = self.TRACEBACK_FILE_PATTERN.search(clean_line)
            if tb_match:
                parsed_lines += 1
                current_traceback = {
                    "file_path": tb_match.group(1),
                    "line_number": int(tb_match.group(2)),
                    "function_name": tb_match.group(3) or "module",
                    "raw_line": clean_line,
                    "log_line_idx": idx,
                }
                continue

            # 3. Detect Exception Lines
            exc_match = self.EXCEPTION_PATTERN.search(clean_line)
            if exc_match and ("Error:" in clean_line or "Exception:" in clean_line or current_traceback is not None):
                parsed_lines += 1
                exc_type = exc_match.group(1)
                exc_msg = (exc_match.group(2) or clean_line).strip()

                trace_data = current_traceback or {
                    "file_path": file_name,
                    "line_number": None,
                    "function_name": None,
                }

                stack_traces.append({
                    "exception_type": exc_type,
                    "message": exc_msg,
                    "file_path": trace_data.get("file_path"),
                    "line_number": trace_data.get("line_number"),
                    "function_name": trace_data.get("function_name"),
                    "log_line": idx,
                })

                log_issues.append({
                    "timestamp": self._extract_timestamp(clean_line),
                    "level": "CRITICAL",
                    "message": f"{exc_type}: {exc_msg}",
                    "service": self._extract_service(clean_line),
                    "file_path": trace_data.get("file_path"),
                    "line_number": trace_data.get("line_number"),
                    "count": 1,
                })
                error_counts_by_level["CRITICAL"] += 1
                current_traceback = None
                continue

            # 4. Detect Standard Log Levels / Timestamps
            level_match = self.LOG_LEVEL_PATTERN.search(clean_line)
            ts_val = self._extract_timestamp(clean_line)
            if level_match or ts_val:
                parsed_lines += 1
            if level_match:
                level = self._normalize_level(level_match.group(1).upper())
                if level in error_counts_by_level:
                    error_counts_by_level[level] += 1

                if level in ("CRITICAL", "ERROR", "WARN"):
                    log_issues.append({
                        "timestamp": ts_val,
                        "level": level,
                        "message": clean_line,
                        "service": self._extract_service(clean_line),
                        "file_path": None,
                        "line_number": None,
                        "count": 1,
                    })

        consolidated = self._consolidate_issues(log_issues)
        consolidated.sort(key=lambda x: (0 if x["level"] == "CRITICAL" else 1 if x["level"] == "ERROR" else 2, -x["count"]))

        repeated_patterns = [
            {
                "level": item["level"],
                "message": item["message"][:140],
                "count": item["count"],
                "service": item.get("service"),
                "first_seen": item.get("timestamp"),
            }
            for item in consolidated
            if item["count"] >= 2
        ]

        non_empty_lines = sum(1 for l in lines if l.strip())
        limitation = None
        valid = True
        if non_empty_lines > 0 and parsed_lines == 0:
            valid = False
            limitation = (
                f"No recognizable log timestamps, severity levels (INFO/WARN/ERROR/CRITICAL), JSON log records, "
                f"or stack traces were parsed from '{file_name}' ({non_empty_lines} non-empty lines). "
                "Verify the file format before relying on zero-error results."
            )

        return {
            "valid": valid,
            "issues": consolidated,
            "stack_traces": stack_traces,
            "summary": (
                limitation
                if limitation
                else f"Processed {len(lines)} log lines ({parsed_lines} structured). Identified {len(stack_traces)} stack trace(s) and {len(consolidated)} distinct warning/error group(s)."
            ),
            "counts": error_counts_by_level,
            "total_lines": len(lines),
            "parsed_lines": parsed_lines,
            "limitation": limitation,
            "repeated_patterns": repeated_patterns,
        }

    def _normalize_level(self, raw_level: str) -> str:
        if raw_level in ("FATAL", "CRITICAL", "CRIT", "EMERG", "ALERT"):
            return "CRITICAL"
        if raw_level in ("ERROR", "ERR"):
            return "ERROR"
        if "WARN" in raw_level:
            return "WARN"
        return "INFO"

    def _extract_timestamp(self, line: str) -> Optional[str]:
        m = self.TIMESTAMP_PATTERN.search(line)
        return m.group(1) if m else None

    def _extract_service(self, line: str) -> Optional[str]:
        m = re.search(r"\[([a-zA-Z0-9_\-]+(?:-service|-api|-worker|-db|-gw)?)\]", line)
        if m:
            return m.group(1)
        m2 = re.search(r"(?:service|app|service_name)=([a-zA-Z0-9_\-]+)", line, re.IGNORECASE)
        if m2:
            return m2.group(1)
        return None

    def _normalize_message_for_grouping(self, msg: str) -> str:
        """Strips timestamps and volatile IDs/numbers so recurring identical errors consolidate cleanly."""
        cleaned = self.TIMESTAMP_PATTERN.sub("", msg).strip()
        cleaned = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d{4,}\b", "<num>", cleaned)
        return cleaned[:100]

    def _consolidate_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        dedup: Dict[str, Dict[str, Any]] = {}
        for issue in issues:
            norm = self._normalize_message_for_grouping(issue["message"])
            key = f"{issue['level']}:{norm}"
            if key in dedup:
                dedup[key]["count"] += 1
            else:
                dedup[key] = dict(issue)
        return list(dedup.values())
