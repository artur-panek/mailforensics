from datetime import UTC, datetime

from mailtrace.model import Event
from mailtrace.trace import find_trace


def test_recipient_query_uses_latest_matching_message_only():
    events = [
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="OLD1",
            kind="delivery",
            message="old",
            details={"recipient": "tester@example.com", "status": "sent"},
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 6, 0, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="NEW2",
            kind="delivery",
            message="new",
            details={"recipient": "tester@example.com", "status": "deferred"},
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 6, 1, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="qmgr",
            queue_id="NEW2",
            kind="queued",
            message="new queued",
        ),
    ]

    trace = find_trace(events, recipient="tester@example.com")

    assert trace.queue_ids == {"NEW2"}
    assert {event.queue_id for event in trace.events} == {"NEW2"}
    assert "latest match" in trace.query


def test_recipient_query_can_seed_from_postqueue_recipients_list():
    event = Event(
        timestamp=datetime(2026, 10, 4, 6, 0, tzinfo=UTC),
        source="postfix-queue",
        host="gateway",
        component="deferred",
        queue_id="ABC",
        kind="live-queue",
        message="queued",
        details={"recipients": ["one@example.com", "two@example.com"]},
    )

    trace = find_trace([event], recipient="two@example.com")

    assert trace.queue_ids == {"ABC"}
