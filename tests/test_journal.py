from __future__ import annotations

import os
import tempfile
import unittest

from enterprise_fabric.journal import WorkflowJournal
from enterprise_fabric.models import WorkRequest, WorkflowState, WorkflowStatus


class JournalTests(unittest.TestCase):
    def test_state_survives_a_new_journal_connection(self) -> None:
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        try:
            first = WorkflowJournal(path)
            state = WorkflowState(
                workflow_id="wf-durable",
                request=WorkRequest(
                    request_id="req-durable",
                    tenant_id="tenant-a",
                    intent="Investigate an integration timeout",
                    idempotency_key="idem-durable",
                ),
                status=WorkflowStatus.PLANNED,
            )
            first.save(state)
            first.append(state.workflow_id, "workflow.saved", {"status": "planned"})

            second = WorkflowJournal(path)
            recovered = second.load("wf-durable")
            self.assertIsNotNone(recovered)
            self.assertEqual(recovered.status, WorkflowStatus.PLANNED)
            self.assertEqual(second.events("wf-durable")[0]["type"], "workflow.saved")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
