from backend.app.autofix.registry import AutoFixRegistry, AutoFixDefinition
from backend.app.autofix.patch_generator import PatchGenerator
from backend.app.autofix.patch_validator import PatchValidator, PatchValidationResult, sha256_text
from backend.app.autofix.patch_applier import PatchApplier
from backend.app.autofix.reanalyzer import FixReanalyzer

__all__ = [
    "AutoFixRegistry",
    "AutoFixDefinition",
    "PatchGenerator",
    "PatchValidator",
    "PatchValidationResult",
    "PatchApplier",
    "FixReanalyzer",
    "sha256_text",
]
