from __future__ import annotations

from .connectors import ToolRegistry
from .model_gateway import ToolSuggestionGateway
from .models import Evidence, PlannedStep, WorkRequest


class BoundedPlanner:
    """Deterministic planner whose output is constrained to the registered catalog."""

    def __init__(
        self,
        registry: ToolRegistry,
        model_gateway: ToolSuggestionGateway | None = None,
    ) -> None:
        self.registry = registry
        self.model_gateway = model_gateway

    def create_plan(self, request: WorkRequest, evidence: list[Evidence]) -> list[PlannedStep]:
        intent = request.intent.lower()
        selected: list[tuple[str, str, str, dict[str, object]]] = []

        if any(word in intent for word in ("payment", "transfer", "transaction", "timeout")):
            selected.extend(
                [
                    (
                        "integration-investigator",
                        "Read the payment state before proposing any mutation",
                        "payments.lookup",
                        {"payment_ref": request.metadata.get("payment_ref", "PAY-DEMO-1042")},
                    ),
                    (
                        "integration-investigator",
                        "Correlate gateway and runtime diagnostics",
                        "integration.trace",
                        {"correlation_id": request.metadata.get("correlation_id", "corr-demo-42")},
                    ),
                ]
            )

        if any(word in intent for word in ("kyc", "onboarding", "identity")):
            selected.append(
                (
                    "risk-analyst",
                    "Summarize onboarding signals for a human reviewer",
                    "customers.kyc_summary",
                    {"customer_ref": request.customer_ref or "CUS-DEMO-7"},
                )
            )

        if any(word in intent for word in ("replay", "retry", "redeliver")):
            selected.append(
                (
                    "workflow-operator",
                    "Replay the synthetic message with the original idempotency key",
                    "integration.replay_message",
                    {"message_id": request.metadata.get("message_id", "MSG-DEMO-77")},
                )
            )

        if "release" in intent and "hold" in intent:
            selected.append(
                (
                    "workflow-operator",
                    "Release the synthetic hold after maker-checker approval",
                    "payments.release_hold",
                    {"payment_ref": request.metadata.get("payment_ref", "PAY-DEMO-1042")},
                )
            )

        if not selected:
            selected.append(
                (
                    "integration-investigator",
                    "Inspect the integration path and return a bounded diagnostic",
                    "integration.trace",
                    {"correlation_id": request.metadata.get("correlation_id", "corr-demo-42")},
                )
            )

        if self.model_gateway is not None:
            suggestions = self.model_gateway.suggest_tools(
                request.intent,
                evidence,
                [item.name for item in self.registry.catalog()],
            )
            existing = {tool: (agent, action, tool, arguments) for agent, action, tool, arguments in selected}
            selected = [existing[name] for name in suggestions if name in existing] or selected

        steps: list[PlannedStep] = []
        seen: set[str] = set()
        for agent, action, tool, arguments in selected:
            if tool in seen:
                continue
            spec = self.registry.spec(tool)
            seen.add(tool)
            steps.append(
                PlannedStep(
                    step_id=f"step-{len(steps) + 1:02d}",
                    agent=agent,
                    action=action,
                    tool=tool,
                    arguments=dict(arguments),
                    risk=spec.risk,
                    requires_approval=spec.risk in {"high", "critical"},
                )
            )
        return steps
