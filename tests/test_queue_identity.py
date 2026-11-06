import json

import pytest

from mailforensics.cli import main
from mailforensics.diagnose import assess
from mailforensics.postfix import parse_postfix
from mailforensics.rspamd import parse_rspamd
from mailforensics.structured import parse_structured_events
from mailforensics.trace import find_trace


def cleanup(host, queue, message, second=0):
    return (
        f"2026-11-01T10:00:{second:02}Z {host} postfix/cleanup[1]: "
        f"{queue}: message-id=<{message}>"
    )


def delivery(host, queue, status, second=1, response="250 OK"):
    return (
        f"2026-11-01T10:00:{second:02}Z {host} postfix/smtp[2]: "
        f"{queue}: to=<user@example.net>, status={status} ({response})"
    )


def test_message_query_does_not_borrow_another_hosts_delivery():
    events = parse_postfix([
        cleanup("mx-a", "ABC123", "one@example.net"),
        cleanup("mx-b", "ABC123", "two@example.net"),
        delivery("mx-b", "ABC123", "sent"),
    ])

    trace = find_trace(events, message_id="one@example.net")

    assert trace.events == [events[0]]
    assert trace.message_ids == {"one@example.net"}
    assert trace.status == "unknown"
    assert assess(trace).outcome != "accepted-by-next-hop"


def test_queue_query_rejects_multiple_hosts():
    events = parse_postfix([
        cleanup("mx-a", "ABC123", "one@example.net"),
        cleanup("mx-b", "ABC123", "two@example.net"),
    ])

    with pytest.raises(ValueError, match="ABC123.*multiple hosts"):
        find_trace(events, queue_id="ABC123")


def test_recipient_query_selects_the_latest_hosts_queue():
    events = parse_postfix([
        cleanup("mx-a", "ABC123", "one@example.net"),
        delivery("mx-a", "ABC123", "sent"),
        cleanup("mx-b", "ABC123", "two@example.net", 2),
        delivery("mx-b", "ABC123", "deferred", 3),
    ])

    trace = find_trace(events, recipient="user@example.net")

    assert {event.host for event in trace.events} == {"mx-b"}
    assert trace.message_ids == {"two@example.net"}
    assert trace.status == "deferred"


@pytest.mark.parametrize("selector", [
    {"queue_id": "ABC123"},
    {"message_id": "one@example.net"},
    {"recipient": "user@example.net"},
    {"correlation_id": "request-1"},
])
def test_reused_queue_with_conflicting_message_ids_is_not_guessed(selector):
    events = [*application_event(), *parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        delivery("mx", "ABC123", "deferred"),
        cleanup("mx", "ABC123", "two@example.net", 2),
        delivery("mx", "ABC123", "sent", 3),
    ])]

    with pytest.raises(ValueError, match="ABC123.*conflicting Message-IDs"):
        find_trace(events, **selector)


@pytest.mark.parametrize("next_host", ["mx", "relay"])
def test_explicit_handoff_preserves_same_and_cross_host_evidence(next_host):
    events = parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        delivery("mx", "ABC123", "sent", response="250 queued as DEF456"),
        delivery(next_host, "DEF456", "deferred", 2),
    ])

    trace = find_trace(events, message_id="one@example.net")

    assert trace.events == events
    assert trace.queue_ids == {"ABC123", "DEF456"}
    assert trace.status == "deferred"
    assert find_trace(events, queue_id="DEF456").events == events


def test_handoff_with_multiple_possible_hosts_is_ambiguous():
    events = parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        delivery("mx", "ABC123", "sent", response="250 queued as DEF456"),
        delivery("relay-a", "DEF456", "deferred", 2),
        delivery("relay-b", "DEF456", "sent", 3),
    ])

    with pytest.raises(ValueError, match="DEF456.*multiple hosts"):
        find_trace(events, message_id="one@example.net")


def application_event():
    return parse_structured_events([json.dumps({
        "timestamp": "2026-11-01T10:00:00Z", "source": "app", "host": "web",
        "queue_id": "ABC123", "correlation_id": "request-1",
    })])


def test_application_queue_reference_can_bridge_to_one_native_host():
    events = [*application_event(), *parse_postfix([delivery("mx", "ABC123", "sent")])]

    trace = find_trace(events, correlation_id="request-1")

    assert trace.events == events
    assert trace.status == "sent"


def test_application_queue_reference_does_not_choose_between_hosts():
    events = [*application_event(), *parse_postfix([
        delivery("mx-a", "ABC123", "deferred"),
        delivery("mx-b", "ABC123", "sent", 2),
    ])]

    with pytest.raises(ValueError, match="ABC123.*multiple hosts"):
        find_trace(events, correlation_id="request-1")


def test_remote_filter_queue_reference_can_bridge_to_one_native_host():
    events = [*parse_rspamd([
        "2026-11-01T10:00:00Z filter rspamd[1]: task; qid: <ABC123>, "
        "(default: T (no action): [1.20/15.00])",
    ]), *parse_postfix([delivery("mx", "ABC123", "sent")])]

    trace = find_trace(events, queue_id="ABC123")

    assert trace.events == events


