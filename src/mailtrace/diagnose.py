from __future__ import annotations

from .model import Assessment, Event, Trace


def _stage(event: Event) -> str:
    return f"{event.source}:{event.component}"


def _latest(events: list[Event]) -> Event | None:
    return max(events, key=lambda event: event.timestamp) if events else None


def assess(trace: Trace) -> Assessment:
    if not trace.events:
        return Assessment(
            outcome="no-evidence",
            last_confirmed_stage="-",
            confidence="high",
            summary="No matching events were found in the supplied evidence.",
            caveat="This says nothing about systems whose logs were not provided.",
        )

    events = sorted(trace.events, key=lambda event: event.timestamp)
    last = events[-1]
    delivery_events = [
        event
        for event in events
        if event.source == "postfix"
        and event.kind == "delivery"
        and event.details.get("status")
    ]
    latest_delivery = _latest(delivery_events)

    live_queue = _latest([event for event in events if event.kind == "live-queue"])

    if latest_delivery:
        status = str(latest_delivery.details["status"]).casefold()

        if status == "sent":
            return Assessment(
                outcome="accepted-by-next-hop",
                last_confirmed_stage=_stage(latest_delivery),
                confidence="high",
                summary="Postfix recorded status=sent: the next SMTP/LMTP/local hop accepted the message.",
                caveat="This is not proof that the message reached a recipient's inbox.",
            )

        if status == "bounced":
            return Assessment(
                outcome="bounced",
                last_confirmed_stage=_stage(latest_delivery),
                confidence="high",
                summary="The latest Postfix delivery result is a bounce.",
            )

        if status == "deferred":
            if live_queue and live_queue.timestamp >= latest_delivery.timestamp:
                return Assessment(
                    outcome="queued-for-retry",
                    last_confirmed_stage=_stage(live_queue),
                    confidence="high",
                    summary="Postfix deferred delivery and the message is still present in the live queue.",
                    caveat="Postfix can retry later according to its queue schedule.",
                )
            return Assessment(
                outcome="deferred",
                last_confirmed_stage=_stage(latest_delivery),
                confidence="high",
                summary="The latest Postfix delivery result is deferred.",
                caveat="Postfix may retry after the end of the supplied evidence window.",
            )

    milter_rejections = [
        event
        for event in events
        if event.kind in {"milter-reject", "milter-discard"}
    ]
    if event := _latest(milter_rejections):
        action = event.details.get("milter_action", "reject")
        return Assessment(
            outcome=f"milter-{action}",
            last_confirmed_stage=_stage(event),
            confidence="high",
            summary=f"Postfix recorded a milter {action} decision.",
        )

    rspamd_events = [event for event in events if event.source == "rspamd"]
    rejected_by_filter = [
        event
        for event in rspamd_events
        if str(event.details.get("action", "")).casefold()
        in {"reject", "soft reject", "discard"}
    ]
    if event := _latest(rejected_by_filter):
        action = str(event.details.get("action", "reject"))
        return Assessment(
            outcome="rejected-by-filter",
            last_confirmed_stage=_stage(event),
            confidence="high",
            summary=f"Rspamd recorded action={action} for the correlated message.",
            caveat="A matching SMTP/milter rejection would provide stronger end-to-end evidence.",
        )

    if live_queue:
        return Assessment(
            outcome="queued-live",
            last_confirmed_stage=_stage(live_queue),
            confidence="high",
            summary="The correlated message is currently present in the Postfix queue.",
            caveat="Queue presence does not by itself explain why delivery has not completed.",
        )

    postfix_queued = [
        event
        for event in events
        if event.source == "postfix" and event.kind == "queued"
    ]
    postfix_seen = [event for event in events if event.source == "postfix"]
    non_postfix = [event for event in events if event.source != "postfix"]

    if rspamd_events:
        event = rspamd_events[-1]
        return Assessment(
            outcome="trace-stops-after-filter",
            last_confirmed_stage=_stage(event),
            confidence="medium",
            summary="Rspamd processed the correlated message, but no later Postfix delivery result appears in the supplied evidence.",
            caveat="The message may continue outside the supplied log window or in logs that were not provided.",
        )

    if postfix_queued:
        event = postfix_queued[-1]
        return Assessment(
            outcome="trace-stops-after-queue",
            last_confirmed_stage=_stage(event),
            confidence="medium",
            summary="Postfix queued the message, but no later delivery result appears in the supplied evidence.",
            caveat="The message may still be queued, retried later, or continue outside the supplied log window.",
        )

    if postfix_seen:
        event = postfix_seen[-1]
        return Assessment(
            outcome="trace-stops-inside-postfix",
            last_confirmed_stage=_stage(event),
            confidence="medium",
            summary="Postfix saw the correlated message, but the supplied evidence does not show it reaching the queue manager or a delivery result.",
            caveat="Check whether the relevant Postfix component logs are included.",
        )

    if non_postfix:
        return Assessment(
            outcome="gap-before-postfix",
            last_confirmed_stage=_stage(last),
            confidence="medium",
            summary="Application/gateway evidence exists, but no correlated Postfix event appears in the supplied evidence.",
            caveat="The gap may be between the application and Postfix, or the Postfix logs may simply be missing.",
        )

    return Assessment(
        outcome="unknown",
        last_confirmed_stage=_stage(last),
        confidence="low",
        summary="The trace contains events, but they are not enough to determine a delivery outcome.",
    )
