"""Generic release-claim reconciliation gate."""
from __future__ import annotations

RULE_ID = "CBP-CLM-001"

import hashlib
import json
import re
from pathlib import Path

from .config import GateConfig
from . import cel_gates

TOKEN = re.compile(r"(?m)^QUALITY_COUNTS:\s*(\d+)/(\d+)\s*$")
GATE_CLAIM = re.compile(r"\b(?:all|across|through)\s+([A-Za-z]+|\d+)\s+gates?\b", re.IGNORECASE)
WORDS = {
    word: number
    for number, word in enumerate(
        ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
    )
}


def _gate_number(text: str, total: int, *, required: bool) -> str:
    match = GATE_CLAIM.search(text)
    if not match:
        return "release body must state the gate count" if required else ""
    token = match.group(1).lower()
    number = int(token) if token.isdigit() else WORDS.get(token)
    if number is None:
        return f"unknown gate count claim: {match.group(0)}"
    if number != total:
        return f"notes claim {token} gates but manifest has {total}"
    return ""


def _body_problem(path: Path, expected: str, total: int, cfg: GateConfig) -> str:
    if not path.is_file():
        return f"release body missing: {path}"
    text = path.read_text(encoding="utf-8")
    tokens = TOKEN.findall(text)
    if len(tokens) != 1:
        return "release body needs exactly one QUALITY_COUNTS line"
    actual = f"{tokens[0][0]}/{tokens[0][1]}"
    if actual != expected:
        return f"release body {actual} != manifest {expected}"
    problem = _gate_number(text, total, required=True)
    if problem:
        return "release body " + problem
    if "First public release" in text:
        return "release body must not claim First public release"
    version = str(getattr(cfg, "release_version", "") or "").strip().lstrip("vV")
    if version and not re.search(rf"(?<![0-9.])v?{re.escape(version)}(?![0-9.])", text):
        return f"release body must name version {version}"  # pragma: no cover - defensive/error branch
    artifact_name = str(getattr(cfg, "release_artifact", "") or "")
    if artifact_name:
        artifact = cfg.path(artifact_name)
        if not artifact.is_file():
            return f"release artifact missing: {artifact_name}"  # pragma: no cover - defensive/error branch
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest.lower() not in text.lower():
            return f"release body must contain wheel SHA256 {digest}"
    project = str(getattr(cfg, "pypi_project", "") or "").strip()
    if project and version:
        link = f"https://pypi.org/project/{project}/{version}/"
        if link not in text:
            return f"release body must contain {link}"  # pragma: no cover - defensive/error branch
    return ""


def _detect(cfg: GateConfig) -> tuple[bool, str]:
    """Match release-note quality claims to the machine manifest."""
    if not cfg.claims_manifest or not cfg.claims_notes:
        return False, "claims_manifest and claims_notes must be configured"  # pragma: no cover - defensive/error branch
    manifest = cfg.path(cfg.claims_manifest)
    notes = cfg.path(cfg.claims_notes)
    if not manifest.is_file():
        return False, (
            "quality-manifest.json missing. "
            "Run `python tools/dogfood_manifest.py --root .` first to generate a local manifest."
        )
    if not notes.is_file():
        return False, "release notes missing. Run the dogfood command first to generate them."  # pragma: no cover - defensive/error branch
    data = json.loads(manifest.read_text(encoding="utf-8"))
    gates = data.get("gates")
    if isinstance(gates, list):
        passed_count = sum(1 for entry in gates if entry.get("status") == "PASS")
        total = len(gates)
        expected = f"{passed_count}/{total}"
    else:
        counts = data.get("counts", {})
        expected = f"{counts.get('passed', -1)}/{counts.get('total', -1)}"
        total = int(counts.get("total", -1))
    text = notes.read_text(encoding="utf-8")
    tokens = TOKEN.findall(text)
    if len(tokens) != 1:
        return False, "release notes need exactly one QUALITY_COUNTS line"  # pragma: no cover - defensive/error branch
    actual = f"{tokens[0][0]}/{tokens[0][1]}"
    if actual != expected:
        return False, f"notes {actual} != manifest {expected}"
    gate_problem = _gate_number(text, total, required=False)
    if gate_problem:
        return False, gate_problem
    body = getattr(cfg, "release_body", "")
    if body:
        body_problem = _body_problem(cfg.path(body), expected, total, cfg)
        if body_problem:
            return False, body_problem
    return True, f"claims={actual}"


def run(cfg: GateConfig) -> tuple[bool, str]:
    """Run detection, then apply the CEL policy decision."""
    passed, detail = _detect(cfg)
    return cel_gates.apply("claims", passed, detail, cfg)
