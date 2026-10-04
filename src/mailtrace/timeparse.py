from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

LOCAL_TZ = datetime.now().astimezone().tzinfo or UTC


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return value.astimezone(UTC)


def parse_iso_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    return normalize_timestamp(datetime.fromisoformat(normalized))


def parse_classic_syslog(month: str, day: str, clock: str, year: int) -> datetime:
    parsed = parsedate_to_datetime(f"{month} {day} {clock} {year}")
    return normalize_timestamp(parsed)
