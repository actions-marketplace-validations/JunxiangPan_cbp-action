"""Strict profile is opt-in and does not alter the default path."""
from __future__ import annotations

import json
from pathlib import Path

from cbp import strict_profile
from cbp.cli import main as cli_main


def _root(tmp: Path) -> Path:
    (tmp / "docs/1.3.0").mkdir(parents=True)
    (tmp / "docs/1.3.0/MUTATION_REPORT.md").write_text("- recall: 100.00%\n", encoding="utf-8")
    (tmp / "tests/hostile").mkdir(parents=True)
    (tmp / "tests/hostile/corpus.json").write_text(
        json.dumps([{"id": str(i), "expect": "FAIL"} for i in range(50)]), encoding="utf-8"
    )
    (tmp / "docs/1.5.0").mkdir(parents=True)
    report = tmp / "docs/1.5.0/mutation-report.json"
    report.write_text(json.dumps({"score": 0.96, "changed_code_score": 0.95}), encoding="utf-8")
    (tmp / "docs/1.5.0/mutation-report.json.sha256").write_text(
        __import__("hashlib").sha256(report.read_bytes()).hexdigest() + "  mutation-report.json\n",
        encoding="utf-8",
    )
    (tmp / "docs/1.5.0").mkdir(parents=True, exist_ok=True)
    (tmp / "docs/1.5.0/SBOM.json").write_text(
        json.dumps({"bomFormat": "CycloneDX", "components": [{"name": "x"}]}), encoding="utf-8"
    )
    (tmp / ".github/workflows").mkdir(parents=True)
    (tmp / ".github/workflows/ci.yml").write_text("runs-on: windows-latest\n", encoding="utf-8")
    (tmp / "docs/tags-expected.json").write_text(json.dumps({"v1.0.0": "a" * 40}), encoding="utf-8")
    (tmp / "quality").mkdir()
    (tmp / "quality/GATES.sha256").write_text("", encoding="utf-8")
    (tmp / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp / "provenance.json").write_text("{}", encoding="utf-8")
    return tmp


def _options(root: Path) -> strict_profile.StrictOptions:
    return strict_profile.StrictOptions(
        root=root,
        manifest=Path("manifest.json"),
        provenance=Path("provenance.json"),
        bundle_dir=Path("signatures"),
        artifacts=(Path("a.whl"),),
        identity_regexp="identity",
    )


def _mock_all(monkeypatch, status: str = "SIGNED") -> None:
    monkeypatch.setattr(strict_profile, "_gate_manifest_problems", lambda *args: [])
    monkeypatch.setattr(strict_profile.artifact_integrity, "action_pin_findings", lambda *args: [])
    monkeypatch.setattr(strict_profile.dependency_gate, "run", lambda *args: (True, "locked"))
    monkeypatch.setattr(strict_profile, "_tag_diff", lambda *args: [])
    monkeypatch.setattr(strict_profile, "_actual_tags", lambda root, tags: {"v1.0.0": "a" * 40})
    monkeypatch.setattr(strict_profile.provenance, "verify", lambda *args, **kwargs: {"status": status, "problems": []})


def test_strict_passes_with_all_evidence(tmp_path: Path, monkeypatch, capsys) -> None:
    root = _root(tmp_path)
    _mock_all(monkeypatch)
    assert strict_profile.run(_options(root)) == 0
    report = json.loads((root / "strict-profile.json").read_text(encoding="utf-8"))
    assert report["profile"] == "strict"
    assert report["passed"] is True
    assert {item["name"] for item in report["checks"]} >= {
        "gates_sha256", "mutation", "hostile_corpus", "fuzz", "action_pins",
        "lockfile", "tag_immutability", "windows", "sbom", "provenance", "target_mutation",
    }


def test_strict_fails_when_provenance_is_unsigned(tmp_path: Path, monkeypatch) -> None:
    root = _root(tmp_path)
    _mock_all(monkeypatch, status="BLOCKED_NO_SIGNING_IDENTITY")
    assert strict_profile.run(_options(root)) == 3
    report = json.loads((root / "strict-profile.json").read_text(encoding="utf-8"))
    assert any(item["name"] == "provenance" and item["status"] == "FAIL" for item in report["checks"])


def test_strict_cli_requires_identity(tmp_path: Path) -> None:
    root = _root(tmp_path)
    assert cli_main(["--root", str(root), "--profile", "strict"]) == 2
