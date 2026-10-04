from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .diagnose import assess
from .latency import latency_spans, total_observed_ms
from .model import Event, Trace
from .pipeline import build_pipeline

STATE_MARKERS = {
    "confirmed": "[ok]",
    "pending": "[..]",
    "failed": "[!!]",
    "rejected": "[xx]",
    "unknown": "[??]",
}


def _duration(milliseconds: int) -> str:
    if milliseconds < 1000:
        return f"{milliseconds}ms"
    if milliseconds < 60_000:
        return f"{milliseconds / 1000:.3f}s"
    return f"{milliseconds / 60_000:.2f}m"


def _event_summary(event: Event) -> str:
    bits: list[str] = []
    if message_id := event.details.get("message_id"):
        bits.append(f"message-id=<{message_id}>")
    if sender := event.details.get("sender"):
        bits.append(f"from=<{sender}>")
    if recipient := event.details.get("recipient"):
        bits.append(f"to=<{recipient}>")
    if action := event.details.get("action"):
        bits.append(f"action={action}")
    if relay := event.details.get("relay"):
        bits.append(f"relay={relay}")
    if status := event.details.get("status"):
        bits.append(f"status={status}")
    if dsn := event.details.get("dsn"):
        bits.append(f"dsn={dsn}")
    if delay := event.details.get("delay"):
        bits.append(f"delay={delay}s")
    if linked := event.details.get("linked_queue_id"):
        bits.append(f"queued-as={linked}")
    if correlation := event.details.get("correlation_id"):
        bits.append(f"correlation={correlation}")
    if queue_name := event.details.get("queue_name"):
        bits.append(f"queue={queue_name}")
    return "  ".join(bits) if bits else event.message


def _assessment_lines(trace: Trace) -> list[str]:
    assessment = assess(trace)
    lines = [
        "Assessment",
        f"  outcome:    {assessment.outcome}",
        f"  last stage: {assessment.last_confirmed_stage}",
        f"  confidence: {assessment.confidence}",
        f"  {assessment.summary}",
    ]
    if assessment.caveat:
        lines.append(f"  Caveat: {assessment.caveat}")
    return lines


def _latency_lines(trace: Trace) -> list[str]:
    spans = latency_spans(trace)
    lines = [f"Latency  total observed: {_duration(total_observed_ms(trace))}"]
    if not spans:
        lines.append("  not enough events for a breakdown")
        return lines

    for span in spans:
        lines.append(
            f"  {span.from_stage:<24} -> {span.to_stage:<24} "
            f"{_duration(span.duration_ms):>9}"
        )
    return lines


def render_text(trace: Trace) -> str:
    lines = [
        "MAILTRACE",
        f"query:        {trace.query}",
        f"status:       {trace.status}",
        f"queues:       {', '.join(sorted(trace.queue_ids)) or '-'}",
        f"message-ids:  {', '.join(sorted(trace.message_ids)) or '-'}",
        "",
    ]

    if not trace.events:
        lines.append("No matching events found.")
    else:
        base = trace.events[0].timestamp
        for event in trace.events:
            delta_ms = int((event.timestamp - base).total_seconds() * 1000)
            stamp = event.timestamp.isoformat(timespec="milliseconds")
            queue = event.queue_id or "-"
            component = f"{event.source}/{event.component}"
            lines.append(
                f"{stamp}  +{delta_ms:>6}ms  {queue:<14} "
                f"{component:<20} {_event_summary(event)}"
            )

    lines.extend(["", *_latency_lines(trace), "", *_assessment_lines(trace)])
    return "\n".join(lines)


def render_explain(trace: Trace) -> str:
    lines = [
        "MAILTRACE EXPLAIN",
        f"query:   {trace.query}",
        f"status:  {trace.status}",
        "",
        "Pipeline",
    ]
    pipeline = build_pipeline(trace)
    if pipeline:
        for stage in pipeline:
            marker = STATE_MARKERS.get(stage.state, "[??]")
            lines.append(f"  {marker} {stage.label:<8} {stage.detail}")
    else:
        lines.append("  [??] no pipeline stages confirmed")

    lines.extend(["", *_latency_lines(trace), "", *_assessment_lines(trace)])
    lines.extend(
        [
            "",
            f"Evidence: {len(trace.events)} event(s), "
            f"{len(trace.queue_ids)} queue id(s), "
            f"{len(trace.message_ids)} message id(s).",
        ]
    )
    return "\n".join(lines)


def _event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "timestamp": event.timestamp.isoformat(),
        "source": event.source,
        "host": event.host,
        "component": event.component,
        "queue_id": event.queue_id,
        "kind": event.kind,
        "message": event.message,
        "details": event.details,
    }


def render_json(trace: Trace) -> str:
    assessment = assess(trace)
    payload = {
        "query": trace.query,
        "status": trace.status,
        "queue_ids": sorted(trace.queue_ids),
        "message_ids": sorted(trace.message_ids),
        "correlation_ids": sorted(trace.correlation_ids),
        "assessment": asdict(assessment),
        "pipeline": [
            {
                **asdict(stage),
                "timestamp": stage.timestamp.isoformat() if stage.timestamp else None,
            }
            for stage in build_pipeline(trace)
        ],
        "latency": {
            "total_observed_ms": total_observed_ms(trace),
            "spans": [
                {
                    **asdict(span),
                    "from_timestamp": span.from_timestamp.isoformat(),
                    "to_timestamp": span.to_timestamp.isoformat(),
                }
                for span in latency_spans(trace)
            ],
        },
        "events": [_event_to_dict(event) for event in trace.events],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
