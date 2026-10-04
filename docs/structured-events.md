# Structured application events

Applications and custom mail gateways can participate in `mailtrace` without a bespoke parser by emitting JSON Lines.

Each line is one JSON object.

## Minimal example

```json
{"timestamp":"2026-10-04T04:36:47+00:00","source":"korpoappka","stage":"invite","correlation_id":"invite-42","message_id":"3927a888@example.net","recipient":"tester@example.com","status":"submitted"}
```

## Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `timestamp` | yes | ISO 8601 timestamp |
| `source` | no | application/service name; defaults to `application` |
| `host` | no | host that produced the event |
| `stage` / `component` | no | pipeline stage |
| `kind` | no | semantic event kind |
| `message` | no | human-readable event text |
| `message_id` | no | RFC Message-ID, angle brackets optional |
| `queue_id` | no | known mail queue identifier |
| `linked_queue_id` | no | queue ID created by a handoff |
| `correlation_id` | no | application-level request/job identifier |
| `sender` / `from` | no | sender address |
| `recipient` / `to` | no | recipient address |
| `status` | no | service-specific status |
| `relay` | no | next relay if known |
| `details` | no | free-form JSON object preserved in the trace |

The best bridge event contains an application `correlation_id` plus a Message-ID or queue ID. That connects business/application context to the mail infrastructure without guessing from time or recipient alone.
