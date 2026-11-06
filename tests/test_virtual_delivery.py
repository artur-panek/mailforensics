import pytest

from mailforensics.diagnose import assess
from mailforensics.postfix import parse_postfix
from mailforensics.trace import find_trace


def _delivery(recipient, status, clock="05:00:01"):
    dsn = {"sent": "2.0.0", "deferred": "4.2.0", "bounced": "5.1.1"}[status]
    return (
        f"2026-10-04T{clock}Z gateway postfix/virtual[101]: ABC123: "
        f"to=<{recipient}>, relay=virtual, delay=1, dsn={dsn}, status={status}"
    )


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        ("sent", "accepted-by-next-hop"),
        ("deferred", "deferred"),
        ("bounced", "bounced"),
    ],
)
def test_virtual_transport_delivery_drives_trace_outcome(status, outcome):
    events = parse_postfix([_delivery("user@example.net", status)])

    assert events[0].kind == "delivery"
    trace = find_trace(events, queue_id="ABC123")
    assert trace.status == status
    assert assess(trace).outcome == outcome
    assert assess(trace).last_confirmed_stage == "postfix:virtual"


def test_virtual_transport_preserves_distinct_recipient_outcomes():
    events = parse_postfix([
        _delivery("alice@example.net", "deferred"),
        _delivery("bob@example.net", "sent", "05:00:02"),
    ])
    trace = find_trace(events, queue_id="ABC123")

    assert trace.status == "mixed"
    assert assess(trace).outcome == "mixed-recipients"
    assert {result.recipient: result.status for result in trace.recipient_results} == {
        "alice@example.net": "deferred",
        "bob@example.net": "sent",
    }


def test_virtual_activity_without_status_is_not_delivery():
    event = parse_postfix([
        "2026-10-04T05:00:01Z gateway postfix/virtual[101]: ABC123: "
        "to=<user@example.net>, relay=virtual"
    ])[0]

    assert event.kind == "activity"
    assert find_trace([event], queue_id="ABC123").status == "unknown"
