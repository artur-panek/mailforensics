from __future__ import annotations

import json
from typing import Any

from .model import Event, Trace


def _event_summary(event: Event) -> str:
    bits: list[str] = []
    if message_id := event.details.get("message_id"):
        bits.append(f"message-id=<{message_id}>")
    if sender := event.details.get("sender"):
        bits.append(f"from=<{sender}>")
    if recipient := event.details.get("recipient"):
        bits.append(f"to=<{recipient}>")
    if relay := event.details.get("relay"):
        bits.append(f"relay={relay}")
    if status := event.details.get("status"):
        bits.append(f"status={status}")
    if dsn := event.details.get("dsn"):
        bits.append(f"dsn={dsn}")
    if delay := event.details.get("delay"):
        bits.append(f"delay={delay}s")
    if linked := event.details.get("linked_queue_id"):
        bits.append(f"queued-as={linked}")
    return "  ".join(bits) if bits else event.message


def render_text(trace: Trace) -> str:
    lines = [
        "MAILTRACE",
        f"query:    {trace.query}",
        f"status:   {trace.status}",
        f"queues:   {', '.join(sorted(trace.queue_ids)) or '-'}",
        "",
    ]

    if not trace.events:
        lines.append("No matching Postfix events found.")
        return "\n".join(lines)

    base = trace.events[0].timestamp
    for event in trace.events:
        delta_ms = int((event.timestamp - base).total_seconds() * 1000)
        stamp = event.timestamp.isoformat(timespec="milliseconds")
        lines.append(
            f"{stamp}  +{delta_ms:>6}ms  {event.queue_id:<14} "
            f"{event.component:<8} {_event_summary(event)}"
        )

    return "\n".join(lines)


def _event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "timestamp": event.timestamp.isoformat(),
        "host": event.host,
        "component": event.component,
        "queue_id": event.queue_id,
        "kind": event.kind,
        "message": event.message,
        "details": event.details,
    }


def render_json(trace: Trace) -> str:
    payload = {
        "query": trace.query,
        "status": trace.status,
        "queue_ids": sorted(trace.queue_ids),
        "events": [_event_to_dict(event) for event in trace.events],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
