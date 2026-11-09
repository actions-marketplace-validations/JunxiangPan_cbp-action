"""Release preflight: RC artifact provenance and tag/run consistency."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools import release_preflight as rp


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, str, str]:
    rc = tmp_path / "rc"
    artifact = tmp_path / "artifact"
    (artifact / "docs").mkdir(parents=True)
    rc.mkdir()
    wheel = rc / "cbp_action-1.2.0-py3-none-any.whl"
    sdist = rc / "cbp_action-1.2.0.tar.gz"
    wheel.write_bytes(b"wheel-bytes")
    sdist.write_bytes(b"sdist-bytes")
    wheel_hash = _sha(wheel.read_bytes())
    sdist_hash = _sha(sdist.read_bytes())
    (rc / "RC_ASSETS.sha256").write_text(
        f"{wheel_hash}  dist/{wheel.name}\n{sdist_hash}  dist/{sdist.name}\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.2.0",
        "gate_status": "PASS",
        "applicable_gate_count": 1,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [{"name": "encoding", "status": "PASS", "reason": ""}],
        "artifact_hashes": {wheel.name: wheel_hash},
        "release_body_hash": "a" * 64,
        "evidence_sha256": "b" * 64,
        "body_hash_scope": "base",
        "ci_commit_sha": "a" * 40,
        "artifact_repository": {
            "repository": "JunxiangPan/cbp-action",
            "run_id": "42602640952",
            "artifact_name": "cbp-rc",
        },
    }
    manifest_path = artifact / "quality-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (artifact / "quality-manifest.json.sha256").write_text(
        f"{_sha(manifest_path.read_bytes())}  quality-manifest.json\n", encoding="utf-8"
    )
    (artifact / "docs" / "RELEASE_NOTES.generated.md").write_text(
        "## CBP 1.2.0\n\nQUALITY_COUNTS: 9/9\n", encoding="utf-8"
    )
    return rc, artifact, wheel_hash, sdist_hash


def _argv(rc: Path, artifact: Path, wheel_hash: str, sdist_hash: str, **overrides) -> list[str]:
    values = {
        "--rc-run-id": "100",
        "--ci-run-id": "200",
        "--tag": "v1.2.0",
        "--repository": "owner/repo",
        "--rc-dir": str(rc),
        "--artifact-dir": str(artifact),
        "--tag-commit": "a" * 40,
        "--rc-head": "a" * 40,
        "--ci-head": "a" * 40,
        "--expected-wheel-sha256": wheel_hash,
        "--expected-sdist-sha256": sdist_hash,
    }
    values.update(overrides)
    argv = []
    for key, value in values.items():
        argv.extend([key, value])
    return argv


def test_preflight_ok(tmp_path: Path, capsys) -> None:
    rc, artifact, wheel_hash, sdist_hash = _fixture(tmp_path)
    assert rp.main(_argv(rc, artifact, wheel_hash, sdist_hash)) == 0
    assert "PREFLIGHT_OK" in capsys.readouterr().out


def test_wrong_wheel_hash_is_exit_3(tmp_path: Path) -> None:
    rc, artifact, wheel_hash, sdist_hash = _fixture(tmp_path)
    assert rp.main(_argv(rc, artifact, "0" * 64, sdist_hash)) == 3


def test_wrong_sdist_hash_is_exit_3(tmp_path: Path) -> None:
    rc, artifact, wheel_hash, sdist_hash = _fixture(tmp_path)
    assert rp.main(_argv(rc, artifact, wheel_hash, "0" * 64)) == 3


def test_commit_mismatch_is_exit_3(tmp_path: Path) -> None:
    rc, artifact, wheel_hash, sdist_hash = _fixture(tmp_path)
    argv = _argv(rc, artifact, wheel_hash, sdist_hash)
    argv[argv.index("--rc-head") + 1] = "b" * 40
    assert rp.main(argv) == 3


def test_preflight_accepts_a_manifest_that_needs_reminting(tmp_path: Path, capsys) -> None:
    rc, artifact, wheel_hash, sdist_hash = _fixture(tmp_path)
    manifest_path = artifact / "quality-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["artifact_hashes"] = {"cbp_action-1.2.0-py3-none-any.whl": "0" * 64}
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    (artifact / "quality-manifest.json.sha256").write_text(
        f"{_sha(manifest_path.read_bytes())}  quality-manifest.json\n", encoding="utf-8"
    )
    assert rp.main(_argv(rc, artifact, wheel_hash, sdist_hash)) == 0
    assert "PREFLIGHT_OK" in capsys.readouterr().out
