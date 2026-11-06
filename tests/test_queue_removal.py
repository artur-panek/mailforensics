from datetime import UTC, datetime

from mailforensics.pipeline import build_pipeline
from mailforensics.postfix import parse_postfix
from mailforensics.render import render_explain
from mailforensics.trace import find_trace

LOG = """\
2026-10-04T05:00:00Z gateway postfix/qmgr[100]: ABC123: from=<removed@example.net>, size=100, nrcpt=1 (queue active)
2026-10-04T05:00:01Z gateway postfix/smtp[101]: ABC123: to=<user@example.net>, relay=mx.example.net, status=sent (250 OK)
2026-10-04T05:00:02Z gateway postfix/qmgr[100]: ABC123: removed
"""


def test_queue_removal_is_not_a_new_queue_entry():
    events = parse_postfix(LOG.splitlines())

    assert [event.kind for event in events] == ["queued", "delivery", "removed"]
    assert events[0].details["sender"] == "removed@example.net"


def test_pipeline_uses_queue_entry_time_before_removal():
    trace = find_trace(parse_postfix(LOG.splitlines()), queue_id="ABC123")
    stages = build_pipeline(trace)

    assert stages[0].label == "QUEUE"
    assert stages[0].timestamp == datetime(2026, 10, 4, 5, 0, 0, tzinfo=UTC)
    assert stages[1].label == "RELAY"
    assert stages[1].timestamp == datetime(2026, 10, 4, 5, 0, 1, tzinfo=UTC)
    assert "| 1.000s" in render_explain(trace, ascii_only=True)
    assert len(trace.events) == 3
    assert trace.status == "sent"


def test_removal_without_intake_does_not_invent_a_queue_stage():
    trace = find_trace(parse_postfix([LOG.splitlines()[-1]]), queue_id="ABC123")

    assert build_pipeline(trace) == []
