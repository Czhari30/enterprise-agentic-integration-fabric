from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .models import Evidence


class ToolSuggestionGateway(Protocol):
    def suggest_tools(
        self,
        intent: str,
        evidence: list[Evidence],
        allowed_tools: list[str],
    ) -> list[str]: ...


def validate_tool_suggestions(payload: object, allowed_tools: list[str]) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("tools"), list):
        raise ValueError("Model output must be an object containing a tools list")
    allowlist = set(allowed_tools)
    suggestions: list[str] = []
    for item in payload["tools"]:
        if not isinstance(item, str) or item not in allowlist:
            raise ValueError(f"Model suggested an unregistered tool: {item!r}")
        if item not in suggestions:
            suggestions.append(item)
    return suggestions


@dataclass(frozen=True)
class OpenAICompatibleGateway:
    """Optional model gateway; model output can select tools but cannot execute them."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 15.0

    def suggest_tools(
        self,
        intent: str,
        evidence: list[Evidence],
        allowed_tools: list[str],
    ) -> list[str]:
        context = [
            {"citation": item.citation, "excerpt": item.excerpt}
            for item in evidence[:4]
        ]
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a constrained enterprise workflow planner. Return JSON only as "
                        "{\"tools\": [\"registered.tool\"]}. Never invent tools or arguments."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"intent": intent, "evidence": context, "allowed_tools": allowed_tools}
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        return validate_tool_suggestions(json.loads(content), allowed_tools)
