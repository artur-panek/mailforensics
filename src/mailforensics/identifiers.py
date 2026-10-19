from __future__ import annotations

import re


def normalize_queue_id(value: str) -> str:
    # Short Postfix IDs are hexadecimal. Long IDs use a case-sensitive alphabet.
    return value.upper() if re.fullmatch(r"[0-9a-fA-F]+", value) else value
