"""
Backwards-compatible facade over the modular backend.app.autofix engine.
"""
from typing import Dict, Any, List, Optional, Tuple
from backend.app.autofix import (
    AutoFixRegistry,
    PatchGenerator,
    PatchValidator,
    FixReanalyzer,
    sha256_text,
)


class SafeFixEngine:
    @classmethod
    def is_rule_potentially_auto_fixable(cls, rule_id: Optional[str], original_snippet: str = "") -> Tuple[bool, Optional[str]]:
        defn = AutoFixRegistry.get(rule_id)
        if not defn or not defn.auto_fixable:
            reason = defn.unavailable_reason if defn and defn.unavailable_reason else "Auto Fix Unavailable for this recommendation."
            return False, reason
        return True, None

    @classmethod
    def preview_patch(
        cls,
        rule_id: Optional[str],
        file_path: str,
        original_code: str,
        target_lines: List[int],
        original_snippet: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return PatchGenerator.generate_patch(
            rule_id=rule_id,
            file_path=file_path,
            original_code=original_code,
            target_lines=target_lines,
            original_snippet=original_snippet,
            options=options,
        )

    @staticmethod
    def compute_comparison(before_analysis, after_analysis) -> Dict[str, Any]:
        return FixReanalyzer.compute_comparison(before_analysis, after_analysis)


__all__ = ["SafeFixEngine", "sha256_text", "PatchValidator", "PatchGenerator", "FixReanalyzer", "AutoFixRegistry"]
