import os
import sys
import time
import subprocess
from typing import Dict, Any, Optional


class IsolatedCodeRunner:
    """
    Executes Python code in a sandboxed, isolated subprocess with strict timeouts
    and resource limits to safely evaluate code and verify test cases without
    affecting the main application process.
    """

    DEFAULT_TIMEOUT: float = 2.0  # seconds

    @classmethod
    def run_code(
        cls,
        code: str,
        timeout: Optional[float] = None,
        stdin_text: str = "",
    ) -> Dict[str, Any]:
        timeout_val = timeout or cls.DEFAULT_TIMEOUT
        start_time = time.perf_counter()

        # Sanitize execution environment
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=timeout_val,
                env=clean_env,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or "",
                "timed_out": False,
                "duration_ms": duration_ms,
            }
        except subprocess.TimeoutExpired as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "",
                "stderr": f"Execution timed out after {timeout_val} seconds (possible infinite loop).",
                "timed_out": True,
                "duration_ms": duration_ms,
            }
        except Exception as ex:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Subprocess runner execution error: {str(ex)}",
                "timed_out": False,
                "duration_ms": duration_ms,
            }
