from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from email.utils import parsedate_to_datetime

from .model import Event, Trace

CLASSIC_SYSLOG_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+"
    r"(?P<process>postfix/[A-Za-z0-9_-]+)\[(?P<pid>\d+)\]:\s+(?P<body>.*)$"
)
ISO_SYSLOG_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?P<host>\S+)\s+(?P<process>postfix/[A-Za-z0-9_-]+)\[(?P<pid>\d+)\]:\s+(?P<body>.*)$"
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
        raw = iso_match.group("timestamp").replace("Z", "+00:00")
        return datetime.fromisoformat(raw), iso_match.groupdict()

    classic_match = CLASSIC_SYSLOG_RE.match(line)
    if not classic_match:
        return None
    data = classic_match.groupdict()
    stamp = parsedate_to_datetime(
        f"{data['month']} {data['day']} {data['time']} {year}"
    ).replace(tzinfo=None)
    return stamp, data


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

        queue_id = queue_match.group("queue")
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
                details[key] = match.group("value")

        events.append(
            Event(
                timestamp=timestamp,
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


def _expand_linked_queue_ids(events: list[Event], queue_ids: set[str]) -> set[str]:
    expanded = set(queue_ids)
    changed = True
    while changed:
        changed = False
        for event in events:
            linked = event.details.get("linked_queue_id")
            if event.queue_id in expanded and linked and linked not in expanded:
                expanded.add(linked)
                changed = True
            if linked in expanded and event.queue_id not in expanded:
                expanded.add(event.queue_id)
                changed = True
    return expanded


def find_trace(
    events: list[Event],
    *,
    message_id: str | None = None,
    queue_id: str | None = None,
    recipient: str | None = None,
) -> Trace:
    selectors = [value is not None for value in (message_id, queue_id, recipient)]
    if sum(selectors) != 1:
        raise ValueError("exactly one of message_id, queue_id, or recipient must be provided")

    selected: set[str] = set()
    query: str

    if message_id is not None:
        normalized = message_id.strip("<>")
        query = f"message-id=<{normalized}>"
        selected = {
            event.queue_id
            for event in events
            if event.details.get("message_id", "").strip("<>") == normalized
        }
    elif queue_id is not None:
        query = f"queue={queue_id}"
        selected = {queue_id}
    else:
        assert recipient is not None
        query = f"to=<{recipient}>"
        selected = {
            event.queue_id
            for event in events
            if event.details.get("recipient", "").casefold() == recipient.casefold()
        }

    selected = _expand_linked_queue_ids(events, selected)
    trace_events = [event for event in events if event.queue_id in selected]
    return Trace(events=trace_events, queue_ids=selected, query=query)
