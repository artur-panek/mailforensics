import json

import pytest

from mailforensics.cli import main
from mailforensics.diagnose import assess
from mailforensics.model import event_recipients
from mailforensics.rspamd import parse_rspamd
from mailforensics.trace import find_trace


def log(recipients):
    return (
        "2026-11-10T10:00:00Z mx rspamd[42]: "
        "<abc>; task; rspamd_task_write_log: id: <blocked@example.net>, "
        "qid: <ABC123>, (default: T (reject): [20.00/15.00]), "
        f"rcpts: <{recipients}>, mime_rcpts: <header-only@example.net>"
    )


@pytest.mark.parametrize("recipient", ["alice@example.net", "bob@example.net"])
def test_default_rspamd_log_is_traceable_by_each_envelope_recipient(recipient):
    events = parse_rspamd([log("alice@example.net,bob@example.net")])
    assert event_recipients(events[0]) == ["alice@example.net", "bob@example.net"]

    trace = find_trace(events, recipient=recipient)
    assert trace.events == events
    assert assess(trace).outcome == "rejected-by-filter"
    assert not find_trace(events, recipient="header-only@example.net").events


def test_recipient_list_preserves_quoted_local_parts():
    events = parse_rspamd([log('"last,first"@example.net, alice@example.net')])
    assert event_recipients(events[0]) == ['"last,first"@example.net', "alice@example.net"]


@pytest.mark.parametrize("field", ["rcpt", "to"])
def test_singular_recipient_fields_remain_supported(field):
    line = log("").replace("rcpts: <>", f"{field}: <alice@example.net>")
    assert event_recipients(parse_rspamd([line])[0]) == ["alice@example.net"]


def test_mime_recipients_do_not_become_envelope_evidence():
    events = parse_rspamd([log("").replace("rcpts: <>, ", "")])
    assert event_recipients(events[0]) == []
    assert not find_trace(events, recipient="header-only@example.net").events


def test_cli_finds_default_rspamd_rejection_by_recipient(tmp_path, capsys):
    path = tmp_path / "mail.log"
    path.write_text(log("alice@example.net,bob@example.net"), encoding="utf-8")
    assert main([
        "--file", str(path), "--to", "bob@example.net", "--json", "--no-plugins",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["assessment"]["outcome"] == "rejected-by-filter"
