"""Opt-in AI evidence gate: hashes, lines, commands, contradictions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cbp import ai_evidence


def _fixture(tmp: Path) -> tuple[Path, str]:
    source = tmp / "src/thing.py"
    source.parent.mkdir(parents=True)
    source.write_text("line one\nline two\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    claims = {
        "claims": [
            {
                "id": "c1",
                "claim": "the change is covered",
                "metrics": {"coverage": 90.0, "mutation_score": 1.0},
                "evidence": [
                    {"file": "src/thing.py", "line": 2, "command": "pytest tests/test_thing.py", "sha256": digest}
                ],
            }
        ]
    }
    (tmp / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
    (tmp / "coverage.json").write_text(json.dumps({"total": {"percent_covered": 90.0}}), encoding="utf-8")
    (tmp / "mutation.json").write_text(json.dumps({"score": 1.0}), encoding="utf-8")
    return tmp / "claims.json", digest


def _options(tmp: Path, claims: Path) -> ai_evidence.AIEvidenceOptions:
    return ai_evidence.AIEvidenceOptions(
        root=tmp, claims=Path(claims.name),
        coverage_json=Path("coverage.json"), mutation_report=Path("mutation.json"),
    )


def test_valid_evidence_passes(tmp_path: Path) -> None:
    claims, _ = _fixture(tmp_path)
    assert ai_evidence.run(_options(tmp_path, claims))["status"] == "PASS"


def test_no_evidence_is_advisory(tmp_path: Path) -> None:
    claims, _ = _fixture(tmp_path)
    data = json.loads(claims.read_text(encoding="utf-8"))
    data["claims"][0]["evidence"] = []
    claims.write_text(json.dumps(data), encoding="utf-8")
    assert ai_evidence.run(_options(tmp_path, claims))["status"] == "ADVISORY"


def test_subjective_is_advisory(tmp_path: Path) -> None:
    claims, _ = _fixture(tmp_path)
    data = json.loads(claims.read_text(encoding="utf-8"))
    data["claims"][0]["subjective"] = True
    claims.write_text(json.dumps(data), encoding="utf-8")
    assert ai_evidence.run(_options(tmp_path, claims))["status"] == "ADVISORY"


def test_bad_hash_fails(tmp_path: Path) -> None:
    claims, _ = _fixture(tmp_path)
    data = json.loads(claims.read_text(encoding="utf-8"))
    data["claims"][0]["evidence"][0]["sha256"] = "0" * 64
    claims.write_text(json.dumps(data), encoding="utf-8")
    assert ai_evidence.run(_options(tmp_path, claims))["status"] == "FAIL"


def test_coverage_contradiction_fails(tmp_path: Path) -> None:
    claims, _ = _fixture(tmp_path)
    data = json.loads(claims.read_text(encoding="utf-8"))
    data["claims"][0]["metrics"]["coverage"] = 70.0
    claims.write_text(json.dumps(data), encoding="utf-8")
    result = ai_evidence.run(_options(tmp_path, claims))
    assert result["status"] == "FAIL"
    assert any("contradicts" in item for item in result["findings"])
