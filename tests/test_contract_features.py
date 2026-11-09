"""CONTRACT features: rules pack input, explicit asset manifest, infra status."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cbp import cli, report_schema, verify_release


def _pack(tmp_path: Path, rule: dict, *, name: str = "cbp-inline") -> Path:
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({
        "name": name,
        "version": "1.0.0",
        "rules": [rule],
    }), encoding="utf-8")
    return pack


def _rule(**overrides) -> dict:
    rule = {
        "name": "no_print",
        "pattern": "print(",
        "match": "literal",
        "files": ["*.py"],
        "message": "no print",
        "mode": "enforce",
    }
    rule.update(overrides)
    return rule


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("print('hit')\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("clean\n", encoding="utf-8")
    return tmp_path


def test_rules_path_missing_file_exits_two(tmp_path: Path, capsys) -> None:
    _repo(tmp_path)
    assert cli.main(["--root", str(tmp_path), "--rules-path", str(tmp_path / "missing.json")]) == 2
    assert "rules pack unreadable" in capsys.readouterr().out


def test_rules_path_invalid_json_exits_two(tmp_path: Path, capsys) -> None:
    _repo(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert cli.main(["--root", str(tmp_path), "--rules-path", str(bad)]) == 2
    assert "rules pack unreadable" in capsys.readouterr().out


def test_rules_path_hash_mismatch_exits_two(tmp_path: Path, capsys) -> None:
    _repo(tmp_path)
    pack = _pack(tmp_path, _rule())
    assert cli.main([
        "--root", str(tmp_path), "--rules-path", str(pack),
        "--rules-sha256", "0" * 64,
    ]) == 2
    assert "hash mismatch" in capsys.readouterr().out


def test_rules_sha256_without_path_exits_two(tmp_path: Path, capsys) -> None:
    assert cli.main(["--root", str(tmp_path), "--rules-sha256", "0" * 64]) == 2
    assert "--rules-sha256 requires --rules-path" in capsys.readouterr().out


def test_rules_path_enforces_a_matching_rule(tmp_path: Path, capsys) -> None:
    _repo(tmp_path)
    pack = _pack(tmp_path, _rule())
    assert cli.main(["--root", str(tmp_path), "--rules-path", str(pack)]) == 3
    out = capsys.readouterr().out
    assert "custom: FAIL" in out
    assert "no print" in out


def test_rules_path_without_a_match_passes(tmp_path: Path) -> None:
    _repo(tmp_path)
    pack = _pack(tmp_path, _rule(pattern="CBP_NEVER_MATCH_9F3"))
    assert cli.main(["--root", str(tmp_path), "--rules-path", str(pack)]) == 0


def test_release_assets_uses_the_explicit_path(tmp_path: Path, monkeypatch) -> None:
    body = tmp_path / "body.md"
    body.write_text("body\n", encoding="utf-8")
    assets = tmp_path / "elsewhere" / "RELEASE_ASSETS.sha256"
    assets.parent.mkdir()
    assets.write_text("", encoding="utf-8")
    seen: dict[str, str] = {}
    monkeypatch.setattr(verify_release, "fetch_release_body", lambda *a, **k: "body\n")
    monkeypatch.setattr(
        "cbp.verify_release_assets.verify_from_manifest",
        lambda path, repository, tag, token: (seen.update(path=str(path)) or (True, "RELEASE_ASSETS_OK")),
    )
    code = cli.main([
        "--root", str(tmp_path), "--release-body", str(body),
        "--release-assets", str(assets),
        "--verify-release", "v1.0.0", "--repository", "o/r",
    ])
    assert code == 0
    assert seen["path"] == str(assets)


def test_release_assets_missing_exits_two(tmp_path: Path, monkeypatch) -> None:
    body = tmp_path / "body.md"
    body.write_text("body\n", encoding="utf-8")
    monkeypatch.setattr(verify_release, "fetch_release_body", lambda *a, **k: "body\n")
    assert cli.main([
        "--root", str(tmp_path), "--release-body", str(body),
        "--release-assets", str(tmp_path / "missing.sha256"),
        "--verify-release", "v1.0.0", "--repository", "o/r",
    ]) == 2


def test_api_error_classifies_5xx_as_infra_and_4xx_as_input() -> None:
    assert isinstance(verify_release._api_error(503, "o/r", "v1"), report_schema.InfraError)
    assert not isinstance(verify_release._api_error(404, "o/r", "v1"), report_schema.InfraError)


def test_verify_release_propagates_infra_error(tmp_path: Path, monkeypatch) -> None:
    body = tmp_path / "body.md"
    body.write_text("body\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise report_schema.InfraError("GitHub API unavailable: timeout")

    monkeypatch.setattr(verify_release, "fetch_release_body", boom)
    with pytest.raises(report_schema.InfraError):
        verify_release.verify("o/r", "v1.0.0", body)


def test_cli_maps_infra_failure_to_exit_three_and_skipped_infra(tmp_path: Path, monkeypatch, capsys) -> None:
    body = tmp_path / "body.md"
    body.write_text("body\n", encoding="utf-8")

    def boom(*args, **kwargs):
        raise report_schema.InfraError("GitHub API unavailable: timeout")

    monkeypatch.setattr(verify_release, "fetch_release_body", boom)
    code = cli.main([
        "--root", str(tmp_path), "--release-body", str(body),
        "--verify-release", "v1.0.0", "--repository", "o/r",
    ])
    assert code == 3
    assert "GATE_STATUS=SKIPPED_INFRA" in capsys.readouterr().out
