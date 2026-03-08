from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: int = 60


def config_from_env(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int = 60,
) -> LLMConfig:
    resolved_base = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com").strip().rstrip("/")
    resolved_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    resolved_model = (model or os.getenv("OPENAI_MODEL") or "").strip()
    return LLMConfig(base_url=resolved_base, api_key=resolved_key, model=resolved_model, timeout=timeout)


def build_log_analysis_messages(question: str, log_lines: list[str]) -> list[dict[str, str]]:
    lines_block = "\n".join(log_lines)
    system_prompt = (
        "You are a senior SRE log analysis assistant. "
        "Analyze log snippets, identify root causes, impact, and next troubleshooting steps. "
        "Keep response concise and actionable."
    )
    user_prompt = (
        f"User question: {question}\n\n"
        "Log snippets:\n"
        f"{lines_block}\n\n"
        "Please provide:\n"
        "1) Key findings\n"
        "2) Possible root causes\n"
        "3) Suggested next actions"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def chat_completion(config: LLMConfig, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    if not config.api_key:
        raise ValueError("Missing API key. Set OPENAI_API_KEY or pass --llm-api-key.")
    if not config.model:
        raise ValueError("Missing model name. Set OPENAI_MODEL or pass --llm-model.")

    url = f"{config.base_url}/v1/chat/completions"
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    )

    try:
        with request.urlopen(req, timeout=max(1, int(config.timeout))) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM request failed: HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    data = json.loads(raw)
    return _extract_content(data)


def _extract_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response missing choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("LLM response format invalid: choices[0].")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM response format invalid: message.")
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts).strip()
    raise RuntimeError("LLM response missing message content.")
