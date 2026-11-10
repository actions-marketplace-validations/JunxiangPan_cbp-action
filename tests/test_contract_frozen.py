"""Frozen contract: changing these semantics must break this test.

This file is intentionally a change detector, not a policy engine. If a future
contract release changes a value, update the pin in a reviewed commit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cbp import report_schema, v12_rules

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "manifest.schema.json"

SCHEMA_SHA256 = "147d7f2590cd38c3cb1eae027913c8731fcb6c079e2b502b53c1bcc219886844"
REQUIRED = {
    "schema_version", "package_id", "producer_id", "version", "gate_status",
    "applicable_gate_count", "skip_count", "skip_ratio", "blocking_skip",
    "gates", "artifact_hashes", "artifact_repository", "release_body_hash",
    "body_hash_scope", "evidence_sha256", "ci_commit_sha",
}
STATUSES = {"PASS", "FAIL", "SKIPPED", "SKIPPED_INFRA", "PRECONDITION_FAIL", "NOT_UPLOADED"}


def test_schema_is_frozen() -> None:
    assert hashlib.sha256(SCHEMA.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == SCHEMA_SHA256


def test_schema_required_fields_are_frozen() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert set(schema["required"]) == REQUIRED
    assert schema["properties"]["schema_version"]["const"] == "1"
    assert schema["properties"]["artifact_repository"]["type"] == "object"
    assert schema["properties"]["body_hash_scope"]["const"] == "base"


def test_exit_codes_are_frozen() -> None:
    assert (report_schema.EXIT_PASS, report_schema.EXIT_INPUT, report_schema.EXIT_GATE, report_schema.EXIT_SKIP) == (0, 2, 3, 4)
    assert report_schema.VALID_EXIT_CODES == (0, 2, 3, 4)


def test_skip_ratio_limit_is_frozen() -> None:
    assert report_schema.SKIP_RATIO_LIMIT == 0.20
    assert report_schema.report_exit_code(blocking_skip=False, failed=False, skip_ratio=0.20) == (0, "PASS")
    assert report_schema.report_exit_code(blocking_skip=False, failed=False, skip_ratio=0.2000001) == (4, "FAIL")


def test_status_enum_is_frozen() -> None:
    assert set(report_schema.GATE_STATUS_VALUES) == STATUSES
    assert "NOT_UPLOADED" in report_schema.REPORT_STATUS_VALUES


def test_body_rule_and_canonical_hash_are_frozen() -> None:
    rule_ids = {rule[0] for rule in v12_rules.RULES}
    assert "CBP-BODY-001" in rule_ids
    assert len(v12_rules.RULES) == 13
    from cbp.body_hash import canonical_body_hash
    assert canonical_body_hash(b"body\n") == canonical_body_hash(b"body\n\n")
    assert canonical_body_hash(b"body\r\n") == canonical_body_hash(b"body\n")
