"""Opt-in semantic-claims gate (CBP 1.6.0).

Program validation always runs first. local/cloud are optional and mutually
exclusive; cloud requires explicit consent and receives only redacted payloads.
This gate does not replace mutation or test-quality gates.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class SemanticClaimsError(ValueError):
    """Invalid input or unsafe mode request."""


@dataclass
class SemanticClaimsOptions:
    root: Path
    claims: Path
    mode: str = "program"  # program | local | cloud
    no_evidence: str = "review"  # review | fail
    cloud_consent: bool = False
    backend_command: str = ""
    backend: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _program_claim(root: Path, claim: dict, no_evidence: str) -> dict:
    cid = str(claim.get("id", "unnamed"))
    if claim.get("subjective") is True:
        return {"id": cid, "status": "ADVISORY", "reason": "subjective conclusion"}
    evidence = claim.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        status = "FAIL" if no_evidence == "fail" else "REVIEW"
        return {"id": cid, "status": status, "reason": "no evidence"}
    problems: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            problems.append("evidence entry is not an object")
            continue
        rel = item.get("file")
        if not isinstance(rel, str) or not rel:
            problems.append("evidence file missing")
            continue
        path = root / rel
        if not path.is_file():
            problems.append(f"evidence file missing: {rel}")
            continue
        line = item.get("line")
        if not isinstance(line, int) or line < 1:
            problems.append(f"{rel}: line must be a positive integer")
            continue
        try:
            count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError as exc:
            problems.append(f"{rel}: unreadable: {exc}")
            continue
        if line > count:
            problems.append(f"{rel}: line {line} exceeds {count}")
        expected = item.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            problems.append(f"{rel}: 64-hex sha256 required")
        elif _sha(path) != expected:
            problems.append(f"{rel}: evidence hash mismatch")
        command = item.get("command")
        if not isinstance(command, str) or not command.strip():
            problems.append(f"{rel}: command required")
        elif any(ord(char) < 0x20 for char in command):
            problems.append(f"{rel}: command contains control characters")
    if problems:
        return {"id": cid, "status": "FAIL", "problems": problems}
    return {"id": cid, "status": "PASS", "reason": "evidence verified"}


def redact_text(text: str) -> str:
    """Best-effort redaction for cloud payloads; never send raw content."""
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]", text)
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    text = re.sub(r"(?<![\w.-])(?:[A-Za-z]:\\|/)[^\s\"']+", "[REDACTED_PATH]", text)
    return text


def _cloud_payload(claims: list[dict]) -> dict[str, Any]:
    redacted = []
    for claim in claims:
        redacted.append({
            "id": claim.get("id"),
            "claim": redact_text(str(claim.get("claim", ""))),
            "subjective": bool(claim.get("subjective")),
            "evidence": [
                {"file": "[REDACTED_PATH]", "line": item.get("line"),
                 "command": "[REDACTED_COMMAND]"}
                for item in claim.get("evidence", []) if isinstance(item, dict)
            ],
        })
    return {"mode": "cloud", "claims": redacted}


def _run_backend(options: SemanticClaimsOptions, payload: dict, claims: list[dict]) -> dict:
    if options.backend is not None:
        return options.backend(payload)
    if not options.backend_command:
        return {"status": "REVIEW", "reason": "no local/cloud backend configured"}
    try:
        proc = subprocess.run(shlex.split(options.backend_command), input=json.dumps(payload),
                              capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "FAIL", "reason": f"backend failed: {exc}"}
    if proc.returncode != 0:
        return {"status": "FAIL", "reason": f"backend exit {proc.returncode}"}
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return {"status": "FAIL", "reason": "backend did not return JSON"}
    status = data.get("status")
    if status not in {"PASS", "ADVISORY", "REVIEW", "FAIL"}:
        return {"status": "FAIL", "reason": "backend returned invalid status"}
    return {"status": status, "reason": str(data.get("reason", ""))}


def run(options: SemanticClaimsOptions) -> dict:
    root = options.root.resolve()
    if options.mode not in {"program", "local", "cloud"}:
        raise SemanticClaimsError("mode must be program, local or cloud")
    if options.no_evidence not in {"review", "fail"}:
        raise SemanticClaimsError("no_evidence must be review or fail")
    if options.mode == "cloud" and not options.cloud_consent:
        raise SemanticClaimsError("cloud mode requires explicit consent")
    try:
        data = json.loads((root / options.claims).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"gate": "semantic-claims", "status": "FAIL", "findings": [f"claims unreadable: {exc}"]}
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        return {"gate": "semantic-claims", "status": "FAIL", "findings": ["claims array is empty"]}

    # Program validation always runs first.
    program = [_program_claim(root, claim, options.no_evidence) for claim in claims if isinstance(claim, dict)]
    if not program or any(item["status"] == "FAIL" for item in program):
        return {"gate": "semantic-claims", "mode": options.mode, "status": "FAIL",
                "program": program, "findings": ["program validation failed"]}
    if any(item["status"] == "REVIEW" for item in program):
        return {"gate": "semantic-claims", "mode": options.mode, "status": "REVIEW",
                "program": program, "findings": ["no evidence; review required"]}
    if any(item["status"] == "ADVISORY" for item in program):
        return {"gate": "semantic-claims", "mode": options.mode, "status": "ADVISORY",
                "program": program, "findings": ["subjective conclusion"]}

    if options.mode == "program":
        return {"gate": "semantic-claims", "mode": "program", "status": "PASS", "program": program,
                "findings": []}

    payload = (_cloud_payload(claims) if options.mode == "cloud"
               else {"mode": "local", "claims": claims})
    backend = _run_backend(options, payload, claims)
    status = backend["status"]
    if status == "PASS":
        status = "PASS"
    return {"gate": "semantic-claims", "mode": options.mode, "status": status,
            "program": program, "backend": backend, "findings": [backend.get("reason", "")] if status != "PASS" else []}
