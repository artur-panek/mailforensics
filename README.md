# MailForensics

[![PyPI](https://img.shields.io/pypi/v/mailforensics.svg)](https://pypi.org/project/mailforensics/)
[![Python](https://img.shields.io/pypi/pyversions/mailforensics.svg)](https://pypi.org/project/mailforensics/)
[![CI](https://github.com/artur-panek/mailforensics/actions/workflows/ci.yml/badge.svg)](https://github.com/artur-panek/mailforensics/actions/workflows/ci.yml)

**`strace` for an email moving through your mail stack.**

MailForensics is an evidence-driven CLI for answering a deceptively simple question:

> **Where did this email actually go?**

It correlates application events, Postfix queue IDs, Message-IDs, Rspamd/milter activity, live queue state, handoffs, and relay results into one trace — then explains what the available evidence proves and where it stops.

```text
      ╭──────────────────╮
──────┤  MAILFORENSICS   ├──────▶
      ╰──────────────────╯
          trace the evidence,
          not the guess.
```

By [Artur Panek](https://artur.panek.tech/) · [Project page](https://artur.panek.tech/work/mailforensics/) · [Postfix evidence note](https://artur.panek.tech/notes/postfix-status-sent/) · [PyPI](https://pypi.org/project/mailforensics/) · [Releases](https://github.com/artur-panek/mailforensics/releases)

## Quick start

Install from PyPI:

```bash
python -m pip install mailforensics
```

See the tool without needing a mail server:

```bash
mailforensics demo
```

![MailForensics demo showing a deferred message traced through application, Postfix, Rspamd, relay, and live queue state](https://raw.githubusercontent.com/artur-panek/mailforensics/main/docs/assets/mailforensics-demo.webp)

Or inspect the local environment:

```bash
mailforensics doctor
```

Python 3.11+ is required. Live journald and Postfix queue inspection are intended for Linux; file, JSONL, and saved-queue analysis can be used independently.

## When it is useful

Use MailForensics when:

- an application says it submitted mail, but the message never seems to arrive;
- a message changes queue ID during a `queued as` handoff;
- a deferred message may or may not still be present in the live queue;
- Rspamd, a milter, Postfix, and the next relay each tell only part of the story;
- you need to know exactly what the logs prove — without turning missing evidence into a guessed root cause.

## What it does

MailForensics can:

- correlate **Message-ID**, Postfix queue IDs, `queued as` handoffs, and application `correlation_id` values;
- parse Postfix, Rspamd, milter, RFC 3164/5424, and journald-style evidence;
- inspect the current Postfix queue with `postqueue -j`;
- distinguish historical queue activity from **what is still queued now**;
- explain `sent`, `deferred`, `bounced`, filter rejection, and evidence gaps;
- show per-stage timing and the total observed trace window;
- emit human-readable, JSON, and self-contained HTML reports;
- load additional parsers through the `mailforensics.parsers` plugin entry point.

It is deliberately **not** an email-header analyzer and not an always-on monitoring platform.

## Example

```bash
mailforensics explain \
  --journal \
  --since '20 minutes ago' \
  --live-queue \
  --message-id '<invite-123@example.net>'
```

Example output:

```text
MAILFORENSICS EXPLAIN
query:   message-id=<invite-123@example.net>
status:  deferred

Pipeline
  ● APP       app/invite
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
  ◐ RELAY     deferred via mx.example.net
  │ 2.12m
  ▼
  ◐ QUEUE NOW still present in deferred queue

Assessment
  outcome:    queued-for-retry
  last stage: postfix-queue:deferred
  confidence: high
  Postfix deferred delivery and the message is still present in the live queue.
  Caveat: Postfix can retry later according to its queue schedule.
```

The distinction matters: an absent event is an **evidence boundary**, not automatic proof that a component failed.

## Commands

| Command | Purpose |
| --- | --- |
| `mailforensics explain` | Compact pipeline, latency, and assessment |
| `mailforensics trace` | Full normalized evidence timeline |
| `mailforensics demo` | Built-in zero-setup scenarios |
| `mailforensics doctor` | Check local capabilities and permissions |
| `mailforensics parsers` | List built-in and external parser adapters |
| `mailforensics completion` | Generate Bash, Zsh, or Fish completion |

The default CLI form also accepts trace options directly:

```bash
mailforensics --file /var/log/mail.log --queue 0DC461ACD87
```

## Evidence sources

A single run can combine multiple sources:

- classic syslog mail logs;
- ISO/journald-style logs;
- RFC 5424 syslog;
- direct `journalctl` collection;
- live or saved `postqueue -j` snapshots;
- Rspamd task/proxy logs;
- Postfix milter reject/discard events;
- structured JSONL application or gateway events;
- external parser plugins.

### Live queue state

```bash
mailforensics explain \
  --journal \
  --since '2 hours ago' \
  --live-queue \
  --queue 0DC461ACD87
```

Or inspect a saved snapshot:

```bash
postqueue -j > queue.jsonl

mailforensics explain \
  --queue-file queue.jsonl \
  --queue 0DC461ACD87
```

This lets MailForensics distinguish an old `deferred` event from a message that is **still present in the queue now**.

### Application and gateway events

Applications can join the trace without a custom parser by emitting JSON Lines:

```json
{"timestamp":"2026-10-04T12:00:00+00:00","source":"app","stage":"invite","kind":"submitted","correlation_id":"invite-42","message_id":"invite-123@example.net","recipient":"tester@example.com","status":"submitted"}
```

Then correlate it with infrastructure evidence:

```bash
mailforensics explain \
  --events app-mail-events.jsonl \
  --journal \
  --since '30 minutes ago' \
  --correlation-id invite-42
```

See [structured application events](https://github.com/artur-panek/mailforensics/blob/main/docs/structured-events.md) for the supported schema.

## Correlation model

MailForensics expands a trace through explicit identifiers rather than timestamp proximity:

```text
correlation_id
      │
      ▼
  Message-ID
      │
      ▼
Postfix queue ID ─── queued as ─── next queue ID
      │
      ├────────────── Rspamd / milter
      ├────────────── live postqueue
      └────────────── SMTP / LMTP / local delivery
```

Timestamp proximity alone is **never** enough to merge two messages.

See [correlation model](https://github.com/artur-panek/mailforensics/blob/main/docs/correlation.md) for details.

## Evidence semantics

MailForensics intentionally keeps a few boundaries explicit:

- Postfix `status=sent` means the configured next hop accepted the message.
- It does **not** prove inbox placement.
- A live queue entry proves the queue item existed at capture time, not why delivery is delayed.
- A later delivery result takes precedence over an earlier retry state.
- Rspamd rejection and Postfix milter rejection remain separate pieces of evidence.
- Missing evidence stays unknown instead of becoming a green check or a fabricated root cause.

## Reports and automation

Machine-readable JSON:

```bash
mailforensics explain \
  --journal \
  --since today \
  --queue ABC123 \
  --json
```

Self-contained HTML report:

```bash
mailforensics explain \
  --journal \
  --since '30 minutes ago' \
  --queue ABC123 \
  --html mailforensics-report.html
```

The HTML report contains no external JavaScript or assets.

## Demo fixtures

The repository includes small sanitized evidence sets for:

- delivered mail;
- deferred mail;
- filter rejection;
- a trace that stops before Postfix.

Example:

```bash
mailforensics explain \
  --file examples/fixtures/deferred/mail.log \
  --queue-file examples/fixtures/deferred/queue.jsonl \
  --queue 0DC461ACD87
```

## Parser plugins

Third-party packages can register parser adapters with:

```toml
[project.entry-points."mailforensics.parsers"]
my_gateway = "my_mailforensics_plugin:parse"
```

Parsers should emit `mailforensics.model.Event` objects and only attach identifiers that are supported by the source evidence.

See [parser plugin API](https://github.com/artur-panek/mailforensics/blob/main/docs/parser-plugins.md).

## Shell completion

```bash
mailforensics completion bash
mailforensics completion zsh
mailforensics completion fish
```

Convenience stubs are also available under `completions/`.

## Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | Trace found / command succeeded |
| `1` | No matching trace, or `doctor` found a hard failure |
| `2` | Invocation or runtime error |

## Development

```bash
git clone https://github.com/artur-panek/mailforensics.git
cd mailforensics

python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

ruff check .
pytest
```

CI also builds the wheel and source distribution, validates package metadata with `twine check --strict`, and installs the built wheel in a clean virtual environment.

See [CONTRIBUTING.md](https://github.com/artur-panek/mailforensics/blob/main/CONTRIBUTING.md) for contribution guidelines.

## Origin

MailForensics started during a rage-fix after debugging an invite path that was accepted by one layer and then seemed to disappear in the next.

The project grew around one rule:

> **Report what the evidence proves. Make uncertainty explicit.**

## License

MIT
