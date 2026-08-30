from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import ToolResult, WorkRequest
from .security import stable_token


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    required_scope: str
    risk: str
    read_only: bool
    adapter: str


ToolHandler = Callable[[dict[str, Any], WorkRequest], ToolResult]


class ToolRegistry:
    """Allow-listed enterprise tool catalog with idempotent synthetic adapters."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, ToolHandler]] = {}
        self._executions: dict[str, ToolResult] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = (spec, handler)

    def spec(self, name: str) -> ToolSpec:
        return self._tools[name][0]

    def catalog(self) -> list[ToolSpec]:
        return [item[0] for item in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        request: WorkRequest,
        execution_key: str,
    ) -> ToolResult:
        if execution_key in self._executions:
            return self._executions[execution_key]
        _, handler = self._tools[name]
        result = handler(arguments, request)
        self._executions[execution_key] = result
        return result


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    def payment_lookup(arguments: dict[str, Any], request: WorkRequest) -> ToolResult:
        reference = arguments.get("payment_ref") or request.metadata.get("payment_ref", "PAY-DEMO-1042")
        return ToolResult(
            "payments.lookup",
            "found",
            {
                "payment_ref": reference,
                "status": "pending_downstream_confirmation",
                "amount": request.amount,
                "currency": request.currency,
                "synthetic": True,
            },
        )

    def gateway_trace(arguments: dict[str, Any], request: WorkRequest) -> ToolResult:
        return ToolResult(
            "integration.trace",
            "correlated",
            {
                "correlation_id": arguments.get("correlation_id", f"corr-{request.request_id[-8:]}"),
                "gateway": "policy-pass",
                "integration_runtime": "downstream-timeout",
                "event_stream": "delivery-confirmed",
                "synthetic": True,
            },
        )

    def kyc_summary(arguments: dict[str, Any], request: WorkRequest) -> ToolResult:
        return ToolResult(
            "customers.kyc_summary",
            "manual_review_recommended",
            {
                "customer_token": stable_token(request.customer_ref or "synthetic-customer"),
                "signals": ["document-name-mismatch", "device-risk-low"],
                "decision": "not-made-by-agent",
                "synthetic": True,
            },
        )

    def replay_message(arguments: dict[str, Any], request: WorkRequest) -> ToolResult:
        token = f"replay:{request.idempotency_key}"
        return ToolResult(
            "integration.replay_message",
            "accepted",
            {
                "message_id": arguments.get("message_id", "MSG-DEMO-77"),
                "idempotency_key": request.idempotency_key,
                "synthetic": True,
            },
            compensating_token=token,
        )

    def release_hold(arguments: dict[str, Any], request: WorkRequest) -> ToolResult:
        return ToolResult(
            "payments.release_hold",
            "released_in_sandbox",
            {
                "payment_ref": arguments.get("payment_ref", "PAY-DEMO-1042"),
                "approval_bound": True,
                "synthetic": True,
            },
            compensating_token=f"restore:{request.idempotency_key}",
        )

    specs = (
        ToolSpec(
            "payments.lookup",
            "Read a synthetic payment status through an API-led connector.",
            "payments:read",
            "low",
            True,
            "mulesoft-compatible-api",
        ),
        ToolSpec(
            "integration.trace",
            "Correlate gateway, integration-runtime and event-stream diagnostics.",
            "integration:read",
            "low",
            True,
            "ibm-ace-datapower-pattern",
        ),
        ToolSpec(
            "customers.kyc_summary",
            "Summarize synthetic onboarding signals without making a customer decision.",
            "customers:restricted:read",
            "high",
            True,
            "api-led-connector",
        ),
        ToolSpec(
            "integration.replay_message",
            "Replay an idempotent synthetic integration message.",
            "integration:write",
            "high",
            False,
            "kafka-compatible-event-adapter",
        ),
        ToolSpec(
            "payments.release_hold",
            "Release a synthetic payment hold after explicit approval.",
            "payments:write",
            "critical",
            False,
            "mcp-style-tool-adapter",
        ),
    )
    handlers = (payment_lookup, gateway_trace, kyc_summary, replay_message, release_hold)
    for spec, handler in zip(specs, handlers, strict=True):
        registry.register(spec, handler)
    return registry
