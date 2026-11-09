"""1.2.0 core fields: body_hash_scope, artifact_repository, cbc-event emission."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from cbp import cbc_event, cli, report_parser, report_schema
from tools import dogfood_manifest as dog


def _manifest(**overrides) -> dict:
    values = {
        "version": "v1.2.0",
        "run_id": "1",
        "commit_sha": "a" * 40,
        "gate_status": "PASS",
        "gates": [dog._gate_entry(name, "PASS") for name in report_schema.ALL_GATES],
        "artifact_hashes": {"x.whl": "b" * 64},
        "release_body_hash": "c" * 64,
    }
    values.update(overrides)
    return dog._manifest_document(**values)


def test_manifest_records_body_scope_and_repository() -> None:
    manifest = _manifest(artifact_repository="owner/repo")
    assert manifest["body_hash_scope"] == "base"
    assert manifest["artifact_repository"]["repository"] == "owner/repo"
    assert manifest["artifact_repository"]["artifact_name"] == "cbp-dist"
    assert report_schema.validate_manifest(manifest) == []


def test_manifest_omits_empty_repository() -> None:
    assert "artifact_repository" not in _manifest()


def test_unsupported_body_scope_is_rejected() -> None:
    assert "unsupported value 'full'" in report_schema.body_hash_scope_problem("full")
    with pytest.raises(dog.ManifestError, match="unsupported body_hash_scope"):
        dog._manifest_document(
            version="v1.2.0", run_id="1", commit_sha="a" * 40, gate_status="PASS",
            gates=[dog._gate_entry(name, "PASS") for name in report_schema.ALL_GATES],
            artifact_hashes={"x.whl": "b" * 64}, release_body_hash="c" * 64,
            body_hash_scope="full",
        )


def test_missing_body_scope_is_reported_when_required() -> None:
    manifest = _manifest()
    del manifest["body_hash_scope"]
    assert any("body_hash_scope" in item for item in report_schema.validate_manifest(manifest, require_body_scope=True))
    assert report_schema.validate_manifest(manifest) == []


def test_cross_repository_artifact_is_rejected() -> None:
    manifest = _manifest(artifact_repository="other/repo")
    problems = report_schema.validate_manifest(manifest, expected_repository="me/repo")
    assert any("cross-repository" in item for item in problems)


def _gate_report(**overrides) -> dict:
    data = {
        "schema_version": "1",
        "package_id": "cbp",
        "producer_id": "cbp",
        "version": "v1.2.0",
        "gate_status": "PASS",
        "exit_code": 0,
        "applicable_gate_count": 9,
        "skip_count": 0,
        "skip_ratio": 0.0,
        "blocking_skip": False,
        "body_hash_scope": "base",
        "gates": [{"name": name, "status": "PASS", "reason": ""} for name in report_schema.ALL_GATES],
    }
    data.update(overrides)
    return data


def test_parser_accepts_base_scope_and_expected_repository() -> None:
    parsed = report_parser.parse_report_data(
        _gate_report(artifact_repository="me/repo"),
        require_body_scope=True,
        expected_repository="me/repo",
    )
    assert parsed.body_hash_scope == "base"
    assert parsed.artifact_repository == "me/repo"


def test_parser_rejects_missing_scope_when_required() -> None:
    data = _gate_report()
    del data["body_hash_scope"]
    with pytest.raises(report_parser.ReportError, match="body_hash_scope"):
        report_parser.parse_report_data(data, require_body_scope=True)


def test_parser_rejects_full_scope() -> None:
    with pytest.raises(report_parser.ReportError, match="unsupported value 'full'"):
        report_parser.parse_report_data(_gate_report(body_hash_scope="full"))


def test_parser_rejects_cross_repository_report() -> None:
    with pytest.raises(report_parser.ReportError, match="cross-repository"):
        report_parser.parse_report_data(
            _gate_report(artifact_repository="other/repo"),
            expected_repository="me/repo",
        )


def test_emitter_is_disabled_by_default(tmp_path: Path) -> None:
    emitter = cbc_event.EventEmitter(tmp_path / "events")
    assert emitter.emit("INFO", "cbp.test", {}) is None
    assert not (tmp_path / "events").exists()


def _read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_emitter_writes_a_valid_hash_chain(tmp_path: Path) -> None:
    emitter = cbc_event.EventEmitter(tmp_path, enabled=True, max_events=10)
    for index in range(3):
        assert emitter.emit("INFO", "cbp.test", {"index": index}) is not None
    events = _read_events(tmp_path / "events.jsonl")
    assert [event["seq"] for event in events] == [1, 2, 3]
    previous = cbc_event.GENESIS
    for event in events:
        assert event["prev_hash"] == previous
        assert event["event_hash"] == cbc_event.event_hash(event["prev_hash"], event)
        previous = event["event_hash"]


def test_emitter_rate_limit_is_counted(tmp_path: Path) -> None:
    emitter = cbc_event.EventEmitter(tmp_path, enabled=True, max_events=2)
    emitter.emit("INFO", "a", {})
    emitter.emit("INFO", "b", {})
    assert emitter.emit("INFO", "c", {}) is None
    assert emitter.emitted == 2
    assert emitter.dropped == 1
    assert len(_read_events(tmp_path / "events.jsonl")) == 2


def test_emitter_hmac_binds_the_event(tmp_path: Path) -> None:
    key = "secret-key"
    emitter = cbc_event.EventEmitter(tmp_path, enabled=True, hmac_key=key)
    event = emitter.emit("INFO", "a", {"x": 1})
    assert event is not None
    body = {k: v for k, v in event.items() if k not in {"hmac_sha256", "event_hash"}}
    expected = hmac.new(key.encode(), cbc_event.canonical_bytes(body), hashlib.sha256).hexdigest()
    assert event["hmac_sha256"] == expected


def _consumer_repo(root: Path) -> None:
    (root / "README.md").write_text("clean\n", encoding="utf-8")
    (root / "cbp.json").write_text(json.dumps({
        "schema_version": "1.0.8",
        "enable_encoding": True,
        "enable_coverage": False,
        "enable_dependency": False,
        "enable_comments": False,
        "enable_docs": False,
        "enable_binary": False,
        "enable_claims": False,
        "enable_custom": False,
        "enable_upgrade": False,
    }), encoding="utf-8")


def test_cli_report_json_includes_body_scope(tmp_path: Path) -> None:
    _consumer_repo(tmp_path)
    report = tmp_path / "report.json"
    assert cli.main(["--root", str(tmp_path), "--report-json", str(report)]) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["body_hash_scope"] == "base"


def test_cli_rejects_unsupported_body_scope(tmp_path: Path, capsys) -> None:
    assert cli.main(["--root", str(tmp_path), "--body-hash-scope", "full"]) == 2
    assert "unsupported body_hash_scope" in capsys.readouterr().out


def test_cli_emits_cbc_events(tmp_path: Path) -> None:
    _consumer_repo(tmp_path)
    event_dir = tmp_path / "events"
    code = cli.main(["--root", str(tmp_path), "--cbc-event-dir", str(event_dir)])
    assert code == 0
    events = _read_events(event_dir / "events.jsonl")
    assert events[0]["action"] == "cbp.run.start"
    assert events[-1]["action"] == "cbp.run.end"
    assert any(event["action"] == "cbp.gate.result" for event in events)
