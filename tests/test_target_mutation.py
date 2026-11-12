"""Opt-in target-mutation gate: report hash, thresholds, command."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cbp import target_mutation


def _report(tmp: Path, score: float = 0.96, changed: float = 0.95) -> Path:
    path = tmp / "mutation-report.json"
    path.write_text(json.dumps({"score": score, "changed_code_score": changed}), encoding="utf-8")
    (tmp / "mutation-report.json.sha256").write_text(
        hashlib.sha256(path.read_bytes()).hexdigest() + "  mutation-report.json\n", encoding="utf-8"
    )
    return path


def _options(tmp: Path, path: Path, **kwargs) -> target_mutation.MutationOptions:
    return target_mutation.MutationOptions(root=tmp, report=Path(path.name), **kwargs)


def test_valid_report_passes(tmp_path: Path) -> None:
    path = _report(tmp_path)
    assert target_mutation.run(_options(tmp_path, path))["status"] == "PASS"


def test_low_score_fails(tmp_path: Path) -> None:
    path = _report(tmp_path, score=0.8)
    assert target_mutation.run(_options(tmp_path, path))["status"] == "FAIL"


def test_wrong_report_hash_fails(tmp_path: Path) -> None:
    path = _report(tmp_path)
    assert target_mutation.run(_options(tmp_path, path, expected_sha256="0" * 64))["status"] == "FAIL"


def test_command_failure_fails(tmp_path: Path) -> None:
    path = _report(tmp_path)
    assert target_mutation.run(_options(tmp_path, path, command="python -c 'raise SystemExit(2)'"))["status"] == "FAIL"
