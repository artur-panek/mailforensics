from __future__ import annotations

from .model import Assessment, Event, Trace


def _stage(event: Event) -> str:
    return f"{event.source}:{event.component}"


def assess(trace: Trace) -> Assessment:
    if not trace.events:
        return Assessment(
            outcome="no-evidence",
            last_confirmed_stage="-",
            confidence="high",
            summary="No matching events were found in the supplied evidence.",
            caveat="This says nothing about systems whose logs were not provided.",
        )

    last = trace.events[-1]
    delivery_events = [
        event
        for event in trace.events
        if event.source == "postfix"
        and event.kind == "delivery"
        and event.details.get("status")
    ]
    statuses = [str(event.details["status"]).casefold() for event in delivery_events]

    if "bounced" in statuses:
        event = next(
            event
            for event in reversed(delivery_events)
            if str(event.details["status"]).casefold() == "bounced"
        )
        return Assessment(
            outcome="bounced",
            last_confirmed_stage=_stage(event),
            confidence="high",
            summary="Postfix recorded a bounce for the correlated message.",
        )

    if "deferred" in statuses:
        event = next(
            event
            for event in reversed(delivery_events)
            if str(event.details["status"]).casefold() == "deferred"
        )
        return Assessment(
            outcome="deferred",
            last_confirmed_stage=_stage(event),
            confidence="high",
            summary="Postfix deferred delivery; the supplied trace contains no later successful delivery.",
            caveat="Postfix may retry after the end of the supplied log window.",
        )

    if "sent" in statuses:
        event = next(
            event
            for event in reversed(delivery_events)
            if str(event.details["status"]).casefold() == "sent"
        )
        return Assessment(
            outcome="accepted-by-next-hop",
            last_confirmed_stage=_stage(event),
            confidence="high",
            summary="Postfix recorded status=sent: the next SMTP/LMTP/local hop accepted the message.",
            caveat="This is not proof that the message reached a recipient's inbox.",
        )

    rspamd_events = [event for event in trace.events if event.source == "rspamd"]
    postfix_queued = [
        event
        for event in trace.events
        if event.source == "postfix" and event.kind == "queued"
    ]
    postfix_seen = [event for event in trace.events if event.source == "postfix"]
    non_postfix = [event for event in trace.events if event.source != "postfix"]

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
