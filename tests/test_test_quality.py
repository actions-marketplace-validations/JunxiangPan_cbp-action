"""Opt-in test-quality gate: weak assertions, empty skips, deleted tests."""
from __future__ import annotations

import json
from pathlib import Path

from cbp import test_quality


def _write(tmp: Path, name: str, text: str) -> Path:
    path = tmp / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_good_test_file_passes(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_good.py", "def test_a():\n    assert 1 == 1\n")
    result = test_quality.run(test_quality.TestQualityOptions(root=tmp_path))
    assert result["status"] == "PASS"


def test_assert_true_and_no_assert_fail(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_bad.py", "def test_a():\n    assert True\n\ndef test_b():\n    pass\n")
    result = test_quality.run(test_quality.TestQualityOptions(root=tmp_path))
    assert result["status"] == "FAIL"
    assert any("assert True" in item for item in result["findings"])
    assert any("no assertion" in item for item in result["findings"])


def test_empty_skip_fails(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_skip.py", "import pytest\n\ndef test_a():\n    pytest.skip()\n")
    result = test_quality.run(test_quality.TestQualityOptions(root=tmp_path))
    assert any("skip without a reason" in item for item in result["findings"])


def test_deleted_test_is_detected(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a():\n    assert True is False\n")
    (tmp_path / "tests/test_baseline.json").write_text(json.dumps({"tests": ["test_a", "test_b"]}), encoding="utf-8")
    result = test_quality.run(test_quality.TestQualityOptions(root=tmp_path, baseline=Path("tests/test_baseline.json")))
    assert any("test deleted: test_b" in item for item in result["findings"])


def test_generic_language_adapter(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_x.js", "test('x', () => { expect(1).toBe(1); });\n")
    result = test_quality.run(test_quality.TestQualityOptions(root=tmp_path, language="generic"))
    assert result["status"] == "PASS"
