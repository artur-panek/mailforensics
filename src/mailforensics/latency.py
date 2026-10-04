from __future__ import annotations

from .model import Event, LatencySpan, Trace


def stage_name(event: Event) -> str:
    return f"{event.source}:{event.component}"


def latency_spans(trace: Trace) -> list[LatencySpan]:
    events = sorted(trace.events, key=lambda event: event.timestamp)
    spans: list[LatencySpan] = []

    for previous, current in zip(events, events[1:], strict=False):
        milliseconds = max(
            0,
            int((current.timestamp - previous.timestamp).total_seconds() * 1000),
        )
        spans.append(
            LatencySpan(
                from_stage=stage_name(previous),
                to_stage=stage_name(current),
                duration_ms=milliseconds,
                from_timestamp=previous.timestamp,
                to_timestamp=current.timestamp,
            )
        )

    return spans


def total_observed_ms(trace: Trace) -> int:
    if len(trace.events) < 2:
        return 0
    events = sorted(trace.events, key=lambda event: event.timestamp)
    return max(
        0,
        int((events[-1].timestamp - events[0].timestamp).total_seconds() * 1000),
    )
