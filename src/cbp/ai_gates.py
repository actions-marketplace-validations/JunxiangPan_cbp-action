"""Audit-only AI gates: evidence coherence, test integrity, change audit."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GateResult:
    gate: str
    status: str
    findings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def line(self) -> str:
        return f"AI_GATE={self.gate} status={self.status} findings={len(self.findings)} skipped={len(self.skipped)}"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return completed.stdout if completed.returncode == 0 else ""


def _version(root: Path) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8") if (root / "pyproject.toml").is_file() else ""
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def ai_release(root: Path, tag: str, body_path: str = "") -> GateResult:
    """CBP-REL-001..004: structured release evidence, no natural language."""
    findings: list[str] = []
    skipped: list[str] = []
    version = tag.lstrip("v")
    body = root / body_path if body_path else root / "docs" / "RELEASE_BODY.md"
    notes = root / "docs" / "RELEASE_NOTES.generated.md"
    assets = root / "dist" / "RELEASE_ASSETS.sha256"
    if not body.is_file():
        findings.append("CBP-REL-001 release body missing")
    else:
        text = body.read_text(encoding="utf-8")
        if version not in text:
            findings.append(f"CBP-REL-001 release body does not name {version}")
    if _version(root) != version:
        findings.append(f"CBP-REL-001 pyproject version {_version(root)} != tag {version}")
    if not notes.is_file():
        findings.append("CBP-REL-003 release notes missing")
    if not assets.is_file():
        findings.append("CBP-REL-003 RELEASE_ASSETS.sha256 missing")
    else:
        names = {line.split("*")[-1].strip() for line in assets.read_text(encoding="utf-8").splitlines() if line.strip()}
        if not any(name.endswith(".whl") for name in names):
            findings.append("CBP-REL-003 asset manifest lacks wheel")
    changelog = root / "CHANGELOG.md"
    if changelog.is_file() and version not in changelog.read_text(encoding="utf-8"):
        findings.append(f"CBP-REL-004 CHANGELOG lacks {version}")
    skipped.append("CBP-REL-002 dependency diff: audit v1.0.7")
    return GateResult("ai-release", "FAIL" if findings else "PASS", findings, skipped)


def _test_functions(path: Path) -> list[ast.FunctionDef]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]


def ai_test(root: Path, baseline: str, test_path: str = "") -> GateResult:
    """CBP-TEST-001..004: missing/tautological assertions in changed tests."""
    if test_path:
        tests = [root / test_path]
    else:
        changed = _git(root, "diff", "--name-only", baseline).splitlines()
        tests = [root / name for name in changed if Path(name).name.startswith("test_") and name.endswith(".py")]
    if not tests:
        return GateResult("ai-test", "SKIP", [], ["no changed test files"])
    findings: list[str] = []
    for path in tests:
        for function in _test_functions(path):
            asserts = [node for node in ast.walk(function) if isinstance(node, ast.Assert)]
            if not asserts:
                findings.append(f"CBP-TEST-001 {path.name}::{function.name} has no assert")
            for node in asserts:
                source = ast.unparse(node.test)
                if source == "True" or re.search(r"\b(\w+)\s*==\s*\1\b", source):
                    findings.append(f"CBP-TEST-004 {path.name}::{function.name} tautology: {source}")
    return GateResult("ai-test", "WARN" if findings else "PASS", findings, ["CBP-TEST-003 coverage diff: audit v1.0.7"])


def ai_change(root: Path, baseline: str) -> GateResult:
    """CBP-CHG-001..004: lightweight, module-level change audit."""
    if not baseline:
        return GateResult("ai-change", "SKIP", [], ["no baseline"])
    changed = _git(root, "diff", "--name-only", baseline).splitlines()
    findings: list[str] = []
    if any(name.startswith("requirements") for name in changed) and not any("lock" in name for name in changed):
        findings.append("CBP-CHG-001 dependency file changed without lockfile")
    for name in changed:
        path = root / name
        if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            findings.append(f"CBP-CHG-004 large file: {name}")
    return GateResult("ai-change", "WARN" if findings else "PASS", findings, ["CBP-CHG-002/003 AST diff: audit v1.0.8"])


def run(gate: str, root: Path, tag: str = "", baseline: str = "", test_path: str = "", body_path: str = "") -> GateResult:
    if gate == "ai-release":
        return ai_release(root, tag, body_path)
    if gate == "ai-test":
        return ai_test(root, baseline, test_path)
    if gate == "ai-change":
        return ai_change(root, baseline)
    return GateResult(gate, "SKIP", [], ["unknown gate"])


def sarif(result: GateResult) -> dict:
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "CBP-AI", "rules": [{"id": "CBP-AI-001"}]}},
            "results": [{"ruleId": "CBP-AI-001", "level": "warning", "message": {"text": item}} for item in result.findings],
        }],
    }
