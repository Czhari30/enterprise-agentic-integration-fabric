from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from .models import (
    DataClass,
    Evidence,
    PlannedStep,
    PolicyDecision,
    ToolResult,
    WorkflowState,
    WorkflowStatus,
    WorkRequest,
)
from .security import redact


class WorkflowJournal:
    """SQLite event journal and state snapshot store for restart-safe workflows."""

    def __init__(self, path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workflow_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    def save(self, state: WorkflowState) -> None:
        now = datetime.now(UTC).isoformat()
        self.connection.execute(
            """
            INSERT INTO workflows(workflow_id, idempotency_key, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
              state_json = excluded.state_json,
              updated_at = excluded.updated_at
            """,
            (
                state.workflow_id,
                state.request.idempotency_key,
                json.dumps(state.to_dict(), sort_keys=True),
                now,
            ),
        )
        self.connection.commit()

    def append(self, workflow_id: str, event_type: str, payload: dict[str, Any]) -> None:
        safe_payload = json.loads(redact(json.dumps(payload, sort_keys=True)))
        self.connection.execute(
            """
            INSERT INTO workflow_events(workflow_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (workflow_id, event_type, json.dumps(safe_payload), datetime.now(UTC).isoformat()),
        )
        self.connection.commit()

    def load(self, workflow_id: str) -> WorkflowState | None:
        row = self.connection.execute(
            "SELECT state_json FROM workflows WHERE workflow_id = ?", (workflow_id,)
        ).fetchone()
        return self._decode(row["state_json"]) if row else None

    def find_by_idempotency(self, idempotency_key: str) -> WorkflowState | None:
        row = self.connection.execute(
            "SELECT state_json FROM workflows WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return self._decode(row["state_json"]) if row else None

    def events(self, workflow_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT sequence, event_type, payload_json, created_at
            FROM workflow_events WHERE workflow_id = ? ORDER BY sequence
            """,
            (workflow_id,),
        ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _decode(value: str) -> WorkflowState:
        raw = json.loads(value)
        request = WorkRequest(**raw["request"])
        return WorkflowState(
            workflow_id=raw["workflow_id"],
            request=request,
            status=WorkflowStatus(raw["status"]),
            evidence=[
                Evidence(
                    **{key: item[key] for key in ("document_id", "title", "excerpt", "score", "citation")},
                    classification=DataClass(item["classification"]),
                )
                for item in raw["evidence"]
            ],
            plan=[PlannedStep(**item) for item in raw["plan"]],
            policy_decisions=[PolicyDecision(**item) for item in raw["policy_decisions"]],
            results=[ToolResult(**item) for item in raw["results"]],
            approvals=list(raw["approvals"]),
            error=raw["error"],
        )
