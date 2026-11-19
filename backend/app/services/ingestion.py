import os
import re
import io
import zipfile
from typing import List, Dict, Any
from backend.app.core.config import settings


class IngestionService:
    """
    Ingestion service that safely handles single files, multiple files, and ZIP archives.
    Guarantees:
    - Safe archive extraction (explicitly rejects Zip Slip path traversal and ZIP bombs).
    - Strict file extension & binary content validation.
    - File size enforcement.
    - Relative path retention and exclusion of build/cache directories.
    - Credential masking in displayed snippets.
    - Zero execution of uploaded source code.
    """

    SUPPORTED_CODE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
    }

    SUPPORTED_EXTENSIONS = {
        **SUPPORTED_CODE_EXTENSIONS,
        ".json": "json",
        ".csv": "csv",
        ".log": "log",
        ".txt": "text",
    }

    IGNORE_DIRS = {
        "__pycache__", ".git", ".github", ".vscode", ".idea", "node_modules",
        "dist", "build", "coverage", ".pytest_cache", ".venv", "venv", "env",
        "__MACOSX",
    }

    MAX_ZIP_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB total uncompressed zip-bomb guard

    @staticmethod
    def detect_language(filename: str, content: str = "") -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext in IngestionService.SUPPORTED_EXTENSIONS:
            return IngestionService.SUPPORTED_EXTENSIONS[ext]

        sniff = content[:800].lower()
        if "def " in sniff or ("import " in sniff and ":" in sniff):
            return "python"
        if "function " in sniff or "const " in sniff or ("import " in sniff and ";" in sniff):
            return "javascript"
        return "unsupported"

    @staticmethod
    def mask_credentials(snippet: str) -> str:
        """Masks discovered credentials in code or log snippets to prevent exposing secrets."""
        pattern = r'((?:api[_-]?key|password|secret|token|auth|bearer)[\s=:\"\']+\s*[\'\"])([^\'\"]{4,})([\'\"])'

        def replacer(match):
            prefix = match.group(1)
            val = match.group(2)
            suffix = match.group(3)
            masked = val[:2] + "****" + val[-2:] if len(val) > 6 else "******"
            return f"{prefix}{masked}{suffix}"

        return re.sub(pattern, replacer, snippet, flags=re.IGNORECASE)

    @staticmethod
    def read_text_safe(raw_bytes: bytes) -> str:
        """Decodes bytes using UTF-8 with fallback to latin-1; rejects binary null bytes."""
        if b"\x00" in raw_bytes:
            raise ValueError("Binary file content detected; only UTF-8/text source, log, or metric files are supported.")
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1", errors="replace")

    @classmethod
    def process_single_file(cls, filename: str, content_bytes: bytes) -> Dict[str, Any]:
        """Validates and processes a single source code file."""
        if not content_bytes or not content_bytes.strip():
            raise ValueError(f"File '{filename}' is empty.")
        if len(content_bytes) > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File '{filename}' exceeds maximum allowed size ({settings.MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB)."
            )

        safe_name = os.path.basename(filename)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in cls.SUPPORTED_CODE_EXTENSIONS:
            supported_str = ", ".join(sorted(cls.SUPPORTED_CODE_EXTENSIONS.keys()))
            raise ValueError(
                f"Unsupported source file type '{ext or 'none'}' for '{safe_name}'. Supported code formats: {supported_str}."
            )

        text = cls.read_text_safe(content_bytes)
        language = cls.SUPPORTED_CODE_EXTENSIONS[ext]
        lines = text.splitlines()

        return {
            "file_path": safe_name,
            "filename": safe_name,
            "content": text,
            "language": language,
            "lines_count": len(lines),
            "size_bytes": len(content_bytes),
        }

    @classmethod
    def process_zip_archive(cls, archive_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Safely extracts and validates source code files from a ZIP archive.
        Rejects directory traversal (Zip Slip), ZIP bombs, and malformed archives.
        """
        if not archive_bytes:
            raise ValueError("Uploaded ZIP archive is empty.")
        if len(archive_bytes) > settings.MAX_ZIP_SIZE_BYTES:
            raise ValueError(
                f"ZIP archive exceeds maximum compressed size ({settings.MAX_ZIP_SIZE_BYTES / 1024 / 1024:.0f}MB)."
            )

        try:
            zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
        except zipfile.BadZipFile:
            raise ValueError("Uploaded archive is not a valid or readable ZIP file.")

        infolist = zf.infolist()
        if len(infolist) > settings.MAX_ZIP_FILES:
            raise ValueError(
                f"Archive contains too many entries ({len(infolist)} > max {settings.MAX_ZIP_FILES})."
            )

        files: List[Dict[str, Any]] = []
        total_uncompressed = 0

        for info in infolist:
            raw_name = info.filename.replace("\\", "/")
            # Explicit Zip Slip / path traversal rejection
            if raw_name.startswith("/") or raw_name.startswith("../") or "/../" in raw_name or raw_name == "..":
                raise ValueError(f"Unsafe ZIP archive rejected: path traversal entry detected ('{info.filename}').")

            if info.is_dir():
                continue

            normalized_path = os.path.normpath(raw_name).replace("\\", "/")
            if normalized_path.startswith("/") or normalized_path.startswith("../") or "/../" in normalized_path:
                raise ValueError(f"Unsafe ZIP archive rejected: path traversal entry detected ('{info.filename}').")

            parts = normalized_path.split("/")
            if any(p.startswith(".") or p in cls.IGNORE_DIRS for p in parts):
                continue

            ext = os.path.splitext(normalized_path)[1].lower()
            if ext not in cls.SUPPORTED_CODE_EXTENSIONS:
                continue

            if info.file_size > settings.MAX_FILE_SIZE_BYTES:
                raise ValueError(
                    f"Archive entry '{normalized_path}' exceeds maximum file size ({settings.MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB)."
                )

            total_uncompressed += info.file_size
            if total_uncompressed > cls.MAX_ZIP_UNCOMPRESSED_BYTES:
                raise ValueError("ZIP archive exceeds maximum total uncompressed size limit (50MB).")

            raw_bytes = zf.read(info)
            if not raw_bytes.strip():
                continue
            text = cls.read_text_safe(raw_bytes)
            language = cls.SUPPORTED_CODE_EXTENSIONS[ext]

            files.append({
                "file_path": normalized_path,
                "filename": os.path.basename(normalized_path),
                "content": text,
                "language": language,
                "lines_count": len(text.splitlines()),
                "size_bytes": len(raw_bytes),
            })

        if not files:
            supported_str = ", ".join(sorted(cls.SUPPORTED_CODE_EXTENSIONS.keys()))
            raise ValueError(f"No supported source code files ({supported_str}) found in archive.")

        return files
