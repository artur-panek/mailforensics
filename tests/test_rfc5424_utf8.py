import json

import pytest

from mailforensics.cli import main
from mailforensics.diagnose import assess
from mailforensics.parsers import parse_log_lines
from mailforensics.syslog import parse_rfc5424
from mailforensics.trace import find_trace


@pytest.mark.parametrize("structured_data", ["-", '[example@32473 key="value"]'])
@pytest.mark.parametrize("marker", ["", "\ufeff"])
def test_rfc5424_message_encoding_marker_is_not_part_of_the_body(structured_data, marker):
    body = "ABC123: to=<user@example.net>, status=sent (réponse: \ufeffOK)"
    line = (
        "<14>1 2026-10-04T04:36:49Z gateway postfix/smtp 1202 - "
        f"{structured_data} {marker}{body}"
    )

    record = parse_rfc5424(line)

    assert record is not None
    assert record.body == body


def test_rfc5424_removes_only_one_leading_message_marker():
    line = "<14>1 2026-10-04T04:36:49Z gateway postfix/smtp 1202 - - \ufeff\ufeffABC123"

    record = parse_rfc5424(line)

    assert record is not None
    assert record.body == "\ufeffABC123"


def test_utf8_postfix_delivery_is_not_lost_from_a_mixed_recipient_trace():
    lines = [
        "<14>1 2026-10-04T04:36:48Z gateway postfix/smtp 1202 - - "
        "ABC123: to=<alice@example.net>, status=sent (250 OK)",
        "<14>1 2026-10-04T04:36:49Z gateway postfix/smtp 1203 - - "
        "\ufeffABC123: to=<bob@example.net>, status=deferred (450 Réessayez plus tard)",
    ]
    events = parse_log_lines(lines, include_plugins=False)
    trace = find_trace(events, queue_id="ABC123")

    assert trace.status == "mixed"
    assert assess(trace).outcome == "mixed-recipients"
    assert {result.recipient: result.status for result in trace.recipient_results} == {
        "alice@example.net": "sent", "bob@example.net": "deferred",
    }
    assert events[1].raw == lines[1]
    assert events[1].message.endswith("(450 Réessayez plus tard)")


def test_cli_reads_utf8_syslog_message_marker(tmp_path, capsys):
    path = tmp_path / "mail.log"
    line = (
        "<14>1 2026-10-04T04:36:49Z gateway postfix/smtp 1202 - - "
        "\ufeffABC123: to=<user@example.net>, status=sent (250 accepté)"
    )
    path.write_bytes((line + "\n").encode("utf-8"))

    result = main(["--file", str(path), "--queue", "ABC123", "--json", "--no-plugins"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "sent"
    assert payload["assessment"]["outcome"] == "accepted-by-next-hop"
    assert "not proof" in payload["assessment"]["caveat"]
    assert len(payload["events"]) == 1
