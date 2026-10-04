from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .journal import JournalError, read_journal
from .postfix import parse_postfix
from .render import render_json, render_text
from .rspamd import parse_rspamd
from .structured import parse_structured_events
from .trace import find_trace

DEFAULT_LOGS = (Path("/var/log/mail.log"), Path("/var/log/maillog"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mailtrace",
        description="Correlate an outbound email across application, Postfix, Rspamd, and relay evidence.",
    )
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        type=Path,
        help="Mail/syslog file. Repeat for multiple files. Use '-' for stdin.",
    )
    parser.add_argument(
        "--events",
        action="append",
        type=Path,
        help="Structured JSONL application/gateway events. Repeat for multiple files.",
    )
    parser.add_argument(
        "--journal",
        action="store_true",
        help="Read Postfix/Rspamd logs from journald.",
    )
    parser.add_argument(
        "--unit",
        action="append",
        help="systemd unit for --journal. Repeat as needed. Defaults to postfix and rspamd.",
    )
    parser.add_argument("--since", help="journalctl --since value, for example '10 minutes ago'.")
    parser.add_argument("--until", help="journalctl --until value.")
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--message-id", help="Trace by RFC Message-ID, with or without angle brackets.")
    query.add_argument("--queue", help="Trace by Postfix queue ID.")
    query.add_argument("--to", dest="recipient", help="Trace messages for an exact recipient address.")
    query.add_argument("--correlation-id", help="Trace by application/gateway correlation ID.")
    parser.add_argument("--year", type=int, help="Year for classic syslog timestamps without a year.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def _read_path(path: Path) -> list[str]:
    if str(path) == "-":
        return sys.stdin.read().splitlines()
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _default_log_lines() -> list[str]:
    for candidate in DEFAULT_LOGS:
        if candidate.exists():
            return _read_path(candidate)
    if not sys.stdin.isatty():
        return sys.stdin.read().splitlines()
    raise FileNotFoundError(
        "no mail log found; pass --file, --journal, or pipe logs on stdin"
    )


def _dedupe(events):
    seen = set()
    unique = []
    for event in sorted(events, key=lambda item: item.timestamp):
        key = (
            event.timestamp,
            event.source,
            event.host,
            event.component,
            event.queue_id,
            event.message,
        )
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return unique


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if (args.since or args.until or args.unit) and not args.journal:
        print("mailtrace: --since/--until/--unit require --journal", file=sys.stderr)
        return 2

    try:
        events = []
        explicit_source = bool(args.file or args.events or args.journal)

        log_batches: list[list[str]] = []
        for path in args.file or []:
            log_batches.append(_read_path(path))

        if args.journal:
            log_batches.append(
                read_journal(units=args.unit, since=args.since, until=args.until)
            )

        if not explicit_source:
            log_batches.append(_default_log_lines())

        for lines in log_batches:
            events.extend(parse_postfix(lines, year=args.year))
            events.extend(parse_rspamd(lines, year=args.year))

        for path in args.events or []:
            events.extend(parse_structured_events(_read_path(path)))

        trace = find_trace(
            _dedupe(events),
            message_id=args.message_id,
            queue_id=args.queue,
            recipient=args.recipient,
            correlation_id=args.correlation_id,
        )
    except (JournalError, OSError, ValueError) as exc:
        print(f"mailtrace: {exc}", file=sys.stderr)
        return 2

    print(render_json(trace) if args.json else render_text(trace))
    return 0 if trace.events else 1
