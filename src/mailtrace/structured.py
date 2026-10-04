from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from .model import Event
from .timeparse import parse_iso_timestamp


def _string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def parse_structured_events(lines: Iterable[str]) -> list[Event]:
    events: list[Event] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"structured event line {line_number}: invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"structured event line {line_number}: expected a JSON object")

        timestamp_value = payload.get("timestamp")
        if not timestamp_value:
            raise ValueError(f"structured event line {line_number}: missing timestamp")

        source = _string(payload.get("source")) or "application"
        component = _string(payload.get("component") or payload.get("stage")) or source
        message = _string(payload.get("message")) or component
        queue_id = _string(payload.get("queue_id"))
        if queue_id:
            queue_id = queue_id.upper()

        details: dict[str, Any] = {}
        supplied_details = payload.get("details")
        if supplied_details is not None:
            if not isinstance(supplied_details, dict):
                raise ValueError(
                    f"structured event line {line_number}: details must be a JSON object"
                )
            details.update(supplied_details)

        aliases = {
            "message_id": payload.get("message_id"),
            "recipient": payload.get("recipient", payload.get("to")),
            "sender": payload.get("sender", payload.get("from")),
            "status": payload.get("status"),
            "correlation_id": payload.get("correlation_id"),
            "linked_queue_id": payload.get("linked_queue_id"),
            "relay": payload.get("relay"),
        }
        for key, value in aliases.items():
            if value is not None:
                details[key] = str(value)

        if "message_id" in details:
            details["message_id"] = str(details["message_id"]).strip("<>")
        if "linked_queue_id" in details:
            details["linked_queue_id"] = str(details["linked_queue_id"]).upper()

        kind = _string(payload.get("kind"))
        if not kind:
            status = str(details.get("status", "")).casefold()
            kind = "submitted" if status in {"accepted", "submitted", "queued"} else "activity"

        events.append(
            Event(
                timestamp=parse_iso_timestamp(str(timestamp_value)),
                source=source,
                host=_string(payload.get("host")) or "-",
                component=component,
                queue_id=queue_id,
                kind=kind,
                message=message,
                details=details,
                raw=line,
            )
        )

    return sorted(events, key=lambda event: event.timestamp)
