# mailtrace

**`strace` for an email moving through your mail stack.**

By [Artur Panek](https://artur.panek.tech/) · [Project page](https://artur.panek.tech/work/mailtrace/)

`mailtrace` reconstructs the journey of an outbound message by correlating evidence from applications, Postfix, Rspamd, queue handoffs, and relays.

It is intentionally not an email-header analyzer and not a monitoring daemon. Point it at logs when a message disappears and ask one question: **where did this mail go?**

> Early alpha. v0.2 focuses on local forensic correlation rather than always-on monitoring.

> Origin story: this started during a rage-fix session after one SMTP invite path refused to explain where the mail was disappearing.

## Example

```console
$ mailtrace --journal --since '10 minutes ago' --message-id '<invite-123@example.net>'
MAILTRACE
query:        message-id=<invite-123@example.net>
status:       sent
queues:       0DC461ACD87
message-ids:  invite-123@example.net

2026-10-04T04:36:48.000+00:00  +     0ms  0DC461ACD87   postfix/cleanup      message-id=<invite-123@example.net>
2026-10-04T04:36:48.500+00:00  +   500ms  0DC461ACD87   rspamd/filter        message-id=<invite-123@example.net>  action=no action
2026-10-04T04:36:49.000+00:00  +  1000ms  0DC461ACD87   postfix/smtp         to=<tester@example.com>  relay=mx.example.com[203.0.113.10]:25  status=sent  dsn=2.0.0

Assessment
  outcome:    accepted-by-next-hop
  last stage: postfix:smtp
  confidence: high
  Postfix recorded status=sent: the next SMTP/LMTP/local hop accepted the message.
  Caveat: This is not proof that the message reached a recipient's inbox.
```

The assessment is evidence-based. If the supplied logs stop after the application, queue manager, or filter, `mailtrace` reports that boundary rather than pretending to know what happened next.

## Install from source

```bash
git clone https://github.com/artur-panek/mailtrace.git
cd mailtrace
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Python 3.11+ is required.

## Usage

### Read normal mail logs

```bash
mailtrace --file /var/log/mail.log --message-id '<3927a888@example.net>'
```

`--file` can be repeated. Each mail/syslog file is inspected for both Postfix and Rspamd events.

### Read journald directly

```bash
mailtrace --journal --since '10 minutes ago' --to tester@example.com
```

By default the journald reader asks for `postfix` and `rspamd`. Override the unit set with repeated `--unit` options:

```bash
mailtrace --journal \
  --unit postfix \
  --unit rspamd \
  --since '30 minutes ago' \
  --message-id '<3927a888@example.net>'
```

### Correlate application/gateway events

Custom services can emit a tiny JSONL event stream:

```json
{"timestamp":"2026-10-04T04:36:47+00:00","source":"korpoappka","stage":"invite","kind":"submitted","correlation_id":"invite-42","message_id":"3927a888@example.net","recipient":"tester@example.com","status":"submitted","message":"alpha invite handed to mail gateway"}
```

Trace it together with mail logs:

```bash
mailtrace \
  --events app-mail-events.jsonl \
  --file /var/log/mail.log \
  --correlation-id invite-42
```

Supported structured fields include:

- `timestamp` (required, ISO 8601)
- `source`
- `host`
- `stage` or `component`
- `kind`
- `message`
- `message_id`
- `queue_id`
- `linked_queue_id`
- `correlation_id`
- `sender` / `from`
- `recipient` / `to`
- `status`
- `relay`
- `details` (free-form JSON object)

### Query by Postfix queue ID

```bash
mailtrace --file /var/log/mail.log --queue 0DC461ACD87
```

### Pipe logs

```bash
journalctl -u postfix -u rspamd --since '10 minutes ago' -o short-iso-precise | \
  mailtrace --file - --to tester@example.com
```

### Machine-readable output

```bash
mailtrace --journal --since today --message-id '<3927a888@example.net>' --json
```

## What v0.2 understands

- classic Postfix syslog lines
- ISO timestamps emitted by journald
- direct journald collection
- common syslog-wrapped Rspamd task logs
- structured JSONL events from applications and gateways
- Message-ID, queue-ID, `queued as`, and correlation-ID graph expansion
- sender, recipient, relay, delay, DSN, filter action, and status extraction
- evidence-based assessment of the last confirmed stage
- human and JSON output

## What `status=sent` means

Postfix `status=sent` means the configured next hop accepted the message. It does **not** prove that a provider placed the message in the user's inbox.

`mailtrace` keeps that distinction explicit.

## Design goals

1. **Forensic, not always-on.** No database or daemon is required.
2. **Correlate evidence, do not invent it.** Missing evidence stays missing.
3. **Composable.** Read files, stdin, journald, or structured application events.
4. **Small enough to trust.** Parsers and correlation logic stay explicit and testable.
5. **Useful during an incident.** The output should answer where the observable trace stops.

## Roadmap

- [x] direct journald input
- [x] Rspamd correlation
- [x] structured application/gateway events
- [x] evidence-based trace assessment
- [ ] richer Rspamd/milter log variants
- [ ] RFC 5424 syslog support
- [ ] per-stage latency breakdown
- [ ] Postfix queue inspection for currently queued mail
- [ ] pluggable parser adapters
- [ ] optional HTML trace report

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## License

MIT
