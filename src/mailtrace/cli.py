from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .branding import banner, compact_mark
from .completions import SHELLS, completion_script
from .console import CYAN, bold, paint, state, supports_color, supports_unicode
from .demo import SCENARIOS, demo_trace
from .doctor import collect_checks, has_failures
from .exitcodes import ERROR, NO_TRACE, OK
from .html import render_html
from .journal import JournalError, read_journal
from .parsers import ParserError, builtin_adapters, discover_adapters, parse_log_lines
from .queue import QueueError, parse_postqueue_json, read_postqueue
from .render import render_explain, render_json, render_text
from .structured import parse_structured_events
from .trace import find_trace

DEFAULT_LOGS = (Path("/var/log/mail.log"), Path("/var/log/maillog"))


def _root_help() -> str:
    ascii_only = not supports_unicode(stream=sys.stdout)
    logo = banner(ascii_only=ascii_only)
    return f"""{logo}

mailtrace {__version__} — strace for an email moving through your mail stack

Usage:
  mailtrace [trace] QUERY [SOURCES] [OPTIONS]
  mailtrace explain QUERY [SOURCES] [OPTIONS]
  mailtrace demo [deferred|delivered|rejected|gap]
  mailtrace doctor
  mailtrace parsers
  mailtrace completion [bash|zsh|fish]

Commands:
  trace       full normalized evidence timeline (default)
  explain     compact forensic pipeline + latency + assessment
  demo        zero-setup built-in scenarios
  doctor      inspect local mailtrace capabilities and permissions
  parsers     list built-in and external parser adapters
  completion  print a shell completion script

Quick start:
  mailtrace demo
  mailtrace explain --journal --since '20 minutes ago' --live-queue --message-id '<id@example.net>'

Output:
  color is auto-detected; NO_COLOR disables it
  --color auto|always|never overrides detection
  --ascii forces ASCII-only connectors and branding
"""


