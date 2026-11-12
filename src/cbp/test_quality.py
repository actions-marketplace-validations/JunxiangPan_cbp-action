"""Opt-in test-quality gate: weak assertions, empty skips and deleted tests."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestQualityOptions:
    root: Path
    paths: tuple[str, ...] = ("tests",)
    language: str = "python"
    baseline: Path | None = None


def _python_files(root: Path, paths: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for item in paths:
        path = root / item
        if path.is_file() and path.suffix == ".py":
            found.append(path)
        elif path.is_dir():
            found.extend(sorted(path.rglob("test_*.py")))
    return list(dict.fromkeys(found))


def _python_findings(path: Path, root: Path) -> list[str]:
    findings: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{path.relative_to(root).as_posix()}:{exc.lineno}: test file does not parse"]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test"):
            continue
        assertions = any(isinstance(item, ast.Assert) for item in ast.walk(node))
        raises = False
        weak = False
        empty_skip = False
        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                name = ""
                if isinstance(item.func, ast.Attribute):
                    name = item.func.attr
                elif isinstance(item.func, ast.Name):
                    name = item.func.id
                if name in {"raises", "assertRaises", "fail", "assert_raises"}:
                    raises = True
                if name in {"skip", "skipTest", "skipIf", "xfail"}:
                    if not item.args or (isinstance(item.args[0], ast.Constant) and not str(item.args[0].value).strip()):
                        empty_skip = True
            if isinstance(item, ast.Assert) and isinstance(item.test, ast.Constant) and item.test.value is True:
                weak = True
        if not assertions and not raises:
            findings.append(f"{path.relative_to(root).as_posix()}:{node.lineno}: test has no assertion")
        if weak:
            findings.append(f"{path.relative_to(root).as_posix()}:{node.lineno}: assert True")
        if empty_skip:
            findings.append(f"{path.relative_to(root).as_posix()}:{node.lineno}: skip without a reason")
    return findings


def _generic_findings(path: Path, root: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    relative = path.relative_to(root).as_posix()
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if re.search(r"\b(?:test|it)\s*\(", stripped) and "expect(" not in stripped and "assert" not in stripped:
            findings.append(f"{relative}:{line_no}: test block has no nearby assertion")
        if re.search(r"\bassert\s+true\b", stripped, re.I):
            findings.append(f"{relative}:{line_no}: assert true")
        if re.search(r"\b(?:skip|xit|xtest)\s*\(\s*\)", stripped):
            findings.append(f"{relative}:{line_no}: skip without a reason")
    return findings


def run(options: TestQualityOptions) -> dict:
    root = options.root.resolve()
    paths = options.paths
    if options.language == "python":
        files = _python_files(root, paths)
        findings: list[str] = []
        for path in files:
            findings.extend(_python_findings(path, root))
    else:
        files = []
        for item in paths:
            target = root / item
            if target.is_dir():
                files.extend(sorted(target.rglob("test_*.*")))
            elif target.is_file():
                files.append(target)
        findings = []
        for path in files:
            findings.extend(_generic_findings(path, root))
    if not files:
        findings.append("no test files found")
    if options.baseline is not None:
        baseline_path = root / options.baseline
        try:
            expected = set(json.loads(baseline_path.read_text(encoding="utf-8")).get("tests", []))
        except (OSError, ValueError) as exc:
            findings.append(f"test baseline unreadable: {exc}")
            expected = set()
        present = {path.stem for path in files}
        for missing in sorted(expected - present):
            findings.append(f"test deleted: {missing}")
    return {"gate": "test-quality", "status": "PASS" if not findings else "FAIL",
            "files": len(files), "findings": findings}
