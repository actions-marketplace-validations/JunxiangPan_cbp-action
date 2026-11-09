"""CBP-BODY-001: manifest.release_body_hash must bind the actual body."""
from __future__ import annotations

from pathlib import Path

from cbp import cli, v12_rules as v12

BODY = Path(__file__).parent / "fixtures" / "body" / "v120-release-body.md"
V120 = Path(__file__).parent / "fixtures" / "body" / "v120-quality-manifest.json"
V121 = Path(__file__).parent / "fixtures" / "body" / "v121-quality-manifest.json"


def _run(manifest: Path, body: Path, tmp_path: Path, monkeypatch) -> list[str]:
    monkeypatch.setenv("CBP_BODY_MANIFEST", str(manifest))
    monkeypatch.setenv("CBP_BODY_FILE", str(body))
    results, _ = v12.run_rules(tmp_path, only={"CBP-BODY-001"})
    return results[0].findings


def test_v120_manifest_fails_against_the_real_body(tmp_path: Path, monkeypatch) -> None:
    findings = _run(V120, BODY, tmp_path, monkeypatch)
    assert findings
    assert "1fa44c14139c747601663e2971a8fcade6554f3d9dd404bba5716ba19bd0bb80" in findings[0]
    assert "4798acf332ce8a4ea0093cba7755d57132a3e9e81c4d5c0ec9974fd719e802ef" in findings[0]


def test_v121_manifest_passes(tmp_path: Path, monkeypatch) -> None:
    assert _run(V121, BODY, tmp_path, monkeypatch) == []


def test_newline_variants_do_not_change_the_hash(tmp_path: Path, monkeypatch) -> None:
    variant = tmp_path / "body-crlf.md"
    variant.write_bytes(b"# CBP v1.2.0 - Release-evidence gate\r\n\r\nbody\r\n\r\n")
    manifest = tmp_path / "quality-manifest.json"
    manifest.write_text(V121.read_text(encoding="utf-8"), encoding="utf-8")
    data = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    from cbp.body_hash import canonical_body_hash
    data["release_body_hash"] = canonical_body_hash(variant.read_bytes())
    manifest.write_text(__import__("json").dumps(data), encoding="utf-8")
    assert _run(manifest, variant, tmp_path, monkeypatch) == []


def test_missing_body_is_a_finding(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CBP_BODY_MANIFEST", str(V120))
    monkeypatch.setenv("CBP_BODY_FILE", str(tmp_path / "missing.md"))
    results, _ = v12.run_rules(tmp_path, only={"CBP-BODY-001"})
    assert results[0].findings
    assert "release body missing" in results[0].findings[0]


def test_full_scope_is_rejected(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "quality-manifest.json"
    data = __import__("json").loads(V121.read_text(encoding="utf-8"))
    data["body_hash_scope"] = "full"
    manifest.write_text(__import__("json").dumps(data), encoding="utf-8")
    assert any("not supported" in item for item in _run(manifest, BODY, tmp_path, monkeypatch))


def test_cli_v12_blocks_v120_and_passes_v121(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CBP_BODY_FILE", str(BODY))
    monkeypatch.setenv("CBP_BODY_MANIFEST", str(V120))
    assert cli.main(["--root", str(tmp_path), "--v12", "--v12-only", "CBP-BODY-001"]) == 3
    monkeypatch.setenv("CBP_BODY_MANIFEST", str(V121))
    assert cli.main(["--root", str(tmp_path), "--v12", "--v12-only", "CBP-BODY-001"]) == 0


def test_rule_count_is_thirteen() -> None:
    assert len(v12.RULES) == 13
