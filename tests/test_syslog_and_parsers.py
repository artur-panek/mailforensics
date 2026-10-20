import os
import subprocess
import sys

from mailforensics.parsers import parse_log_lines
from mailforensics.postfix import parse_postfix
from mailforensics.rspamd import parse_rspamd
from mailforensics.syslog import parse_rfc5424


def test_rfc5424_parser_handles_structured_data():
    line = (
        '<14>1 2026-10-04T04:36:49.125Z gateway postfix/smtp 1202 ID47 '
        '[example@32473 key="value"] 0DC461ACD87: to=<tester@example.com>, '
        'relay=mx.example.com[203.0.113.10]:25, dsn=2.0.0, status=sent'
    )
    record = parse_rfc5424(line)

    assert record is not None
    assert record.host == "gateway"
    assert record.app == "postfix/smtp"
    assert record.body.startswith("0DC461ACD87:")


def test_postfix_parses_rfc5424_delivery():
    line = (
        "<14>1 2026-10-04T04:36:49Z gateway postfix/smtp 1202 - - "
        "0DC461ACD87: to=<tester@example.com>, "
        "relay=mx.example.com[203.0.113.10]:25, dsn=2.0.0, status=sent"
    )
    events = parse_postfix([line])

    assert len(events) == 1
    assert events[0].queue_id == "0DC461ACD87"
    assert events[0].kind == "delivery"


def test_postfix_marks_milter_reject():
    line = (
        "Oct  4 04:36:48 gateway postfix/smtpd[1200]: NOQUEUE: "
        "milter-reject: END-OF-MESSAGE from client[192.0.2.5]: "
        "5.7.1 blocked; from=<sender@example.net> to=<tester@example.com> "
        "proto=ESMTP helo=<client>"
    )
    event = parse_postfix([line], year=2026)[0]

    assert event.kind == "milter-reject"
    assert event.details["milter_action"] == "reject"
    assert event.details["milter_stage"] == "END-OF-MESSAGE"
    assert event.details["status"] == "rejected"


def test_rspamd_accepts_proxy_process_and_soft_reject():
    line = (
        "<14>1 2026-10-04T04:36:48.500Z gateway rspamd_proxy 2222 - - "
        "<abc>; proxy; rspamd_task_write_log: id: <mail@example.net>, "
        "qid: <ABC123>, rcpt: <tester@example.com>, "
        "(default: T (soft reject): [16.00/15.00])"
    )
    event = parse_rspamd([line])[0]

    assert event.queue_id == "ABC123"
    assert event.details["recipient"] == "tester@example.com"
    assert event.details["action"] == "soft reject"
    assert event.kind == "filter-reject"


def test_builtin_registry_runs_both_parsers():
    lines = [
        "2026-10-04T04:36:48+00:00 gateway postfix/cleanup[1200]: "
        "ABC123: message-id=<mail@example.net>",
        "2026-10-04T04:36:48.500+00:00 gateway rspamd[2222]: "
        "<abc>; task; rspamd_task_write_log: id: <mail@example.net>, "
        "qid: <ABC123>, (default: T (no action): [1.20/15.00])",
    ]
    events = parse_log_lines(lines, include_plugins=False)

    assert {event.source for event in events} == {"postfix", "rspamd"}


def test_local_syslog_timestamps_use_the_offset_for_the_logged_date():
    # Keep the test independent of the CI runner's local timezone.
    script = (
        "from mailforensics.timeparse import parse_iso_timestamp, parse_classic_syslog\n"
        "print(parse_iso_timestamp('2026-01-15T12:00:00').isoformat())\n"
        "print(parse_iso_timestamp('2026-07-15T12:00:00').isoformat())\n"
        "print(parse_classic_syslog('Jan', '15', '12:00:00', 2026).isoformat())\n"
        "print(parse_iso_timestamp('2026-01-15T12:00:00+02:00').isoformat())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "TZ": "Europe/Brussels"},
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout.splitlines() == [
        "2026-01-15T11:00:00+00:00",
        "2026-07-15T10:00:00+00:00",
        "2026-01-15T11:00:00+00:00",
        "2026-01-15T10:00:00+00:00",
    ]
