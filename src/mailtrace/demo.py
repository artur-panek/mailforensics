from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .model import Event, Trace

SCENARIOS = ("deferred", "delivered", "rejected", "gap")


def _event(
    seconds: float,
    *,
    source: str,
    component: str,
    kind: str,
    message: str,
    queue_id: str | None = "0DC461ACD87",
    details: dict | None = None,
) -> Event:
    base = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    return Event(
        timestamp=base + timedelta(seconds=seconds),
        source=source,
        host="demo-gateway",
        component=component,
        queue_id=queue_id,
        kind=kind,
        message=message,
        details=details or {},
    )


def demo_trace(scenario: str = "deferred") -> Trace:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown demo scenario: {scenario}")

    message_id = "invite-123@example.net"
    correlation_id = "invite-42"

    app = _event(
        0,
        source="demo-app",
        component="invite",
        kind="submitted",
        message="invite handed to mail gateway",
        queue_id=None,
        details={
            "message_id": message_id,
            "correlation_id": correlation_id,
            "recipient": "tester@example.com",
            "status": "submitted",
        },
    )

    if scenario == "gap":
        return Trace(
            events=[app],
            queue_ids=set(),
            message_ids={message_id},
            correlation_ids={correlation_id},
            query=f"correlation={correlation_id}",
        )

    cleanup = _event(
        0.092,
        source="postfix",
        component="cleanup",
        kind="message-id",
        message=f"message-id=<{message_id}>",
        details={"message_id": message_id},
    )
    filter_event = _event(
        0.126,
        source="rspamd",
        component="filter",
        kind="filter",
        message="Rspamd task result",
        details={"message_id": message_id, "action": "no action", "score": "1.20"},
    )
    queued = _event(
        0.137,
        source="postfix",
        component="qmgr",
        kind="queued",
        message="queue active",
        details={"sender": "app@example.net"},
    )

    if scenario == "rejected":
        rejected_filter = _event(
            0.126,
            source="rspamd",
            component="filter",
            kind="filter-reject",
            message="Rspamd rejected message",
            details={"message_id": message_id, "action": "reject", "score": "20.00"},
        )
        return Trace(
            events=[app, cleanup, rejected_filter],
            queue_ids={"0DC461ACD87"},
            message_ids={message_id},
            correlation_ids={correlation_id},
            query=f"correlation={correlation_id}",
        )

    if scenario == "delivered":
        sent = _event(
            0.979,
            source="postfix",
            component="smtp",
            kind="delivery",
            message="status=sent",
            details={
                "recipient": "tester@example.com",
                "relay": "mx.example.net[203.0.113.10]:25",
                "status": "sent",
                "dsn": "2.0.0",
                "delay": "0.842",
            },
        )
        return Trace(
            events=[app, cleanup, filter_event, queued, sent],
            queue_ids={"0DC461ACD87"},
            message_ids={message_id},
            correlation_ids={correlation_id},
            query=f"correlation={correlation_id}",
        )

    deferred = _event(
        0.979,
        source="postfix",
        component="smtp",
        kind="delivery",
        message="status=deferred",
        details={
            "recipient": "tester@example.com",
            "relay": "mx.example.net[203.0.113.10]:25",
            "status": "deferred",
            "dsn": "4.4.1",
            "delay": "0.842",
        },
    )
    live_queue = _event(
        128.979,
        source="postfix-queue",
        component="deferred",
        kind="live-queue",
        message="queue entry still present",
        details={
            "queue_name": "deferred",
            "recipient": "tester@example.com",
            "captured_at": "2026-10-04T12:02:08.979000+00:00",
        },
    )
    return Trace(
        events=[app, cleanup, filter_event, queued, deferred, live_queue],
        queue_ids={"0DC461ACD87"},
        message_ids={message_id},
        correlation_ids={correlation_id},
        query=f"correlation={correlation_id}",
    )
