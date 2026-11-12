"""Semantic-claims gate: program first, local/cloud exclusive, cloud redaction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cbp import semantic_claims


def _fixture(tmp: Path, claim: dict | None = None) -> Path:
    source = tmp / "src/thing.py"
    source.parent.mkdir(parents=True)
    source.write_text("line one\nline two\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    value = claim or {
        "id": "c1", "claim": "the change is covered",
        "evidence": [{"file": "src/thing.py", "line": 2, "command": "pytest", "sha256": digest}],
    }
    path = tmp / "claims.json"
    path.write_text(json.dumps({"claims": [value]}), encoding="utf-8")
    return path


def _options(tmp: Path, claims: Path, **kwargs) -> semantic_claims.SemanticClaimsOptions:
    return semantic_claims.SemanticClaimsOptions(root=tmp, claims=Path(claims.name), **kwargs)


def test_program_pass(tmp_path: Path) -> None:
    assert semantic_claims.run(_options(tmp_path, _fixture(tmp_path)))["status"] == "PASS"


def test_no_evidence_review_and_fail(tmp_path: Path) -> None:
    claims = _fixture(tmp_path, {"id": "c1", "claim": "no evidence", "evidence": []})
    assert semantic_claims.run(_options(tmp_path, claims))["status"] == "REVIEW"
    assert semantic_claims.run(_options(tmp_path, claims, no_evidence="fail"))["status"] == "FAIL"


def test_subjective_advisory(tmp_path: Path) -> None:
    claims = _fixture(tmp_path, {"id": "c1", "claim": "I think it is good", "subjective": True, "evidence": []})
    assert semantic_claims.run(_options(tmp_path, claims))["status"] == "ADVISORY"


def test_cloud_requires_consent(tmp_path: Path) -> None:
    claims = _fixture(tmp_path)
    with pytest.raises(semantic_claims.SemanticClaimsError):
        semantic_claims.run(_options(tmp_path, claims, mode="cloud"))


def test_local_backend_pass(tmp_path: Path) -> None:
    claims = _fixture(tmp_path)
    seen: dict = {}

    def backend(payload: dict) -> dict:
        seen.update(payload)
        return {"status": "PASS"}

    result = semantic_claims.run(_options(tmp_path, claims, mode="local", backend=backend))
    assert result["status"] == "PASS"
    assert seen["mode"] == "local"


def test_cloud_redacts_and_never_passes_raw(tmp_path: Path) -> None:
    claims = _fixture(tmp_path)
    data = json.loads(claims.read_text(encoding="utf-8"))
    data["claims"][0]["claim"] = r"contact a@example.com at C:\\secret\\x.txt token=abc123"
    data["claims"][0]["evidence"][0]["command"] = r"cat C:\\secret\\x.txt"
    data["claims"][0]["evidence"][0]["sha256"] = hashlib.sha256((tmp_path / "src/thing.py").read_bytes()).hexdigest()
    claims.write_text(json.dumps(data), encoding="utf-8")
    seen: dict = {}

    def backend(payload: dict) -> dict:
        seen.update(payload)
        return {"status": "PASS"}

    result = semantic_claims.run(_options(tmp_path, claims, mode="cloud", cloud_consent=True, backend=backend))
    assert result["status"] == "PASS"
    blob = json.dumps(seen)
    assert "a@example.com" not in blob
    assert "secret" not in blob.lower()
    assert seen["claims"][0]["claim"].count("[REDACTED") >= 1


def test_program_runs_before_backend(tmp_path: Path) -> None:
    claims = _fixture(tmp_path, {
        "id": "c1", "claim": "bad", "evidence": [{"file": "missing.py", "line": 1, "command": "x", "sha256": "0" * 64}],
    })
    called = False

    def backend(payload: dict) -> dict:
        nonlocal called
        called = True
        return {"status": "PASS"}

    result = semantic_claims.run(_options(tmp_path, claims, mode="local", backend=backend))
    assert result["status"] == "FAIL"
    assert called is False


def test_cli_cloud_without_consent_is_input_error(tmp_path: Path, capsys) -> None:
    from cbp.cli import main as cli_main
    claims = _fixture(tmp_path)
    assert cli_main(["--root", str(tmp_path), "--semantic-claims",
                     "--semantic-claims-file", claims.name, "--semantic-mode", "cloud"]) == 2
