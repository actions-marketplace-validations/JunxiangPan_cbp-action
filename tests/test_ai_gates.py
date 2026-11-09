"""Audit-only AI gates: E2E for missing, tampered, extra inputs."""
from pathlib import Path
import json
from cbp import ai_gates


def test_ai_release_missing_fails(tmp_path: Path) -> None:
    result = ai_gates.ai_release(tmp_path, "v1.0.7")
    assert result.status == "FAIL"
    assert any("release body missing" in item for item in result.findings)


def test_ai_release_tampered_version_fails(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.7"\n', encoding="utf-8")
    (tmp_path / "docs" / "RELEASE_BODY.md").write_text("wrong v9.9.9", encoding="utf-8")
    (tmp_path / "docs" / "RELEASE_NOTES.generated.md").write_text("x", encoding="utf-8")
    (tmp_path / "dist" / "RELEASE_ASSETS.sha256").write_text("abc *a.whl\n", encoding="utf-8")
    result = ai_gates.ai_release(tmp_path, "v1.0.7")
    assert result.status == "FAIL"
    assert any("does not name" in item for item in result.findings)


def test_ai_test_missing_assert_warns(tmp_path: Path, monkeypatch) -> None:
    test_file = tmp_path / "tests" / "test_bad.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_bad():\n    print('x')\n", encoding="utf-8")
    monkeypatch.setattr(ai_gates, "_git", lambda *a, **k: "tests/test_bad.py\n")
    result = ai_gates.ai_test(tmp_path, "HEAD")
    assert result.status == "WARN"
    assert any("no assert" in item for item in result.findings)


def test_ai_test_tautology_warns(tmp_path: Path, monkeypatch) -> None:
    test_file = tmp_path / "tests" / "test_bad.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_bad():\n    assert True\n", encoding="utf-8")
    monkeypatch.setattr(ai_gates, "_git", lambda *a, **k: "tests/test_bad.py\n")
    result = ai_gates.ai_test(tmp_path, "HEAD")
    assert "WARN" in result.status


def test_ai_change_without_baseline_skips(tmp_path: Path) -> None:
    assert ai_gates.ai_change(tmp_path, "").status == "SKIP"


def test_sarif_stable() -> None:
    result = ai_gates.GateResult("ai-test", "WARN", ["x"])
    doc = ai_gates.sarif(result)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"][0]["ruleId"] == "CBP-AI-001"
