import json
from datetime import datetime

import pytest

from mailforensics.cli import main
from mailforensics.diagnose import assess
from mailforensics.html import render_html
from mailforensics.latency import total_observed_ms
from mailforensics.postfix import parse_postfix
from mailforensics.queue import parse_postqueue_json
from mailforensics.render import render_json, render_text
from mailforensics.trace import find_trace

RAW = json.dumps(
    {"queue_id": "ABC123", "arrival_time": 1791080000, "recipients": [{"address": "u@example.net"}]}
)
DELIVERY = (
    "2026-10-04T05:00:01Z mx postfix/smtp[1]: ABC123: to=<u@example.net>, status=sent (250 OK)"
)


@pytest.mark.parametrize(
    "observed,outcome",
    [
        (None, "accepted-by-next-hop"),
        ("2026-10-04T04:00:00+00:00", "accepted-by-next-hop"),
        ("2026-10-04T06:00:00+00:00", "queued-at-snapshot"),
    ],
)
def test_saved_queue_never_invents_current_presence(observed, outcome):
    queue = parse_postqueue_json(
        [RAW],
        host="mx",
        live=False,
        captured_at=datetime.fromisoformat(observed) if observed else None,
    )
    trace = find_trace([*queue, *parse_postfix([DELIVERY])], queue_id="ABC123")
    result = assess(trace)
    assert result.outcome == outcome
    assert "currently" not in result.summary
    if observed is None:
        assert queue == parse_postqueue_json([RAW], host="mx", live=False)
        assert queue[0].details["captured_at"] is None


def test_unknown_age_alone_is_explicit():
    trace = find_trace(parse_postqueue_json([RAW], live=False), queue_id="ABC123")
    assert trace.status == "unknown"
    assert assess(trace).outcome == "queue-observation-unknown-age"


def test_unknown_age_is_not_rendered_as_a_date_or_latency_origin():
    trace = find_trace(
        [*parse_postqueue_json([RAW], host="mx", live=False), *parse_postfix([DELIVERY])],
        queue_id="ABC123",
    )
    assert total_observed_ms(trace) == 0
    payload = json.loads(render_json(trace))
    assert payload["events"][0]["timestamp"] is None
    assert "0001-01-01" not in render_text(trace)
    assert "0001-01-01" not in render_html(trace)


@pytest.mark.parametrize("time", ["invalid", "2026-10-04T04:00:00"])
def test_cli_rejects_invalid_or_naive_observation_time(tmp_path, capsys, time):
    p = tmp_path / "queue.jsonl"
    p.write_text(RAW)
    assert main(["--queue-file", str(p), "--queue", "ABC123", "--queue-observed-at", time]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_smtp_rejection_retains_stage_code_without_queue_identity():
    event = parse_postfix(
        [
            "2026-10-04T05:00:00Z mx postfix/smtpd[1]: NOQUEUE: reject: RCPT from peer[192.0.2.1]: 550 5.1.1 unknown user; from=<a@example.net> to=<u@example.net> proto=ESMTP helo=<peer>"
        ]
    )[0]
    assert event.queue_id is None
    assert event.kind == "smtp-reject"
    assert event.details["smtp_stage"] == "RCPT"
    assert event.details["smtp_code"] == "550"
    trace = find_trace([event], recipient="u@example.net")
    assert trace.status == "rejected"
    assert assess(trace).outcome == "smtp-rejected"


def test_reject_warning_is_not_an_smtp_rejection():
    event = parse_postfix(
        [
            "2026-10-04T05:00:00Z mx postfix/smtpd[1]: NOQUEUE: reject_warning: RCPT from peer[192.0.2.1]: 450 policy; to=<u@example.net>"
        ]
    )[0]
    assert event.kind == "received"
    assert "smtp_code" not in event.details
