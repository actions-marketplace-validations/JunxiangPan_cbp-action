"""CONTRACT v1.7 status enum, exit-code table, and manifest validation."""
from __future__ import annotations

from cbp import report_schema as schema


def _valid_manifest() -> dict:
    return {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.0.9",
        "gate_status": "PASS",
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "gates": [{"name": name, "status": "PASS", "reason": ""} for name in schema.ALL_GATES],
        "artifact_hashes": {"cbp_action-1.0.9-py3-none-any.whl": "a" * 64},
        "release_body_hash": "b" * 64,
        "evidence_sha256": "c" * 64,
    }


def test_gate_status_enum_has_exactly_six_values() -> None:
    assert {status.value for status in schema.GateStatus} == {
        "PASS",
        "FAIL",
        "SKIPPED",
        "SKIPPED_INFRA",
        "PRECONDITION_FAIL",
        "NOT_UPLOADED",
    }


def test_exit_three_without_gate_status_is_an_input_error() -> None:
    problems = schema.exit_status_problems(3, None)
    assert problems
    assert "input error" in problems[0]


def test_exit_three_with_a_bad_gate_status_is_an_input_error() -> None:
    problems = schema.exit_status_problems(3, "SKIP")
    assert problems
    assert "not one of" in problems[0]


def test_exit_zero_cannot_carry_fail() -> None:
    assert schema.exit_status_problems(0, "FAIL")


def test_exit_four_requires_fail() -> None:
    assert not schema.exit_status_problems(4, "FAIL")
    assert schema.exit_status_problems(4, "PASS")


def test_exit_three_accepts_skipped_infra() -> None:
    assert not schema.exit_status_problems(3, "SKIPPED_INFRA")


def test_precondition_fail_accepts_two_or_three() -> None:
    assert not schema.exit_status_problems(2, "PRECONDITION_FAIL")
    assert not schema.exit_status_problems(3, "PRECONDITION_FAIL")


def test_skip_ratio_accepts_exactly_twenty_percent() -> None:
    assert schema.ratio_problem(5, 1, 0.2) == ""


def test_skip_ratio_rejects_rounding_mismatch() -> None:
    assert "does not equal" in schema.ratio_problem(5, 2, 0.3)


def test_skip_ratio_rejects_more_skips_than_applicable() -> None:
    assert "greater than" in schema.ratio_problem(2, 3, 0.5)


def test_hash_accepts_bare_lowercase_hex() -> None:
    assert schema.hash_problem("a" * 64, "hash") == ""


def test_hash_rejects_sha256_prefix_and_is_not_stripped() -> None:
    problem = schema.hash_problem("sha256:" + "a" * 64, "hash")
    assert "prefix is an input error" in problem


def test_hash_rejects_uppercase_and_short_values() -> None:
    assert schema.hash_problem("A" * 64, "hash")
    assert schema.hash_problem("a" * 63, "hash")


def test_valid_manifest_has_no_problems() -> None:
    assert schema.validate_manifest(_valid_manifest(), require_producer=True) == []


def test_manifest_missing_required_field_is_reported() -> None:
    manifest = _valid_manifest()
    del manifest["evidence_sha256"]
    problems = schema.validate_manifest(manifest)
    assert any("evidence_sha256: required field is missing" in item for item in problems)


def test_manifest_unknown_key_is_reported() -> None:
    manifest = _valid_manifest()
    manifest["counts"] = {"passed": 9, "total": 9}
    problems = schema.validate_manifest(manifest)
    assert any("unexpected key" in item for item in problems)


def test_manifest_forced_skip_requires_blocking_skip() -> None:
    manifest = _valid_manifest()
    for entry in manifest["gates"]:
        if entry["name"] == "claims":
            entry["status"] = "SKIPPED"
    problems = schema.validate_manifest(manifest)
    assert any("blocking_skip" in item for item in problems)


def test_manifest_blocking_skip_requires_a_forced_skip() -> None:
    manifest = _valid_manifest()
    manifest["blocking_skip"] = True
    problems = schema.validate_manifest(manifest)
    assert any("no forced gate is SKIPPED" in item for item in problems)


def test_report_exit_code_mapping() -> None:
    assert schema.report_exit_code(blocking_skip=True, failed=False, skip_ratio=0.0) == (3, "FAIL")
    assert schema.report_exit_code(blocking_skip=False, failed=True, skip_ratio=0.0) == (3, "FAIL")
    assert schema.report_exit_code(blocking_skip=False, failed=False, skip_ratio=0.21) == (4, "FAIL")
    assert schema.report_exit_code(blocking_skip=False, failed=False, skip_ratio=0.2) == (0, "PASS")
