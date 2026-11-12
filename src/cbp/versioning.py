"""PEP 440 version acceptance for CBP manifests and reports.

CBP's historical validator only accepted X.Y.Z. Release candidates such as
0.1.0rc1 are valid PEP 440 versions and must be represented as such, not
renamed to a fake stable version.
"""
from __future__ import annotations

import re

# PEP 440 release + optional pre/post/dev + local. CBP requires at least three
# release segments (X.Y.Z) to preserve the historical minimum.
PEP440_PATTERN = re.compile(
    r"^v?"
    r"(?P<release>\d+\.\d+\.\d+)"
    r"(?:(?:[-_.]?)(?P<pre>a|b|c|rc|alpha|beta|pre|preview)(?:[-_.]?)(?P<pre_n>\d+))?"
    r"(?:(?:[-_.]?)post(?:[-_.]?)(?P<post>\d+))?"
    r"(?:(?:[-_.]?)dev(?:[-_.]?)(?P<dev>\d+))?"
    r"(?:\+[a-z0-9]+(?:[-_.][a-z0-9]+)*)?$",
    re.IGNORECASE,
)


def normalize_version(value: str) -> str:
    """Return the CBP-prefixed version, preserving a PEP 440 prerelease."""
    text = str(value).strip()
    if text.startswith(("v", "V")):
        text = text[1:]
    if not PEP440_PATTERN.fullmatch(text):
        raise ValueError(f"version must be PEP 440 X.Y.Z (optionally pre/post/dev), got {value!r}")
    return "v" + text
