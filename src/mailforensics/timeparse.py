from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def normalize_timestamp(value: datetime) -> datetime:
    # Naive log timestamps are local wall time. astimezone resolves the local
    # UTC offset for that date, including DST, rather than using today's offset.
    return value.astimezone(UTC)


def parse_iso_timestamp(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    return normalize_timestamp(datetime.fromisoformat(normalized))


def parse_classic_syslog(month: str, day: str, clock: str, year: int) -> datetime:
    parsed = parsedate_to_datetime(f"{month} {day} {clock} {year}")
    return normalize_timestamp(parsed)
