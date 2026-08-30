"""Optional MCP exposure for two narrow, governed workflow tools."""

from __future__ import annotations

import uuid

from mcp.server.fastmcp import FastMCP

from .models import ActorContext, DataClass, WorkRequest
from .service import EnterpriseFabric


mcp = FastMCP("enterprise-agentic-integration-fabric")
fabric = EnterpriseFabric()


@mcp.tool()
def triage_integration_incident(intent: str, tenant_id: str = "tenant-a") -> dict:
    """Run read-only synthetic integration triage with evidence and audit controls."""
    actor = ActorContext(
        tenant_id=tenant_id,
        subject="mcp-demo-operator",
        scopes=("payments:read", "integration:read"),
        clearance=DataClass.CONFIDENTIAL,
    )
    request = WorkRequest(
        request_id=f"mcp-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        intent=intent,
        idempotency_key=f"mcp-{uuid.uuid4().hex}",
        metadata={"initiated_by": actor.subject},
    )
    return fabric.orchestrator.start(request, actor).to_dict()


@mcp.tool()
def get_workflow_status(workflow_id: str) -> dict:
    """Read a previously created synthetic workflow without executing new actions."""
    state = fabric.journal.load(workflow_id)
    return state.to_dict() if state else {"error": "not_found"}


if __name__ == "__main__":
    mcp.run()
