from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from .postfix import find_trace, parse_postfix
from .render import render_json, render_text

DEFAULT_LOGS = (Path("/var/log/mail.log"), Path("/var/log/maillog"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mailtrace",
        description="Reconstruct an outbound email journey from Postfix logs.",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="Postfix log file. Use '-' for stdin. Defaults to /var/log/mail.log or /var/log/maillog.",
    )
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--message-id", help="Trace by RFC Message-ID, with or without angle brackets.")
    query.add_argument("--queue", help="Trace by Postfix queue ID.")
    query.add_argument("--to", dest="recipient", help="Trace messages for an exact recipient address.")
    parser.add_argument("--year", type=int, help="Year for classic syslog timestamps without a year.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def _open_lines(path: Path | None) -> Iterable[str]:
    if path and str(path) == "-":
        return sys.stdin
    if path:
        return path.open(encoding="utf-8", errors="replace")
    for candidate in DEFAULT_LOGS:
        if candidate.exists():
            return candidate.open(encoding="utf-8", errors="replace")
    if not sys.stdin.isatty():
        return sys.stdin
    raise FileNotFoundError(
        "no mail log found; pass --file /path/to/mail.log or pipe logs on stdin"
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        lines = _open_lines(args.file)
        events = parse_postfix(lines, year=args.year)
        trace = find_trace(
            events,
            message_id=args.message_id,
            queue_id=args.queue,
            recipient=args.recipient,
        )
    except (OSError, ValueError) as exc:
        print(f"mailtrace: {exc}", file=sys.stderr)
        return 2

    print(render_json(trace) if args.json else render_text(trace))
    return 0 if trace.events else 1
