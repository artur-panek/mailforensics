from datetime import UTC, datetime

from mailforensics.cli import _split_mode
from mailforensics.html import render_html
from mailforensics.model import Event, Trace
from mailforensics.render import render_explain, render_json


def _trace():
    events = [
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, 0, tzinfo=UTC),
            source="app",
            host="app",
            component="invite",
            queue_id=None,
            kind="submitted",
            message="submitted",
            details={"message_id": "mail@example.net"},
        ),
        Event(
            timestamp=datetime(2026, 10, 4, 5, 0, 1, tzinfo=UTC),
            source="postfix",
            host="gateway",
            component="smtp",
            queue_id="ABC",
            kind="delivery",
            message="sent",
            details={"status": "sent", "relay": "mx.example.net"},
        ),
    ]
    return Trace(events, {"ABC"}, {"mail@example.net"}, set(), "queue=ABC")


def test_explain_mode_is_backward_compatible():
    assert _split_mode(["--queue", "ABC"]) == ("trace", ["--queue", "ABC"])
    assert _split_mode(["explain", "--queue", "ABC"]) == (
        "explain",
        ["--queue", "ABC"],
    )


def test_explain_renders_pipeline_and_evidence_boundary():
    output = render_explain(_trace(), ascii_only=True)

    assert "Pipeline" in output
    assert "* APP" in output
    assert "* RELAY" in output
    assert "? MAILBOX" in output
    assert "accepted-by-next-hop" in output


def test_json_includes_pipeline_and_latency():
    output = render_json(_trace())

    assert '"pipeline"' in output
    assert '"latency"' in output
    assert '"total_observed_ms": 1000' in output


def test_html_report_is_self_contained_and_escaped():
    trace = _trace()
    trace.events[0].details["message_id"] = "<unsafe&value>"
    output = render_html(trace)

    assert "<!doctype html>" in output
    assert "mailforensics report" in output
    assert "outside available evidence" in output
    assert "<script" not in output
