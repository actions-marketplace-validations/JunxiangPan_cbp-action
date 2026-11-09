"""Coverage for CLI utility branches and the claims gate array format."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cbp import claims_gate, cli
from cbp.config import GateConfig


def test_policy_test_subcommand_runs_in_process(tmp_path: Path, capsys) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"cases": [{
        "name": "hit",
        "cel": 'files.exists(t, t.matches(".*secret.*"))',
        "files": {"a": "secret"},
        "expect": True,
    }]}), encoding="utf-8")
    assert cli.main(["policy", "test", str(fixture)]) == 0
    assert "POLICY_TEST=PASS" in capsys.readouterr().out


def test_changed_files_returns_empty_when_git_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no git")))
    assert cli._changed_files(tmp_path, "HEAD") == set()


def test_claims_gate_reads_a_gate_array(tmp_path: Path) -> None:
    manifest = tmp_path / "quality-manifest.json"
    manifest.write_text(json.dumps({"gates": [
        {"name": "a", "status": "PASS"},
        {"name": "b", "status": "PASS"},
    ]}), encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("QUALITY_COUNTS: 2/2\nAll 2 gates are active.\n", encoding="utf-8")
    cfg = GateConfig(root=tmp_path, claims_manifest=manifest, claims_notes=notes)
    passed, detail = claims_gate.run(cfg)
    assert passed is True
    assert detail == "claims=2/2"


def test_claims_gate_array_skips_count_as_not_passed(tmp_path: Path) -> None:
    manifest = tmp_path / "quality-manifest.json"
    manifest.write_text(json.dumps({"gates": [
        {"name": "a", "status": "PASS"},
        {"name": "b", "status": "SKIPPED"},
    ]}), encoding="utf-8")
    notes = tmp_path / "notes.md"
    notes.write_text("QUALITY_COUNTS: 1/2\nAll 2 gates are active.\n", encoding="utf-8")
    cfg = GateConfig(root=tmp_path, claims_manifest=manifest, claims_notes=notes)
    passed, detail = claims_gate.run(cfg)
    assert passed is True
    assert detail == "claims=1/2"
