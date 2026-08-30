# Architecture decisions

## Objective

Demonstrate a credible control plane for agent-assisted enterprise integration. The system must
remain explainable and testable when the model is unavailable, produce evidence for every completed
workflow, and prevent a model from becoming an authorization or execution boundary.

## Trust boundaries

1. **Client boundary** — identity, tenant and scope claims enter through headers in the demo. A real
   deployment would validate signed OIDC tokens at the gateway and again at sensitive services.
2. **Reasoning boundary** — retrieved context and operator intent can be sent to a configured model.
   Raw prompt and result contents are excluded from telemetry by default.
3. **Tool boundary** — only code-registered operations are callable. Each invocation is reauthorized
   immediately before execution.
4. **Enterprise-system boundary** — adapters represent existing APIs, integration runtimes and
   event platforms. Included handlers never call a real system.
5. **Audit boundary** — the journal records decisions and outcomes; telemetry records operational
   spans. Both receive redacted content.

## Key decisions

### Deterministic shell around probabilistic reasoning

The model can suggest registered tool names in structured JSON. It cannot set policy, invent a
runtime tool, approve an action or execute it. This keeps business invariants in testable code.

### Retrieval before planning

The knowledge agent applies tenant and classification filters before scoring. Lexical matching and a
deterministic hashed dense representation are combined so the repository runs without an embedding
service. Production implementations can replace this adapter with a governed vector store while
retaining the same access checks and citation contract.

### Durable approval checkpoints

Workflow state and events are committed to SQLite before the API returns `waiting_approval`.
The workflow can be recovered through a new journal connection. Production would use a replicated
database or durable execution platform, but the state-machine semantics remain the same.

### Idempotency and compensation

The request idempotency key identifies the workflow, and a derived execution key identifies each
tool step. Mutation adapters return a compensation token. On partial failure, compensations are
recorded in reverse execution order.

### Evidence-aware verification

A workflow cannot complete without tool results, policy-visible evidence and machine-checkable
citations. High-risk plans cannot complete without approval evidence.

## Integration mapping

| Project boundary | Common enterprise equivalent |
|---|---|
| `ToolRegistry` | API catalog, MCP registry, Anypoint Exchange or internal developer portal |
| `PolicyEngine` | API gateway, agent gateway, OPA-style policy service or IAM authorization |
| `HybridRetriever` | Governed vector/keyword knowledge layer with document ACLs |
| `WorkflowJournal` | Durable workflow engine, event store and audit trail |
| `OpenAICompatibleGateway` | Approved model gateway or private inference endpoint |
| Synthetic adapters | Mule application, IBM ACE flow, DataPower API, Kafka producer or core API |
| OTel sidecar | Central telemetry collector with content redaction and export controls |

## Scaling path

- Replace process-local tool idempotency with a transactional database constraint.
- Replace SQLite with PostgreSQL plus an outbox or a durable workflow service.
- Store knowledge in a tenant-filtered vector database with document-version citations.
- Use an event broker for long-running work and propagate trace context through messages.
- Split planner, retrieval, verifier and connectors into separately deployable services only when
  independent scaling or ownership justifies the operational cost.
- Add evaluation gates for retrieval recall, groundedness, policy compliance, task completion,
  latency and cost before promoting prompt or model changes.
