from __future__ import annotations

FORENSIC_BANNER = """\
      ╭──────────────╮
──────┤  MAILTRACE   ├──────▶
      ╰──────────────╯
          trace the evidence,
          not the guess."""

FORENSIC_BANNER_ASCII = """\
      +--------------+
------|  MAILTRACE   |------->
      +--------------+
          trace the evidence,
          not the guess."""

COMPACT_MARK = "✉──●──●──●──▶  MAILTRACE"
COMPACT_MARK_ASCII = "[mail]--o--o--o-->  MAILTRACE"


def banner(*, ascii_only: bool = False) -> str:
    return FORENSIC_BANNER_ASCII if ascii_only else FORENSIC_BANNER


def compact_mark(*, ascii_only: bool = False) -> str:
    return COMPACT_MARK_ASCII if ascii_only else COMPACT_MARK
