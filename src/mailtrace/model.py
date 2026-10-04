from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    host: str
    component: str
    queue_id: str
    kind: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass(slots=True)
class Trace:
    events: list[Event]
    queue_ids: set[str]
    query: str

    @property
    def status(self) -> str:
        statuses = [event.details.get("status") for event in self.events]
        if "bounced" in statuses:
            return "bounced"
        if "deferred" in statuses:
            return "deferred"
        if "sent" in statuses:
            return "sent"
        if any(event.kind == "queued" for event in self.events):
            return "queued"
        return "unknown"
