# mailforensics

**`strace` for an email moving through your mail stack.**

By [Artur Panek](https://artur.panek.tech/) · [Project page](https://artur.panek.tech/work/mailforensics/)

`mailforensics` reconstructs and explains an outbound message by correlating evidence from applications, Postfix, Rspamd/milters, live queues, handoffs, and relays.

It is intentionally not an email-header analyzer and not an always-on monitoring daemon. Point it at evidence when a message disappears and ask one question: **where did this mail go?**

> Early alpha. v0.5 is focused on local, evidence-driven mail forensics.

> Origin story: this started during a rage-fix session after one SMTP invite path refused to explain where the mail was disappearing.


## Forensic terminal identity

The full banner appears in root help and demos, not on every normal trace:

```text
      ╭──────────────╮
──────┤  MAILFORENSICS   ├──────▶
      ╰──────────────╯
          trace the evidence,
          not the guess.
```

Interactive output uses terminal color only when appropriate. `NO_COLOR` is respected, and `--color auto|always|never` plus `--ascii` make the behavior explicit.

## The useful command

```bash
mailforensics explain \
  --journal \
  --since '20 minutes ago' \
  --live-queue \
  --message-id '<invite-123@example.net>'
```

Example:

```text
MAILFORENSICS EXPLAIN
query:   message-id=<invite-123@example.net>
status:  deferred

Pipeline
  ● APP       korpoappka/invite
  │ 92ms
  ▼
  ● POSTFIX   postfix/cleanup
  │ 34ms
  ▼
  ● FILTER    Rspamd: no action
  │ 11ms
  ▼
  ● QUEUE     queue 0DC461ACD87
  │ 842ms
  ▼
  ◐ RELAY     deferred via gmail-smtp-in.l.google.com
  │ 2.12m
  ▼
  ◐ QUEUE NOW still present in deferred queue

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

The output is deliberately conservative. If the evidence ends, `mailforensics` says where it ends instead of inventing a failure.

## Install

After the first PyPI release:

```bash
python -m pip install mailforensics
```

Then:

```bash
mailforensics demo
mailforensics doctor
```

Until the first PyPI release, install from source:

## Install from source

```bash
git clone https://github.com/artur-panek/mailforensics.git
cd mailforensics
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Python 3.11+ is required.

## Zero-setup demo

```bash
mailforensics demo
mailforensics demo delivered
mailforensics demo rejected
mailforensics demo gap
```

The default demo is a deferred message still visible in the live queue. It requires no Postfix installation or log files, which makes it useful for evaluating the project from a fresh clone.

## Environment doctor

```bash
mailforensics doctor
```

The doctor checks Python, `journalctl`, journal readability, `postqueue`, queue access, default mail logs, and parser plugins. Missing optional local capabilities are warnings rather than fake failures.

## Shell completion

Print a completion script:

```bash
mailforensics completion bash
mailforensics completion zsh
mailforensics completion fish
```

Repository convenience stubs also live under `completions/`.

## Example fixtures

Four small evidence sets live under `examples/fixtures/`:

- `delivered/`
- `deferred/`
- `rejected/`
- `gap/`

For example:

```bash
mailforensics explain \
  --file examples/fixtures/deferred/mail.log \
  --queue-file examples/fixtures/deferred/queue.jsonl \
  --queue 0DC461ACD87
```

## Exit codes

- `0`: trace found / command succeeded
- `1`: no matching trace, or doctor found a hard failure
- `2`: invocation or runtime error

## Commands

### Trace the full evidence timeline

Legacy syntax remains supported:

```bash
mailforensics --journal --since '10 minutes ago' --message-id '<3927a888@example.net>'
```

The explicit form is equivalent:

```bash
mailforensics trace --journal --since '10 minutes ago' --message-id '<3927a888@example.net>'
```

### Explain the pipeline

```bash
mailforensics explain --file /var/log/mail.log --queue 0DC461ACD87
```

This gives a compact pipeline, latency breakdown, and evidence-based assessment.

### Inspect the current Postfix queue

Add `postqueue -j` as live evidence:

```bash
mailforensics explain \
  --journal \
  --since '2 hours ago' \
  --live-queue \
  --queue 0DC461ACD87
```

Or analyze a saved queue snapshot:

```bash
postqueue -j > queue.jsonl
mailforensics explain --queue-file queue.jsonl --queue 0DC461ACD87
```

If a deferred message still exists in the queue, the assessment can distinguish **old deferred evidence** from **currently queued for retry**.

### Correlate application/gateway events

Custom services can emit tiny JSONL events:

```json
{"timestamp":"2026-10-04T04:36:47+00:00","source":"korpoappka","stage":"invite","kind":"submitted","correlation_id":"invite-42","message_id":"3927a888@example.net","recipient":"tester@example.com","status":"submitted","message":"alpha invite handed to mail gateway"}
```

Then:

```bash
mailforensics explain \
  --events app-mail-events.jsonl \
  --journal \
  --since '30 minutes ago' \
  --correlation-id invite-42
```

The strongest bridge is an application `correlation_id` plus a Message-ID or queue ID.

### Query by recipient

```bash
mailforensics explain --journal --since today --to tester@example.com
```

Recipient lookup intentionally selects the **latest matching message** in the supplied evidence window before expanding by Message-ID/queue ID. It does not merge every email sent to that address.

### Export JSON

```bash
mailforensics explain --journal --since today --queue ABC123 --json
```

JSON includes the assessment, pipeline, latency spans, identifiers, and raw normalized events.

### Generate a self-contained HTML report

```bash
mailforensics explain \
  --journal \
  --since '30 minutes ago' \
  --queue ABC123 \
  --html mailforensics-report.html
```

The report contains no external JavaScript or assets.

### List parsers

```bash
mailforensics parsers
```

Built-in parsers currently cover Postfix and Rspamd. Third-party packages can register parser adapters through the `mailforensics.parsers` Python entry-point group.

See [docs/parser-plugins.md](docs/parser-plugins.md).

## Inputs

`mailforensics` can combine all of these in one run:

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
[project.entry-points."mailforensics.parsers"]
amavis = "mailforensics_amavis:parse"
```

The callable receives the same log lines as the built-in parsers and returns `mailforensics.model.Event` objects.

Use `--no-plugins` when you want a run limited to built-in parsers.

## What v0.5 ships

- [x] Postfix trace correlation
- [x] Message-ID and queue-ID handoffs
- [x] direct journald input
- [x] Rspamd correlation
- [x] Postfix milter reject/discard evidence
- [x] structured application/gateway events
- [x] RFC 5424 ingestion
- [x] live Postfix queue inspection
- [x] per-event latency breakdown
- [x] compact `mailforensics explain` pipeline
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
