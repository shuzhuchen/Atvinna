from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

import certifi
from dotenv import load_dotenv
from pydantic import BaseModel


class LLMClient:
    """Mistral client used by every production pipeline step."""

    def __init__(self, model: str = "mistral-small-latest") -> None:
        load_dotenv()
        self.model = os.getenv("MISTRAL_MODEL", model)
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.api_url = os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions")

        if not self.api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY is required. Add it to a root .env file before running the pipeline."
            )

    def call_json(self, step_name: str, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        content = self._mistral_chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        f"You are executing pipeline action {step_name}. "
                        "Return only valid JSON matching the requested schema."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
        return response_model.model_validate_json(content)

    def _mistral_chat_completion(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(request, timeout=45, context=ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Mistral API request failed: {exc.code} {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Mistral API request failed: {exc.reason}") from exc

        return data["choices"][0]["message"].get("content") or "{}"
