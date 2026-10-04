from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import metadata

from .model import Event
from .postfix import parse_postfix
from .rspamd import parse_rspamd

ParserFn = Callable[..., Iterable[Event]]
ENTRY_POINT_GROUP = "mailforensics.parsers"


class ParserError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ParserAdapter:
    name: str
    parse: ParserFn
    external: bool = False


def builtin_adapters() -> list[ParserAdapter]:
    return [
        ParserAdapter(name="postfix", parse=parse_postfix),
        ParserAdapter(name="rspamd", parse=parse_rspamd),
    ]


def discover_adapters() -> list[ParserAdapter]:
    try:
        entries = metadata.entry_points()
        selected = entries.select(group=ENTRY_POINT_GROUP)
    except AttributeError:
        selected = metadata.entry_points().get(ENTRY_POINT_GROUP, [])

    adapters: list[ParserAdapter] = []
    for entry in selected:
        try:
            parser = entry.load()
        except Exception as exc:
            raise ParserError(f"failed to load parser plugin {entry.name}: {exc}") from exc
        if not callable(parser):
            raise ParserError(f"parser plugin {entry.name} did not resolve to a callable")
        adapters.append(ParserAdapter(name=entry.name, parse=parser, external=True))
    return adapters


def parse_log_lines(
    lines: Iterable[str],
    *,
    year: int | None = None,
    include_plugins: bool = True,
) -> list[Event]:
    materialized = list(lines)
    adapters = builtin_adapters()
    if include_plugins:
        adapters.extend(discover_adapters())

    events: list[Event] = []
    for adapter in adapters:
        try:
            parsed = list(adapter.parse(materialized, year=year))
        except Exception as exc:
            if adapter.external:
                raise ParserError(f"parser plugin {adapter.name} failed: {exc}") from exc
            raise
        if not all(isinstance(event, Event) for event in parsed):
            raise ParserError(f"parser {adapter.name} returned a non-Event value")
        events.extend(parsed)

    return sorted(events, key=lambda event: event.timestamp)
