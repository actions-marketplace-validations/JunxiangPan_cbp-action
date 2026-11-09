"""Normalize Semgrep, SonarQube, CodeQL and SARIF reports into CBP findings."""
from __future__ import annotations

import json
import re
from pathlib import Path


class ReportError(ValueError):
    """Raised when an external report cannot be normalized."""


_UNSAFE = re.compile(r"[^A-Za-z0-9]+")
_FOREIGN_PREFIXES = ("CBE-", "CBS-", "CBM-", "CBC-", "CBG-")


def _namespaced_rule(tool: str, rule: str) -> str:
    """CONTRACT §6: CBP output may carry only CBP-* rule IDs.

    A foreign or native ID is mapped, never emitted verbatim. The original ID is
    kept in ``origin_rule`` for traceability.
    """
    value = (rule or "").strip()
    if value.startswith("CBP-"):
        return value
    for prefix in _FOREIGN_PREFIXES:
        if value.upper().startswith(prefix):
            value = value[len(prefix):]
            break
    slug = _UNSAFE.sub("-", value).strip("-").upper()
    if not slug:
        slug = _UNSAFE.sub("-", tool or "unknown").strip("-").upper() or "UNKNOWN"
    return ("CBP-EXT-" + slug)[:80]


def _finding(tool: str, rule: str, path: str, line: int, message: str, severity: str) -> dict:
    return {
        "path": path.replace("\\", "/"),
        "line": max(1, int(line or 1)),
        "rule": _namespaced_rule(tool, rule),
        "origin_rule": rule or "",
        "message": message or rule,
        "severity": severity or "warning",
        "tool": tool,
    }


def _sarif(data: dict) -> list[dict]:
    findings = []
    for run in data.get("runs", []):
        tool = run.get("tool", {}).get("driver", {}).get("name", "sarif")
        for result in run.get("results", []):
            locations = result.get("locations", [])
            if not locations:
                continue
            physical = locations[0].get("physicalLocation", {})
            uri = physical.get("artifactLocation", {}).get("uri", "")
            line = physical.get("region", {}).get("startLine", 1)
            findings.append(_finding(tool, result.get("ruleId", ""), uri, line,
                                     result.get("message", {}).get("text", ""), result.get("level", "warning")))
    return findings


def _semgrep(data: dict) -> list[dict]:
    return [
        _finding("semgrep", item.get("check_id", ""), item.get("path", ""), item.get("start", {}).get("line", 1),
                 item.get("extra", {}).get("message", ""), item.get("extra", {}).get("severity", "warning"))
        for item in data.get("results", [])
    ]


def _sonar(data: dict) -> list[dict]:
    return [
        _finding("sonarqube", item.get("rule", ""), item.get("component", ""), item.get("line", 1),
                 item.get("message", ""), item.get("severity", "warning"))
        for item in data.get("issues", [])
    ]


def normalize(path: Path) -> list[dict]:
    """Read one JSON report and normalize its findings."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReportError(f"cannot read {path.name}: {exc}") from exc
    if "runs" in data:
        return _sarif(data)
    if "results" in data:
        return _semgrep(data)
    if "issues" in data:
        return _sonar(data)
    raise ReportError(f"unsupported report format: {path.name}")


def aggregate(root: Path, reports: list[str]) -> list[dict]:
    """Load all configured reports and deduplicate by path, line, rule."""
    findings: list[dict] = []
    seen: set[tuple] = set()
    for name in reports:
        path = Path(name)
        if not path.is_absolute():
            path = root / path
        for item in normalize(path):
            key = (item["path"], item["line"], item["rule"])
            if key in seen:
                continue
            seen.add(key)
            findings.append(item)
    return findings
