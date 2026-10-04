from __future__ import annotations

FORENSIC_BANNER = """\
      ╭──────────────╮
──────┤  MAILFORENSICS   ├──────▶
      ╰──────────────╯
          trace the evidence,
          not the guess."""

FORENSIC_BANNER_ASCII = """\
      +--------------+
------|  MAILFORENSICS   |------->
      +--------------+
          trace the evidence,
          not the guess."""

COMPACT_MARK = "✉──●──●──●──▶  MAILFORENSICS"
COMPACT_MARK_ASCII = "[mail]--o--o--o-->  MAILFORENSICS"


def banner(*, ascii_only: bool = False) -> str:
    return FORENSIC_BANNER_ASCII if ascii_only else FORENSIC_BANNER


def compact_mark(*, ascii_only: bool = False) -> str:
    return COMPACT_MARK_ASCII if ascii_only else COMPACT_MARK
