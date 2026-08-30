from __future__ import annotations

import unittest

from enterprise_fabric.models import ActorContext, DataClass, WorkRequest, WorkflowStatus
from enterprise_fabric.service import EnterpriseFabric


class OrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = EnterpriseFabric()
        self.maker = ActorContext(
            tenant_id="tenant-a",
            subject="maker-01",
            scopes=(
                "payments:read",
                "payments:write",
                "integration:read",
                "integration:write",
                "customers:restricted:read",
            ),
            clearance=DataClass.RESTRICTED,
        )

    def request(self, intent: str, *, amount: float | None = None, key: str = "idem-001") -> WorkRequest:
        return WorkRequest(
            request_id=f"request-{key}",
            tenant_id="tenant-a",
            intent=intent,
            idempotency_key=key,
            amount=amount,
            metadata={"initiated_by": "maker-01", "payment_ref": "PAY-DEMO-1042"},
        )

    def test_read_only_investigation_completes_with_evidence(self) -> None:
        state = self.fabric.orchestrator.start(
            self.request("Investigate the payment timeout and correlate the integration trace"),
            self.maker,
        )

        self.assertEqual(state.status, WorkflowStatus.COMPLETED)
        self.assertGreaterEqual(len(state.evidence), 1)
        self.assertEqual([result.tool for result in state.results], ["payments.lookup", "integration.trace"])
        self.assertTrue(all(item.citation.startswith("knowledge://") for item in state.evidence))

    def test_high_impact_replay_pauses_for_maker_checker_approval(self) -> None:
        state = self.fabric.orchestrator.start(
            self.request(
                "Investigate the payment timeout and safely replay the message",
                amount=25_000,
                key="idem-high-value",
            ),
            self.maker,
        )
        self.assertEqual(state.status, WorkflowStatus.WAITING_APPROVAL)
        self.assertEqual(state.results, [])

        checker = ActorContext(
            tenant_id="tenant-a",
            subject="checker-02",
            roles=("approver",),
            scopes=self.maker.scopes,
            clearance=DataClass.RESTRICTED,
        )
        completed = self.fabric.orchestrator.approve(
            state.workflow_id,
            checker,
            "APR-2026-0001",
        )
        self.assertEqual(completed.status, WorkflowStatus.COMPLETED)
        self.assertIn("APR-2026-0001", completed.approvals)
        self.assertIn("integration.replay_message", [item.tool for item in completed.results])

    def test_maker_cannot_self_approve(self) -> None:
        state = self.fabric.orchestrator.start(
            self.request("Replay the payment message", amount=15_000, key="idem-maker"),
            self.maker,
        )
        self_approver = ActorContext(
            tenant_id="tenant-a",
            subject="maker-01",
            roles=("approver",),
            scopes=self.maker.scopes,
            clearance=DataClass.RESTRICTED,
        )
        with self.assertRaises(PermissionError):
            self.fabric.orchestrator.approve(state.workflow_id, self_approver, "APR-SELF")

    def test_idempotency_returns_the_original_workflow(self) -> None:
        request = self.request("Investigate a gateway timeout", key="idem-repeat")
        first = self.fabric.orchestrator.start(request, self.maker)
        second = self.fabric.orchestrator.start(request, self.maker)
        self.assertEqual(first.workflow_id, second.workflow_id)
        self.assertEqual(self.fabric.telemetry.metrics["idempotency_hit_total"], 1)


if __name__ == "__main__":
    unittest.main()