def test_unrelated_reused_queue_does_not_block_a_trace():
    events = parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        cleanup("mx", "ABC123", "two@example.net", 2),
        delivery("mx", "DEF456", "sent", 3),
    ])

    trace = find_trace(events, queue_id="DEF456")

    assert trace.events == [events[-1]]
    assert trace.status == "sent"


def test_explicit_message_id_still_bridges_different_hosts():
    events = parse_postfix([
        cleanup("mx-a", "ABC123", "one@example.net"),
        cleanup("mx-b", "ABC123", "one@example.net"),
        delivery("mx-b", "ABC123", "sent"),
    ])

    assert find_trace(events, message_id="one@example.net").events == events


def test_repeated_message_id_on_one_queue_is_not_a_conflict():
    events = parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        cleanup("mx", "ABC123", "one@example.net", 1),
        delivery("mx", "ABC123", "sent", 2),
    ])

    assert find_trace(events, message_id="one@example.net").status == "sent"


def test_handoff_can_bridge_an_explicit_message_id_change():
    events = parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        delivery("mx", "ABC123", "sent", response="250 queued as DEF456"),
        cleanup("relay", "DEF456", "rewritten@example.net", 2),
        delivery("relay", "DEF456", "deferred", 3),
    ])

    trace = find_trace(events, message_id="one@example.net")

    assert trace.events == events
    assert trace.message_ids == {"one@example.net", "rewritten@example.net"}
    assert trace.status == "deferred"


def test_missing_native_host_can_resolve_only_a_unique_queue():
    events = parse_postfix([
        cleanup("-", "ABC123", "one@example.net"),
        delivery("mx", "ABC123", "sent"),
    ])

    assert find_trace(events, message_id="one@example.net").events == events

    events.extend(parse_postfix([delivery("other", "ABC123", "deferred", 2)]))
    with pytest.raises(ValueError, match="ABC123.*multiple hosts"):
        find_trace(events, message_id="one@example.net")


def test_hostname_aliases_are_not_guessed():
    events = parse_postfix([
        cleanup("mx", "ABC123", "one@example.net"),
        delivery("mx.example.net", "ABC123", "sent"),
    ])

    trace = find_trace(events, message_id="one@example.net")

    assert trace.events == [events[0]]
    assert trace.status == "unknown"


def test_cli_ambiguous_queue_is_an_error_without_a_success_report(tmp_path, capsys):
    path = tmp_path / "mail.log"
    path.write_text("\n".join([
        cleanup("mx-a", "ABC123", "one@example.net"),
        delivery("mx-b", "ABC123", "sent"),
    ]), encoding="utf-8")

    result = main(["--file", str(path), "--queue", "ABC123", "--json", "--no-plugins"])

    assert result == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "multiple hosts" in output.err


@pytest.mark.parametrize("selector", [
    ["--queue", "ABC123"], ["--message-id", "one@example.net"],
])
def test_cli_saved_queue_does_not_claim_the_analysts_hostname(tmp_path, capsys, monkeypatch, selector):
    log = tmp_path / "mail.log"
    log.write_text("\n".join([
        cleanup("remote-mx.example.net", "ABC123", "one@example.net"),
        delivery("remote-mx.example.net", "ABC123", "deferred"),
    ]), encoding="utf-8")
    queue = tmp_path / "queue.jsonl"
    queue.write_text(json.dumps({
        "queue_id": "ABC123", "queue_name": "deferred",
        "recipients": [{"address": "user@example.net"}],
    }), encoding="utf-8")

    result = main([
        "--file", str(log), "--queue-file", str(queue), "--queue-observed-at", "2026-11-01T11:00:00Z", *selector, "--json", "--no-plugins",
    ])

    assert result == 0
    output = capsys.readouterr()
    assert output.err == ""
    payload = json.loads(output.out)
    assert payload["assessment"]["outcome"] == "queued-for-retry"
    assert payload["recipient_results"][0]["live_queue"]["host"] == "-"
    assert len(payload["events"]) == 3


def test_cli_saved_queue_does_not_resolve_a_multiple_host_selector(tmp_path, capsys):
    log = tmp_path / "mail.log"
    log.write_text("\n".join([
        cleanup("mx-a", "ABC123", "one@example.net"),
        cleanup("mx-b", "ABC123", "two@example.net"),
    ]), encoding="utf-8")
    queue = tmp_path / "queue.jsonl"
    queue.write_text(json.dumps({
        "queue_id": "ABC123", "recipients": [{"address": "user@example.net"}],
    }), encoding="utf-8")

    result = main([
        "--file", str(log), "--queue-file", str(queue), "--queue", "ABC123", "--json", "--no-plugins",
    ])

    assert result == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "multiple hosts" in output.err
