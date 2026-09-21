from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class JsonHttpClient:
    """Small JSON-over-HTTP adapter with explicit timeouts and error handling."""

    base_url: str
    timeout_s: float = 5.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = requests.get(
            f"{self.base_url}/{path.lstrip('/')}",
            params=params,
            timeout=self.timeout_s,
        )
        if response.status_code == 404:
            return {"error": response.json().get("detail", "Not found")}
        response.raise_for_status()
        return response.json()
