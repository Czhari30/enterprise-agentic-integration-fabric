from __future__ import annotations

import uuid

from .connectors import ToolRegistry
from .journal import WorkflowJournal
from .models import ActorContext, PolicyDecision, WorkflowState, WorkflowStatus, WorkRequest
from .planner import BoundedPlanner
from .policy import PolicyEngine
from .retrieval import HybridRetriever
from .telemetry import Telemetry


class AgenticOrchestrator:
    """Governed plan-execute-verify workflow with durable approval checkpoints."""

    def __init__(
        self,
        registry: ToolRegistry,
        retriever: HybridRetriever,
        policy: PolicyEngine,
        planner: BoundedPlanner,
        journal: WorkflowJournal,
        telemetry: Telemetry,
    ) -> None:
        self.registry = registry
        self.retriever = retriever
        self.policy = policy
        self.planner = planner
        self.journal = journal
        self.telemetry = telemetry

    def start(self, request: WorkRequest, actor: ActorContext) -> WorkflowState:
        existing = self.journal.find_by_idempotency(request.idempotency_key)
        if existing:
            self.telemetry.metrics["idempotency_hit_total"] += 1
            return existing

        state = WorkflowState(workflow_id=f"wf-{uuid.uuid4().hex[:12]}", request=request)
        trace_id = uuid.uuid4().hex
        intake = self.policy.authorize_request(request, actor)
        state.policy_decisions.append(intake)
        self.journal.append(state.workflow_id, "request.received", {"request_id": request.request_id})
        if not intake.allowed:
            state.status = WorkflowStatus.DENIED
            state.error = intake.reason
            self._persist(state, "policy.denied", {"reason": intake.reason})
            return state

        with self.telemetry.span(
            "agent.retrieval",
            trace_id=trace_id,
            attributes={
                "gen_ai.operation.name": "retrieval",
                "gen_ai.agent.name": "knowledge-agent",
                "tenant.id": actor.tenant_id,
            },
        ):
            state.evidence = self.retriever.search(request.intent, actor)

        with self.telemetry.span(
            "agent.plan",
            trace_id=trace_id,
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.agent.name": "bounded-planner",
            },
        ):
            state.plan = self.planner.create_plan(request, state.evidence)
            state.status = WorkflowStatus.PLANNED

        for step in state.plan:
            decision = self.policy.authorize_tool(self.registry.spec(step.tool), request, actor)
            state.policy_decisions.append(decision)
            if not decision.allowed:
                state.status = WorkflowStatus.DENIED
                state.error = decision.reason
                self._persist(state, "tool.denied", {"tool": step.tool, "reason": decision.reason})
                return state

        if any(decision.requires_approval for decision in state.policy_decisions):
            state.status = WorkflowStatus.WAITING_APPROVAL
            self._persist(
                state,
                "approval.requested",
                {"reason": "High-impact tool or value threshold", "maker": actor.subject},
            )
            return state

        return self._execute(state, trace_id)

    def approve(
        self,
        workflow_id: str,
        actor: ActorContext,
        approval_reference: str,
    ) -> WorkflowState:
        state = self.journal.load(workflow_id)
        if state is None:
            raise KeyError(workflow_id)
        if state.request.tenant_id != actor.tenant_id:
            raise PermissionError("Cross-tenant approval is forbidden")
        if "approver" not in actor.roles:
            raise PermissionError("The approver role is required")
        maker = str(state.request.metadata.get("initiated_by", ""))
        if maker and maker == actor.subject:
            raise PermissionError("Maker-checker separation requires a different approver")
        if state.status is not WorkflowStatus.WAITING_APPROVAL:
            return state

        state.approvals.append(approval_reference)
        self._persist(
            state,
            "approval.granted",
            {"approver": actor.subject, "reference": approval_reference},
        )
        return self._execute(state, uuid.uuid4().hex)

    def _execute(self, state: WorkflowState, trace_id: str) -> WorkflowState:
        state.status = WorkflowStatus.EXECUTING
        self._persist(state, "execution.started", {"step_count": len(state.plan)})
        executed = []
        try:
            for step in state.plan:
                with self.telemetry.span(
                    "agent.execute_tool",
                    trace_id=trace_id,
                    attributes={
                        "gen_ai.operation.name": "execute_tool",
                        "gen_ai.tool.name": step.tool,
                        "gen_ai.agent.name": step.agent,
                        "workflow.step.id": step.step_id,
                    },
                ):
                    result = self.registry.execute(
                        step.tool,
                        step.arguments,
                        state.request,
                        execution_key=f"{state.request.idempotency_key}:{step.step_id}",
                    )
                executed.append(result)
                state.results.append(result)
                self.journal.append(
                    state.workflow_id,
                    "tool.completed",
                    {"tool": result.tool, "outcome": result.outcome},
                )

            state.status = WorkflowStatus.VERIFYING
            self._verify(state)
            state.status = WorkflowStatus.COMPLETED
            self.telemetry.metrics["workflow_completed_total"] += 1
            self._persist(
                state,
                "workflow.completed",
                {"evidence_count": len(state.evidence), "tool_count": len(state.results)},
            )
            return state
        except Exception as exc:
            state.error = str(exc)
            compensations = [item.compensating_token for item in reversed(executed) if item.compensating_token]
            state.status = WorkflowStatus.COMPENSATED if compensations else WorkflowStatus.FAILED
            self.telemetry.metrics["workflow_failed_total"] += 1
            self._persist(
                state,
                "workflow.failed",
                {"error": str(exc), "compensations": compensations},
            )
            return state

    @staticmethod
    def _verify(state: WorkflowState) -> None:
        if not state.evidence:
            raise ValueError("No policy-visible evidence was retrieved")
        if not state.results:
            raise ValueError("No tools completed")
        if any(step.requires_approval for step in state.plan) and not state.approvals:
            raise ValueError("High-impact execution is missing approval evidence")
        if any(not item.citation.startswith("knowledge://") for item in state.evidence):
            raise ValueError("Evidence citation validation failed")

    def _persist(self, state: WorkflowState, event_type: str, payload: dict[str, object]) -> None:
        self.journal.save(state)
        self.journal.append(state.workflow_id, event_type, payload)
