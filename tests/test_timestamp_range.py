import pytest

from mailforensics.parsers import parse_log_lines


@pytest.mark.parametrize("timestamp", [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59-01:00",
])
@pytest.mark.parametrize("rfc5424", [False, True])
@pytest.mark.parametrize("source", ["postfix/smtp", "rspamd"])
def test_unrepresentable_utc_timestamp_does_not_discard_following_event(
    timestamp, rfc5424, source,
):
    body = (
        "ABC123: to=<tester@example.com>, status=sent"
        if source == "postfix/smtp"
        else "qid: <ABC123>, (default: T (reject): [16.00/15.00])"
    )

    def line(stamp):
        if rfc5424:
            return f"<14>1 {stamp} gateway {source} 1200 - - {body}"
        return f"{stamp} gateway {source}[1200]: {body}"

    events = parse_log_lines(
        [line(timestamp), line("2026-10-04T12:00:00Z")],
        include_plugins=False,
    )

    assert len(events) == 1
    assert events[0].queue_id == "ABC123"
    assert events[0].timestamp.isoformat() == "2026-10-04T12:00:00+00:00"
