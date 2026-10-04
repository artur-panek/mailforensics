from mailforensics.diagnose import assess
from mailforensics.postfix import parse_postfix
from mailforensics.rspamd import parse_rspamd
from mailforensics.structured import parse_structured_events
from mailforensics.trace import find_trace

APP = """\
{"timestamp":"2026-10-04T04:36:47+00:00","source":"korpoappka","stage":"invite","kind":"submitted","correlation_id":"invite-42","message_id":"invite-123@sidelobe.dev","recipient":"tester@example.com","status":"submitted","message":"alpha invite handed to mail gateway"}
"""

POSTFIX = """\
2026-10-04T04:36:48+00:00 gateway postfix/cleanup[1200]: 0DC461ACD87: message-id=<invite-123@sidelobe.dev>
2026-10-04T04:36:48+00:00 gateway postfix/qmgr[1201]: 0DC461ACD87: from=<korpoappka@sidelobe.dev>, size=1184, nrcpt=1 (queue active)
2026-10-04T04:36:49+00:00 gateway postfix/smtp[1202]: 0DC461ACD87: to=<tester@example.com>, relay=mx.example.com[203.0.113.10]:25, delay=1.1, dsn=2.0.0, status=sent (250 2.0.0 OK)
"""

RSPAMD = """\
2026-10-04T04:36:48.500+00:00 gateway rspamd[2222]: <abc>; task; rspamd_task_write_log: id: <invite-123@sidelobe.dev>, qid: <0DC461ACD87>, from: <korpoappka@sidelobe.dev>, (default: T (no action): [1.20/15.00])
"""


def test_correlation_bridges_application_postfix_and_rspamd():
    events = [
        *parse_structured_events(APP.splitlines()),
        *parse_postfix(POSTFIX.splitlines()),
        *parse_rspamd(RSPAMD.splitlines()),
    ]
    trace = find_trace(events, correlation_id="invite-42")

    assert {event.source for event in trace.events} == {"korpoappka", "postfix", "rspamd"}
    assert trace.queue_ids == {"0DC461ACD87"}
    assert trace.message_ids == {"invite-123@sidelobe.dev"}
    assert trace.status == "sent"

    result = assess(trace)
    assert result.outcome == "accepted-by-next-hop"
    assert "not proof" in (result.caveat or "")


def test_assessment_points_out_gap_before_postfix():
    events = parse_structured_events(APP.splitlines())
    trace = find_trace(events, correlation_id="invite-42")

    result = assess(trace)
    assert result.outcome == "gap-before-postfix"
    assert result.last_confirmed_stage == "korpoappka:invite"


def test_message_id_correlation_does_not_casefold_opaque_id():
    events = [
        *parse_structured_events(
            [
                '{"timestamp":"2026-10-04T04:36:47+00:00","source":"app","message_id":"CaseSensitive@example.net","correlation_id":"a"}',
                '{"timestamp":"2026-10-04T04:36:48+00:00","source":"app","message_id":"casesensitive@example.net","correlation_id":"b"}',
            ]
        )
    ]
    trace = find_trace(events, message_id="CaseSensitive@example.net")

    assert [event.details["correlation_id"] for event in trace.events] == ["a"]
