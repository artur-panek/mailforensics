from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

from .model import Event
from .syslog import parse_rfc5424
from .timeparse import parse_classic_syslog, parse_iso_timestamp

RSPAMD_APP_RE = re.compile(r"^rspamd(?:[_-][A-Za-z0-9_-]+)?$", re.IGNORECASE)
CLASSIC_SYSLOG_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+"
    r"(?P<process>rspamd(?:[_-][A-Za-z0-9_-]+)?(?:\[[0-9]+\])?):\s+(?P<body>.*)$",
    re.IGNORECASE,
)
ISO_SYSLOG_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<host>\S+)\s+"
    r"(?P<process>rspamd(?:[_-][A-Za-z0-9_-]+)?(?:\[[0-9]+\])?):\s+(?P<body>.*)$",
    re.IGNORECASE,
)
MESSAGE_ID_RE = re.compile(r"\b(?:id|message-id):\s*<(?P<value>[^>]+)>", re.IGNORECASE)
QID_RE = re.compile(r"\bqid:\s*<?(?P<value>[A-Za-z0-9_-]+)>?", re.IGNORECASE)
FROM_RE = re.compile(r"\bfrom:\s*<(?P<value>[^>]*)>", re.IGNORECASE)
TO_RE = re.compile(r"\b(?:rcpt|to):\s*<(?P<value>[^>]*)>", re.IGNORECASE)
ACTION_RE = re.compile(
    r"\b[A-Z]\s+\((?P<value>"
    r"reject|soft reject|add header|rewrite subject|greylist|quarantine|discard|accept|no action"
    r")\)",
    re.IGNORECASE,
)
SCORE_RE = re.compile(r"\[(?P<score>-?\d+(?:\.\d+)?)/(?P<required>-?\d+(?:\.\d+)?)\]")


def _parse_timestamp(line: str, year: int) -> tuple[datetime, dict[str, str]] | None:
    rfc5424 = parse_rfc5424(line)
    if rfc5424 and RSPAMD_APP_RE.match(rfc5424.app):
        return rfc5424.timestamp, {
            "host": rfc5424.host,
            "process": rfc5424.app,
            "pid": rfc5424.procid,
            "body": rfc5424.body,
        }

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


def parse_rspamd(lines: Iterable[str], *, year: int | None = None) -> list[Event]:
    inferred_year = year or datetime.now().year
    events: list[Event] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        parsed = _parse_timestamp(line, inferred_year)
        if not parsed:
            continue
        timestamp, data = parsed
        body = data["body"]

        message_match = MESSAGE_ID_RE.search(body)
        queue_match = QID_RE.search(body)
        sender_match = FROM_RE.search(body)
        recipient_match = TO_RE.search(body)
        action_match = ACTION_RE.search(body)
        score_match = SCORE_RE.search(body)

        details: dict[str, str] = {}
        if message_match:
            details["message_id"] = message_match.group("value")
        if sender_match:
            details["sender"] = sender_match.group("value")
        if recipient_match:
            details["recipient"] = recipient_match.group("value")
        if action_match:
            details["action"] = action_match.group("value").casefold()
        if score_match:
            details["score"] = score_match.group("score")
            details["required_score"] = score_match.group("required")

        queue_id = queue_match.group("value").upper() if queue_match else None
        if queue_id in {"UNDEF", "UNKNOWN", "NONE", "-"}:
            queue_id = None

        if not queue_id and "message_id" not in details:
            continue

        action = details.get("action", "")
        kind = "filter"
        if action in {"reject", "soft reject", "discard"}:
            kind = "filter-reject"

        events.append(
            Event(
                timestamp=timestamp,
                source="rspamd",
                host=data["host"],
                component="filter",
                queue_id=queue_id,
                kind=kind,
                message=body,
                details=details,
                raw=line,
            )
        )

    return sorted(events, key=lambda event: event.timestamp)
