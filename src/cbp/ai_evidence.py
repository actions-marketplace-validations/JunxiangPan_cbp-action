"""Opt-in AI evidence gate: claims must carry verifiable file/line/command/hash.

No evidence and subjective conclusions are advisory, and claims
that contradict coverage/mutation evidence fail. The gate never calls an LLM.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AIEvidenceOptions:
    root: Path
    claims: Path
    coverage_json: Path | None = None
    mutation_report: Path | None = None
    tolerance: float = 0.01


def _coverage_score(root: Path, path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        data = json.loads((root / path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    total = data.get("total")
    if isinstance(total, dict) and "percent_covered" in total:
        return float(total["percent_covered"])
    if "percent_covered" in data:
        return float(data["percent_covered"])
    statements = 0
    missing = 0
    for entry in data.get("files", {}).values():
        summary = entry.get("summary", {})
        statements += int(summary.get("num_statements", 0))
        missing += len(entry.get("missing_lines", []))
    return ((statements - missing) / statements * 100.0) if statements else None


def _mutation_score(root: Path, path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        data = json.loads((root / path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("score", data.get("mutation_score"))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number / 100.0 if number > 1.0 else number


def _check_evidence(root: Path, item: dict) -> str:
    file_value = item.get("file")
    if not isinstance(file_value, str) or not file_value:
        return "evidence file missing"
    path = root / file_value
    if not path.is_file():
        return f"evidence file missing: {file_value}"
    line = item.get("line")
    if not isinstance(line, int) or line < 1:
        return f"{file_value}: line must be a positive integer"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"{file_value}: unreadable: {exc}"
    if line > len(lines):
        return f"{file_value}: line {line} exceeds {len(lines)}"
    expected = item.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        return f"{file_value}: 64-hex sha256 required"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        return f"{file_value}: evidence hash mismatch"
    command = item.get("command")
    if not isinstance(command, str) or not command.strip():
        return f"{file_value}: command required"
    if any(ord(char) < 0x20 for char in command):
        return f"{file_value}: command contains control characters"
    return ""


def run(options: AIEvidenceOptions) -> dict:
    root = options.root.resolve()
    findings: list[str] = []
    results: list[dict] = []
    try:
        data = json.loads((root / options.claims).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"gate": "ai-evidence", "status": "FAIL", "findings": [f"claims unreadable: {exc}"]}
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        return {"gate": "ai-evidence", "status": "FAIL", "findings": ["claims array is empty"]}
    coverage = _coverage_score(root, options.coverage_json)
    mutation = _mutation_score(root, options.mutation_report)
    for claim in claims:
        claim_id = str(claim.get("id", "unnamed"))
        if claim.get("subjective") is True:
            results.append({"id": claim_id, "status": "ADVISORY"})
            continue
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            results.append({"id": claim_id, "status": "ADVISORY"})
            continue
        problems = [problem for item in evidence if (problem := _check_evidence(root, item))]
        metrics = claim.get("metrics", {})
        if isinstance(metrics, dict):
            if coverage is not None and "coverage" in metrics:
                try:
                    if abs(float(metrics["coverage"]) - coverage) > options.tolerance * 100:
                        problems.append(f"coverage {metrics['coverage']} contradicts {coverage:.2f}%")
                except (TypeError, ValueError):
                    problems.append("coverage claim is not numeric")
            if mutation is not None and "mutation_score" in metrics:
                try:
                    if abs(float(metrics["mutation_score"]) - mutation) > options.tolerance:
                        problems.append(f"mutation_score {metrics['mutation_score']} contradicts {mutation:.4f}")
                except (TypeError, ValueError):
                    problems.append("mutation_score claim is not numeric")
        if problems:
            findings.extend(f"{claim_id}: {problem}" for problem in problems)
            results.append({"id": claim_id, "status": "FAIL", "problems": problems})
        else:
            results.append({"id": claim_id, "status": "PASS"})
    status = "FAIL" if findings else "PASS"
    if status == "PASS" and any(item["status"] == "ADVISORY" for item in results):
        status = "ADVISORY"
    return {"gate": "ai-evidence", "status": status, "findings": findings, "claims": results}
