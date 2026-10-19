import json
from datetime import UTC, datetime

import pytest

from mailforensics.cli import main
from mailforensics.diagnose import assess
from mailforensics.html import render_html
from mailforensics.pipeline import build_pipeline
from mailforensics.postfix import parse_postfix
from mailforensics.queue import parse_postqueue_json
from mailforensics.render import render_json
from mailforensics.structured import parse_structured_events
from mailforensics.trace import find_trace

MESSAGE = "2026-10-18T10:00:00Z mx postfix/cleanup[1]: ABC123: message-id=<group@example.net>"


def delivery(recipient, status, second):
    return (
        f"2026-10-18T10:00:{second:02}Z mx postfix/smtp[2]: ABC123: "
        f"to=<{recipient}>, relay=mx.example.net, status={status} (synthetic result)"
    )


@pytest.mark.parametrize(
    ("alice_status", "bob_status", "expected_outcome"),
    [("deferred", "sent", "deferred"), ("bounced", "sent", "bounced"),
     ("sent", "deferred", "accepted-by-next-hop")],
)
def test_recipient_query_keeps_other_recipients_out_of_its_result(
    alice_status, bob_status, expected_outcome
):
    events = parse_postfix([
        MESSAGE, delivery("alice@example.net", alice_status, 1),
        delivery("bob@example.net", bob_status, 2),
    ])
    trace = find_trace(events, recipient="ALICE@example.net")

    assert trace.events == events
    assert trace.status == alice_status
    assert assess(trace).outcome == expected_outcome
    relay = next(stage for stage in build_pipeline(trace) if stage.key == "relay")
    assert "alice@example.net" in relay.detail
    assert "bob@example.net" not in relay.detail
    payload = json.loads(render_json(trace))
    assert payload["recipient"] == "ALICE@example.net"
    assert [result["status"] for result in payload["recipient_results"]] == [alice_status]


def test_message_query_reports_mixed_outcomes_in_all_formats():
    trace = find_trace(parse_postfix([
        MESSAGE, delivery("alice@example.net", "deferred", 1),
        delivery("bob@example.net", "sent", 2),
    ]), message_id="group@example.net")

    assert trace.status == "mixed"
    assert assess(trace).outcome == "mixed-recipients"
    relay = next(stage for stage in build_pipeline(trace) if stage.key == "relay")
    assert relay.state == "mixed"
    assert "<alice@example.net>: deferred" in relay.detail
    assert "<bob@example.net>: sent" in relay.detail
    payload = json.loads(render_json(trace))
    assert {result["recipient"]: result["status"] for result in payload["recipient_results"]} == {
        "alice@example.net": "deferred", "bob@example.net": "sent",
    }
    assert len(payload["events"]) == 3
    assert "mixed-recipients" in render_html(trace)
    assert "&lt;alice@example.net&gt;: deferred" in render_html(trace)


def test_later_retry_only_replaces_that_recipients_result():
    events = parse_postfix([
        MESSAGE, delivery("alice@example.net", "deferred", 1),
        delivery("bob@example.net", "bounced", 2),
        delivery("alice@example.net", "sent", 3),
    ])
    trace = find_trace(list(reversed(events)), queue_id="ABC123")

    assert {result.recipient: result.status for result in trace.recipient_results} == {
        "alice@example.net": "sent", "bob@example.net": "bounced",
    }
    assert trace.status == "mixed"
    assert find_trace(events, recipient="alice@example.net").status == "sent"


def queue_snapshot(recipients, second=3):
    return parse_postqueue_json([
        json.dumps({"queue_id": "ABC123", "queue_name": "deferred", "recipients": recipients})
    ], captured_at=datetime(2026, 10, 18, 10, 0, second, tzinfo=UTC))


def test_remaining_queue_recipient_does_not_change_a_successful_recipient():
    events = [
        *parse_postfix([MESSAGE, delivery("alice@example.net", "sent", 1)]),
        *queue_snapshot([{"address": "bob@example.net"}]),
    ]
    alice = find_trace(events, recipient="alice@example.net")
    bob = find_trace(events, recipient="bob@example.net")
    whole = find_trace(events, queue_id="ABC123")

    assert alice.status == "sent"
    assert assess(alice).outcome == "accepted-by-next-hop"
    assert all(stage.key != "queue-live" for stage in build_pipeline(alice))
    assert bob.status == "queued"
    assert assess(bob).outcome == "queued-live"
    assert whole.status == "mixed"
    assert assess(whole).outcome == "mixed-recipients"


def test_deferred_recipient_is_confirmed_in_its_own_queue_snapshot():
    events = [
        *parse_postfix([
            MESSAGE, delivery("alice@example.net", "deferred", 1),
            delivery("bob@example.net", "sent", 2),
        ]),
        *queue_snapshot([{"address": "alice@example.net"}]),
    ]
    trace = find_trace(events, recipient="alice@example.net")

    assert trace.status == "deferred"
    assert assess(trace).outcome == "queued-for-retry"
    payload = json.loads(render_json(trace))
    assert payload["recipient_results"][0]["live_queue"]["kind"] == "live-queue"


def test_success_after_a_queue_snapshot_clears_the_pending_result():
    events = [
        *queue_snapshot([{"address": "alice@example.net"}], second=1),
        *parse_postfix([MESSAGE, delivery("alice@example.net", "sent", 2)]),
    ]
    trace = find_trace(events, recipient="alice@example.net")

    assert trace.status == "sent"
    assert assess(trace).outcome == "accepted-by-next-hop"
    assert all(stage.key != "queue-live" for stage in build_pipeline(trace))
    assert json.loads(render_json(trace))["recipient_results"][0]["live_queue"] is None


def test_recipient_without_delivery_evidence_does_not_borrow_another_result():
    events = [
        *parse_structured_events([json.dumps({
            "timestamp": "2026-10-18T10:00:00Z", "source": "app", "kind": "submitted",
            "recipient": "alice@example.net", "message_id": "group@example.net",
        })]),
        *parse_postfix([MESSAGE, delivery("bob@example.net", "sent", 2)]),
    ]
    alice = find_trace(events, recipient="alice@example.net")
    whole = find_trace(events, message_id="group@example.net")

    assert alice.status == "submitted"
    assert assess(alice).outcome != "accepted-by-next-hop"
    assert alice.recipient_results[0].status == "unknown"
    assert whole.status == "mixed"


def test_cli_recipient_query_uses_structured_recipient_scope(tmp_path, capsys):
    path = tmp_path / "mail.log"
    path.write_text("\n".join([
        MESSAGE, delivery("alice@example.net", "deferred", 1),
        delivery("bob@example.net", "sent", 2),
    ]), encoding="utf-8")

    assert main(["--file", str(path), "--to", "alice@example.net", "--json", "--no-plugins"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "deferred"
    assert payload["assessment"]["outcome"] == "deferred"
    assert len(payload["events"]) == 3
