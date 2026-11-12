"""PEP 440 prerelease support in manifests and reports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cbp import package_manifest, report_schema
from cbp.versioning import PEP440_PATTERN, normalize_version


def test_pep440_prerelease_acceptance() -> None:
    assert normalize_version("0.1.0rc1") == "v0.1.0rc1"
    assert normalize_version("v0.1.0rc1") == "v0.1.0rc1"
    assert normalize_version("1.2.3") == "v1.2.3"
    assert PEP440_PATTERN.fullmatch("0.1.0rc1")
    assert not PEP440_PATTERN.fullmatch("1.2")


def test_report_schema_accepts_prerelease() -> None:
    manifest = {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v0.1.0rc1",
        "gate_status": "PASS",
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [
            {"name": name, "status": "PASS", "reason": ""}
            for name in report_schema.ALL_GATES
        ],
        "artifact_hashes": {"x.whl": "a" * 64},
        "release_body_hash": "b" * 64,
        "evidence_sha256": "c" * 64,
    }
    assert report_schema.validate_manifest(manifest) == []


def _report(tmp: Path, version: str = "v0.1.0rc1") -> Path:
    gates = [
        {"name": name, "status": "PASS", "reason": ""}
        for name in report_schema.ALL_GATES
    ]
    path = tmp / "gate-report.json"
    path.write_text(json.dumps({
        "schema_version": "1", "package_id": "cbf", "producer_id": "cbf",
        "version": version, "gate_status": "PASS", "exit_code": 0,
        "applicable_gate_count": len(gates), "skip_count": 0, "skip_ratio": 0.0,
        "blocking_skip": False, "gates": gates,
    }), encoding="utf-8")
    return path


def test_subject_manifest_accepts_rc1(tmp_path: Path) -> None:
    artifact = tmp_path / "cbf-0.1.0rc1-py3-none-any.whl"
    artifact.write_bytes(b"cbf-wheel")
    body = tmp_path / "RELEASE_NOTES.md"
    body.write_text("release notes\n", encoding="utf-8")
    manifest = package_manifest.build_manifest(
        package_id="cbf", producer_id="cbf", version="0.1.0rc1",
        gate_report=_report(tmp_path), artifacts=[str(artifact)],
        release_body=body, body_hash_scope="base",
        artifact_sha256={artifact.name: hashlib.sha256(artifact.read_bytes()).hexdigest()},
    )
    assert manifest["version"] == "v0.1.0rc1"
    assert report_schema.validate_manifest(manifest, require_body_scope=True) == []


def test_cbf_rc1_subject_manifest_evidence_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "docs/1.5.1/cbf-0.1.0rc1-subject-manifest.json").read_text(encoding="utf-8"))
    assert data["version"] == "v0.1.0rc1"
    assert data["package_id"] == "cbf"
    assert data["producer_id"] == "cbf"
    assert data["artifact_hashes"]["cbf-0.1.0rc1-py3-none-any.whl"] == "3c8faa174fdfa5a6fcd69157f566dde7ac2b11bbd4d164b2ecb7badbe8190060"
