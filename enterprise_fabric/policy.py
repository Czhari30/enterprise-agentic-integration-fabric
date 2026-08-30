from __future__ import annotations

from .connectors import ToolSpec
from .models import (
    CLASSIFICATION_RANK,
    ActorContext,
    DataClass,
    PolicyDecision,
    WorkRequest,
)
from .security import contains_prompt_injection


class PolicyEngine:
    """Small policy-as-code kernel used before retrieval and every tool call."""

    def __init__(self, approval_threshold: float = 10_000.0) -> None:
        self.approval_threshold = approval_threshold

    def authorize_request(
        self, request: WorkRequest, actor: ActorContext
    ) -> PolicyDecision:
        if request.tenant_id != actor.tenant_id:
            return PolicyDecision(False, "Cross-tenant access is forbidden", policy_id="TENANT-001")
        if contains_prompt_injection(request.intent):
            return PolicyDecision(False, "Prompt-injection pattern detected", policy_id="AI-INPUT-004")
        return PolicyDecision(True, "Request passed intake controls", policy_id="INTAKE-001")

    def can_read(self, classification: DataClass, actor: ActorContext) -> bool:
        return CLASSIFICATION_RANK[actor.clearance] >= CLASSIFICATION_RANK[classification]

    def authorize_tool(
        self,
        spec: ToolSpec,
        request: WorkRequest,
        actor: ActorContext,
    ) -> PolicyDecision:
        if spec.required_scope not in actor.scopes:
            return PolicyDecision(
                False,
                f"Missing scope: {spec.required_scope}",
                policy_id="AUTHZ-002",
            )

        approval = spec.risk in {"high", "critical"}
        if request.amount is not None and request.amount >= self.approval_threshold:
            approval = True

        reason = "Tool call authorized"
        if approval:
            reason = "Human approval required for a high-impact action"
        return PolicyDecision(
            True,
            reason,
            requires_approval=approval,
            policy_id="TOOL-003",
        )
