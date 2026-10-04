from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    source: str
    host: str
    component: str
    kind: str
    message: str
    queue_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass(frozen=True, slots=True)
class Assessment:
    outcome: str
    last_confirmed_stage: str
    confidence: str
    summary: str
    caveat: str | None = None


@dataclass(slots=True)
class Trace:
    events: list[Event]
    queue_ids: set[str]
    message_ids: set[str]
    correlation_ids: set[str]
    query: str

    @property
    def status(self) -> str:
        statuses = [
            str(event.details.get("status", "")).casefold()
            for event in self.events
            if event.source == "postfix" and event.kind == "delivery"
        ]
        if "bounced" in statuses:
            return "bounced"
        if "deferred" in statuses:
            return "deferred"
        if "sent" in statuses:
            return "sent"
        if any(event.kind == "queued" for event in self.events):
            return "queued"
        if any(event.kind == "submitted" for event in self.events):
            return "submitted"
        return "unknown"
