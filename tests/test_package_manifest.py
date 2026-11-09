"""External-package quality manifest generator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cbp import cli, package_manifest as pm, report_schema


def _write(path: Path, data: bytes | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8", newline="\n")
    else:
        path.write_bytes(data)
    return path


def _report(overrides: dict | None = None) -> dict:
    value = {
        "schema_version": "1",
        "package_id": "cbc",
        "producer_id": "cbp",
        "version": "v0.1.0",
        "gate_status": "PASS",
        "applicable_gate_count": 2,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [
            {"name": "encoding", "status": "PASS", "reason": ""},
            {"name": "docs", "status": "PASS", "reason": ""},
        ],
    }
    value.update(overrides or {})
    return value


def _inputs(tmp_path: Path):
    report = _write(tmp_path / "gate-report.json", json.dumps(_report()))
    artifact = _write(tmp_path / "cbc-0.1.0-py3-none-any.whl", b"wheel-bytes")
    body = _write(
        tmp_path / "RELEASE_BODY.md",
        "# cbc 0.1.0\n\nbase\n<!-- CBC-EVIDENCE-BEGIN -->\nappendix\n<!-- CBC-EVIDENCE-END -->\n",
    )
    return report, artifact, body


def _build(tmp_path: Path, **overrides):
    report, artifact, body = _inputs(tmp_path)
    values = {
        "package_id": "cbc",
        "producer_id": "cbp",
        "version": "0.1.0",
        "gate_report": report,
        "artifacts": [str(artifact)],
        "release_body": body,
        "body_hash_scope": "base",
        "out": tmp_path / "quality-manifest.json",
    }
    values.update(overrides)
    return pm.build_manifest(**values)


def test_manifest_writes_subject_and_producer(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    assert manifest["package_id"] == "cbc"
    assert manifest["producer_id"] == "cbp"
    assert manifest["version"] == "v0.1.0"
    assert manifest["body_hash_scope"] == "base"
    assert manifest["gate_status"] == "PASS"
    assert manifest["applicable_gate_count"] == 2
    assert list(manifest["artifact_hashes"]) == ["cbc-0.1.0-py3-none-any.whl"]
    assert report_schema.validate_manifest(manifest, require_body_scope=True) == []
    written = json.loads((tmp_path / "quality-manifest.json").read_text(encoding="utf-8"))
    assert written == manifest


def test_base_body_hash_excludes_the_cbc_appendix(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    expected = hashlib.sha256(b"# cbc 0.1.0\n\nbase\n").hexdigest()
    assert manifest["release_body_hash"] == expected


def test_missing_gate_report_is_exit_two(tmp_path: Path) -> None:
    report, artifact, body = _inputs(tmp_path)
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(tmp_path / "missing.json"), "--artifact", str(artifact),
        "--release-body", str(body), "--body-hash-scope", "base", "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


def test_missing_artifact_is_exit_two(tmp_path: Path) -> None:
    report, artifact, body = _inputs(tmp_path)
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(report), "--artifact", str(tmp_path / "missing.whl"),
        "--release-body", str(body), "--body-hash-scope", "base", "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


def test_missing_release_body_is_exit_two(tmp_path: Path) -> None:
    report, artifact, _body = _inputs(tmp_path)
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(report), "--artifact", str(artifact),
        "--release-body", str(tmp_path / "missing.md"), "--body-hash-scope", "base",
        "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


@pytest.mark.parametrize("scope", ["", "full"])
def test_missing_or_full_scope_is_exit_two(tmp_path: Path, scope: str) -> None:
    report, artifact, body = _inputs(tmp_path)
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(report), "--artifact", str(artifact),
        "--release-body", str(body), "--body-hash-scope", scope, "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


def test_artifact_hash_mismatch_is_exit_two(tmp_path: Path) -> None:
    report, artifact, body = _inputs(tmp_path)
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(report), "--artifact", str(artifact),
        "--artifact-sha256", "cbc-0.1.0-py3-none-any.whl=" + "0" * 64,
        "--release-body", str(body), "--body-hash-scope", "base", "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


def test_artifact_hashes_and_evidence_are_stable(tmp_path: Path) -> None:
    evidence = _write(tmp_path / "gate.log", "gate log\n")
    first = _build(tmp_path, evidence=[str(evidence)])
    second = _build(tmp_path, evidence=[str(evidence)])
    assert first == second
    assert first["evidence_sha256"] != canonical_without_evidence(first)
    assert first["evidence_sha256"] == second["evidence_sha256"]


def canonical_without_evidence(manifest: dict) -> str:
    unsigned = {key: value for key, value in manifest.items() if key != "evidence_sha256"}
    return pm.canonical_sha256(unsigned)


def test_evidence_free_hash_is_the_manifest_self_hash(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    assert manifest["evidence_sha256"] == canonical_without_evidence(manifest)


def test_a_failing_gate_report_keeps_fail(tmp_path: Path) -> None:
    report = _write(tmp_path / "gate-report.json", json.dumps(_report({
        "gate_status": "FAIL",
        "gates": [
            {"name": "encoding", "status": "FAIL", "reason": "bad"},
            {"name": "docs", "status": "PASS", "reason": ""},
        ],
    })))
    artifact = _write(tmp_path / "a.whl", b"x")
    body = _write(tmp_path / "body.md", "base\n")
    manifest = pm.build_manifest(
        package_id="cbc", producer_id="cbp", version="v0.1.0",
        gate_report=report, artifacts=[str(artifact)], release_body=body,
        body_hash_scope="base",
    )
    assert manifest["gate_status"] == "FAIL"
    assert manifest["gates"][0]["status"] == "FAIL"


def test_skipped_gate_without_reason_is_exit_two(tmp_path: Path) -> None:
    report = _write(tmp_path / "gate-report.json", json.dumps(_report({
        "gates": [
            {"name": "encoding", "status": "SKIPPED", "reason": ""},
            {"name": "docs", "status": "PASS", "reason": ""},
        ],
    })))
    artifact = _write(tmp_path / "a.whl", b"x")
    body = _write(tmp_path / "body.md", "base\n")
    with pytest.raises(pm.ManifestError, match="SKIPPED without a reason"):
        pm.build_manifest(
            package_id="cbc", producer_id="cbp", version="v0.1.0",
            gate_report=report, artifacts=[str(artifact)], release_body=body,
            body_hash_scope="base",
        )


def test_gate_report_package_id_must_match_the_target(tmp_path: Path) -> None:
    report, artifact, body = _inputs(tmp_path)
    report.write_text(json.dumps(_report({"package_id": "cbp"})), encoding="utf-8")
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(report), "--artifact", str(artifact),
        "--release-body", str(body), "--body-hash-scope", "base", "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


def test_gate_report_version_must_match_the_target(tmp_path: Path) -> None:
    report, artifact, body = _inputs(tmp_path)
    report.write_text(json.dumps(_report({"version": "v0.0.0"})), encoding="utf-8")
    out = tmp_path / "quality-manifest.json"
    code = cli.main([
        "manifest", "--package-id", "cbc", "--producer-id", "cbp", "--version", "v0.1.0",
        "--gate-report", str(report), "--artifact", str(artifact),
        "--release-body", str(body), "--body-hash-scope", "base", "--out", str(out),
    ])
    assert code == 2
    assert not out.exists()


def test_manifest_gates_come_from_the_gate_report(tmp_path: Path) -> None:
    manifest = _build(tmp_path)
    expected = _report()["gates"]
    assert manifest["gates"] == expected


def _consumer_repo(root: Path) -> None:
    (root / "README.md").write_text("clean\n", encoding="utf-8")
    (root / "cbp.json").write_text(json.dumps({
        "schema_version": "1.0.8",
        "enable_encoding": True,
        "enable_coverage": False,
        "enable_dependency": False,
        "enable_comments": False,
        "enable_docs": False,
        "enable_binary": False,
        "enable_claims": False,
        "enable_custom": False,
        "enable_upgrade": False,
    }), encoding="utf-8")


def test_gate_report_generator_records_target_identity(tmp_path: Path) -> None:
    _consumer_repo(tmp_path)
    cbc_report = tmp_path / "cbc-gate.json"
    cbm_report = tmp_path / "cbm-gate.json"
    for package, path in (("cbc", cbc_report), ("cbm", cbm_report)):
        code = cli.main([
            "--root", str(tmp_path), "--mode", "audit", "--report-json", str(path),
            "--package-id", package, "--producer-id", "cbp", "--version", "v0.1.0",
        ])
        assert code == 0
    cbc = json.loads(cbc_report.read_text(encoding="utf-8"))
    cbm = json.loads(cbm_report.read_text(encoding="utf-8"))
    assert (cbc["package_id"], cbc["producer_id"], cbc["version"]) == ("cbc", "cbp", "v0.1.0")
    assert (cbm["package_id"], cbm["producer_id"], cbm["version"]) == ("cbm", "cbp", "v0.1.0")
    assert cbc_report.read_bytes() != cbm_report.read_bytes()
