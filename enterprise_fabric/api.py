from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import ActorContext, DataClass, WorkRequest
from .service import EnterpriseFabric


class WorkflowRequest(BaseModel):
    request_id: str = Field(min_length=3, max_length=80)
    intent: str = Field(min_length=8, max_length=2_000)
    idempotency_key: str = Field(min_length=6, max_length=120)
    amount: float | None = Field(default=None, ge=0)
    currency: str = Field(default="MYR", min_length=3, max_length=3)
    customer_ref: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    approval_reference: str = Field(min_length=4, max_length=120)


def actor_context(
    x_tenant_id: str = Header(default="tenant-a"),
    x_subject: str = Header(default="demo-maker"),
    x_roles: str = Header(default="operator"),
    x_scopes: str = Header(
        default=(
            "payments:read,integration:read,integration:write,payments:write,"
            "customers:restricted:read"
        )
    ),
    x_clearance: DataClass = Header(default=DataClass.RESTRICTED),
) -> ActorContext:
    return ActorContext(
        tenant_id=x_tenant_id,
        subject=x_subject,
        roles=tuple(item.strip() for item in x_roles.split(",") if item.strip()),
        scopes=tuple(item.strip() for item in x_scopes.split(",") if item.strip()),
        clearance=x_clearance,
    )


fabric = EnterpriseFabric(os.getenv("FABRIC_DB_PATH", ":memory:"))
app = FastAPI(
    title="Enterprise Agentic Integration Fabric",
    version="0.1.0",
    description=(
        "Governed agent workflows, tenant-aware hybrid RAG, approval gates and "
        "synthetic enterprise integration tools."
    ),
)


def workflow_view(workflow_id: str) -> dict[str, Any]:
    state = fabric.journal.load(workflow_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        **state.to_dict(),
        "events": fabric.journal.events(workflow_id),
        "trace_spans": [
            span.__dict__ for span in fabric.telemetry.spans if span.trace_id
        ][-25:],
    }


@app.get("/healthz", tags=["platform"])
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "synthetic-reference-platform"}


@app.get("/metrics", tags=["platform"], response_class=Response)
def metrics() -> Response:
    return Response(fabric.telemetry.prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/v1/catalog/tools", tags=["catalog"])
def tool_catalog() -> list[dict[str, Any]]:
    return [item.__dict__ for item in fabric.registry.catalog()]


@app.post("/v1/workflows", tags=["workflows"], status_code=202)
def start_workflow(
    body: WorkflowRequest,
    actor: ActorContext = Depends(actor_context),
) -> dict[str, Any]:
    metadata = {**body.metadata, "initiated_by": actor.subject}
    request = WorkRequest(
        request_id=body.request_id,
        tenant_id=actor.tenant_id,
        intent=body.intent,
        idempotency_key=body.idempotency_key,
        amount=body.amount,
        currency=body.currency.upper(),
        customer_ref=body.customer_ref,
        metadata=metadata,
    )
    state = fabric.orchestrator.start(request, actor)
    return workflow_view(state.workflow_id)


@app.get("/v1/workflows/{workflow_id}", tags=["workflows"])
def get_workflow(workflow_id: str) -> dict[str, Any]:
    return workflow_view(workflow_id)


@app.post("/v1/workflows/{workflow_id}/approve", tags=["workflows"])
def approve_workflow(
    workflow_id: str,
    body: ApprovalRequest,
    actor: ActorContext = Depends(actor_context),
) -> dict[str, Any]:
    try:
        state = fabric.orchestrator.approve(workflow_id, actor, body.approval_reference)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return workflow_view(state.workflow_id)


STATIC_DIR = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
