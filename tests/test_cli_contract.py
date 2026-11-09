"""CONTRACT v1.7 CLI exit codes: 0 pass, 2 input, 3 gate, 4 skip ratio."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cbp import cli, report_parser


def _write_docs_manifest(root: Path) -> None:
    digest = hashlib.sha256((root / "doc.md").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    (root / "docs-manifest.json").write_text(
        json.dumps({"files": [{"path": "doc.md", "sha256": digest}]}), encoding="utf-8"
    )


def _repo(tmp_path: Path, **overrides) -> Path:
    (tmp_path / "doc.md").write_text("stable documentation\n", encoding="utf-8")
    _write_docs_manifest(tmp_path)
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "quality-manifest.json").write_text(
        json.dumps({"counts": {"passed": 5, "total": 5}}), encoding="utf-8"
    )
    (tmp_path / "notes.md").write_text(
        "QUALITY_COUNTS: 5/5\nAll 5 gates are active.\n", encoding="utf-8"
    )
    config = {
        "schema_version": "1.0.8",
        "package_type": "cbp",
        "enable_encoding": True,
        "enable_coverage": False,
        "enable_dependency": False,
        "enable_comments": False,
        "enable_docs": True,
        "enable_binary": True,
        "enable_claims": True,
        "enable_custom": True,
        "enable_upgrade": False,
        "docs_manifest": "docs-manifest.json",
        "binary_artifacts": "artifacts",
        "claims_manifest": "quality-manifest.json",
        "claims_notes": "notes.md",
        "release_version": "1.0.9",
        "custom_rules": [{
            "name": "never_matches",
            "pattern": "CBP_NEVER_MATCH_9F3",
            "files": ["*.py"],
            "message": "never",
            "mode": "warn",
        }],
    }
    config.update(overrides)
    (tmp_path / "cbp.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


def _run(root: Path, *extra: str) -> int:
    return cli.main(["--root", str(root), "--config", str(root / "cbp.json"), *extra])


def test_contract_pass_exits_zero_and_writes_a_parseable_report(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    report = root / "report.json"
    assert _run(root, "--report-json", str(report)) == 0
    parsed = report_parser.parse_report(report)
    assert parsed.gate_status == "PASS"
    assert parsed.applicable_count == 5
    assert parsed.skip_ratio == 0.0
    assert "CBP_GATE_STATUS=PASS" in capsys.readouterr().out


def test_gate_failure_exits_three(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    (root / "doc.md").write_text("changed after the manifest\n", encoding="utf-8")
    report = root / "report.json"
    assert _run(root, "--report-json", str(report)) == 3
    parsed = report_parser.parse_report(report)
    assert parsed.gate_status == "FAIL"
    assert any(entry["name"] == "docs" and entry["status"] == "FAIL" for entry in parsed.gates)
    assert "CBP_EXIT_CODE=3" in capsys.readouterr().out


def test_forced_gate_skip_exits_three_with_blocking_skip(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path, custom_rules=[])
    report = root / "report.json"
    assert _run(root, "--report-json", str(report)) == 3
    parsed = report_parser.parse_report(report)
    assert parsed.blocking_skip is True
    assert parsed.gate_status == "FAIL"
    assert "CBP_BLOCKING_SKIP=true" in capsys.readouterr().out


def test_skip_ratio_over_threshold_exits_four(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path, enable_coverage=True, enable_dependency=True)
    report = root / "report.json"
    assert _run(root, "--report-json", str(report)) == 4
    parsed = report_parser.parse_report(report)
    assert parsed.gate_status == "FAIL"
    assert parsed.skip_count == 2
    assert parsed.applicable_count == 7
    assert parsed.skip_ratio > 0.20
    assert "CBP_EXIT_CODE=4" in capsys.readouterr().out


def test_input_error_exits_two(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path, unknown_key=True)
    assert _run(root) == 2
    assert "exit_code" in capsys.readouterr().out


def test_parse_report_accepts_a_valid_document(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    report = root / "report.json"
    assert _run(root, "--report-json", str(report)) == 0
    assert cli.main(["--parse-report", str(report)]) == 0


def test_parse_report_rejects_exit_three_without_gate_status(tmp_path: Path, capsys) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.0.9",
        "exit_code": 3,
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [],
    }), encoding="utf-8")
    assert cli.main(["--parse-report", str(broken), "--observed-exit-code", "3"]) == 2
    assert "input error" in capsys.readouterr().out


def test_unknown_flag_exits_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--not-a-flag"])
    assert excinfo.value.code == 2


def test_parallel_jobs_match_sequential_output(tmp_path: Path, capsys) -> None:
    root = _repo(tmp_path)
    assert _run(root) == 0
    sequential = capsys.readouterr().out
    assert _run(root, "--jobs", "2") == 0
    parallel = capsys.readouterr().out
    assert [line.split(":")[0] for line in sequential.splitlines() if ":" in line and not line.startswith("CBP_")] == [
        line.split(":")[0] for line in parallel.splitlines() if ":" in line and not line.startswith("CBP_")
    ]
