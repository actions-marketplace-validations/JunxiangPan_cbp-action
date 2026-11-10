"""Tampering a gate script or workflow must fail the self-protection check."""
from __future__ import annotations

import shutil
from pathlib import Path

from tools import verify_gate_manifest as vg

ROOT = Path(__file__).resolve().parents[1]


def _copy_repo(tmp_path: Path) -> Path:
    target = tmp_path / "repo"
    target.mkdir()
    manifest = (ROOT / "quality/GATES.sha256").read_text(encoding="utf-8")
    rels = ["quality/GATES.sha256"] + [line.split(None, 1)[1] for line in manifest.splitlines() if line.strip()]
    for rel in rels:
        source = ROOT / rel
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return target


def test_clean_manifest_passes(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    assert vg.verify(root / "quality/GATES.sha256", root) == []


def test_coverage_gate_tamper_is_detected(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    path = root / "src/cbp/coverage_gate.py"
    path.write_text(path.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
    assert any("coverage_gate.py" in item for item in vg.verify(root / "quality/GATES.sha256", root))


def test_claims_gate_tamper_is_detected(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    path = root / "src/cbp/claims_gate.py"
    path.write_text(path.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
    assert any("claims_gate.py" in item for item in vg.verify(root / "quality/GATES.sha256", root))


def test_workflow_tamper_is_detected(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    path = root / ".github/workflows/ci.yml"
    path.write_text(path.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
    assert any("ci.yml" in item for item in vg.verify(root / "quality/GATES.sha256", root))