def _build_parser(*, prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Correlate outbound email evidence across applications, Postfix, filters, queues, and relays.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit codes: 0 trace found, 1 no trace, 2 invocation/runtime error.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-f", "--file", action="append", type=Path, help="Mail/syslog file. Repeat for multiple files. Use '-' for stdin.")
    parser.add_argument("--events", action="append", type=Path, help="Structured JSONL application/gateway events.")
    parser.add_argument("--journal", action="store_true", help="Read mail logs from journald.")
    parser.add_argument("--unit", action="append", help="systemd unit for --journal.")
    parser.add_argument("--since", help="journalctl --since value.")
    parser.add_argument("--until", help="journalctl --until value.")
    parser.add_argument("--live-queue", action="store_true", help="Add a live Postfix queue snapshot using postqueue -j.")
    parser.add_argument("--queue-file", action="append", type=Path, help="Read saved postqueue -j JSONL.")
    parser.add_argument("--no-plugins", action="store_true", help="Disable external parser plugins.")
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--message-id", help="Trace by RFC Message-ID.")
    query.add_argument("--queue", help="Trace by Postfix queue ID.")
    query.add_argument("--to", dest="recipient", help="Trace latest matching message to recipient.")
    query.add_argument("--correlation-id", help="Trace by application correlation ID.")
    parser.add_argument("--year", type=int, help="Year for classic syslog timestamps.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--html", type=Path, help="Also write a self-contained HTML report.")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto", help="Terminal color mode.")
    parser.add_argument("--ascii", action="store_true", help="Use ASCII-only terminal graphics.")
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
    raise FileNotFoundError("no mail log found; pass --file, --journal, --live-queue, or pipe logs on stdin")


def _dedupe(events):
    seen = set()
    unique = []
    for event in sorted(events, key=lambda item: item.timestamp):
        key = (event.timestamp, event.source, event.host, event.component, event.queue_id, event.message)
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return unique


def _list_parsers() -> int:
    try:
        adapters = [*builtin_adapters(), *discover_adapters()]
    except ParserError as exc:
        print(f"mailtrace: {exc}", file=sys.stderr)
        return ERROR
    print("mailtrace parsers")
    for adapter in adapters:
        print(f"  {adapter.name:<20} {'plugin' if adapter.external else 'builtin'}")
    return OK


def _run_demo(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="mailtrace demo", description="Run mailtrace with built-in forensic evidence.")
    parser.add_argument("scenario", nargs="?", choices=SCENARIOS, default="deferred")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--ascii", action="store_true")
    args = parser.parse_args(argv)
    color = supports_color(args.color, stream=sys.stdout)
    ascii_only = args.ascii or not supports_unicode(stream=sys.stdout)
    print(paint(banner(ascii_only=ascii_only), CYAN, enabled=color))
    print()
    print(render_explain(demo_trace(args.scenario), color=color, ascii_only=ascii_only))
    print()
    separator = " - " if ascii_only else " · "\n    print(f"scenario: {args.scenario}{separator}try: mailtrace demo delivered")
    return OK


def _run_doctor(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="mailtrace doctor", description="Check local mailtrace capabilities.")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--ascii", action="store_true")
    args = parser.parse_args(argv)
    color = supports_color(args.color, stream=sys.stdout)
    ascii_only = args.ascii or not supports_unicode(stream=sys.stdout)
    print(paint(compact_mark(ascii_only=ascii_only), CYAN, enabled=color))
    print(bold("forensic environment check", enabled=color))
    print()
    checks = collect_checks()
    icons = {"pass": "[ok]", "warn": "[!!]", "fail": "[xx]"}
    tones = {"pass": "confirmed", "warn": "pending", "fail": "failed"}
    for check in checks:
        icon = state(icons[check.state], tones[check.state], enabled=color)
        print(f"  {icon} {check.name:<18} {check.detail}")
    print()
    print("Warnings are optional capabilities; failures mean mailtrace itself is unhealthy.")
    return NO_TRACE if has_failures(checks) else OK


def _split_mode(argv: list[str]) -> tuple[str, list[str]]:
    commands = {"trace", "explain", "parsers", "demo", "doctor", "completion"}
    if argv and argv[0] in commands:
        return argv[0], argv[1:]
    return "trace", argv


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw or raw in (["-h"], ["--help"]):
        print(_root_help())
        return OK

    mode, command_argv = _split_mode(raw)
    if mode == "parsers":
        if command_argv:
            print("mailtrace: parsers takes no arguments", file=sys.stderr)
            return ERROR
        return _list_parsers()
    if mode == "demo":
        return _run_demo(command_argv)
    if mode == "doctor":
        return _run_doctor(command_argv)
    if mode == "completion":
        parser = argparse.ArgumentParser(prog="mailtrace completion")
        parser.add_argument("shell", choices=SHELLS)
        args = parser.parse_args(command_argv)
        print(completion_script(args.shell), end="")
        return OK

    args = _build_parser(prog=f"mailtrace {mode}" if mode != "trace" else "mailtrace").parse_args(command_argv)
    if (args.since or args.until or args.unit) and not args.journal:
        print("mailtrace: --since/--until/--unit require --journal", file=sys.stderr)
        return ERROR

    try:
        events = []
        explicit = bool(args.file or args.events or args.journal or args.live_queue or args.queue_file)
        batches = [_read_path(path) for path in (args.file or [])]
        if args.journal:
            batches.append(read_journal(units=args.unit, since=args.since, until=args.until))
        if not explicit:
            batches.append(_default_log_lines())
        for lines in batches:
            events.extend(parse_log_lines(lines, year=args.year, include_plugins=not args.no_plugins))
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
        return ERROR

    if args.html:
        args.html.write_text(render_html(trace), encoding="utf-8")

    color = False if args.json else supports_color(args.color, stream=sys.stdout)
    ascii_only = args.ascii or not supports_unicode(stream=sys.stdout)
    if args.json:
        print(render_json(trace))
    elif mode == "explain":
        print(render_explain(trace, color=color, ascii_only=ascii_only))
    else:
        print(render_text(trace, color=color))
    return OK if trace.events else NO_TRACE
