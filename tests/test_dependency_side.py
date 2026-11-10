"""Dependency-side controls: lock integrity, pins, tag immutability helper."""
from __future__ import annotations

import hashlib
from pathlib import Path

from cbp import dependency_gate
from cbp.config import GateConfig
from tools import tag_immutability


def _lock(tmp_path: Path) -> tuple[GateConfig, Path]:
    lock = tmp_path / "requirements.lock"
    lock.write_text("requests==2.0\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    (tmp_path / "install.sh").write_text("python -m pip install --require-hashes -r requirements.lock\n", encoding="utf-8")
    return GateConfig(root=tmp_path, dependency_lock="requirements.lock", install_command="install.sh"), lock


def test_lock_without_sidecar_passes(tmp_path: Path) -> None:
    cfg, _ = _lock(tmp_path)
    assert dependency_gate.run(cfg)[0] is True


def test_lock_sidecar_detects_change(tmp_path: Path) -> None:
    cfg, lock = _lock(tmp_path)
    (tmp_path / "requirements.lock.sha256").write_text(hashlib.sha256(lock.read_bytes()).hexdigest() + "  requirements.lock\n", encoding="utf-8")
    assert dependency_gate.run(cfg)[0] is True
    lock.write_text("requests==3.0\n    --hash=sha256:" + "b" * 64 + "\n", encoding="utf-8")
    assert dependency_gate.run(cfg)[0] is False


def test_tag_immutability_detects_moved_tag() -> None:
    expected = {"v1.2.2": "d4bfefbd5f66c6bbdb74549b37f1f187fcb61924"}
    assert tag_immutability.diff(expected, expected) == []
    moved = dict(expected, **{"v1.2.2": "0" * 40})
    assert tag_immutability.diff(expected, moved)
