"""The default profile must behave exactly like the pre-1.4 path."""
from __future__ import annotations

from pathlib import Path

from cbp.cli import main as cli_main


def test_default_profile_is_not_strict(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    first = cli_main(["--root", root, "--v12", "--v12-only", "CBP-CI-001"])
    first_out = capsys.readouterr().out
    second = cli_main(["--root", root, "--profile", "default", "--v12", "--v12-only", "CBP-CI-001"])
    second_out = capsys.readouterr().out
    assert first == second
    assert first_out == second_out
