import os
import json
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings


class LLMSemanticAnalyzer:
    """
    Optional LLM-based semantic analysis component. Uses Gemini or OpenAI APIs
    when configured to detect subtle semantic and algorithmic logic errors,
    falling back seamlessly to deterministic AST semantic evaluation when unset.
    """

    @classmethod
    def is_configured(cls) -> bool:
        return bool(settings.GEMINI_API_KEY or settings.OPENAI_API_KEY)

    @classmethod
    def analyze(cls, code: str, file_path: str = "service.py") -> List[Dict[str, Any]]:
        if not cls.is_configured():
            return []

        # When API keys are supplied by the user/environment, query the configured provider
        try:
            if settings.GEMINI_API_KEY:
                return cls._query_gemini(code, file_path)
            elif settings.OPENAI_API_KEY:
                return cls._query_openai(code, file_path)
        except Exception:
            return []
        return []

    @classmethod
    def _query_gemini(cls, code: str, file_path: str) -> List[Dict[str, Any]]:
        # Structured Gemini REST call using standard library urllib
        import urllib.request
        api_key = settings.GEMINI_API_KEY
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        prompt = (
            "You are a static analysis expert. Analyze this Python code for LOGICAL ERRORS that compile and run but produce wrong results.\n"
            "Return JSON array of findings with: rule_id, title, line_number, description, suggested_next_step.\n"
            f"Code:\n```python\n{code}\n```"
        )
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode())
            text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
            items = json.loads(text)
            for item in items:
                item["category"] = "Logical Error"
                item["file_path"] = file_path
                item["severity"] = "High"
            return items

    @classmethod
    def _query_openai(cls, code: str, file_path: str) -> List[Dict[str, Any]]:
        # Structured OpenAI REST call
        import urllib.request
        api_key = settings.OPENAI_API_KEY
        url = "https://api.openai.com/v1/chat/completions"
        prompt = (
            "Analyze this Python code for LOGICAL ERRORS that execute but give wrong outputs. "
            "Return a JSON array of objects with: rule_id, title, line_number, description, suggested_next_step."
        )
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": code}
            ],
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode())
            text = resp_data["choices"][0]["message"]["content"]
            parsed = json.loads(text)
            items = parsed.get("findings") or parsed.get("errors") or []
            for item in items:
                item["category"] = "Logical Error"
                item["file_path"] = file_path
                item["severity"] = "High"
            return items
