from __future__ import annotations

import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from .security import redact


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    span_id: str
    name: str
    duration_ms: float
    status: str
    attributes: dict[str, Any]


class Telemetry:
    """In-process audit telemetry using OpenTelemetry-compatible GenAI names."""

    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []
        self.metrics: Counter[str] = Counter()

    @contextmanager
    def span(
        self,
        name: str,
        *,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[None]:
        started = time.perf_counter()
        status = "ok"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            safe_attributes = {
                key: redact(str(value)) if isinstance(value, str) else value
                for key, value in (attributes or {}).items()
            }
            self.spans.append(
                SpanRecord(
                    trace_id=trace_id,
                    span_id=uuid.uuid4().hex[:16],
                    name=name,
                    duration_ms=round((time.perf_counter() - started) * 1000, 3),
                    status=status,
                    attributes=safe_attributes,
                )
            )
            self.metrics[f"span_{status}_total"] += 1

    def prometheus(self) -> str:
        lines = ["# TYPE enterprise_fabric_events_total counter"]
        for name, value in sorted(self.metrics.items()):
            lines.append(f'enterprise_fabric_events_total{{event="{name}"}} {value}')
        return "\n".join(lines) + "\n"
