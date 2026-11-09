"""The single canonical release-body hash used by every CBP producer/checker.

Definition:

* decode as UTF-8, dropping a leading UTF-8 BOM;
* normalize CRLF and lone CR to LF;
* strip all trailing newlines and append exactly one LF when the body is
  non-empty;
* hash the resulting UTF-8 bytes with SHA-256.

This makes a body with no trailing newline, one trailing newline, or several
trailing newlines hash the same, and makes CRLF checkouts hash the same as LF.
Other whitespace and all content are preserved.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


BASE_END_MARKERS = (
    b"<!-- CBP-BODY-BASE-END -->",
    b"<!-- CBC-EVIDENCE-BEGIN -->",
)


def base_body_bytes(data: bytes) -> bytes:
    """Return the bytes before the first base-end marker."""
    indexes = [data.find(marker) for marker in BASE_END_MARKERS if marker in data]
    if indexes:
        data = data[: min(indexes)]
    return data


def canonical_body_bytes(data: bytes) -> bytes:
    data = base_body_bytes(data)
    text = data.decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n")
    if text:
        text += "\n"
    return text.encode("utf-8")


def canonical_body_hash(data: bytes) -> str:
    return hashlib.sha256(canonical_body_bytes(data)).hexdigest()


def canonical_body_hash_file(path: Path) -> str:
    return canonical_body_hash(Path(path).read_bytes())
