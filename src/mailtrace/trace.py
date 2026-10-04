from __future__ import annotations

from .model import Event, Trace


def _normalize_message_id(value: str) -> str:
    return value.strip().strip("<>")


def _queue(value: str) -> str:
    return value.upper()


def _identifiers(event: Event) -> set[tuple[str, str]]:
    identifiers: set[tuple[str, str]] = set()
    if event.queue_id:
        identifiers.add(("queue", _queue(event.queue_id)))
    if linked := event.details.get("linked_queue_id"):
        identifiers.add(("queue", _queue(str(linked))))
    if message_id := event.details.get("message_id"):
        identifiers.add(("message", _normalize_message_id(str(message_id))))
    if correlation_id := event.details.get("correlation_id"):
        identifiers.add(("correlation", str(correlation_id)))
    return identifiers


def _matches_recipient(event: Event, recipient: str) -> bool:
    candidate = event.details.get("recipient")
    if candidate and str(candidate).casefold() == recipient.casefold():
        return True
    recipients = event.details.get("recipients")
    if isinstance(recipients, list):
        return any(str(value).casefold() == recipient.casefold() for value in recipients)
    return False


def find_trace(
    events: list[Event],
    *,
    message_id: str | None = None,
    queue_id: str | None = None,
    recipient: str | None = None,
    correlation_id: str | None = None,
) -> Trace:
    selectors = [
        value is not None
        for value in (message_id, queue_id, recipient, correlation_id)
    ]
    if sum(selectors) != 1:
        raise ValueError(
            "exactly one of message_id, queue_id, recipient, or correlation_id must be provided"
        )

    selected: set[int] = set()
    query: str

    if message_id is not None:
        normalized = _normalize_message_id(message_id)
        query = f"message-id=<{message_id.strip().strip('<>')}>"
        for index, event in enumerate(events):
            candidate = event.details.get("message_id")
            if candidate and _normalize_message_id(str(candidate)) == normalized:
                selected.add(index)
    elif queue_id is not None:
        normalized_queue = _queue(queue_id)
        query = f"queue={normalized_queue}"
        for index, event in enumerate(events):
            event_ids = _identifiers(event)
            if ("queue", normalized_queue) in event_ids:
                selected.add(index)
    elif recipient is not None:
        query = f"to=<{recipient}> (latest match)"
        matches = [
            (index, event)
            for index, event in enumerate(events)
            if _matches_recipient(event, recipient)
        ]
        if matches:
            latest_index, _ = max(matches, key=lambda item: item[1].timestamp)
            selected.add(latest_index)
    else:
        assert correlation_id is not None
        query = f"correlation={correlation_id}"
        for index, event in enumerate(events):
            candidate = event.details.get("correlation_id")
            if candidate and str(candidate) == correlation_id:
                selected.add(index)

    known: set[tuple[str, str]] = set()
    for index in selected:
        known.update(_identifiers(events[index]))

    changed = True
    while changed:
        changed = False
        for index, event in enumerate(events):
            identifiers = _identifiers(event)
            if index in selected or (known and identifiers & known):
                if index not in selected:
                    selected.add(index)
                    changed = True
                before = len(known)
                known.update(identifiers)
                if len(known) != before:
                    changed = True

    trace_events = sorted((events[index] for index in selected), key=lambda event: event.timestamp)
    queue_ids = {value for kind, value in known if kind == "queue"}
    message_ids = {value for kind, value in known if kind == "message"}
    correlation_ids = {value for kind, value in known if kind == "correlation"}

    return Trace(
        events=trace_events,
        queue_ids=queue_ids,
        message_ids=message_ids,
        correlation_ids=correlation_ids,
        query=query,
    )
