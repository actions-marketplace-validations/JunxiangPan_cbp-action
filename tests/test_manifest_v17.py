"""Quality manifest v1.7 fields and the publish gate pass requirement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cbp import report_schema
from tools import dogfood_manifest as dog
from tools import verify_manifest_artifact as vma


def _all_pass() -> list[dict]:
    return [dog._gate_entry(name, "PASS") for name in report_schema.ALL_GATES]


def _manifest(**overrides) -> dict:
    values = {
        "version": "v1.1.0",
        "run_id": "4242",
        "commit_sha": "a" * 40,
        "gate_status": "PASS",
        "gates": _all_pass(),
        "artifact_hashes": {"cbp_action-1.1.0-py3-none-any.whl": "b" * 64},
        "release_body_hash": "c" * 64,
    }
    values.update(overrides)
    return dog._manifest_document(**values)


def test_manifest_has_the_contract_fields() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "1"
    assert manifest["package_id"] == "cbp"
    assert manifest["producer_id"] == "cbp"
    assert manifest["applicable_gate_count"] == 9
    assert manifest["skip_count"] == 0
    assert manifest["skip_ratio"] == 0.0
    assert manifest["blocking_skip"] is False
    assert [entry["name"] for entry in manifest["gates"]] == list(report_schema.ALL_GATES)
    assert manifest["artifact_hashes"] == {"cbp_action-1.1.0-py3-none-any.whl": "b" * 64}


def test_manifest_validates_for_actions() -> None:
    manifest = _manifest()
    assert dog.validate_manifest(manifest, actions=True) == []


def test_forced_skip_sets_blocking_skip() -> None:
    gates = [dog._gate_entry(name, "SKIPPED" if name == "claims" else "PASS") for name in report_schema.ALL_GATES]
    manifest = _manifest(gate_status="FAIL", gates=gates)
    assert manifest["blocking_skip"] is True
    assert manifest["skip_count"] == 1
    assert manifest["skip_ratio"] == pytest.approx(1 / 9)


def test_evidence_hash_is_canonical_and_deterministic() -> None:
    manifest = _manifest()
    payload = {key: value for key, value in manifest.items() if key != "evidence_sha256"}
    first = dog._canonical_sha(payload)
    second = dog._canonical_sha(dict(reversed(list(payload.items()))))
    assert first == second
    assert len(first) == 64


def _write_artifact(tmp_path: Path, manifest: dict) -> tuple[Path, Path, Path]:
    manifest_path = tmp_path / "quality-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    hash_path = tmp_path / "quality-manifest.json.sha256"
    hash_path.write_text(digest + "  quality-manifest.json\n", encoding="utf-8")
    passed = sum(1 for entry in manifest["gates"] if entry["status"] == "PASS")
    notes = tmp_path / "notes.md"
    notes.write_text(f"QUALITY_COUNTS: {passed}/{len(manifest['gates'])}\nAll 9 gates are active.\n", encoding="utf-8")
    return manifest_path, hash_path, notes


def test_require_gate_pass_accepts_a_pass_manifest(tmp_path: Path) -> None:
    manifest = _manifest()
    paths = _write_artifact(tmp_path, manifest)
    result = vma.verify(*paths, "4242", "a" * 40, require_gate_pass=True)
    assert result["gate_status"] == "PASS"


def test_require_gate_pass_rejects_skipped_infra(tmp_path: Path) -> None:
    gates = [dog._gate_entry(name, "PASS") for name in report_schema.ALL_GATES]
    manifest = _manifest(gate_status="SKIPPED_INFRA", gates=gates)
    paths = _write_artifact(tmp_path, manifest)
    with pytest.raises(vma.ArtifactError, match="publish requires gate_status PASS"):
        vma.verify(*paths, "4242", "a" * 40, require_gate_pass=True)


def test_require_gate_pass_rejects_skip_ratio_above_twenty_percent(tmp_path: Path) -> None:
    gates = [
        dog._gate_entry(name, "SKIPPED" if name in {"coverage", "dependency"} else "PASS")
        for name in report_schema.ALL_GATES
    ]
    manifest = _manifest(gate_status="PASS", gates=gates)
    assert manifest["skip_ratio"] > 0.20
    paths = _write_artifact(tmp_path, manifest)
    with pytest.raises(vma.ArtifactError, match="skip_ratio"):
        vma.verify(*paths, "4242", "a" * 40, require_gate_pass=True)


def test_require_gate_pass_rejects_blocking_skip(tmp_path: Path) -> None:
    gates = [dog._gate_entry(name, "SKIPPED" if name == "claims" else "PASS") for name in report_schema.ALL_GATES]
    manifest = _manifest(gate_status="FAIL", gates=gates)
    paths = _write_artifact(tmp_path, manifest)
    with pytest.raises(vma.ArtifactError, match="publish requires gate_status PASS"):
        vma.verify(*paths, "4242", "a" * 40, require_gate_pass=True)
