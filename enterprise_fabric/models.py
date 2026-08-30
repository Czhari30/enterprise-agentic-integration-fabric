from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DataClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


CLASSIFICATION_RANK = {
    DataClass.PUBLIC: 0,
    DataClass.INTERNAL: 1,
    DataClass.CONFIDENTIAL: 2,
    DataClass.RESTRICTED: 3,
}


class WorkflowStatus(str, Enum):
    RECEIVED = "received"
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    DENIED = "denied"
    COMPENSATED = "compensated"
    FAILED = "failed"


@dataclass(frozen=True)
class ActorContext:
    tenant_id: str
    subject: str
    roles: tuple[str, ...] = ("operator",)
    scopes: tuple[str, ...] = ("payments:read", "integration:read")
    clearance: DataClass = DataClass.CONFIDENTIAL


@dataclass(frozen=True)
class WorkRequest:
    request_id: str
    tenant_id: str
    intent: str
    idempotency_key: str
    amount: float | None = None
    currency: str = "MYR"
    customer_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Evidence:
    document_id: str
    title: str
    excerpt: str
    score: float
    citation: str
    classification: DataClass


@dataclass(frozen=True)
class PlannedStep:
    step_id: str
    agent: str
    action: str
    tool: str
    arguments: dict[str, Any]
    risk: str = "low"
    requires_approval: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False
    policy_id: str = "enterprise-default"


@dataclass(frozen=True)
class ToolResult:
    tool: str
    outcome: str
    data: dict[str, Any]
    compensating_token: str | None = None


@dataclass
class WorkflowState:
    workflow_id: str
    request: WorkRequest
    status: WorkflowStatus = WorkflowStatus.RECEIVED
    evidence: list[Evidence] = field(default_factory=list)
    plan: list[PlannedStep] = field(default_factory=list)
    policy_decisions: list[PolicyDecision] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["request"] = asdict(self.request)
        value["evidence"] = [
            {**asdict(item), "classification": item.classification.value}
            for item in self.evidence
        ]
        return value
