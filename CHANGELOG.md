# Changelog

## 0.5.2

- refresh the package long description so documentation and contributor links render correctly on PyPI
- include the current portfolio and engineering-note cross-links in the published README
- keep runtime functionality unchanged from 0.5.1

## 0.5.1

- rewrite the public README around installation, evidence sources, commands, and correlation semantics
- make PyPI installation the default quick-start path
- simplify the forensic branding presentation and public examples
- remove development-history framing from the main project page
- keep functionality unchanged from 0.5.0

## 0.5.0

- rename the project from `mailtrace` to **MailForensics** and the Python package/CLI to `mailforensics` before the first PyPI release
- avoid a naming collision with an existing mail-tracing package
- prepare secretless PyPI Trusted Publishing through GitHub Actions OIDC
- add package build validation and clean-wheel smoke testing
- add contribution and issue-reporting workflows

## 0.4.0

- add forensic ASCII/Unicode console identity
- add auto color with `NO_COLOR` support and explicit `--color`
- add `--ascii` fallback for terminal graphics
- render explain pipelines as vertical forensic trees with per-hop timing
- add `mailforensics demo` with deferred, delivered, rejected, and evidence-gap scenarios
- add `mailforensics doctor` environment checks
- add Bash, Zsh, and Fish completion generation
- add delivered/deferred/rejected/gap fixtures for zero-setup testing
- document stable exit codes and terminal behavior

## 0.3.0

- add `mailforensics explain` pipeline view
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
