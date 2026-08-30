# MuleSoft and enterprise integration mapping

This repository is vendor-neutral code with MuleSoft-compatible boundaries. It is not exported
Anypoint metadata and does not require MuleSoft licensing.

| Agent Fabric capability | Reference implementation |
|---|---|
| Discover agents, APIs and MCP servers | `ToolRegistry` and the `/v1/catalog/tools` endpoint |
| Govern calls at runtime | `PolicyEngine`, scopes, approvals and audit events |
| Orchestrate multi-step processes | `AgenticOrchestrator` and its durable state machine |
| Observe agent and tool behavior | Workflow journal and OpenTelemetry-compatible spans |
| MCP Bridge existing APIs | Synthetic OpenAPI contract plus narrow MCP server |
| MCP Connector custom composition | Python adapters composing lookup, trace and replay steps |
| Agent network | Planner, knowledge, integration, operator and verifier roles |

## API-led connectivity

The synthetic payment contract can be treated as a system API. A real integration layer could
expose a process API that composes payment state, gateway telemetry and event delivery status. The
agent-facing operation should remain a narrow experience API or MCP tool—not direct access to the
underlying core systems.

## IBM integration touchpoints

The `integration.trace` adapter models correlation across an API gateway, an integration runtime and
an event stream. In an IBM estate, that boundary could be implemented through governed DataPower APIs,
ACE flows and platform telemetry. The repository intentionally includes no vendor configuration,
internal topology or proprietary flow logic.
