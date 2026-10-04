# Parser plugins

`mailforensics` can load external log parsers from the Python entry-point group:

```text
mailforensics.parsers
```

This is intended for MTAs, filters, gateways, or organization-specific log formats that do not belong in the core package.

## Minimal plugin

```python
from collections.abc import Iterable

from mailforensics.model import Event


def parse(lines: Iterable[str], *, year: int | None = None) -> list[Event]:
    events: list[Event] = []

    for line in lines:
        # Recognize only lines owned by your parser.
        if "my-mail-gateway" not in line:
            continue

        # Parse an Event with a real timestamp and any identifiers you can
        # prove from the source data.
        events.append(...)

    return events
```

Register it in the plugin package:

```toml
[project.entry-points."mailforensics.parsers"]
my-gateway = "my_mailforensics_plugin:parse"
```

After installation:

```bash
mailforensics parsers
```

should show:

```text
mailforensics parsers
  postfix              builtin
  rspamd               builtin
  my-gateway           plugin
```

## Contract

A parser callable must:

1. accept an iterable of text lines as its first argument;
2. accept the keyword argument `year`;
3. return an iterable of `mailforensics.model.Event` objects;
4. ignore lines it does not recognize;
5. avoid deriving identifiers from timestamp proximity or other weak guesses.

The same materialized log batch is passed to every parser.

## Event identifiers

Correlation becomes useful when an event contains one or more of:

- `queue_id`
- `details["linked_queue_id"]`
- `details["message_id"]`
- `details["correlation_id"]`

A plugin should only emit identifiers that are explicitly supported by the source evidence.

## Failure behavior

If a discovered plugin cannot be imported, is not callable, raises while parsing, or returns non-`Event` values, `mailforensics` fails the run with a parser error instead of silently dropping evidence.

Use:

```bash
mailforensics explain --no-plugins ...
```

to restrict a forensic run to the built-in parsers.

## Compatibility

The plugin API is still alpha. Plugins should pin an appropriate `mailforensics` version until the Event model reaches a stable compatibility guarantee.
