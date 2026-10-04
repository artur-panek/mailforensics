from mailtrace.postfix import find_trace, parse_postfix

LOG = """\
Oct  4 04:36:48 gateway postfix/cleanup[1200]: 0DC461ACD87: message-id=<invite-123@sidelobe.dev>
Oct  4 04:36:48 gateway postfix/qmgr[1201]: 0DC461ACD87: from=<korpoappka@sidelobe.dev>, size=1184, nrcpt=1 (queue active)
Oct  4 04:36:49 gateway postfix/smtp[1202]: 0DC461ACD87: to=<tester@example.com>, relay=mx.example.com[203.0.113.10]:25, delay=1.1, delays=0.1/0/0.3/0.7, dsn=2.0.0, status=sent (250 2.0.0 OK: queued as 24D1C1ACD8B)
Oct  4 04:36:49 gateway postfix/qmgr[1201]: 24D1C1ACD8B: from=<korpoappka@sidelobe.dev>, size=1184, nrcpt=1 (queue active)
"""


def test_parse_extracts_delivery_fields():
    events = parse_postfix(LOG.splitlines(), year=2026)
    delivery = events[2]

    assert delivery.queue_id == "0DC461ACD87"
    assert delivery.details["recipient"] == "tester@example.com"
    assert delivery.details["relay"].startswith("mx.example.com")
    assert delivery.details["status"] == "sent"
    assert delivery.details["dsn"] == "2.0.0"
    assert delivery.details["linked_queue_id"] == "24D1C1ACD8B"


def test_message_id_trace_follows_queued_as_link():
    events = parse_postfix(LOG.splitlines(), year=2026)
    trace = find_trace(events, message_id="invite-123@sidelobe.dev")

    assert trace.queue_ids == {"0DC461ACD87", "24D1C1ACD8B"}
    assert len(trace.events) == 4
    assert trace.status == "sent"


def test_recipient_trace_correlates_whole_queue():
    events = parse_postfix(LOG.splitlines(), year=2026)
    trace = find_trace(events, recipient="tester@example.com")

    assert trace.events[0].details["message_id"] == "invite-123@sidelobe.dev"
