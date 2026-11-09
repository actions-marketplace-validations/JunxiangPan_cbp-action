"""Explicit, per-file encoding allowlist for BOM-requiring legacy scripts."""
from __future__ import annotations

import codecs
import subprocess
from pathlib import Path

from cbp.config import GateConfig
from cbp.encoding_gate import run


def _cfg(root: Path, entries: list[dict]) -> GateConfig:
    return GateConfig(root=root, encoding_allowlist=tuple(entries))


def test_allowlisted_bom_file_passes_and_is_counted(tmp_path: Path) -> None:
    (tmp_path / "legacy.ps1").write_bytes(codecs.BOM_UTF8 + b"Write-Host 'ok'\n")
    passed, detail = run(_cfg(tmp_path, [{"path": "legacy.ps1", "reason": "PS 5.1 + CJK requires BOM"}]))
    assert passed is True
    assert "allowlisted=1" in detail
    assert "legacy.ps1" in detail


def test_bom_without_an_entry_still_fails(tmp_path: Path) -> None:
    (tmp_path / "legacy.ps1").write_bytes(codecs.BOM_UTF8 + b"x\n")
    passed, detail = run(_cfg(tmp_path, []))
    assert passed is False
    assert "UTF-8 BOM" in detail


def test_entry_requires_a_path_and_reason(tmp_path: Path) -> None:
    (tmp_path / "legacy.ps1").write_bytes(codecs.BOM_UTF8 + b"x\n")
    passed, detail = run(_cfg(tmp_path, [{"path": "legacy.ps1", "reason": "  "}]))
    assert passed is False
    assert "reason: a non-empty reason is required" in detail


def test_wildcards_are_rejected(tmp_path: Path) -> None:
    passed, detail = run(_cfg(tmp_path, [{"path": "*.ps1", "reason": "all scripts"}]))
    assert passed is False
    assert "wildcards are not allowed" in detail


def test_absolute_paths_are_rejected(tmp_path: Path) -> None:
    passed, detail = run(_cfg(tmp_path, [{"path": str(tmp_path / "a.ps1"), "reason": "x"}]))
    assert passed is False
    assert "absolute path is not allowed" in detail


def test_stale_entry_fails(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("ok\n", encoding="utf-8")
    passed, detail = run(_cfg(tmp_path, [{"path": "missing.ps1", "reason": "stale"}]))
    assert passed is False
    assert "matches no tracked text file" in detail


def test_allowlisted_file_without_bom_is_reported_unused(tmp_path: Path) -> None:
    (tmp_path / "plain.ps1").write_text("Write-Host 'ok'\n", encoding="utf-8")
    passed, detail = run(_cfg(tmp_path, [{"path": "plain.ps1", "reason": "kept for history"}]))
    assert passed is True
    assert "allowlist_unused=1" in detail


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    passed, detail = run(_cfg(tmp_path, [{"path": "a.ps1", "reason": "x", "mode": "warn"}]))
    assert passed is False
    assert "unexpected key" in detail


def test_duplicate_entry_is_rejected(tmp_path: Path) -> None:
    entry = {"path": "a.ps1", "reason": "x"}
    passed, detail = run(_cfg(tmp_path, [entry, dict(entry)]))
    assert passed is False
    assert "duplicate allowlist entry" in detail


def test_allowlist_must_be_an_array(tmp_path: Path) -> None:
    cfg = GateConfig(root=tmp_path, encoding_allowlist="not-a-list")  # type: ignore[arg-type]
    passed, detail = run(cfg)
    assert passed is False
    assert "must be an array" in detail


def test_entry_must_be_an_object(tmp_path: Path) -> None:
    cfg = GateConfig(root=tmp_path, encoding_allowlist=("string",))  # type: ignore[arg-type]
    passed, detail = run(cfg)
    assert passed is False
    assert "must be an object" in detail


def test_entry_requires_a_path(tmp_path: Path) -> None:
    passed, detail = run(_cfg(tmp_path, [{"reason": "x"}]))
    assert passed is False
    assert "path: a relative path is required" in detail


def test_dot_slash_prefix_is_normalized(tmp_path: Path) -> None:
    (tmp_path / "legacy.ps1").write_bytes(codecs.BOM_UTF8 + b"x\n")
    passed, detail = run(_cfg(tmp_path, [{"path": "./legacy.ps1", "reason": "PS 5.1"}]))
    assert passed is True
    assert "allowlisted=1" in detail


def test_git_failure_falls_back_to_a_filesystem_walk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("no git")))
    (tmp_path / "a.md").write_text("ok\n", encoding="utf-8")
    passed, detail = run(GateConfig(root=tmp_path))
    assert passed is True
    assert "encoding=1" in detail


def test_utf16_bom_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_bytes(codecs.BOM_UTF16_LE + b"x\x00")
    passed, detail = run(GateConfig(root=tmp_path))
    assert passed is False
    assert "UTF-16 BOM" in detail
