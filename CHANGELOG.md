# Changelog

## 0.4.0

- add forensic ASCII/Unicode console identity
- add auto color with `NO_COLOR` support and explicit `--color`
- add `--ascii` fallback for terminal graphics
- render explain pipelines as vertical forensic trees with per-hop timing
- add `mailtrace demo` with deferred, delivered, rejected, and evidence-gap scenarios
- add `mailtrace doctor` environment checks
- add Bash, Zsh, and Fish completion generation
- add delivered/deferred/rejected/gap fixtures for zero-setup testing
- document stable exit codes and terminal behavior


## 0.3.0

- add `mailtrace explain` pipeline view
- add live Postfix queue evidence via `postqueue -j`
- add offline queue snapshot ingestion
- add latency spans and observed-duration reporting
- add RFC 5424 syslog parsing
- broaden Rspamd process/action variants
- recognize Postfix milter reject/discard events
- add parser plugin entry points
- add self-contained HTML reports
- make recipient queries select the latest matching message before strong-ID expansion
- make the latest Postfix delivery result authoritative over earlier retries

## 0.2.0

- add direct journald collection
- correlate Postfix and Rspamd evidence
- add structured application/gateway JSONL events
- add application correlation IDs
- add evidence-based assessments
- preserve case-sensitive Message-ID correlation

## 0.1.0

- initial Postfix parser
- correlate Message-ID, queue IDs, and `queued as` handoffs
- render human-readable and JSON timelines
