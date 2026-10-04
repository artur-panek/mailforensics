from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .parsers import ParserError, discover_adapters

DEFAULT_LOGS = (Path("/var/log/mail.log"), Path("/var/log/maillog"))


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    state: str
    detail: str


def _command_check(command: str) -> DoctorCheck:
    path = shutil.which(command)
    if path:
        return DoctorCheck(command, "pass", path)
    return DoctorCheck(command, "warn", "not found in PATH")


def _journal_access() -> DoctorCheck:
    if shutil.which("journalctl") is None:
        return DoctorCheck("journal access", "warn", "journalctl unavailable")
    try:
        proc = subprocess.run(
            ["journalctl", "--no-pager", "-n", "1"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck("journal access", "warn", str(exc))
    if proc.returncode == 0:
        return DoctorCheck("journal access", "pass", "journalctl is readable")
    detail = proc.stderr.strip() or f"exit {proc.returncode}"
    return DoctorCheck("journal access", "warn", detail)


def _queue_access() -> DoctorCheck:
    if shutil.which("postqueue") is None:
        return DoctorCheck("Postfix queue", "warn", "postqueue unavailable")
    try:
        proc = subprocess.run(
            ["postqueue", "-j"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck("Postfix queue", "warn", str(exc))
    if proc.returncode == 0:
        count = sum(1 for line in proc.stdout.splitlines() if line.strip())
        return DoctorCheck("Postfix queue", "pass", f"readable ({count} queue item(s))")
    detail = proc.stderr.strip() or f"exit {proc.returncode}"
    return DoctorCheck("Postfix queue", "warn", detail)


def _mail_logs() -> DoctorCheck:
    existing = [path for path in DEFAULT_LOGS if path.exists()]
    readable = [path for path in existing if os.access(path, os.R_OK)]
    if readable:
        return DoctorCheck("mail logs", "pass", ", ".join(str(path) for path in readable))
    if existing:
        return DoctorCheck("mail logs", "warn", "found but not readable")
    return DoctorCheck("mail logs", "warn", "no default /var/log/mail.log or /var/log/maillog")


def _plugins() -> DoctorCheck:
    try:
        plugins = discover_adapters()
    except ParserError as exc:
        return DoctorCheck("parser plugins", "fail", str(exc))
    names = ", ".join(plugin.name for plugin in plugins)
    detail = names if names else "no external plugins installed"
    return DoctorCheck("parser plugins", "pass", detail)


def collect_checks() -> list[DoctorCheck]:
    version = sys.version_info
    python_state = "pass" if version >= (3, 11) else "fail"
    return [
        DoctorCheck(
            "Python",
            python_state,
            f"{version.major}.{version.minor}.{version.micro}",
        ),
        _command_check("journalctl"),
        _journal_access(),
        _command_check("postqueue"),
        _queue_access(),
        _mail_logs(),
        _plugins(),
    ]


def has_failures(checks: list[DoctorCheck]) -> bool:
    return any(check.state == "fail" for check in checks)
