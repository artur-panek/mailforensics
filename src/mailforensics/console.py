from __future__ import annotations

import os
import sys
from typing import TextIO

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
WHITE = "\x1b[37m"

STATE_COLORS = {
    "confirmed": GREEN,
    "pending": YELLOW,
    "failed": RED,
    "rejected": RED,
    "unknown": DIM,
}


def supports_color(mode: str = "auto", *, stream: TextIO | None = None) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if mode != "auto":
        raise ValueError(f"unknown color mode: {mode}")

    target = stream or sys.stdout
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("TERM", "").casefold() == "dumb":
        return False
    return bool(getattr(target, "isatty", lambda: False)())


def supports_unicode(*, stream: TextIO | None = None) -> bool:
    target = stream or sys.stdout
    encoding = getattr(target, "encoding", None) or "utf-8"
    try:
        "╭│▼✉●◐✕".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def paint(text: str, code: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{code}{text}{RESET}"


def bold(text: str, *, enabled: bool) -> str:
    return paint(text, BOLD, enabled=enabled)


def dim(text: str, *, enabled: bool) -> str:
    return paint(text, DIM, enabled=enabled)


def state(text: str, state_name: str, *, enabled: bool) -> str:
    return paint(text, STATE_COLORS.get(state_name, WHITE), enabled=enabled)
