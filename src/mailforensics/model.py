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


def event_recipients(event: Event) -> list[str]:
    addresses = []
    if recipient := event.details.get("recipient"):
        addresses.append(str(recipient))
    recipients = event.details.get("recipients")
    if isinstance(recipients, list):
        addresses.extend(str(value) for value in recipients if value)
    return list(dict.fromkeys(addresses))


@dataclass(slots=True)
class RecipientResult:
    recipient: str | None
    delivery: Event | None = None
    live_queue: Event | None = None

    @property
    def queued(self) -> bool:
        return self.live_queue is not None and (
            self.delivery is None or self.live_queue.timestamp >= self.delivery.timestamp
        )

    @property
    def status(self) -> str:
        status = str(self.delivery.details["status"]).casefold() if self.delivery else "unknown"
        if self.queued and status != "deferred":
            return "queued"
        return status


@dataclass(frozen=True, slots=True)
class Assessment:
    outcome: str
    last_confirmed_stage: str
    confidence: str
    summary: str
    caveat: str | None = None


@dataclass(frozen=True, slots=True)
class LatencySpan:
    from_stage: str
    to_stage: str
    duration_ms: int
    from_timestamp: datetime
    to_timestamp: datetime


@dataclass(frozen=True, slots=True)
class PipelineStage:
    key: str
    label: str
    state: str
    detail: str
    timestamp: datetime | None = None


@dataclass(slots=True)
class Trace:
    events: list[Event]
    queue_ids: set[str]
    message_ids: set[str]
    correlation_ids: set[str]
    query: str
    recipient: str | None = None

    @property
    def scoped_events(self) -> list[Event]:
        if self.recipient is None:
            return self.events
        recipient = self.recipient.casefold()
        return [
            event for event in self.events
            if not event_recipients(event)
            or recipient in {address.casefold() for address in event_recipients(event)}
        ]

    @property
    def recipient_results(self) -> list[RecipientResult]:
        results: dict[str | None, RecipientResult] = {}
        for event in sorted(self.events, key=lambda item: item.timestamp):
            delivery = (
                event.source == "postfix" and event.kind == "delivery"
                and event.details.get("status")
            )
            addresses: list[str | None] = list(event_recipients(event))
            if not addresses and (delivery or event.kind == "live-queue"):
                addresses = [None]
            for address in addresses:
                key = address.casefold() if address is not None else None
                if self.recipient is not None and key != self.recipient.casefold():
                    continue
                result = results.setdefault(key, RecipientResult(address))
                if delivery:
                    result.delivery = event
                elif event.kind == "live-queue":
                    result.live_queue = event
        return [results[key] for key in sorted(results, key=lambda value: value or "")]

    @property
    def status(self) -> str:
        results = self.recipient_results
        if any(result.delivery or result.live_queue for result in results):
            statuses = {result.status for result in results}
            return next(iter(statuses)) if len(statuses) == 1 else "mixed"
        events = self.scoped_events
        if any(event.kind in {"milter-reject", "filter-reject"} for event in events):
            return "rejected"
        if any(event.kind == "queued" for event in events):
            return "queued"
        if any(event.kind == "submitted" for event in events):
            return "submitted"
        return "unknown"
