"""End-to-end CLI wiring tests: no library-only functions allowed."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "cbp.cli", *args], cwd=cwd, capture_output=True, text=True, env=env)


def test_policy_test_is_reachable_from_cli(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"cases": [{
        "name": "hit", "cel": 'files.exists(t, t.matches(".*secret.*"))',
        "files": {"a": "secret"}, "expect": True,
    }]}), encoding="utf-8")
    result = _run(["policy", "test", str(fixture)], tmp_path)
    assert result.returncode == 0, result.stderr
    assert "POLICY_TEST=PASS" in result.stdout


def test_packs_only_repository_triggers_custom_gate(tmp_path: Path) -> None:
    import hashlib
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({
        "name": "baseline", "version": "1.0.0",
        "rules": [{"name": "pack-rule", "pattern": "print", "files": ["*.py"],
                   "message": "pack hit", "mode": "enforce", "max_matches": 1}],
    }), encoding="utf-8")
    digest = hashlib.sha256(pack.read_bytes()).hexdigest()
    (tmp_path / "a.py").write_text("print('x')\n", encoding="utf-8")
    (tmp_path / "cbp.json").write_text(json.dumps({
        "schema_version": "1.0.0", "enable_claims": False,
        "packs": [{"path": "pack.json", "sha256": digest}],
    }), encoding="utf-8")
    result = _run(["--root", str(tmp_path)], tmp_path)
    assert result.returncode == 3
    assert "custom: FAIL" in result.stdout
    assert "pack hit" in result.stdout


def test_claims_rejects_wrong_release_version_from_cli(tmp_path: Path) -> None:
    import hashlib
    wheel = tmp_path / "cbp_action-9.9.9-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    (tmp_path / "quality-manifest.json").write_text(json.dumps({"counts": {"passed": 1, "total": 1}}), encoding="utf-8")
    (tmp_path / "notes.md").write_text("QUALITY_COUNTS: 1/1\n", encoding="utf-8")
    (tmp_path / "body.md").write_text(
        "All 1 gates are active.\nQUALITY_COUNTS: 1/1\n"
        "wrong version v9.9.9\n" + digest + "\n"
        "https://pypi.org/project/cbp-action/9.9.9/\n", encoding="utf-8")
    (tmp_path / "cbp.json").write_text(json.dumps({
        "schema_version": "1.0.1", "enable_claims": True,
        "claims_manifest": "quality-manifest.json", "claims_notes": "notes.md",
        "release_body": "body.md", "release_version": "1.0.2",
        "release_artifact": wheel.name, "pypi_project": "cbp-action",
        "enable_encoding": False, "enable_coverage": False, "enable_dependency": False,
        "enable_comments": False, "enable_docs": False, "enable_custom": False,
        "enable_upgrade": False, "enable_binary": False,
    }), encoding="utf-8")
    result = _run(["--root", str(tmp_path)], tmp_path)
    assert result.returncode == 3
    assert "must name version 1.0.2" in result.stdout
