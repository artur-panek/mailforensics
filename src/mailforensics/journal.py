from __future__ import annotations

import shutil
import subprocess


class JournalError(RuntimeError):
    pass


def read_journal(
    *,
    units: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[str]:
    if shutil.which("journalctl") is None:
        raise JournalError("journalctl not found")

    command = ["journalctl", "--no-pager", "-o", "short-iso-precise"]
    for unit in units or ["postfix", "rspamd"]:
        command.extend(["-u", unit])
    if since:
        command.extend(["--since", since])
    if until:
        command.extend(["--until", until])

    proc = subprocess.run(command, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit code {proc.returncode}"
        raise JournalError(f"journalctl failed: {detail}")
    return proc.stdout.splitlines()
