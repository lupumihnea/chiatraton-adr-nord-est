"""Minimal paid-only OpenRouter JSON client used by the Qwen adapter."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OpenRouterConfig:
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 180.0
    app_url: str | None = None
    app_name: str = "ChIAtraton"


class OpenRouterError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, config: OpenRouterConfig) -> None:
        if not config.api_key:
            raise OpenRouterError("AI_API_KEY is not configured")
        if config.model.endswith(":free"):
            raise OpenRouterError(
                "This adapter is paid-only; AI_MODEL_NAME must not end in ':free'."
            )
        self.config = config

    async def json_chat(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 3500,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise OpenRouterError("httpx is required by the OpenRouter adapter") from exc

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.app_url:
            headers["HTTP-Referer"] = self.config.app_url
        if self.config.app_name:
            headers["X-Title"] = self.config.app_name

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout_seconds),
            trust_env=False,
        ) as client:
            for attempt in range(7):
                try:
                    response = await client.post(
                        f"{self.config.base_url.rstrip('/')}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    if attempt == 6:
                        raise OpenRouterError("AI request timed out") from exc
                    await asyncio.sleep(min(2 ** attempt, 15))
                    continue
                except httpx.RequestError as exc:
                    if attempt == 6:
                        raise OpenRouterError("AI provider is unavailable") from exc
                    await asyncio.sleep(min(2 ** attempt, 15))
                    continue

                if response.status_code == 401:
                    raise OpenRouterError("AI authentication failed")
                if response.status_code == 402:
                    raise OpenRouterError("OpenRouter paid model requires available credits")
                if response.status_code == 403:
                    raise OpenRouterError("AI provider rejected the request")
                if response.status_code == 404:
                    raise OpenRouterError(
                        f"OpenRouter model '{self.config.model}' was not found"
                    )
                if response.status_code == 413:
                    raise OpenRouterError("AI request payload is too large")
                if response.status_code == 429:
                    if attempt == 6:
                        raise OpenRouterError("AI provider rate limit reached")
                    retry_after = response.headers.get("retry-after")
                    try:
                        wait = float(retry_after) if retry_after else min(2 ** (attempt + 1), 30)
                    except ValueError:
                        wait = min(2 ** (attempt + 1), 30)
                    await asyncio.sleep(max(1.0, min(wait, 60.0)))
                    continue
                if 500 <= response.status_code < 600:
                    if attempt == 6:
                        raise OpenRouterError("AI provider failed after retries")
                    await asyncio.sleep(min(2 ** attempt, 15))
                    continue
                response.raise_for_status()

                try:
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    if isinstance(content, list):
                        content = "".join(
                            part.get("text", "")
                            for part in content
                            if isinstance(part, dict)
                        )
                    text = str(content).strip()
                    if text.startswith("```"):
                        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
                        text = re.sub(r"\s*```$", "", text)
                    result = json.loads(text)
                    if not isinstance(result, dict):
                        raise TypeError("JSON root is not an object")
                    return result
                except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise OpenRouterError("AI provider returned invalid JSON") from exc

        raise OpenRouterError("Unexpected AI retry loop exit")
