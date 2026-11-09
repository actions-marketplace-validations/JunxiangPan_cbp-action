"""Manifest remint: CI gate evidence, RC artifact hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import remint_manifest as rm


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, list[Path]]:
    wheel = tmp_path / "cbp_action-1.2.0-py3-none-any.whl"
    sdist = tmp_path / "cbp_action-1.2.0.tar.gz"
    wheel.write_bytes(b"rc-wheel")
    sdist.write_bytes(b"rc-sdist")
    manifest = {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.2.0",
        "gate_status": "PASS",
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [{"name": "encoding", "status": "PASS", "reason": ""}],
        "artifact_hashes": {
            "cbp_action-1.2.0-py3-none-any.whl": "a" * 64,
            "cbp_action-1.2.0.tar.gz": "b" * 64,
        },
        "release_body_hash": "c" * 64,
        "artifact_repository": {
            "repository": "JunxiangPan/cbp-action",
            "run_id": "42602640952",
            "artifact_name": "cbp-rc",
        },
        "evidence_sha256": "d" * 64,
        "body_hash_scope": "base",
        "ci_run_id": "42602640952",
        "ci_commit_sha": "843171239c14b63731c507357a594dd3e4143a90",
    }
    path = tmp_path / "quality-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    body = tmp_path / "RELEASE_BODY.md"
    body.write_text("# release\n\nbody\n", encoding="utf-8", newline="\n")
    return path, wheel, [wheel, sdist]


def test_remint_replaces_artifact_hashes_and_keeps_gate_evidence(tmp_path: Path) -> None:
    path, wheel, artifacts = _fixture(tmp_path)
    original = json.loads(path.read_text(encoding="utf-8"))
    updated = rm.remint(original, artifacts)
    assert updated["artifact_hashes"] == {
        "cbp_action-1.2.0-py3-none-any.whl": _sha(wheel.read_bytes()),
        "cbp_action-1.2.0.tar.gz": _sha((tmp_path / "cbp_action-1.2.0.tar.gz").read_bytes()),
    }
    assert updated["gate_status"] == original["gate_status"]
    assert updated["release_body_hash"] == original["release_body_hash"]
    assert updated["ci_run_id"] == original["ci_run_id"]
    assert updated["ci_commit_sha"] == original["ci_commit_sha"]
    assert updated["evidence_sha256"] != original["evidence_sha256"]
    unsigned = {k: v for k, v in updated.items() if k != "evidence_sha256"}
    assert updated["evidence_sha256"] == rm.canonical_sha256(unsigned)


def test_check_only_rejects_unreminted_manifest(tmp_path: Path, capsys) -> None:
    path, _wheel, artifacts = _fixture(tmp_path)
    argv = ["--manifest", str(path), "--check-only"]
    for artifact in artifacts:
        argv += ["--artifact", str(artifact)]
    assert rm.main(argv) == 3
    assert "REMIT_FAIL" in capsys.readouterr().err


def test_remint_then_check_only_passes(tmp_path: Path, capsys) -> None:
    path, _wheel, artifacts = _fixture(tmp_path)
    argv = ["--manifest", str(path), "--out", str(path)]
    for artifact in artifacts:
        argv += ["--artifact", str(artifact)]
    assert rm.main(argv) == 0
    check = ["--manifest", str(path), "--check-only"]
    for artifact in artifacts:
        check += ["--artifact", str(artifact)]
    assert rm.main(check) == 0
    assert "REMIT_OK" in capsys.readouterr().out


def test_missing_artifact_is_exit_2(tmp_path: Path) -> None:
    path, _wheel, _artifacts = _fixture(tmp_path)
    assert rm.main(["--manifest", str(path), "--artifact", str(tmp_path / "missing.whl")]) == 2


def test_remint_recomputes_body_hash(tmp_path: Path) -> None:
    path, _wheel, artifacts = _fixture(tmp_path)
    body = tmp_path / "RELEASE_BODY.md"
    body.write_text("# release\n\nbody\n", encoding="utf-8", newline="\n")
    before = json.loads(path.read_text(encoding="utf-8"))["release_body_hash"]
    argv = ["--manifest", str(path), "--release-body", str(body)]
    for artifact in artifacts:
        argv += ["--artifact", str(artifact)]
    assert rm.main(argv) == 0
    after = json.loads(path.read_text(encoding="utf-8"))["release_body_hash"]
    assert after != before
    assert after == rm.canonical_body_hash(body.read_bytes())


def test_remint_rejects_missing_body(tmp_path: Path) -> None:
    path, _wheel, artifacts = _fixture(tmp_path)
    argv = ["--manifest", str(path), "--release-body", str(tmp_path / "missing.md")]
    for artifact in artifacts:
        argv += ["--artifact", str(artifact)]
    assert rm.main(argv) == 2


def test_remint_preserves_artifact_hashes(tmp_path: Path) -> None:
    path, wheel, artifacts = _fixture(tmp_path)
    body = tmp_path / "RELEASE_BODY.md"
    updated = rm.remint(
        json.loads(path.read_text(encoding="utf-8")), artifacts, body.read_bytes()
    )
    assert updated["artifact_hashes"] == {
        "cbp_action-1.2.0-py3-none-any.whl": _sha(wheel.read_bytes()),
        "cbp_action-1.2.0.tar.gz": _sha((tmp_path / "cbp_action-1.2.0.tar.gz").read_bytes()),
    }


def test_commit_mismatch_is_exit_3(tmp_path: Path) -> None:
    path, _wheel, artifacts = _fixture(tmp_path)
    argv = ["--manifest", str(path), "--expect-commit", "f" * 40]
    for artifact in artifacts:
        argv += ["--artifact", str(artifact)]
    assert rm.main(argv) == 3
