from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .models import ActorContext, DataClass, Evidence
from .policy import PolicyEngine


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]+")


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    tenant_id: str
    title: str
    section: str
    content: str
    classification: DataClass


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _dense_hash(text: str, dimensions: int = 96) -> list[float]:
    vector = [0.0] * dimensions
    tokens = _tokens(text)
    for token in tokens:
        for width in (2, 3):
            for index in range(max(1, len(token) - width + 1)):
                gram = token[index : index + width]
                bucket = sum((offset + 1) * ord(char) for offset, char in enumerate(gram))
                vector[bucket % dimensions] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class HybridRetriever:
    """Tenant-filtered lexical + deterministic dense retrieval with citations."""

    def __init__(self, documents: list[KnowledgeDocument], policy: PolicyEngine) -> None:
        self.documents = documents
        self.policy = policy

    def search(self, query: str, actor: ActorContext, limit: int = 4) -> list[Evidence]:
        visible = [
            doc
            for doc in self.documents
            if doc.tenant_id in {actor.tenant_id, "shared"}
            and self.policy.can_read(doc.classification, actor)
        ]
        if not visible:
            return []

        query_terms = Counter(_tokens(query))
        query_dense = _dense_hash(query)
        scored: list[tuple[float, KnowledgeDocument]] = []
        for doc in visible:
            text = f"{doc.title} {doc.section} {doc.content}"
            doc_terms = Counter(_tokens(text))
            overlap = sum(min(count, doc_terms[term]) for term, count in query_terms.items())
            lexical = overlap / max(1, sum(query_terms.values()))
            dense = _cosine(query_dense, _dense_hash(text))
            score = (0.62 * lexical) + (0.38 * dense)
            scored.append((score, doc))

        ranked = sorted(scored, key=lambda item: (-item[0], item[1].document_id))[:limit]
        return [
            Evidence(
                document_id=doc.document_id,
                title=doc.title,
                excerpt=doc.content[:360],
                score=round(score, 4),
                citation=f"knowledge://{doc.document_id}#{doc.section.lower().replace(' ', '-')}",
                classification=doc.classification,
            )
            for score, doc in ranked
            if score > 0
        ]


def sample_knowledge_base() -> list[KnowledgeDocument]:
    return [
        KnowledgeDocument(
            "runbook-payment-timeout",
            "shared",
            "Payment timeout recovery",
            "Safe replay",
            (
                "Before replaying a payment message, verify the idempotency key, inspect the "
                "downstream status, and require approval for high-value or non-read-only actions."
            ),
            DataClass.INTERNAL,
        ),
        KnowledgeDocument(
            "runbook-api-gateway",
            "shared",
            "API gateway incident triage",
            "Diagnostics",
            (
                "Correlate gateway request IDs with integration runtime traces. Check policy "
                "failures, upstream latency, circuit-breaker state, and schema validation errors."
            ),
            DataClass.INTERNAL,
        ),
        KnowledgeDocument(
            "standard-agent-tools",
            "shared",
            "Governed agent tool standard",
            "Controls",
            (
                "Agents may call only registered tools. Every action requires tenant context, "
                "least-privilege scopes, redacted telemetry, an audit event, and deterministic validation."
            ),
            DataClass.CONFIDENTIAL,
        ),
        KnowledgeDocument(
            "tenant-a-kyc",
            "tenant-a",
            "KYC exception procedure",
            "Escalation",
            (
                "Identity mismatches must be routed to manual review. The agent may summarize "
                "signals but must not approve, reject, or alter a customer risk rating."
            ),
            DataClass.RESTRICTED,
        ),
        KnowledgeDocument(
            "tenant-b-private",
            "tenant-b",
            "Tenant B confidential operations",
            "Isolation",
            "This document must never be visible to tenant A workflows.",
            DataClass.CONFIDENTIAL,
        ),
    ]
