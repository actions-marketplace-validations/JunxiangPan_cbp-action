"""Opt-in target-mutation gate (CBP 1.5.0).

Runs an explicitly configured mutation command (no shell), verifies the report
hash and thresholds, and reports the changed-code score. It never runs unless
the caller opts in.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MutationOptions:
    root: Path
    report: Path
    command: str = ""
    threshold: float = 0.95
    changed_code_threshold: float = 0.90
    expected_sha256: str = ""
    timeout_seconds: int = 300


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_hash(options: MutationOptions, root: Path) -> str:
    if options.expected_sha256:
        return options.expected_sha256.lower()
    sidecar = root / Path(str(options.report) + ".sha256")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8").strip().split()[0].lower()
    return ""


def run(options: MutationOptions) -> dict:
    root = options.root.resolve()
    report = root / options.report
    result: dict = {"gate": "target-mutation", "status": "FAIL", "findings": []}
    if options.command:
        try:
            proc = subprocess.run(
                shlex.split(options.command), cwd=root, capture_output=True,
                text=True, timeout=options.timeout_seconds, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["findings"].append(f"mutation command failed: {exc}")
            return result
        if proc.returncode != 0:
            result["findings"].append(f"mutation command exit {proc.returncode}")
    if not report.is_file():
        result["findings"].append(f"mutation report missing: {options.report}")
        return result
    expected = _expected_hash(options, root)
    actual = _sha(report)
    result["report_sha256"] = actual
    if expected and expected != actual:
        result["findings"].append(f"mutation report hash mismatch: {actual} != {expected}")
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except ValueError as exc:
        result["findings"].append(f"mutation report unreadable: {exc}")
        return result
    score = data.get("score", data.get("mutation_score"))
    changed = data.get("changed_code_score", data.get("changed_score"))
    result["score"] = score
    result["changed_code_score"] = changed
    try:
        if score is None or float(score) < options.threshold:
            result["findings"].append(
                f"mutation score {score!r} < threshold {options.threshold}"
            )
        if changed is None or float(changed) < options.changed_code_threshold:
            result["findings"].append(
                f"changed-code score {changed!r} < threshold {options.changed_code_threshold}"
            )
    except (TypeError, ValueError):
        result["findings"].append("mutation score values must be numbers")
    result["status"] = "PASS" if not result["findings"] else "FAIL"
    return result
