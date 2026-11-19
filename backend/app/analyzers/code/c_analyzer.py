import shutil
import subprocess
import re
from typing import Dict, Any, List
from backend.app.services.scoring import EvidenceCategory, SeverityPolicy


class CCodeAnalyzer:
    """
    Language-aware static analyzer for C and C++ source files.
    Invokes Clang compiler diagnostics (-fsyntax-only) to detect syntax defects,
    undeclared identifiers, type incompatibilities, and compiler warnings.
    Guarantees valid C code with #include <stdio.h> and printf() is never flagged.
    """

    def __init__(self):
        self.clang_bin = shutil.which("clang")

    def is_operational(self) -> bool:
        return bool(self.clang_bin)

    def analyze(self, code: str, file_path: str = "main.c") -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []
        lines = code.splitlines()
        is_cpp = file_path.endswith((".cpp", ".cc", ".cxx", ".hpp", ".hxx"))
        lang = "cpp" if is_cpp else "c"

        if not self.clang_bin:
            return {
                "findings": [],
                "relationships": [],
                "operational": False,
                "notice": "Clang toolchain is not available on host system.",
            }

        lang_flag = "-xc++" if is_cpp else "-xc"
        cmd = [self.clang_bin, "-fsyntax-only", "-fno-color-diagnostics", lang_flag, "-"]

        try:
            proc = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=10)
        except Exception:
            return {"findings": [], "relationships": [], "operational": False}

        # Parse Clang diagnostic lines: <stdin>:<line>:<col>: <severity>: <message>
        diag_re = re.compile(r"^<stdin>:(\d+):(\d+):\s+(error|fatal error|warning|note):\s+(.*)$", re.MULTILINE)

        for m in diag_re.finditer(proc.stderr):
            ln = int(m.group(1))
            col = int(m.group(2))
            level = m.group(3)
            msg = m.group(4).strip()

            if level == "note":
                continue

            snippet = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""

            if "undeclared identifier" in msg.lower():
                rule_id = "C_UNDECLARED_IDENTIFIER"
                title = f"Undeclared Identifier in {lang.upper()}"
                category = "Undefined Names / Symbol Errors"
                sev, rationale = SeverityPolicy.classify(rule_id, default_severity="High")
                consequence = "Compilation fails because the identifier is not defined or imported in scope."
                fix_step = f"Declare the identifier or include the required header file before line {ln}."
            elif level in ("error", "fatal error"):
                rule_id = "C_COMPILER_ERROR"
                title = f"Compilation Error ({lang.upper()})"
                category = "Syntax & Parsing"
                sev, rationale = SeverityPolicy.classify(rule_id, default_severity="Critical")
                consequence = "Compiler cannot generate an object file; build process halts immediately."
                fix_step = f"Resolve compiler syntax defect at line {ln}, column {col}."
            else:
                rule_id = "C_COMPILER_WARNING"
                title = f"Compiler Warning ({lang.upper()})"
                category = "Code Quality & Maintainability"
                sev, rationale = SeverityPolicy.classify(rule_id, default_severity="Medium")
                consequence = "Subtle bugs or portability issues may occur depending on compiler target."
                fix_step = f"Address compiler diagnostic warning at line {ln}."

            findings.append({
                "rule_id": rule_id,
                "title": title,
                "category": category,
                "severity": sev,
                "severity_rationale": rationale,
                "file_path": file_path,
                "line_number": ln,
                "line_end": ln,
                "column_number": col,
                "code_snippet": snippet,
                "description": f"Clang compiler diagnostic at line {ln}, col {col}: {msg}",
                "evidence": f"Clang diagnostic: {msg}",
                "evidence_category": EvidenceCategory.STATIC_CODE,
                "detection_method": "Clang Compiler Toolchain (clang -fsyntax-only)",
                "potential_consequences": consequence,
                "suggested_next_step": fix_step,
                "is_confirmed": False,
                "language": lang,
            })

        return {
            "findings": findings,
            "relationships": relationships,
            "operational": True,
        }
