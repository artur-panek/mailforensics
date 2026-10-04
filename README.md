# mailtrace

**`strace` for an email moving through your mail stack.**

By [Artur Panek](https://artur.panek.tech/) · [Project page](https://artur.panek.tech/work/mailtrace/)

`mailtrace` reconstructs and explains an outbound message by correlating evidence from applications, Postfix, Rspamd/milters, live queues, handoffs, and relays.

It is intentionally not an email-header analyzer and not an always-on monitoring daemon. Point it at evidence when a message disappears and ask one question: **where did this mail go?**

> Early alpha. v0.3 is focused on local, evidence-driven mail forensics.

> Origin story: this started during a rage-fix session after one SMTP invite path refused to explain where the mail was disappearing.

## The useful command

```bash
mailtrace explain \
  --journal \
  --since '20 minutes ago' \
  --live-queue \
  --message-id '<invite-123@example.net>'
```

Example:

```text
MAILTRACE EXPLAIN
query:   message-id=<invite-123@example.net>
status:  deferred

Pipeline
  [ok] APP      korpoappka/invite
  [ok] POSTFIX  postfix/cleanup
  [ok] FILTER   Rspamd: no action
  [ok] QUEUE    queue 0DC461ACD87
  [..] RELAY    deferred via gmail-smtp-in.l.google.com
  [..] QUEUE NOW still present in deferred queue

Latency  total observed: 2.14m
  korpoappka:invite         -> postfix:cleanup              92ms
  postfix:cleanup           -> rspamd:filter               34ms
  rspamd:filter             -> postfix:qmgr                11ms
  postfix:qmgr              -> postfix:smtp               842ms
  postfix:smtp              -> postfix-queue:deferred      2.12m

Assessment
  outcome:    queued-for-retry
  last stage: postfix-queue:deferred
  confidence: high
  Postfix deferred delivery and the message is still present in the live queue.
  Caveat: Postfix can retry later according to its queue schedule.
```

The output is deliberately conservative. If the evidence ends, `mailtrace` says where it ends instead of inventing a failure.

## Install from source

```bash
git clone https://github.com/artur-panek/mailtrace.git
cd mailtrace
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Python 3.11+ is required.

## Commands

### Trace the full evidence timeline

Legacy syntax remains supported:

```bash
mailtrace --journal --since '10 minutes ago' --message-id '<3927a888@example.net>'
```

The explicit form is equivalent:

```bash
mailtrace trace --journal --since '10 minutes ago' --message-id '<3927a888@example.net>'
```

### Explain the pipeline

```bash
mailtrace explain --file /var/log/mail.log --queue 0DC461ACD87
```

This gives a compact pipeline, latency breakdown, and evidence-based assessment.

### Inspect the current Postfix queue

Add `postqueue -j` as live evidence:

```bash
mailtrace explain \
  --journal \
  --since '2 hours ago' \
  --live-queue \
  --queue 0DC461ACD87
```

Or analyze a saved queue snapshot:

```bash
postqueue -j > queue.jsonl
mailtrace explain --queue-file queue.jsonl --queue 0DC461ACD87
```

If a deferred message still exists in the queue, the assessment can distinguish **old deferred evidence** from **currently queued for retry**.

### Correlate application/gateway events

Custom services can emit tiny JSONL events:

```json
{"timestamp":"2026-10-04T04:36:47+00:00","source":"korpoappka","stage":"invite","kind":"submitted","correlation_id":"invite-42","message_id":"3927a888@example.net","recipient":"tester@example.com","status":"submitted","message":"alpha invite handed to mail gateway"}
```

Then:

```bash
mailtrace explain \
  --events app-mail-events.jsonl \
  --journal \
  --since '30 minutes ago' \
  --correlation-id invite-42
```

The strongest bridge is an application `correlation_id` plus a Message-ID or queue ID.

### Query by recipient

```bash
mailtrace explain --journal --since today --to tester@example.com
```

Recipient lookup intentionally selects the **latest matching message** in the supplied evidence window before expanding by Message-ID/queue ID. It does not merge every email sent to that address.

### Export JSON

```bash
mailtrace explain --journal --since today --queue ABC123 --json
```

JSON includes the assessment, pipeline, latency spans, identifiers, and raw normalized events.

### Generate a self-contained HTML report

```bash
mailtrace explain \
  --journal \
  --since '30 minutes ago' \
  --queue ABC123 \
  --html mailtrace-report.html
```

The report contains no external JavaScript or assets.

### List parsers

```bash
mailtrace parsers
```

Built-in parsers currently cover Postfix and Rspamd. Third-party packages can register parser adapters through the `mailtrace.parsers` Python entry-point group.

See [docs/parser-plugins.md](docs/parser-plugins.md).

## Inputs

`mailtrace` can combine all of these in one run:

- classic syslog mail logs
- ISO/journald-style syslog
- RFC 5424 syslog
- direct `journalctl` collection
- Postfix `postqueue -j` snapshots
- Rspamd task/proxy logs
- Postfix milter reject/discard events
- structured JSONL application/gateway events
- external parser plugins

## Correlation model

The correlation graph expands through strong identifiers:

```text
correlation_id
      │
      ▼
  Message-ID
      │
      ▼
Postfix queue ID ─── queued as ─── next queue ID
      │
      ├────────────── Rspamd
      │
      ├────────────── live postqueue
      │
      └────────────── SMTP/LMTP/local delivery
```

Timestamp proximity alone is **not** a correlation key.

See [docs/correlation.md](docs/correlation.md).

## Evidence semantics

A few distinctions are intentionally explicit:

- Postfix `status=sent` means the configured next hop accepted the message.
- It does **not** prove inbox placement.
- A live queue entry proves the queue item exists at capture time, but not why delivery is delayed.
- Missing events are an evidence boundary, not proof that a service failed.
- An earlier `deferred` followed by a later `sent` is treated as successful next-hop acceptance.
- Rspamd reject evidence and Postfix milter-reject evidence are reported separately.

## Structured application events

Applications and gateways can join the trace without a custom parser by writing JSON Lines.

See [docs/structured-events.md](docs/structured-events.md).

## Parser plugins

A parser package can register an entry point:

```toml
[project.entry-points."mailtrace.parsers"]
amavis = "mailtrace_amavis:parse"
```

The callable receives the same log lines as the built-in parsers and returns `mailtrace.model.Event` objects.

Use `--no-plugins` when you want a run limited to built-in parsers.

## What v0.3 ships

- [x] Postfix trace correlation
- [x] Message-ID and queue-ID handoffs
- [x] direct journald input
- [x] Rspamd correlation
- [x] Postfix milter reject/discard evidence
- [x] structured application/gateway events
- [x] RFC 5424 ingestion
- [x] live Postfix queue inspection
- [x] per-event latency breakdown
- [x] compact `mailtrace explain` pipeline
- [x] evidence-based assessment
- [x] parser plugin entry points
- [x] JSON output
- [x] self-contained HTML reports

## Next

Useful extensions that still fit the project:

- Exim/OpenSMTPD adapters
- DSN/bounce-message ingestion
- better queue-age and retry-schedule explanation
- optional Graphviz/DOT export
- sanitized diagnostic bundles for sharing traces
- more real-world Rspamd/milter fixtures

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## License

MIT
