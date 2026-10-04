from mailforensics.rspamd import parse_rspamd

LOG = """\
2026-10-04T04:36:48.500+00:00 gateway rspamd[2222]: <abc>; task; rspamd_task_write_log: id: <invite-123@sidelobe.dev>, qid: <0DC461ACD87>, ip: 127.0.0.1, from: <korpoappka@sidelobe.dev>, (default: T (no action): [1.20/15.00] [DKIM_SIGNED(0.00)])
"""


def test_rspamd_extracts_message_and_queue_ids():
    events = parse_rspamd(LOG.splitlines())

    assert len(events) == 1
    event = events[0]
    assert event.source == "rspamd"
    assert event.queue_id == "0DC461ACD87"
    assert event.details["message_id"] == "invite-123@sidelobe.dev"
    assert event.details["action"] == "no action"
    assert event.details["score"] == "1.20"


def test_rspamd_reject_can_be_assessed():
    from mailforensics.diagnose import assess
    from mailforensics.trace import find_trace

    log = (
        "2026-10-04T04:36:48.500+00:00 gateway rspamd[2222]: "
        "<abc>; task; rspamd_task_write_log: id: <blocked@example.net>, "
        "qid: <ABC123>, (default: T (reject): [20.00/15.00])"
    )
    trace = find_trace(parse_rspamd([log]), message_id="blocked@example.net")

    assert assess(trace).outcome == "rejected-by-filter"
