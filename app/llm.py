from __future__ import annotations

import os
from typing import Protocol

import requests


class ChatClient(Protocol):
    """Minimal provider interface used by the agent core."""

    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        ...


class OllamaClient:
    """Local Ollama provider. This is the default and requires no paid API."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or "qwen2.5:7b"

    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"]


class OpenAICompatibleClient:
    """Generic OpenAI-compatible HTTP provider.

    The class is intentionally SDK-free and can point at local servers such as
    LM Studio, vLLM, or another OpenAI-compatible endpoint. No remote service or
    API key is enabled by default.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("OPENAI_COMPAT_BASE_URL")
            or "http://localhost:1234/v1"
        ).rstrip("/")
        self.model = model or os.getenv("OPENAI_COMPAT_MODEL") or "local-model"
        self.api_key = api_key or os.getenv("OPENAI_COMPAT_API_KEY")

    def chat(self, messages: list[dict], temperature: float = 0.1) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        r = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def create_llm_client(provider: str | None = None) -> ChatClient:
    """Create a provider from environment/configuration.

    Supported values:
    - ``ollama`` (default, local)
    - ``openai_compatible`` (generic HTTP protocol; can also be fully local)
    """

    name = (provider or os.getenv("LLM_PROVIDER") or "ollama").strip().lower()
    if name == "ollama":
        return OllamaClient()
    if name in {"openai_compatible", "openai-compatible"}:
        return OpenAICompatibleClient()
    raise ValueError(
        f"Unsupported LLM_PROVIDER: {name}. Available: ollama, openai_compatible"
    )
