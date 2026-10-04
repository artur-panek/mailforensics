from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from .model import Event
from .timeparse import parse_classic_syslog, parse_iso_timestamp
from .trace import find_trace as find_trace

__all__ = ["find_trace", "parse_postfix"]

CLASSIC_SYSLOG_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+"
    r"(?P<process>postfix/[A-Za-z0-9_-]+)\[(?P<pid>\d+)\]:\s+(?P<body>.*)$"
)
ISO_SYSLOG_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<host>\S+)\s+"
    r"(?P<process>postfix/[A-Za-z0-9_-]+)\[(?P<pid>\d+)\]:\s+(?P<body>.*)$"
)
QUEUE_RE = re.compile(r"^(?P<queue>[A-Za-z0-9]+|NOQUEUE):\s+(?P<detail>.*)$")
MESSAGE_ID_RE = re.compile(r"message-id=<(?P<value>[^>]+)>", re.IGNORECASE)
FROM_RE = re.compile(r"from=<(?P<value>[^>]*)>", re.IGNORECASE)
TO_RE = re.compile(r"to=<(?P<value>[^>]*)>", re.IGNORECASE)
RELAY_RE = re.compile(r"relay=(?P<value>[^,]+)", re.IGNORECASE)
STATUS_RE = re.compile(r"status=(?P<value>[A-Za-z]+)", re.IGNORECASE)
DSN_RE = re.compile(r"dsn=(?P<value>[0-9.]+)", re.IGNORECASE)
DELAY_RE = re.compile(r"delay=(?P<value>[0-9.]+)", re.IGNORECASE)
QUEUED_AS_RE = re.compile(r"queued as (?P<value>[A-Za-z0-9]+)", re.IGNORECASE)


def _parse_timestamp(line: str, year: int) -> tuple[datetime, dict[str, str]] | None:
    iso_match = ISO_SYSLOG_RE.match(line)
    if iso_match:
        return parse_iso_timestamp(iso_match.group("timestamp")), iso_match.groupdict()

    classic_match = CLASSIC_SYSLOG_RE.match(line)
    if not classic_match:
        return None
    data = classic_match.groupdict()
    return (
        parse_classic_syslog(data["month"], data["day"], data["time"], year),
        data,
    )


def _kind_for(component: str, detail: str, details: dict[str, str]) -> str:
    if component == "cleanup" and "message_id" in details:
        return "message-id"
    if component == "qmgr":
        return "queued"
    if component in {"smtp", "lmtp", "local", "pipe"} and "status" in details:
        return "delivery"
    if component == "pickup":
        return "pickup"
    if component == "smtpd":
        return "received"
    if component == "bounce":
        return "bounce"
    if "removed" in detail.lower():
        return "removed"
    return "activity"


def parse_postfix(lines: Iterable[str], *, year: int | None = None) -> list[Event]:
    inferred_year = year or datetime.now().year
    events: list[Event] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        parsed = _parse_timestamp(line, inferred_year)
        if not parsed:
            continue
        timestamp, data = parsed
        queue_match = QUEUE_RE.match(data["body"])
        if not queue_match:
            continue

        raw_queue_id = queue_match.group("queue")
        queue_id = None if raw_queue_id == "NOQUEUE" else raw_queue_id.upper()
        detail = queue_match.group("detail")
        component = data["process"].split("/", 1)[1]
        details: dict[str, str] = {}

        extractors = {
            "message_id": MESSAGE_ID_RE,
            "sender": FROM_RE,
            "recipient": TO_RE,
            "relay": RELAY_RE,
            "status": STATUS_RE,
            "dsn": DSN_RE,
            "delay": DELAY_RE,
            "linked_queue_id": QUEUED_AS_RE,
        }
        for key, pattern in extractors.items():
            match = pattern.search(detail)
            if match:
                value = match.group("value")
                if key == "linked_queue_id":
                    value = value.upper()
                details[key] = value

        events.append(
            Event(
                timestamp=timestamp,
                source="postfix",
                host=data["host"],
                component=component,
                queue_id=queue_id,
                kind=_kind_for(component, detail, details),
                message=detail,
                details=details,
                raw=line,
            )
        )

    return sorted(events, key=lambda event: event.timestamp)
