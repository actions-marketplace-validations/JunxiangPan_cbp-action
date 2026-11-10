"""Windows-sensitive path/text semantics; runs on windows-latest in CI."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cbp import hostile_input


def test_backslash_artifact_is_rejected() -> None:
    with pytest.raises(hostile_input.HostileInput):
        hostile_input.artifact_name("cbp-rc\\..\\evil")


@pytest.mark.parametrize("name", ["CON", "nul.txt", "LPT1", "aux"])
def test_windows_reserved_names_are_rejected(name: str) -> None:
    with pytest.raises(hostile_input.HostileInput):
        hostile_input.artifact_name(name)


def test_short_name_is_not_a_hashed_artifact() -> None:
    with pytest.raises(hostile_input.HostileInput):
        hostile_input.artifact_name("A~1.WHL")


def test_case_insensitive_collision_is_visible() -> None:
    names = ["Wheel-1.3.0.whl", "wheel-1.3.0.whl"]
    assert len({name.casefold() for name in names}) == 1


def test_crlf_and_lf_docs_hash_match() -> None:
    lf = b"# doc\nbody\n"
    crlf = lf.replace(b"\n", b"\r\n")
    assert hashlib.sha256(lf.replace(b"\r\n", b"\n")).hexdigest() == hashlib.sha256(crlf.replace(b"\r\n", b"\n")).hexdigest()


def test_powershell_style_path_is_rejected() -> None:
    with pytest.raises(hostile_input.HostileInput):
        hostile_input.relative_path("C:\\Users\\runner\\artifact.whl")
