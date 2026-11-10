"""Provenance sidecar: unsigned is honestly BLOCKED, never a fake signature."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from cbp import provenance
from tools import provenance as cli

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "provenance.schema.json").read_text(encoding="utf-8"))


def _fixture(tmp_path: Path) -> tuple[Path, list[Path], Path]:
    wheel = tmp_path / "cbp_action-1.3.0-py3-none-any.whl"
    sdist = tmp_path / "cbp_action-1.3.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    manifest = tmp_path / "quality-manifest.json"
    manifest.write_text(json.dumps({"artifact_hashes": {wheel.name: provenance._sha(wheel), sdist.name: provenance._sha(sdist)}}), encoding="utf-8")
    out = tmp_path / "provenance"
    provenance.write(manifest, [wheel, sdist], out, repository="JunxiangPan/cbp-action",
                     run_id="123", tag="v1.3.0", commit="a" * 40, generated_at="2026-11-10T00:00:00Z")
    return out / "provenance.json", [wheel, sdist], manifest


def test_schema_accepts_unsigned_sidecar(tmp_path: Path) -> None:
    path, _artifacts, _manifest = _fixture(tmp_path)
    jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), SCHEMA)


def test_unsigned_verifier_is_blocked_not_pass(tmp_path: Path) -> None:
    path, artifacts, manifest = _fixture(tmp_path)
    result = provenance.verify(path, manifest, artifacts)
    assert result["status"] == "BLOCKED_NO_SIGNING_IDENTITY"
    assert result["problems"] == []
    assert (path.parent / "provenance.sig").is_file()


def test_offline_verifier_detects_artifact_tamper(tmp_path: Path) -> None:
    path, artifacts, manifest = _fixture(tmp_path)
    artifacts[0].write_bytes(b"tampered")
    result = provenance.verify(path, manifest, artifacts)
    assert any("subject digest mismatch" in item for item in result["problems"])


def test_offline_verifier_detects_manifest_tamper(tmp_path: Path) -> None:
    path, artifacts, manifest = _fixture(tmp_path)
    manifest.write_text("{}", encoding="utf-8")
    result = provenance.verify(path, manifest, artifacts)
    assert any("manifest_sha256" in item for item in result["problems"])


def test_cli_unsigned_exits_4(tmp_path: Path, capsys) -> None:
    path, artifacts, manifest = _fixture(tmp_path)
    argv = ["verify", "--provenance", str(path), "--manifest", str(manifest)]
    for artifact in artifacts:
        argv += ["--artifact", str(artifact)]
    assert cli.main(argv) == 4
    assert "BLOCKED_NO_SIGNING_IDENTITY" in capsys.readouterr().out


def test_signed_verifier_requires_and_validates_bundles(tmp_path: Path, monkeypatch) -> None:
    bundle_dir = tmp_path / "signatures"
    bundle_dir.mkdir()
    wheel = tmp_path / "a.whl"; wheel.write_bytes(b"a")
    sdist = tmp_path / "a.tar.gz"; sdist.write_bytes(b"b")
    manifest = tmp_path / "quality-manifest.json"
    manifest.write_text(json.dumps({"artifact_hashes": {wheel.name: provenance._sha(wheel), sdist.name: provenance._sha(sdist)}}), encoding="utf-8")
    out = tmp_path / "provenance"
    provenance.write(manifest, [wheel, sdist], out, repository="JunxiangPan/cbp-action",
                     run_id="1", tag="v1.3.2", commit="a" * 40,
                     generated_at="2026-11-11T00:00:00Z", signed=True)
    prov = out / "provenance.json"
    for path in (prov, manifest, wheel, sdist):
        (bundle_dir / (path.name + ".bundle")).write_text("fake bundle", encoding="utf-8")
    monkeypatch.setattr(provenance, "cosign_verify", lambda *args: (True, ""))
    result = provenance.verify(prov, manifest, [wheel, sdist], bundle_dir=bundle_dir,
                               identity_regexp="https://github.com/x/y/.github/workflows/release.yml@refs/tags/v1.3.2")
    assert result["status"] == "SIGNED"
    monkeypatch.setattr(provenance, "cosign_verify", lambda *args: (False, "bad signature"))
    assert provenance.verify(prov, manifest, [wheel, sdist], bundle_dir=bundle_dir,
                             identity_regexp="x")["status"] == "FAIL"
