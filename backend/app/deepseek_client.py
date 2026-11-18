"""DeepSeek API client wrapper."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class JsonChatClient(Protocol):
    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Return a JSON object from an LLM chat completion."""


class DeepSeekClient:
    """OpenAI-compatible DeepSeek client using JSON response mode."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-pro",
    ) -> None:
        self.api_key = api_key or _load_deepseek_api_key()
        self.base_url = base_url
        self.model = model

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("The openai package is required for DeepSeek calls") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("DeepSeek returned an empty response")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("DeepSeek JSON response must be an object")
        return parsed


def _load_deepseek_api_key() -> str:
    env_value = os.getenv("DEEPSEEK_API_KEY")
    if env_value:
        return env_value

    project_root = Path(__file__).resolve().parents[2]
    for env_path in (project_root / ".env", project_root / "backend" / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == "DEEPSEEK_API_KEY":
                clean_value = value.strip().strip('"').strip("'")
                if clean_value:
                    return clean_value

    raise RuntimeError("DEEPSEEK_API_KEY is not configured")
