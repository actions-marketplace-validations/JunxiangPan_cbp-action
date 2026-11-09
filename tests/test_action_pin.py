"""Tag pins are rejected; full 40-hex commit pins are accepted."""
from __future__ import annotations

from pathlib import Path

from cbp import artifact_integrity
from cbp.config import GateConfig

FULL_SHA = "11d5960a326750d5838078e36cf38b85af677262"


def _workflow(root: Path, ref: str) -> None:
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "ci.yml").write_text(
        f"steps:\n  - uses: actions/checkout@{ref}\n", encoding="utf-8"
    )


def test_full_sha_pin_is_accepted(tmp_path: Path) -> None:
    _workflow(tmp_path, FULL_SHA)
    assert artifact_integrity.action_pin_findings(GateConfig(root=tmp_path)) == []


def test_tag_pin_is_rejected_with_a_reason(tmp_path: Path) -> None:
    _workflow(tmp_path, "v4")
    findings = artifact_integrity.action_pin_findings(GateConfig(root=tmp_path))
    assert findings
    assert "not pinned to a full SHA" in findings[0]
    assert "v4" in findings[0]


def test_usage_yml_is_not_scanned(tmp_path: Path) -> None:
    (tmp_path / "usage.yml").write_text("uses: actions/checkout@v4\n", encoding="utf-8")
    assert artifact_integrity.action_pin_findings(GateConfig(root=tmp_path)) == []
