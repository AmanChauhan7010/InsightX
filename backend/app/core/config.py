import os
from pathlib import Path
from typing import List
from pydantic import BaseModel

# Anchor default SQLite database to the repository root so history persists reliably
# regardless of the working directory from which uvicorn/pytest is launched.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_URL = f"sqlite:///{(PROJECT_ROOT / 'insightx.db').as_posix()}"


class Settings(BaseModel):
    PROJECT_NAME: str = "InsightX"
    PROJECT_TITLE: str = "InsightX — AI Root Cause & Decision Intelligence Platform"
    VERSION: str = "2.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # Persistent Database (absolute path by default)
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)

    # Upload and Analysis Limits
    MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    MAX_ZIP_SIZE_BYTES: int = 30 * 1024 * 1024   # 30 MB
    MAX_ZIP_FILES: int = 300

    # Configurable Auto-Fix Policies
    DEFAULT_HTTP_TIMEOUT_SECONDS: float = float(os.getenv("INSIGHTX_DEFAULT_HTTP_TIMEOUT", "10"))
    DEFAULT_COLLECTION_MAXLEN: int = int(os.getenv("INSIGHTX_DEFAULT_COLLECTION_MAXLEN", "1000"))

    # Allowed source code extensions
    SUPPORTED_CODE_EXTENSIONS: List[str] = [
        ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"
    ]

    # Optional LLM Integration (falls back to deterministic engine when unset)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "*"
    ]


settings = Settings()
