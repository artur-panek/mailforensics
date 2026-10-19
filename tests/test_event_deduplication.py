import json
from datetime import UTC, datetime

import pytest

from mailforensics.cli import _dedupe, main
from mailforensics.model import Event


def _run_events(tmp_path, capsys, rows, *query):
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    code = main(["--events", str(path), "--no-plugins", "--json", *query])
    output = capsys.readouterr()
    assert output.err == ""
    return code, json.loads(output.out)


def test_simultaneous_submissions_keep_their_identifiers(tmp_path, capsys):
    rows = [
        {
            "timestamp": "2026-10-19T01:00:00Z",
            "stage": "submit",
            "correlation_id": identifier,
            "message_id": f"{identifier}@example.net",
            "status": "submitted",
        }
        for identifier in ("first", "second")
    ]

    code, payload = _run_events(tmp_path, capsys, rows, "--correlation-id", "second")

    assert code == 0
    assert payload["correlation_ids"] == ["second"]
    assert payload["message_ids"] == ["second@example.net"]
    assert len(payload["events"]) == 1


def test_simultaneous_delivery_results_keep_each_recipient(tmp_path, capsys):
    rows = [
        {
            "timestamp": "2026-10-19T01:00:00Z",
            "source": "postfix",
            "component": "smtp",
            "kind": "delivery",
            "message": "delivery result",
            "queue_id": "ABC123",
            "recipient": recipient,
            "status": status,
        }
        for recipient, status in (
            ("first@example.net", "sent"),
            ("second@example.net", "deferred"),
        )
    ]

    code, payload = _run_events(tmp_path, capsys, rows, "--queue", "ABC123")

    assert code == 0
    assert payload["status"] == "mixed"
    assert len(payload["events"]) == 2
    assert {row["recipient"]: row["status"] for row in payload["recipient_results"]} == {
        "first@example.net": "sent",
        "second@example.net": "deferred",
    }


def test_duplicate_events_ignore_json_key_order_and_numeric_form(tmp_path, capsys):
    row = {
        "timestamp": "2026-10-19T01:00:00Z",
        "correlation_id": "first",
        "details": {"attempt": {"number": 1, "relays": ["mx.example.net"]}},
    }
    duplicate = dict(reversed(list(row.items())))
    duplicate["details"] = {"attempt": {"relays": ["mx.example.net"], "number": 1.0}}
    first_path = tmp_path / "first.jsonl"
    overlap_path = tmp_path / "overlap.jsonl"
    first_path.write_text(json.dumps(row), encoding="utf-8")
    overlap_path.write_text(json.dumps(duplicate), encoding="utf-8")

    code = main([
        "--events", str(first_path), "--events", str(overlap_path),
        "--no-plugins", "--json", "--correlation-id", "first",
    ])
    output = capsys.readouterr()
    assert output.err == ""
    payload = json.loads(output.out)

    assert code == 0
    assert len(payload["events"]) == 1


@pytest.mark.parametrize("values", [(True, 1), (False, 0), ([{"accepted": True}], [{"accepted": 1}])])
def test_boolean_details_are_not_numeric_duplicates(tmp_path, capsys, values):
    rows = [
        {
            "timestamp": "2026-10-19T01:00:00Z",
            "correlation_id": "first",
            "details": {"result": value},
        }
        for value in values
    ]

    code, payload = _run_events(tmp_path, capsys, rows, "--correlation-id", "first")

    assert code == 0
    assert len(payload["events"]) == 2


def test_plugin_details_need_no_hashing_or_json_serialization():
    events = [
        Event(
            timestamp=datetime(2026, 10, 19, 1, tzinfo=UTC),
            source="plugin",
            host="mail",
            component="submit",
            kind="submitted",
            message="mail event",
            details={"payload": bytearray(b"mail"), "tags": {"submitted"}},
        )
        for _ in range(2)
    ]

    assert _dedupe(events) == [events[0]]


def test_distinct_nested_details_are_not_duplicates(tmp_path, capsys):
    rows = [
        {
            "timestamp": "2026-10-19T01:00:00Z",
            "correlation_id": "first",
            "details": {"attempt": {"number": number, "relays": ["mx.example.net"]}},
        }
        for number in (1, 2)
    ]

    code, payload = _run_events(tmp_path, capsys, rows, "--correlation-id", "first")

    assert code == 0
    assert [event["details"]["attempt"]["number"] for event in payload["events"]] == [1, 2]


def test_different_event_kinds_are_not_duplicates(tmp_path, capsys):
    rows = [
        {
            "timestamp": "2026-10-19T01:00:00Z",
            "correlation_id": "first",
            "kind": kind,
            "message": "mail event",
        }
        for kind in ("submitted", "queued")
    ]

    code, payload = _run_events(tmp_path, capsys, rows, "--correlation-id", "first")

    assert code == 0
    assert [event["kind"] for event in payload["events"]] == ["submitted", "queued"]
    assert payload["status"] == "queued"
