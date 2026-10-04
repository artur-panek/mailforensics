from __future__ import annotations

import json
import shutil
import socket
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from .model import Event


class QueueError(RuntimeError):
    pass


def _recipient_addresses(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    addresses: list[str] = []
    for item in value:
        if isinstance(item, dict) and item.get("address") is not None:
            addresses.append(str(item["address"]))
        elif isinstance(item, str):
            addresses.append(item)
    return addresses


def parse_postqueue_json(
    lines: Iterable[str],
    *,
    host: str | None = None,
    captured_at: datetime | None = None,
) -> list[Event]:
    observed = captured_at or datetime.now(UTC)
    hostname = host or socket.gethostname()
    events: list[Event] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QueueError(f"postqueue JSON line {line_number} is invalid") from exc
        if not isinstance(payload, dict):
            raise QueueError(f"postqueue JSON line {line_number} is not an object")

        queue_id = payload.get("queue_id")
        if not queue_id:
            raise QueueError(f"postqueue JSON line {line_number} has no queue_id")

        arrival = payload.get("arrival_time")
        try:
            arrival_timestamp = (
                datetime.fromtimestamp(float(arrival), UTC)
                if arrival is not None
                else observed
            )
        except (TypeError, ValueError, OSError):
            arrival_timestamp = observed

        recipients = _recipient_addresses(payload.get("recipients"))
        details: dict[str, Any] = {
            "queue_name": str(payload.get("queue_name", "unknown")),
            "captured_at": observed.isoformat(),
            "recipients": recipients,
        }
        if sender := payload.get("sender"):
            details["sender"] = str(sender)
        if payload.get("message_size") is not None:
            details["message_size"] = payload["message_size"]
        if recipients:
            details["recipient"] = recipients[0]

        delay_reasons = [
            str(item["delay_reason"])
            for item in payload.get("recipients", [])
            if isinstance(item, dict) and item.get("delay_reason")
        ]
        if delay_reasons:
            details["delay_reasons"] = delay_reasons

        events.append(
            Event(
                timestamp=observed,
                source="postfix-queue",
                host=hostname,
                component=details["queue_name"],
                queue_id=str(queue_id).upper(),
                kind="live-queue",
                message=(
                    f"queue entry present; arrived {arrival_timestamp.isoformat()}"
                ),
                details=details,
                raw=line,
            )
        )

    return sorted(events, key=lambda event: event.timestamp)


def read_postqueue() -> list[Event]:
    if shutil.which("postqueue") is None:
        raise QueueError("postqueue not found; install Postfix or omit --live-queue")

    proc = subprocess.run(
        ["postqueue", "-j"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        raise QueueError(f"postqueue -j failed: {detail}")

    return parse_postqueue_json(proc.stdout.splitlines())
