import ast
import hashlib
from dataclasses import dataclass
from typing import Optional


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class PatchValidationResult:
    valid: bool
    error: Optional[str] = None
    error_code: Optional[str] = None  # "stale_hash" | "no_change" | "syntax_error" | "empty_patch" | "delimiter_error"


class PatchValidator:
    """
    Validates proposed automatic or manually edited source patches before application.
    Guarantees:
    - Never executes user code.
    - Rejects stale patches when expected_source_hash != current source hash.
    - Rejects empty or no-op patches.
    - Enforces Python ast.parse() validity and JS/TS delimiter balance.
    """

    @staticmethod
    def validate_hash(current_source: str, expected_source_hash: Optional[str]) -> PatchValidationResult:
        if expected_source_hash:
            actual_hash = sha256_text(current_source)
            if actual_hash != expected_source_hash:
                return PatchValidationResult(
                    valid=False,
                    error="Stale patch rejected: source file has changed since this preview was generated. Refresh and preview again.",
                    error_code="stale_hash",
                )
        return PatchValidationResult(valid=True)

    @staticmethod
    def validate_patch(
        file_path: str,
        original_source: str,
        patched_source: Optional[str],
        require_change: bool = True,
        require_valid_syntax: bool = True,
    ) -> PatchValidationResult:
        if not patched_source or not patched_source.strip():
            return PatchValidationResult(
                valid=False,
                error="Patched source code cannot be empty.",
                error_code="empty_patch",
            )

        if require_change and patched_source == original_source:
            return PatchValidationResult(
                valid=False,
                error="Patch produced no changes to the source file.",
                error_code="no_change",
            )

        if require_valid_syntax:
            if file_path.endswith(".py"):
                try:
                    ast.parse(patched_source, filename=file_path)
                except SyntaxError as exc:
                    return PatchValidationResult(
                        valid=False,
                        error=f"Patch failed Python AST syntax validation at line {exc.lineno}: {exc.msg}.",
                        error_code="syntax_error",
                    )
            elif file_path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
                brace_diff = patched_source.count("{") - patched_source.count("}")
                paren_diff = patched_source.count("(") - patched_source.count(")")
                if abs(brace_diff) > 0 or abs(paren_diff) > 0:
                    return PatchValidationResult(
                        valid=False,
                        error=f"Patch failed JS/TS delimiter balance check (braces_diff={brace_diff}, parens_diff={paren_diff}).",
                        error_code="delimiter_error",
                    )

        return PatchValidationResult(valid=True)
