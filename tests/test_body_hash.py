"""Canonical body hash: LF, BOM-free, exactly one trailing newline."""
from __future__ import annotations

import hashlib
from pathlib import Path

from cbp.body_hash import canonical_body_bytes, canonical_body_hash

V120_BODY = Path(__file__).parent / "fixtures" / "body" / "v120-release-body.md"
V120_RAW_LF_HASH = "4709f6a5c4c56a416117c1f9070d023b028a2a98a7f98106b0e3688f253baed3"
V120_CANONICAL_HASH = "4798acf332ce8a4ea0093cba7755d57132a3e9e81c4d5c0ec9974fd719e802ef"


def test_canonical_hash_ignores_newline_and_crlf_variants() -> None:
    base = b"# title\n\nbody"
    assert canonical_body_hash(base) == canonical_body_hash(base + b"\n")
    assert canonical_body_hash(base) == canonical_body_hash(base + b"\n\n\n")
    assert canonical_body_hash(base) == canonical_body_hash(b"# title\r\n\r\nbody\r\n")
    assert canonical_body_hash(base) == canonical_body_hash(b"\xef\xbb\xbf" + base)
    assert canonical_body_bytes(base).endswith(b"\n")


def test_canonical_hash_preserves_internal_whitespace() -> None:
    assert canonical_body_hash(b"a  b\n") != canonical_body_hash(b"a b\n")


def test_v120_release_body_hashes_to_the_reported_values() -> None:
    raw = V120_BODY.read_bytes()
    assert hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == V120_RAW_LF_HASH
    assert canonical_body_hash(raw) == V120_CANONICAL_HASH


def test_hash_is_sha256_of_the_canonical_bytes() -> None:
    data = b"# cbp\n"
    expected = hashlib.sha256(canonical_body_bytes(data)).hexdigest()
    assert canonical_body_hash(data) == expected

def test_base_end_marker_excludes_the_appendix() -> None:
    base = b"# cbp\n\nbase\n"
    body = base + b"\n<!-- CBP-BODY-BASE-END -->\n## CBM\n- NOT_UPLOADED\n"
    assert canonical_body_hash(body) == canonical_body_hash(base)
