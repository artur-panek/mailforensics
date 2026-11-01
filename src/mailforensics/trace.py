from __future__ import annotations

from .identifiers import normalize_queue_id
from .model import Event, Trace, event_recipients


def _normalize_message_id(value: str) -> str:
    return value.strip().strip("<>")


def _queue(value: str) -> str:
    return normalize_queue_id(value)


def _native_queue_host(event: Event) -> str:
    # Application/filter hosts need not be the Postfix instance owning the queue.
    if event.source in {"postfix", "postfix-queue"} and event.host != "-":
        return event.host
    return ""


def _unique_queue_host(queue_id: str, queue_hosts: dict[str, set[str]]) -> str:
    hosts = queue_hosts.get(queue_id, set())
    return next(iter(hosts)) if len(hosts) == 1 else ""


def _identifiers(
    event: Event, queue_hosts: dict[str, set[str]]
) -> set[tuple[str, str, str]]:
    identifiers: set[tuple[str, str, str]] = set()
    if event.queue_id:
        queue_id = _queue(event.queue_id)
        host = _native_queue_host(event) or _unique_queue_host(queue_id, queue_hosts)
        identifiers.add(("queue", host, queue_id))
    if linked := event.details.get("linked_queue_id"):
        queue_id = _queue(str(linked))
        identifiers.add(("queue", _unique_queue_host(queue_id, queue_hosts), queue_id))
    if message_id := event.details.get("message_id"):
        identifiers.add(("message", "", _normalize_message_id(str(message_id))))
    if correlation_id := event.details.get("correlation_id"):
        identifiers.add(("correlation", "", str(correlation_id)))
    return identifiers


def _matches_recipient(event: Event, recipient: str) -> bool:
    return any(address.casefold() == recipient.casefold() for address in event_recipients(event))


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

    queue_hosts: dict[str, set[str]] = {}
    for event in events:
        if event.queue_id and (host := _native_queue_host(event)):
            queue_hosts.setdefault(_queue(event.queue_id), set()).add(host)
    event_identifiers = [_identifiers(event, queue_hosts) for event in events]

    queue_messages: dict[tuple[str, str, str], set[str]] = {}
    for event in events:
        if event.queue_id and (observed_message := event.details.get("message_id")):
            observed_queue = _queue(event.queue_id)
            host = _native_queue_host(event) or _unique_queue_host(observed_queue, queue_hosts)
            queue_messages.setdefault(("queue", host, observed_queue), set()).add(
                _normalize_message_id(str(observed_message))
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
        if len(queue_hosts.get(normalized_queue, set())) > 1:
            raise ValueError(
                f"queue ID {normalized_queue} appears on multiple hosts; "
                "use a Message-ID or recipient query, or narrow the supplied logs"
            )
        query = f"queue={normalized_queue}"
        for index, event_ids in enumerate(event_identifiers):
            if any(kind == "queue" and value == normalized_queue for kind, _, value in event_ids):
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

    known: set[tuple[str, str, str]] = set()
    for index in selected:
        known.update(event_identifiers[index])

    changed = True
    while changed:
        changed = False
        for index, identifiers in enumerate(event_identifiers):
            if index in selected or (known and identifiers & known):
                if index not in selected:
                    selected.add(index)
                    changed = True
                before = len(known)
                known.update(identifiers)
                if len(known) != before:
                    changed = True

    for identifier in sorted(known):
        kind, host, value = identifier
        if kind != "queue":
            continue
        if not host and len(queue_hosts.get(value, set())) > 1:
            raise ValueError(
                f"queue ID {value} refers to multiple hosts; "
                "the reference or handoff is ambiguous; narrow the supplied logs"
            )
        if len(queue_messages.get(identifier, set())) > 1:
            raise ValueError(
                f"queue ID {value} on {host or 'an unspecified host'} has conflicting Message-IDs; "
                "queue reuse cannot be resolved safely; narrow the supplied logs"
            )

    trace_events = sorted((events[index] for index in selected), key=lambda event: event.timestamp)
    queue_ids = {value for kind, _, value in known if kind == "queue"}
    message_ids = {value for kind, _, value in known if kind == "message"}
    correlation_ids = {value for kind, _, value in known if kind == "correlation"}

    return Trace(
        events=trace_events,
        queue_ids=queue_ids,
        message_ids=message_ids,
        correlation_ids=correlation_ids,
        query=query,
        recipient=recipient,
    )
