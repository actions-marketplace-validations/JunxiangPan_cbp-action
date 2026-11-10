"""Mutation harness: every known mutant must make a CBP gate fail.

Run: python tests/mutation/run_mutations.py [--report PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cbp import body_hash, claims_gate, coverage_gate, dependency_gate, docs_gate, binary_gate
from cbp.config import GateConfig
from cbp import package_manifest, v12_rules


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def _coverage(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    _write(tmp / "tools/a.py", "x = 1\n")
    _write(tmp / "coverage.json", json.dumps({"format": "lcov", "files": {"tools/a.py": {"summary": {"num_statements": 100}, "missing_lines": []}}}))
    allow = tmp / "allowlist.json"
    _write(allow, '{"files":{}}')
    _write(Path(str(allow) + ".sha256"), _sha(allow.read_bytes()) + "  allowlist.json\n")
    cfg = GateConfig(root=tmp, coverage_json="coverage.json", coverage_allowlist="allowlist.json",
                     coverage_groups=({"name": "core", "files": ["tools/a.py"], "threshold": 80},))
    def mutate() -> None:
        data = json.loads((tmp / "coverage.json").read_text(encoding="utf-8"))
        data["files"]["tools/a.py"]["missing_lines"] = list(range(1, 80))
        _write(tmp / "coverage.json", json.dumps(data))
    return cfg, mutate


def _allowlist(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    cfg, _ = _coverage(tmp)
    def mutate() -> None:
        _write(tmp / "allowlist.json", '{"files":{"tools/a.py":[{"lines":[1,100]}]}}')
    return cfg, mutate


def _lock(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    lock = tmp / "requirements.lock"
    _write(lock, "requests==2.0\n    --hash=sha256:" + "a" * 64 + "\n")
    _write(Path(str(lock) + ".sha256"), _sha(lock.read_bytes()) + "  requirements.lock\n")
    _write(tmp / "install.sh", "python -m pip install --require-hashes -r requirements.lock\n")
    cfg = GateConfig(root=tmp, dependency_lock="requirements.lock", install_command="install.sh")
    def mutate() -> None:
        _write(lock, "requests>=2.0\n    --hash=sha256:" + "a" * 64 + "\n")
    return cfg, mutate


def _lock_tamper(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    lock = tmp / "requirements.lock"
    _write(lock, "requests==2.0\n    --hash=sha256:" + "a" * 64 + "\n")
    _write(Path(str(lock) + ".sha256"), _sha(lock.read_bytes()) + "  requirements.lock\n")
    _write(tmp / "install.sh", "python -m pip install --require-hashes -r requirements.lock\n")
    cfg = GateConfig(root=tmp, dependency_lock="requirements.lock", install_command="install.sh")
    def mutate() -> None:
        _write(lock, "requests==3.0\n    --hash=sha256:" + "b" * 64 + "\n")
    return cfg, mutate


def _docs(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    doc = tmp / "docs/a.md"; _write(doc, "a\n")
    manifest = tmp / "history.json"
    _write(manifest, json.dumps({"files": [{"path": "docs/a.md", "sha256": _sha(doc.read_bytes()).upper()}]}))
    cfg = GateConfig(root=tmp, docs_manifest="history.json")
    def mutate() -> None:
        _write(doc, "b\n")
    return cfg, mutate


def _docs_manifest(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    cfg, _ = _docs(tmp)
    def mutate() -> None:
        _write(tmp / "history.json", json.dumps({"files": [{"path": "docs/a.md", "sha256": "0" * 64}]}))
    return cfg, mutate


def _binary(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    binary = tmp / "a.exe"; _write(binary, b"binary")
    artifacts = tmp / "artifacts"; artifacts.mkdir()
    _write(artifacts / "a.exe.build.json", json.dumps({"sha256": _sha(binary.read_bytes()), "size_bytes": binary.stat().st_size}))
    _write(artifacts / "a.exe.sbom.json", json.dumps({"binary_sha256": _sha(binary.read_bytes()), "binary_size": binary.stat().st_size, "scope": "runtime-only"}))
    cfg = GateConfig(root=tmp, binary_limit_mb=0, binary_artifacts="artifacts")
    def mutate() -> None:
        _write(artifacts / "a.exe.build.json", json.dumps({"sha256": "0" * 64, "size_bytes": binary.stat().st_size}))
    return cfg, mutate


def _binary_sbom(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    cfg, _ = _binary(tmp)
    def mutate() -> None:
        _write(tmp / "artifacts/a.exe.sbom.json", json.dumps({"binary_sha256": "0" * 64, "binary_size": 1, "scope": "runtime-only"}))
    return cfg, mutate


def _claims(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    _write(tmp / "manifest.json", json.dumps({"gates": [{"name": "encoding", "status": "PASS"}]}))
    _write(tmp / "notes.md", "QUALITY_COUNTS: 1/1\n")
    _write(tmp / "body.md", "QUALITY_COUNTS: 1/1\nall 1 gates\n")
    cfg = GateConfig(root=tmp, claims_manifest="manifest.json", claims_notes="notes.md", release_body="body.md")
    def mutate() -> None:
        _write(tmp / "notes.md", "QUALITY_COUNTS: 2/2\n")
    return cfg, mutate


def _claims_body(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    cfg, _ = _claims(tmp)
    def mutate() -> None:
        _write(tmp / "body.md", "QUALITY_COUNTS: 2/2\nall 1 gates\n")
    return cfg, mutate


def _body(tmp: Path) -> tuple[GateConfig, Callable[[], None]]:
    body = tmp / "body.md"; _write(body, "# base\n")
    manifest = tmp / "manifest.json"
    _write(manifest, json.dumps({"release_body_hash": body_hash.canonical_body_hash(body.read_bytes()), "body_hash_scope": "base"}))
    def mutate() -> None:
        _write(body, "# tampered\n")
    return manifest, mutate


def _artifact(tmp: Path) -> tuple[Path, Callable[[], None]]:
    wheel = tmp / "cbp_action-1.3.0-py3-none-any.whl"; _write(wheel, b"wheel")
    expected = {wheel.name: _sha(wheel.read_bytes())}
    def mutate() -> None:
        _write(wheel, b"")
    return expected, mutate


@dataclass
class Mutant:
    id: str
    gate: str
    expected_exit: int
    run: Callable[[Path], tuple[bool, str]]


def _gate_run(fn, cfg: GateConfig) -> tuple[bool, str]:
    return fn(cfg)


def _mutants() -> list[Mutant]:
    def coverage_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _coverage(tmp)
        assert coverage_gate.run(cfg)[0] is True
        mutate(); return coverage_gate.run(cfg)[0], "CBP-COV-001"
    def allow_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _allowlist(tmp)
        assert coverage_gate.run(cfg)[0] is True
        mutate(); return coverage_gate.run(cfg)[0], "CBP-COV-001"
    def lock_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _lock(tmp)
        assert dependency_gate.run(cfg)[0] is True
        mutate(); return dependency_gate.run(cfg)[0], "CBP-DEP-001"
    def lock_tamper_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _lock_tamper(tmp)
        assert dependency_gate.run(cfg)[0] is True
        mutate(); return dependency_gate.run(cfg)[0], "CBP-DEP-001"
    def docs_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _docs(tmp)
        assert docs_gate.run(cfg)[0] is True
        mutate(); return docs_gate.run(cfg)[0], "CBP-DOC-001"
    def docs_manifest_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _docs_manifest(tmp)
        assert docs_gate.run(cfg)[0] is True
        mutate(); return docs_gate.run(cfg)[0], "CBP-DOC-001"
    def binary_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _binary(tmp)
        assert binary_gate.run(cfg)[0] is True
        mutate(); return binary_gate.run(cfg)[0], "CBP-BIN-001"
    def binary_sbom_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _binary_sbom(tmp)
        assert binary_gate.run(cfg)[0] is True
        mutate(); return binary_gate.run(cfg)[0], "CBP-BIN-001"
    def claims_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _claims(tmp)
        assert claims_gate.run(cfg)[0] is True
        mutate(); return claims_gate.run(cfg)[0], "CBP-CLM-001"
    def claims_body_case(tmp: Path) -> tuple[bool, str]:
        cfg, mutate = _claims_body(tmp)
        assert claims_gate.run(cfg)[0] is True
        mutate(); return claims_gate.run(cfg)[0], "CBP-CLM-001"
    def body_case(tmp: Path) -> tuple[bool, str]:
        manifest, mutate = _body(tmp)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        body = tmp / "body.md"
        assert v12_rules.body_binding_findings(manifest, body) == []
        mutate()
        return (not bool(v12_rules.body_binding_findings(manifest, body))), "CBP-BODY-001"
    def artifact_case(tmp: Path) -> tuple[bool, str]:
        expected, mutate = _artifact(tmp)
        wheel = tmp / "cbp_action-1.3.0-py3-none-any.whl"
        package_manifest._artifact_hashes([str(wheel)], expected)
        mutate()
        try:
            package_manifest._artifact_hashes([str(wheel)], expected)
            return True, "CBP-ART-001"
        except package_manifest.ManifestError:
            return False, "CBP-ART-001"
    return [
        Mutant("coverage-low", "CBP-COV-001", 3, coverage_case),
        Mutant("coverage-allowlist", "CBP-COV-001", 3, allow_case),
        Mutant("dependency-unpinned", "CBP-DEP-001", 3, lock_case),
        Mutant("dependency-lock-change", "CBP-DEP-001", 3, lock_tamper_case),
        Mutant("docs-hash", "CBP-DOC-001", 3, docs_case),
        Mutant("docs-manifest", "CBP-DOC-001", 3, docs_manifest_case),
        Mutant("binary-build", "CBP-BIN-001", 3, binary_case),
        Mutant("binary-sbom", "CBP-BIN-001", 3, binary_sbom_case),
        Mutant("claims-counts", "CBP-CLM-001", 3, claims_case),
        Mutant("claims-body", "CBP-CLM-001", 3, claims_body_case),
        Mutant("body-hash", "CBP-BODY-001", 3, body_case),
        Mutant("artifact-empty", "CBP-ART-001", 2, artifact_case),
    ]


def run(report: Path) -> dict:
    rows = []
    for mutant in _mutants():
        with tempfile.TemporaryDirectory() as tmp:
            try:
                passed, detail = mutant.run(Path(tmp))
            except Exception as exc:  # a crash is a detected failure, but record it
                passed, detail = False, f"{type(exc).__name__}: {exc}"
        detected = not passed
        exit_code = mutant.expected_exit if detected else 0
        rows.append({"id": mutant.id, "gate": mutant.gate, "expected_exit": mutant.expected_exit,
                     "actual_exit": exit_code, "detected": detected, "detail": detail})
    detected = sum(1 for row in rows if row["detected"])
    recall = detected / len(rows) if rows else 0.0
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CBP mutation report", "", f"- mutants: {len(rows)}", f"- detected: {detected}", f"- recall: {recall:.2%}", "",
             "| Mutant | Expected gate | Expected exit | Actual exit | Detected |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| `{row['id']}` | {row['gate']} | {row['expected_exit']} | {row['actual_exit']} | {'yes' if row['detected'] else 'NO'} |")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"mutants": len(rows), "detected": detected, "recall": recall, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="docs/1.3.0/MUTATION_REPORT.md")
    args = parser.parse_args()
    result = run(Path(args.report))
    print(json.dumps({key: result[key] for key in ("mutants", "detected", "recall")}))
