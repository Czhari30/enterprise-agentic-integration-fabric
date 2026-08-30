# Threat model

## Protected assets

- Tenant data and retrieved documents
- Tool credentials and approval authority
- Workflow integrity and idempotency records
- Model prompts, outputs and cost budgets
- Audit evidence and telemetry
- Existing APIs, integration runtimes and event streams

## Primary abuse cases

| Threat | Example | Implemented mitigation | Production extension |
|---|---|---|---|
| Prompt injection | A request asks the agent to bypass controls | Intake detector; model is not an execution boundary | Classifier ensemble, content provenance and red-team corpus |
| Cross-tenant retrieval | Tenant A retrieves Tenant B runbooks | Mandatory tenant filter before scoring | Database row-level security and per-tenant encryption |
| Excessive agency | Model selects a destructive operation | Registered tool allow-list and per-call authorization | Fine-grained policy service and just-in-time credentials |
| Hallucinated tool | Model invents an API name | Structured output validator rejects unknown tools | Signed catalog versions and schema-bound generation |
| Unauthorized mutation | Read-only operator requests replay | Scope check and approval gate | OIDC claims, workload identity and transaction signing |
| Approval fraud | Initiator approves their own request | Maker-checker subject separation | Enterprise approval service and phishing-resistant MFA |
| Replay attack | Request is submitted repeatedly | Workflow and step idempotency keys | Expiring nonces and transactional idempotency table |
| Sensitive telemetry | Prompt or tool payload leaks into traces | Redaction plus collector deletion rules | DLP scanning and separate restricted telemetry tier |
| Supply-chain compromise | Container dependency is replaced | Version bounds, CI and non-root image | Signed SBOM, provenance, admission policy and private registry |
| Container escape | Workload gains host capabilities | Restricted security context and dropped capabilities | Sandboxed runtime, seccomp profile tuning and runtime detection |

## Residual risks

- Regex-based injection and PII detection is deliberately limited.
- Header identity in the demo is not authentication.
- SQLite is not a highly available or multi-writer workflow store.
- The optional model gateway sends the selected evidence to a configured endpoint; governance of that
  endpoint is the deployer's responsibility.
- Kubernetes egress allows TCP 443 in the sample. Production should allow explicit destination CIDRs
  or use an egress gateway with application-layer policy.
- The sample compensation records intent; real adapters must implement and test actual compensations.
