# Correlation model

`mailforensics` treats logs as evidence and correlates events by identifiers rather than by timestamp proximity alone.

## Identifiers

The current graph can expand through:

- RFC Message-ID
- Postfix queue ID
- Postfix `queued as <id>` handoffs
- application-defined `correlation_id`

An event joins a trace when it shares at least one known identifier. Its other identifiers are then added to the known set and correlation continues until no new events can be reached.

This allows a structured application event containing both `correlation_id` and `message_id` to bridge an application request to a Postfix cleanup event. A Rspamd event containing the same Message-ID or queue ID can then join the same trace.

## What is intentionally not a correlation key

Timestamp proximity is not currently sufficient by itself. Two messages sent close together should not be merged merely because they happened in the same second.

Recipient address can seed a trace, but once initial matching events are found the graph expands through stronger identifiers.

## Evidence boundaries

An assessment describes the last confirmed stage in the supplied evidence. It does not claim that an absent event proves a component failed.

For example:

- application event, no Postfix event → evidence gap before Postfix
- Postfix queue event, no delivery result → trace stops after queueing
- Rspamd event, no later delivery result → trace stops after filtering
- Postfix `status=sent` → next hop accepted the message, not proof of inbox placement
