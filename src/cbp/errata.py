"""Machine-readable ERRATUM handling (CONTRACT v1.7 F4).

F4 recognises an ERRATUM only when the release body starts, after optional
leading whitespace, with ``ERRATUM:``. A section appended at the end of the body
is human-readable but invisible to the machine rule, so the tool never counts it.
"""
from __future__ import annotations

import difflib
import re

ERRATUM_PREFIX = "ERRATUM:"
_LEADING = re.compile(r"^\s*")


def is_errata(body: str) -> bool:
    """Return True when the body starts with the machine-readable ERRATUM token."""
    return bool(_LEADING.sub("", body, count=1).startswith(ERRATUM_PREFIX))


def trailing_errata_count(body: str) -> int:
    """Count ERRATUM-looking headings that are not at the start of the body."""
    text = _LEADING.sub("", body, count=1)
    if text.startswith(ERRATUM_PREFIX):
        text = text[len(ERRATUM_PREFIX):]
    return sum(
        1
        for line in text.splitlines()
        if line.lstrip().startswith("## ERRATUM") or line.strip() == ERRATUM_PREFIX
    )


def apply_errata(body: str, reason: str) -> str:
    """Prefix the body with ERRATUM: and keep the original text intact.

    Idempotent: a body that already starts with ERRATUM: is returned unchanged.
    """
    if is_errata(body):
        return body
    summary = (reason or "This release is an ERRATUM; do not pin it.").strip()
    return f"{ERRATUM_PREFIX}\n\n{summary}\n\n{body}"


def unified_diff(original: str, corrected: str, *, name: str = "RELEASE_BODY.md") -> str:
    """Return a unified diff between the current and the corrected body."""
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            corrected.splitlines(keepends=True),
            fromfile=name,
            tofile=name + " (corrected)",
        )
    )
