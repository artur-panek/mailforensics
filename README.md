# mailtrace

**`strace` for an email moving through your mail stack.**

`mailtrace` reconstructs the journey of an outbound message from Postfix logs by correlating Message-IDs, queue IDs, relay attempts, DSNs, and delivery status.

It is intentionally not an email-header analyzer and not a monitoring daemon. Point it at logs when a message disappears and ask one question: **where did this mail go?**

> Early alpha. The first release focuses on Postfix and local log analysis.

## Example

```console
$ mailtrace --file /var/log/mail.log --message-id '<invite-123@example.net>'
MAILTRACE
query:    message-id=<invite-123@example.net>
status:   sent
queues:   0DC461ACD87, 24D1C1ACD8B

2026-10-04T04:36:48.000  +     0ms  0DC461ACD87    cleanup  message-id=<invite-123@example.net>
2026-10-04T04:36:48.000  +     0ms  0DC461ACD87    qmgr     from=<app@example.net>
2026-10-04T04:36:49.000  +  1000ms  0DC461ACD87    smtp     to=<tester@example.com>  relay=mx.example.com[203.0.113.10]:25  status=sent  dsn=2.0.0  delay=1.1s  queued-as=24D1C1ACD8B
```

The `queued as ...` response is followed as another queue ID, so traces can continue across a reinjection/handoff recorded in the same logs.

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

Trace by Message-ID:

```bash
mailtrace --file /var/log/mail.log --message-id '<3927a888@example.net>'
```

Trace by Postfix queue ID:

```bash
mailtrace --file /var/log/mail.log --queue 0DC461ACD87
```

Trace by exact recipient:

```bash
mailtrace --file /var/log/mail.log --to tester@example.com
```

Pipe logs directly:

```bash
journalctl -u postfix --since '10 minutes ago' -o short-iso | \
  mailtrace --file - --to tester@example.com
```

Machine-readable output:

```bash
mailtrace --file /var/log/mail.log --queue 0DC461ACD87 --json
```

Classic syslog timestamps do not contain a year. `mailtrace` assumes the current year unless `--year` is supplied.

## What v0.1 understands

- classic Postfix syslog lines
- ISO timestamps commonly emitted by `journalctl -o short-iso`
- Message-ID to queue-ID correlation
- sender and recipient extraction
- relay, delay, DSN and status extraction
- `queued as <id>` queue handoffs
- human and JSON output

## Design goals

1. **Forensic, not always-on.** No database or daemon is required.
2. **Explain evidence, do not invent it.** A Postfix `status=sent` means the next hop accepted the message; it does not prove mailbox delivery.
3. **Composable.** Read files or stdin and support structured output.
4. **Small enough to trust.** Parsers and correlation logic stay explicit and testable.

## Roadmap

- [ ] journald reader with unit filtering
- [ ] multiline and RFC 5424 syslog support
- [ ] richer queue handoff correlation across filters and relays
- [ ] Rspamd event correlation
- [ ] configurable parsers for application/gateway logs
- [ ] latency breakdown per stage
- [ ] `mailtrace explain` failure summaries

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## License

MIT
