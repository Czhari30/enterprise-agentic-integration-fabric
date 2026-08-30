from __future__ import annotations

import hashlib
import re


_PATTERNS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[PAYMENT_CARD]"),
    (re.compile(r"\b(?:acct|account)[- :#]*[A-Z0-9]{6,20}\b", re.I), "[ACCOUNT]"),
    (re.compile(r"\b(?:\+?6?01)[0-46-9]-?\d{7,8}\b"), "[PHONE]"),
)

_INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal system prompt",
    "bypass policy",
    "disable guardrail",
    "exfiltrate",
    "act as root",
)


def redact(text: str) -> str:
    safe = text
    for pattern, replacement in _PATTERNS:
        safe = pattern.sub(replacement, safe)
    return safe


def contains_prompt_injection(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return any(marker in normalized for marker in _INJECTION_MARKERS)


def stable_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
