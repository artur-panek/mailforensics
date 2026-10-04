from datetime import UTC, datetime

from mailtrace.diagnose import assess
from mailtrace.latency import latency_spans, total_observed_ms
from mailtrace.model import Event, Trace
from mailtrace.pipeline import build_pipeline
from mailtrace.queue import parse_postqueue_json


def test_postqueue_json_becomes_live_queue_evidence():
    events = parse_postqueue_json(
        [
            '{"queue_name":"deferred","queue_id":"abc123","arrival_time":1791080000,'
            '"message_size":1200,"sender":"app@example.net",'
            '"recipients":[{"address":"tester@example.com","delay_reason":"connect timed out"}]}'
        ],
        host="gateway",
        captured_at=datetime(2026, 10, 4, 6, 0, tzinfo=UTC),
    )

    event = events[0]
    assert event.queue_id == "ABC123"
    assert event.kind == "live-queue"
    assert event.details["recipient"] == "tester@example.com"
    assert event.details["queue_name"] == "deferred"


def test_latest_delivery_status_wins_over_earlier_deferred():
    events = [
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="ABC",
            kind="delivery",
            message="deferred",
            details={"status": "deferred"},
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 5, 1, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="ABC",
            kind="delivery",
            message="sent",
            details={"status": "sent"},
        ),
    ]
    trace = Trace(events, {"ABC"}, set(), set(), "queue=ABC")

    assert trace.status == "sent"
    assert assess(trace).outcome == "accepted-by-next-hop"


def test_deferred_plus_live_queue_means_retry_pending():
    events = [
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="ABC",
            kind="delivery",
            message="deferred",
            details={"status": "deferred"},
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 5, 2, tzinfo=UTC),
            source="postfix-queue",
            host="gateway",
            component="deferred",
            queue_id="ABC",
            kind="live-queue",
            message="still queued",
            details={"queue_name": "deferred"},
        ),
    ]
    trace = Trace(events, {"ABC"}, set(), set(), "queue=ABC")

    assert assess(trace).outcome == "queued-for-retry"


def test_latency_spans_are_consecutive_and_total_is_observed_window():
    events = [
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, 0, tzinfo=UTC),
            source="app",
            host="app",
            component="submit",
            queue_id=None,
            kind="submitted",
            message="submitted",
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, 1, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="cleanup",
            queue_id="ABC",
            kind="message-id",
            message="cleanup",
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, 3, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="ABC",
            kind="delivery",
            message="sent",
            details={"status": "sent"},
        ),
    ]
    trace = Trace(events, {"ABC"}, set(), set(), "queue=ABC")

    assert [span.duration_ms for span in latency_spans(trace)] == [1000, 2000]
    assert total_observed_ms(trace) == 3000


def test_pipeline_marks_mailbox_as_outside_evidence():
    events = [
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="ABC",
            kind="delivery",
            message="sent",
            details={"status": "sent", "relay": "mx.example.net"},
        )
    ]
    trace = Trace(events, {"ABC"}, set(), set(), "queue=ABC")

    pipeline = build_pipeline(trace)
    assert [(stage.label, stage.state) for stage in pipeline] == [
        ("RELAY", "confirmed"),
        ("MAILBOX", "unknown"),
    ]
