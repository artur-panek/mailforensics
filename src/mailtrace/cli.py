from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .html import render_html
from .journal import JournalError, read_journal
from .parsers import ParserError, builtin_adapters, discover_adapters, parse_log_lines
from .queue import QueueError, parse_postqueue_json, read_postqueue
from .render import render_explain, render_json, render_text
from .structured import parse_structured_events
from .trace import find_trace

DEFAULT_LOGS = (Path("/var/log/mail.log"), Path("/var/log/maillog"))


def _build_parser(*, prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Correlate an outbound email across application, Postfix, filters, queues, and relays.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
        help="Read mail logs from journald.",
    )
    parser.add_argument(
        "--unit",
        action="append",
        help="systemd unit for --journal. Repeat as needed. Defaults to postfix and rspamd.",
    )
    parser.add_argument("--since", help="journalctl --since value, for example '10 minutes ago'.")
    parser.add_argument("--until", help="journalctl --until value.")
    parser.add_argument(
        "--live-queue",
        action="store_true",
        help="Add a live Postfix queue snapshot using postqueue -j.",
    )
    parser.add_argument(
        "--queue-file",
        action="append",
        type=Path,
        help="Read saved postqueue -j JSONL instead of or in addition to --live-queue.",
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="Disable parser plugins registered under the mailtrace.parsers entry-point group.",
    )
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--message-id", help="Trace by RFC Message-ID, with or without angle brackets.")
    query.add_argument("--queue", help="Trace by Postfix queue ID.")
    query.add_argument(
        "--to",
        dest="recipient",
        help="Trace the latest matching message for an exact recipient address.",
    )
    query.add_argument("--correlation-id", help="Trace by application/gateway correlation ID.")
    parser.add_argument("--year", type=int, help="Year for classic syslog timestamps without a year.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--html",
        type=Path,
        help="Also write a self-contained HTML report to this path.",
    )
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
        "no mail log found; pass --file, --journal, --live-queue, or pipe logs on stdin"
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


def _list_parsers() -> int:
    try:
        adapters = [*builtin_adapters(), *discover_adapters()]
    except ParserError as exc:
        print(f"mailtrace: {exc}", file=sys.stderr)
        return 2

    print("mailtrace parsers")
    for adapter in adapters:
        origin = "plugin" if adapter.external else "builtin"
        print(f"  {adapter.name:<20} {origin}")
    return 0


def _split_mode(argv: list[str]) -> tuple[str, list[str]]:
    if argv and argv[0] in {"trace", "explain", "parsers"}:
        return argv[0], argv[1:]
    return "trace", argv


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    mode, command_argv = _split_mode(raw_argv)

    if mode == "parsers":
        if command_argv:
            print("mailtrace: parsers takes no arguments", file=sys.stderr)
            return 2
        return _list_parsers()

    args = _build_parser(prog=f"mailtrace {mode}" if mode != "trace" else "mailtrace").parse_args(
        command_argv
    )

    if (args.since or args.until or args.unit) and not args.journal:
        print("mailtrace: --since/--until/--unit require --journal", file=sys.stderr)
        return 2

    try:
        events = []
        explicit_source = bool(
            args.file
            or args.events
            or args.journal
            or args.live_queue
            or args.queue_file
        )

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
            events.extend(
                parse_log_lines(
                    lines,
                    year=args.year,
                    include_plugins=not args.no_plugins,
                )
            )

        for path in args.events or []:
            events.extend(parse_structured_events(_read_path(path)))

        for path in args.queue_file or []:
            events.extend(parse_postqueue_json(_read_path(path)))

        if args.live_queue:
            events.extend(read_postqueue())

        trace = find_trace(
            _dedupe(events),
            message_id=args.message_id,
            queue_id=args.queue,
            recipient=args.recipient,
            correlation_id=args.correlation_id,
        )
    except (JournalError, OSError, ParserError, QueueError, ValueError) as exc:
        print(f"mailtrace: {exc}", file=sys.stderr)
        return 2

    if args.html:
        args.html.write_text(render_html(trace), encoding="utf-8")

    if args.json:
        print(render_json(trace))
    elif mode == "explain":
        print(render_explain(trace))
    else:
        print(render_text(trace))

    return 0 if trace.events else 1
