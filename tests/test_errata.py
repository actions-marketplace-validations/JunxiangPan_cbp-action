"""CONTRACT F4 ERRATUM recognition and the cbp errata generator."""
from __future__ import annotations

from pathlib import Path

from cbp import cli, errata


def test_is_errata_accepts_leading_whitespace() -> None:
    assert errata.is_errata("ERRATUM:\nbody\n")
    assert errata.is_errata("\n\n  ERRATUM:\ntext\n")


def test_is_errata_rejects_a_trailing_section() -> None:
    body = "# release\n\n## ERRATUM (v1.0.9)\n\nold text\n"
    assert errata.is_errata(body) is False


def test_trailing_errata_count_finds_both_headings() -> None:
    body = "# release\n\n## ERRATUM\n\nx\n\nERRATUM:\n\ny\n"
    assert errata.trailing_errata_count(body) == 2


def test_apply_errata_prefixes_and_preserves_the_original() -> None:
    original = "# CBP v1.0.8\n\nbody text\n\n## ERRATUM\n\nold\n"
    corrected = errata.apply_errata(original, "Do not pin this version.")
    assert corrected.startswith("ERRATUM:\n")
    assert "Do not pin this version." in corrected
    assert corrected.endswith(original)


def test_apply_errata_is_idempotent() -> None:
    once = errata.apply_errata("body\n", "reason")
    assert errata.apply_errata(once, "reason") == once


def test_unified_diff_shows_the_prefix() -> None:
    diff = errata.unified_diff("body\n", errata.apply_errata("body\n", "r"))
    assert "+ERRATUM:" in diff


def test_cli_errata_missing_body_exits_two(tmp_path: Path, capsys) -> None:
    assert cli.main(["errata", "--body", str(tmp_path / "missing.md")]) == 2
    assert "body missing" in capsys.readouterr().out


def test_cli_errata_check_flags_a_missing_token(tmp_path: Path, capsys) -> None:
    body = tmp_path / "body.md"
    body.write_text("# release\n\n## ERRATUM\n\nnot machine readable\n", encoding="utf-8")
    assert cli.main(["errata", "--body", str(body), "--check"]) == 3
    assert "ERRATUM_MISSING" in capsys.readouterr().out


def test_cli_errata_check_accepts_a_prefixed_body(tmp_path: Path, capsys) -> None:
    body = tmp_path / "body.md"
    body.write_text("ERRATUM:\n\nreason\n\n# release\n", encoding="utf-8")
    assert cli.main(["errata", "--body", str(body), "--check"]) == 0
    assert "ERRATUM_OK" in capsys.readouterr().out


def test_cli_errata_writes_a_machine_readable_body(tmp_path: Path, capsys) -> None:
    body = tmp_path / "body.md"
    output = tmp_path / "corrected.md"
    body.write_text("# release\n\n## ERRATUM\n\ntrailing only\n", encoding="utf-8")
    assert cli.main(["errata", "--body", str(body), "--output", str(output), "--reason", "do not pin"]) == 0
    corrected = output.read_text(encoding="utf-8")
    assert errata.is_errata(corrected)
    assert corrected.endswith(body.read_text(encoding="utf-8"))
    out = capsys.readouterr().out
    assert "TRAILING_ERRATUM_SECTIONS=1" in out
    assert "ERRATUM_WRITTEN" in out


def test_cli_errata_directory_body_exits_two(tmp_path: Path, capsys) -> None:
    directory = tmp_path / "dir"
    directory.mkdir()
    assert cli.main(["errata", "--body", str(directory)]) == 2
    assert "body unreadable" in capsys.readouterr().out


def test_cli_errata_already_prefixed_is_idempotent(tmp_path: Path, capsys) -> None:
    body = tmp_path / "body.md"
    body.write_text("ERRATUM:\n\nreason\n\n# release\n", encoding="utf-8")
    assert cli.main(["errata", "--body", str(body)]) == 0
    out = capsys.readouterr().out
    assert "ERRATUM_ALREADY_PRESENT" in out
    assert "ERRATUM_OK" in out
