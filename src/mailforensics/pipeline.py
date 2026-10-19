from __future__ import annotations

from .model import Event, PipelineStage, Trace


def _first(events: list[Event]) -> Event | None:
    return min(events, key=lambda event: event.timestamp) if events else None


def _last(events: list[Event]) -> Event | None:
    return max(events, key=lambda event: event.timestamp) if events else None


def _detail(event: Event) -> str:
    if event.kind == "submitted":
        return f"{event.source}/{event.component}"
    if event.kind == "milter-reject":
        return "milter rejected the message"
    if event.source == "rspamd":
        action = event.details.get("action")
        return f"Rspamd: {action}" if action else "Rspamd processed message"
    if event.kind == "queued":
        return f"queue {event.queue_id or '-'}"
    if event.kind == "live-queue":
        name = event.details.get("queue_name", "queue")
        return f"still present in {name} queue"
    if event.kind == "delivery":
        status = event.details.get("status", "unknown")
        relay = event.details.get("relay")
        return f"{status} via {relay}" if relay else str(status)
    return f"{event.source}/{event.component}"


def build_pipeline(trace: Trace) -> list[PipelineStage]:
    events = sorted(trace.scoped_events, key=lambda event: event.timestamp)
    stages: list[PipelineStage] = []

    application_events = [
        event
        for event in events
        if event.source not in {"postfix", "rspamd", "postfix-queue"}
    ]
    if event := _first(application_events):
        stages.append(
            PipelineStage(
                key="application",
                label="APP",
                state="confirmed",
                detail=_detail(event),
                timestamp=event.timestamp,
            )
        )

    postfix_intake = [
        event
        for event in events
        if event.source == "postfix"
        and event.kind in {"pickup", "received", "message-id", "activity"}
    ]
    if event := _first(postfix_intake):
        stages.append(
            PipelineStage(
                key="postfix",
                label="POSTFIX",
                state="confirmed",
                detail=_detail(event),
                timestamp=event.timestamp,
            )
        )

    filter_events = [
        event
        for event in events
        if event.source == "rspamd"
        or event.kind in {"milter-reject", "milter-discard"}
    ]
    if event := _last(filter_events):
        rejected = (
            event.kind in {"milter-reject", "milter-discard", "filter-reject"}
            or str(event.details.get("action", "")).casefold()
            in {"reject", "soft reject", "discard"}
        )
        stages.append(
            PipelineStage(
                key="filter",
                label="FILTER",
                state="rejected" if rejected else "confirmed",
                detail=_detail(event),
                timestamp=event.timestamp,
            )
        )

    queue_events = [
        event
        for event in events
        if event.source == "postfix" and event.kind == "queued"
    ]
    if event := _last(queue_events):
        stages.append(
            PipelineStage(
                key="queue",
                label="QUEUE",
                state="confirmed",
                detail=_detail(event),
                timestamp=event.timestamp,
            )
        )

    results = trace.recipient_results
    deliveries = [result.delivery for result in results if result.delivery]
    latest_delivery = _last(deliveries)
    if latest_delivery:
        status = trace.status
        if status == "sent":
            state = "confirmed"
        elif status in {"deferred", "queued"}:
            state = "pending"
        elif status == "bounced":
            state = "failed"
        elif status == "mixed":
            state = "mixed"
        else:
            state = "unknown"
        detail = "; ".join(
            (f"<{result.recipient}>: " if result.recipient else "")
            + (result.status if result.queued or not result.delivery else _detail(result.delivery))
            for result in results
        )
        stages.append(
            PipelineStage(
                key="relay",
                label="RELAY",
                state=state,
                detail=detail,
                timestamp=latest_delivery.timestamp,
            )
        )

    live_queue = [result.live_queue for result in results if result.queued and result.live_queue]
    latest_live_queue = _last(live_queue)
    if latest_live_queue:
        stages.append(
            PipelineStage(
                key="queue-live",
                label="QUEUE NOW",
                state="pending",
                detail=_detail(latest_live_queue),
                timestamp=latest_live_queue.timestamp,
            )
        )

    if latest_delivery:
        status = trace.status
        if status == "sent" and not latest_live_queue:
            stages.append(
                PipelineStage(
                    key="mailbox",
                    label="MAILBOX",
                    state="unknown",
                    detail="outside available evidence",
                )
            )

    return stages
