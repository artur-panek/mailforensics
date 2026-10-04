from types import SimpleNamespace

from mailtrace import journal


def test_journal_builds_expected_command(monkeypatch):
    monkeypatch.setattr(journal.shutil, "which", lambda name: "/usr/bin/journalctl")

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="line one\nline two\n", stderr="")

    monkeypatch.setattr(journal.subprocess, "run", fake_run)

    lines = journal.read_journal(
        units=["postfix", "rspamd"],
        since="10 minutes ago",
        until="now",
    )

    assert lines == ["line one", "line two"]
    assert captured["command"] == [
        "journalctl",
        "--no-pager",
        "-o",
        "short-iso-precise",
        "-u",
        "postfix",
        "-u",
        "rspamd",
        "--since",
        "10 minutes ago",
        "--until",
        "now",
    ]
