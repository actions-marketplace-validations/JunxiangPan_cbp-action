"""CONTRACT v1.7 report parser: structured JSON only, exit 2 on bad input."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cbp import report_parser
from cbp import report_schema as schema


def _cbe(**overrides) -> dict:
    data = {
        "schema_version": "1",
        "package_id": "cbs",
        "producer_id": "cbe",
        "version": "v1.7.0",
        "tag": "v1.7.0",
        "gate_status": "PASS",
        "exit_code": 0,
        "applicable_count": 5,
        "skip_count": 1,
        "skip_ratio": 0.2,
        "blocking_skip": False,
        "warn_count": 0,
        "rules_manifest_hash": "a" * 64,
        "sarif_paths": ["cbe.sarif"],
        "evidence_sha256": "b" * 64,
    }
    data.update(overrides)
    return data


def _manifest(**overrides) -> dict:
    data = {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.0.9",
        "gate_status": "PASS",
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [{"name": name, "status": "PASS"} for name in schema.ALL_GATES],
        "artifact_hashes": {"cbp_action-1.0.9-py3-none-any.whl": "c" * 64},
        "release_body_hash": "d" * 64,
        "evidence_sha256": "e" * 64,
    }
    data.update(overrides)
    return data


def _gate_report(**overrides) -> dict:
    data = {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.0.9",
        "gate_status": "PASS",
        "exit_code": 0,
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [{"name": name, "status": "PASS", "reason": ""} for name in schema.ALL_GATES],
    }
    data.update(overrides)
    return data


def test_parses_a_cbe_report() -> None:
    parsed = report_parser.parse_report_data(_cbe())
    assert parsed.kind == "cbe-report"
    assert parsed.exit_code == 0
    assert parsed.skip_ratio == 0.2


def test_parses_a_cbp_manifest() -> None:
    parsed = report_parser.parse_report_data(_manifest())
    assert parsed.kind == "cbp-manifest"
    assert parsed.applicable_count == 9


def test_parses_a_cbp_gate_report() -> None:
    parsed = report_parser.parse_report_data(_gate_report())
    assert parsed.kind == "cbp-gate-report"
    assert parsed.gate_status == "PASS"


def test_exit_three_without_gate_status_is_an_input_error() -> None:
    data = _gate_report(exit_code=3)
    del data["gate_status"]
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(data)
    assert "input error" in str(excinfo.value)
    assert excinfo.value.exit_code == schema.EXIT_INPUT


def test_exit_three_with_a_misspelled_gate_status_is_an_input_error() -> None:
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(_gate_report(exit_code=3, gate_status="SKIP"))
    assert "input error" in str(excinfo.value)


def test_unsupported_schema_version_is_an_input_error() -> None:
    # Synthetic "old consumer" fixture: the manifest claims a future schema.
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(_manifest(schema_version="2"))
    assert "unsupported schema_version" in str(excinfo.value)
    assert excinfo.value.exit_code == schema.EXIT_INPUT


def test_missing_required_field_is_an_input_error() -> None:
    data = _manifest()
    del data["artifact_hashes"]
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(data)
    assert "required field is missing" in str(excinfo.value)


def test_prefixed_hash_is_rejected_and_not_stripped() -> None:
    data = _manifest(release_body_hash="sha256:" + "d" * 64)
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(data)
    assert "prefix is an input error" in str(excinfo.value)


def test_inconsistent_ratio_is_an_input_error() -> None:
    data = _gate_report(skip_count=2, skip_ratio=0.1)
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(data)
    assert "does not equal" in str(excinfo.value)


def test_observed_exit_must_match_the_report() -> None:
    with pytest.raises(report_parser.ReportError):
        report_parser.parse_report_data(_gate_report(), observed_exit_code=3)


def test_blocking_skip_requires_a_forced_skip_entry() -> None:
    data = _gate_report(blocking_skip=True, gate_status="FAIL", exit_code=3)
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report_data(data)
    assert "no forced gate is SKIPPED" in str(excinfo.value)


def test_forced_skip_sets_blocking_skip() -> None:
    gates = [{"name": name, "status": "PASS"} for name in schema.ALL_GATES]
    for entry in gates:
        if entry["name"] == "claims":
            entry["status"] = "SKIPPED"
    parsed = report_parser.parse_report_data(
        _gate_report(
            gate_status="FAIL",
            exit_code=3,
            blocking_skip=True,
            gates=gates,
            applicable_gate_count=9,
            skip_ratio=0.0,
        )
    )
    assert parsed.blocking_skip is True


def test_parse_report_reads_json_only(tmp_path: Path) -> None:
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(_gate_report()), encoding="utf-8")
    assert report_parser.parse_report(path).kind == "cbp-gate-report"


def test_parse_report_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report(tmp_path / "missing.json")
    assert "report missing" in str(excinfo.value)


def test_parse_report_rejects_non_json(tmp_path: Path) -> None:
    path = tmp_path / "gate.json"
    path.write_text("RESULT=PASS", encoding="utf-8")
    with pytest.raises(report_parser.ReportError) as excinfo:
        report_parser.parse_report(path)
    assert "not valid JSON" in str(excinfo.value)
