import json

import pytest

from mailforensics.cli import main
from mailforensics.postfix import parse_postfix
from mailforensics.queue import parse_postqueue_json
from mailforensics.rspamd import parse_rspamd
from mailforensics.structured import parse_structured_events
from mailforensics.trace import find_trace

FIRST = "3Pt2mN2VXxznjll"
SECOND = "3Pt2mN2VXXznjll"


@pytest.mark.parametrize("adapter", ["postfix", "rspamd", "structured", "postqueue"])
def test_adapters_keep_case_distinct_long_queue_ids_separate(adapter):
    ids = [FIRST, SECOND]
    if adapter == "postfix":
        events = parse_postfix([
            f"2026-10-18T10:00:0{index}Z mx postfix/cleanup[1]: {queue_id}: "
            f"message-id=<message-{index}@example.net>"
            for index, queue_id in enumerate(ids)
        ])
    elif adapter == "rspamd":
        events = parse_rspamd([
            f"2026-10-18T10:00:0{index}Z mx rspamd[1]: task; "
            f"id: <message-{index}@example.net>, qid: <{queue_id}>"
            for index, queue_id in enumerate(ids)
        ])
    elif adapter == "structured":
        events = parse_structured_events([
            json.dumps({"timestamp": f"2026-10-18T10:00:0{index}Z", "queue_id": queue_id,
                        "message_id": f"message-{index}@example.net"})
            for index, queue_id in enumerate(ids)
        ])
    else:
        events = parse_postqueue_json([json.dumps({"queue_id": queue_id}) for queue_id in ids])

    assert [event.queue_id for event in events] == ids
    trace = find_trace(events, queue_id=FIRST)
    assert trace.queue_ids == {FIRST}
    assert trace.events == [events[0]]
    assert find_trace(events, queue_id=FIRST.upper()).events == []


def test_postfix_handoff_keeps_the_exact_linked_queue_id():
    events = parse_postfix([
        f"2026-10-18T10:00:00Z mx postfix/cleanup[1]: {FIRST}: message-id=<original@example.net>",
        f"2026-10-18T10:00:01Z mx postfix/smtp[2]: {FIRST}: to=<alice@example.net>, "
        f"status=sent (250 queued as {SECOND})",
        f"2026-10-18T10:00:02Z relay postfix/qmgr[1]: {SECOND}: from=<sender@example.net>",
    ])
    trace = find_trace(events, message_id="original@example.net")

    assert events[1].details["linked_queue_id"] == SECOND
    assert trace.events == events
    assert trace.queue_ids == {FIRST, SECOND}


def test_structured_handoff_keeps_the_exact_linked_queue_id():
    events = parse_structured_events([
        json.dumps({"timestamp": "2026-10-18T10:00:00Z", "queue_id": FIRST,
                    "message_id": "original@example.net", "linked_queue_id": SECOND}),
        json.dumps({"timestamp": "2026-10-18T10:00:01Z", "queue_id": SECOND}),
    ])

    assert events[0].details["linked_queue_id"] == SECOND
    assert find_trace(events, message_id="original@example.net").queue_ids == {FIRST, SECOND}


def test_short_hexadecimal_queue_queries_remain_case_insensitive():
    events = parse_postfix([
        "2026-10-18T10:00:00Z mx postfix/cleanup[1]: ABC123: message-id=<short@example.net>",
    ])

    assert find_trace(events, queue_id="abc123").events == events


def test_rspamd_unknown_queue_id_is_still_ignored():
    events = parse_rspamd([
        "2026-10-18T10:00:00Z mx rspamd[1]: task; id: <original@example.net>, qid: <unknown>",
    ])

    assert events[0].queue_id is None


def test_cli_queue_query_preserves_case(tmp_path, capsys):
    path = tmp_path / "mail.log"
    path.write_text("\n".join([
        f"2026-10-18T10:00:00Z mx postfix/cleanup[1]: {FIRST}: message-id=<first@example.net>",
        f"2026-10-18T10:00:01Z mx postfix/cleanup[1]: {SECOND}: message-id=<second@example.net>",
    ]), encoding="utf-8")

    assert main(["--file", str(path), "--queue", FIRST, "--json", "--no-plugins"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == f"queue={FIRST}"
    assert payload["queue_ids"] == [FIRST]
    assert payload["message_ids"] == ["first@example.net"]
