# Contributing

Thanks for taking an interest in MailForensics.

The project is intentionally small and evidence-driven. Contributions should preserve that character: prefer explicit evidence over clever inference, and say "unknown" when the available logs cannot prove something.

## Development setup

```bash
git clone https://github.com/artur-panek/mailforensics.git
cd mailforensics
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the same checks as CI:

```bash
ruff check .
pytest
python -m build
python -m twine check --strict dist/*
```

## Parser contributions

A parser should:

- ignore lines it does not recognize;
- emit only identifiers supported by source evidence;
- never correlate messages from timestamp proximity alone;
- include focused fixtures and tests;
- preserve the distinction between next-hop acceptance and mailbox delivery.

External formats that do not belong in core can use the `mailforensics.parsers` plugin entry-point API documented in `docs/parser-plugins.md`.

## Bug reports

Please sanitize addresses, domains, IPs, Message-IDs, queue IDs, credentials, and message content before posting logs publicly. Include `mailforensics --version` and `mailforensics doctor` output when useful.
