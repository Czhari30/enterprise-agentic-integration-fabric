from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from enterprise_fabric.models import ActorContext, DataClass, WorkRequest  # noqa: E402
from enterprise_fabric.service import EnterpriseFabric  # noqa: E402


def main() -> int:
    path = Path(__file__).with_name("cases.jsonl")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows = []
    for index, case in enumerate(cases, start=1):
        fabric = EnterpriseFabric()
        actor = ActorContext(
            tenant_id="tenant-a",
            subject="evaluation-maker",
            scopes=tuple(case["scopes"]),
            clearance=DataClass.RESTRICTED,
        )
        request = WorkRequest(
            request_id=f"eval-{index}",
            tenant_id="tenant-a",
            intent=case["intent"],
            idempotency_key=f"eval-{index}",
            amount=case["amount"],
            metadata={"initiated_by": actor.subject},
        )
        state = fabric.orchestrator.start(request, actor)
        tools = [item.tool for item in state.plan]
        status_pass = state.status.value == case["expected_status"]
        tool_pass = tools == case["expected_tools"]
        citation_pass = state.status.value == "denied" or all(
            item.citation.startswith("knowledge://") for item in state.evidence
        )
        rows.append(
            {
                "case_id": case["case_id"],
                "status": state.status.value,
                "status_pass": status_pass,
                "tool_pass": tool_pass,
                "citation_pass": citation_pass,
            }
        )

    passed = sum(all(row[key] for key in ("status_pass", "tool_pass", "citation_pass")) for row in rows)
    report = {
        "cases": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 3),
        "results": rows,
    }
    print(json.dumps(report, indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
