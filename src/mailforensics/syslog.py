from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .timeparse import parse_iso_timestamp

RFC5424_HEADER_RE = re.compile(
    r"^<\d{1,3}>(?P<version>\d+)\s+"
    r"(?P<timestamp>\S+)\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<app>\S+)\s+"
    r"(?P<procid>\S+)\s+"
    r"(?P<msgid>\S+)\s+"
    r"(?P<rest>.*)$"
)


@dataclass(frozen=True, slots=True)
class SyslogRecord:
    timestamp: datetime
    host: str
    app: str
    procid: str
    body: str


def _consume_structured_data(rest: str) -> str | None:
    if rest == "-":
        return ""
    if rest.startswith("- "):
        return rest[2:]
    if not rest.startswith("["):
        return None

    index = 0
    length = len(rest)
    while index < length and rest[index] == "[":
        index += 1
        escaped = False
        while index < length:
            char = rest[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "]":
                index += 1
                break
            index += 1
        else:
            return None

    return rest[index:].lstrip()


def parse_rfc5424(line: str) -> SyslogRecord | None:
    match = RFC5424_HEADER_RE.match(line)
    if not match:
        return None

    data = match.groupdict()
    if data["timestamp"] == "-":
        return None

    body = _consume_structured_data(data["rest"])
    if body is None:
        return None

    try:
        timestamp = parse_iso_timestamp(data["timestamp"])
    except ValueError:
        return None

    return SyslogRecord(
        timestamp=timestamp,
        host=data["host"],
        app=data["app"],
        procid=data["procid"],
        body=body,
    )
