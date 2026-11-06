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

## Queue identity and ambiguity

Queue IDs are not globally unique. [Postfix documents](https://www.postfix.org/postqueue.1.html) that different instances may use the same ID, and an instance may reuse an ID over time.

Native Postfix and postqueue events therefore match ordinary queue IDs only within their recorded host. Application and filter hosts identify their producers, which need not own the queue; their queue references, and explicit `queued as` handoffs, resolve only when the supplied native evidence identifies at most one target host. Saved `--queue-file` snapshots have unknown host (`-`), because their JSON does not identify the source host; the analyst's machine is not assumed to own them. Live `--live-queue` snapshots retain their local host. Report fields are unchanged.

A bare `--queue` matching multiple hosts is an error. Use `--message-id` or the latest-recipient `--to` selector to identify a trace, or narrow the supplied logs. An ambiguous application reference or handoff also causes an error rather than choosing a host. If a selected host/queue has conflicting Message-IDs, narrow the evidence window: the tool does not assign events to reused queue IDs by timestamp proximity. These errors use the existing runtime-error exit code 2 and do not emit a success report.

Host names are compared exactly; short names and fully qualified names are not guessed to be aliases. Supply consistent host identities, including for queue snapshots. Instances sharing a recorded host, and reuse without distinguishing Message-IDs, cannot always be separated from this evidence. Message-ID and application correlation-ID bridges retain their existing semantics: they are supplied identifiers, not authentication or proof of global uniqueness.

## What is intentionally not a correlation key

Timestamp proximity is not currently sufficient by itself. Two messages sent close together should not be merged merely because they happened in the same second.

Recipient address can seed a trace, but once initial matching events are found the graph expands through stronger identifiers.

## Recipient outcomes

Postfix `smtp`, `lmtp`, `local`, `pipe`, and `virtual` records with a delivery status contribute to recipient outcomes. Activity without a delivery status remains separate evidence.

The timeline keeps the complete correlated message. A `--to` query limits its delivery assessment to that recipient, so a successful transfer for another recipient cannot replace a deferred result.

For message, queue, and correlation-ID queries, delivery results are tracked separately for each recipient. The status is `mixed` when those results differ, including a recipient whose outcome is still unknown. Queue snapshots apply to the recipients listed in that snapshot. A later delivery result supersedes an older queue observation.

JSON reports include the selected `recipient` (or `null`) and `recipient_results`, with each recipient's latest delivery and current queue evidence. The original events remain in `events`.

## Evidence boundaries

An assessment describes the last confirmed stage in the supplied evidence. It does not claim that an absent event proves a component failed.

For example:

- application event, no Postfix event → evidence gap before Postfix
- Postfix queue event, no delivery result → trace stops after queueing
- Rspamd event, no later delivery result → trace stops after filtering
- Postfix `status=sent` → next hop accepted the message, not proof of inbox placement
