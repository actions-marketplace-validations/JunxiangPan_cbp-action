"""CONTRACT §6: CBP output must not carry another namespace's rule IDs."""
from __future__ import annotations

import json
from pathlib import Path

from cbp.report_aggregator import aggregate, normalize


def _sarif(tmp_path: Path, rule_id: str) -> Path:
    report = tmp_path / "r.sarif"
    report.write_text(json.dumps({"runs": [{"tool": {"driver": {"name": "CodeQL"}}, "results": [{
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": "bad"},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "a.py"}, "region": {"startLine": 1}}}],
    }]}]}), encoding="utf-8")
    return report


def test_foreign_namespace_is_mapped_to_cbp(tmp_path: Path) -> None:
    finding = normalize(_sarif(tmp_path, "CBE-SECRET-001"))[0]
    assert finding["rule"].startswith("CBP-EXT-")
    assert finding["origin_rule"] == "CBE-SECRET-001"
    assert "CBE" not in finding["rule"]


def test_native_cbp_rule_is_preserved(tmp_path: Path) -> None:
    finding = normalize(_sarif(tmp_path, "CBP-COV-001"))[0]
    assert finding["rule"] == "CBP-COV-001"


def test_rule_id_is_stable_and_slugified(tmp_path: Path) -> None:
    first = normalize(_sarif(tmp_path, "js/path traversal"))[0]["rule"]
    second = normalize(_sarif(tmp_path, "js/path traversal"))[0]["rule"]
    assert first == second == "CBP-EXT-JS-PATH-TRAVERSAL"


def test_missing_rule_id_falls_back_to_a_cbp_id(tmp_path: Path) -> None:
    finding = aggregate(tmp_path, [str(_sarif(tmp_path, ""))])[0]
    assert finding["rule"] == "CBP-EXT-CODEQL"
