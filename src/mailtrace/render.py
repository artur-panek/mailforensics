from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .console import bold, dim, state
from .diagnose import assess
from .latency import latency_spans, total_observed_ms
from .model import Event, Trace
from .pipeline import build_pipeline


def _duration(milliseconds: int) -> str:
    if milliseconds < 1000:
        return f"{milliseconds}ms"
    if milliseconds < 60_000:
        return f"{milliseconds / 1000:.3f}s"
    return f"{milliseconds / 60_000:.2f}m"


def _event_summary(event: Event) -> str:
    bits: list[str] = []
    fields = (
        ("message_id", "message-id"),
        ("sender", "from"),
        ("recipient", "to"),
        ("action", "action"),
        ("relay", "relay"),
        ("status", "status"),
        ("dsn", "dsn"),
        ("delay", "delay"),
        ("linked_queue_id", "queued-as"),
        ("correlation_id", "correlation"),
        ("queue_name", "queue"),
    )
    for key, label in fields:
        if value := event.details.get(key):
            if key in {"message_id", "sender", "recipient"}:
                bits.append(f"{label}=<{value}>")
            elif key == "delay":
                bits.append(f"delay={value}s")
            else:
                bits.append(f"{label}={value}")
    return "  ".join(bits) if bits else event.message


def _assessment_lines(trace: Trace, *, color: bool = False) -> list[str]:
    assessment = assess(trace)
    outcome = assessment.outcome
    tone = "confirmed"
    if any(token in outcome for token in ("reject", "bounce", "fail")):
        tone = "failed"
    elif any(token in outcome for token in ("queue", "defer", "pending")):
        tone = "pending"

    lines = [
        bold("Assessment", enabled=color),
        f"  outcome:    {state(outcome, tone, enabled=color)}",
        f"  last stage: {assessment.last_confirmed_stage}",
        f"  confidence: {assessment.confidence}",
        f"  {assessment.summary}",
    ]
    if assessment.caveat:
        lines.append(dim(f"  Caveat: {assessment.caveat}", enabled=color))
    return lines


def _latency_lines(trace: Trace, *, color: bool = False) -> list[str]:
    spans = latency_spans(trace)
    lines = [
        bold(
            f"Latency  total observed: {_duration(total_observed_ms(trace))}",
            enabled=color,
        )
    ]
    if not spans:
        return [*lines, "  not enough events for a breakdown"]

    for span in spans:
        lines.append(
            f"  {span.from_stage:<24} -> {span.to_stage:<24} "
            f"{_duration(span.duration_ms):>9}"
        )
    return lines


def _pipeline_lines(
    trace: Trace,
    *,
    color: bool = False,
    ascii_only: bool = False,
) -> list[str]:
    stages = build_pipeline(trace)
    if not stages:
        return ["  ? no pipeline stages confirmed"]

    icons_unicode = {
        "confirmed": "●",
        "pending": "◐",
        "failed": "✕",
        "rejected": "✕",
        "unknown": "○",
    }
    icons_ascii = {
        "confirmed": "*",
        "pending": "~",
        "failed": "x",
        "rejected": "x",
        "unknown": "?",
    }
    icons = icons_ascii if ascii_only else icons_unicode
    vertical = "|" if ascii_only else "│"
    arrow = "v" if ascii_only else "▼"

    lines: list[str] = []
    for index, stage in enumerate(stages):
        icon = state(icons.get(stage.state, "?"), stage.state, enabled=color)
        label = bold(f"{stage.label:<9}", enabled=color)
        lines.append(f"  {icon} {label} {stage.detail}")

        if index < len(stages) - 1:
            next_stage = stages[index + 1]
            delta = ""
            if stage.timestamp and next_stage.timestamp:
                milliseconds = max(
                    0,
                    int((next_stage.timestamp - stage.timestamp).total_seconds() * 1000),
                )
                delta = f" {_duration(milliseconds)}"
            lines.append(f"  {vertical}{delta}")
            lines.append(f"  {arrow}")

    return lines


def render_text(trace: Trace, *, color: bool = False) -> str:
    lines = [
        bold("MAILTRACE", enabled=color),
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
            component = f"{event.source}/{event.component}"
            lines.append(
                f"{event.timestamp.isoformat(timespec='milliseconds')}  "
                f"+{delta_ms:>6}ms  {(event.queue_id or '-'):<14} "
                f"{component:<20} {_event_summary(event)}"
            )

    lines.extend(
        [
            "",
            *_latency_lines(trace, color=color),
            "",
            *_assessment_lines(trace, color=color),
        ]
    )
    return "\n".join(lines)


def render_explain(
    trace: Trace,
    *,
    color: bool = False,
    ascii_only: bool = False,
) -> str:
    lines = [
        bold("MAILTRACE EXPLAIN", enabled=color),
        f"query:   {trace.query}",
        f"status:  {trace.status}",
        "",
        bold("Pipeline", enabled=color),
        *_pipeline_lines(trace, color=color, ascii_only=ascii_only),
        "",
        *_latency_lines(trace, color=color),
        "",
        *_assessment_lines(trace, color=color),
        "",
        (
            f"Evidence: {len(trace.events)} event(s), "
            f"{len(trace.queue_ids)} queue id(s), "
            f"{len(trace.message_ids)} message id(s)."
        ),
    ]
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
