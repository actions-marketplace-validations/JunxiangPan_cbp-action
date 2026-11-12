"""Opt-in strict evidence profile (CBP 1.4.0).

The default CLI path is unchanged. `--profile strict` requires signed
provenance, the gate manifest, mutation/hostile/fuzz evidence, action pins,
lock integrity, tag immutability, Windows coverage and an SBOM. It never
modifies the frozen quality-manifest.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import artifact_integrity, dependency_gate, hostile_input, provenance, target_mutation
from .config import GateConfig


@dataclass
class StrictOptions:
    root: Path
    manifest: Path
    provenance: Path
    bundle_dir: Path
    artifacts: tuple[Path, ...]
    identity_regexp: str
    oidc_issuer: str = "https://token.actions.githubusercontent.com"
    tags_expected: Path = Path("docs/tags-expected.json")
    sbom: Path = Path("docs/1.5.0/SBOM.json")
    mutation_report: Path = Path("docs/1.3.0/MUTATION_REPORT.md")
    hostile_corpus: Path = Path("tests/hostile/corpus.json")
    gate_manifest: Path = Path("quality/GATES.sha256")
    lockfile: Path = Path("requirements-test.lock")
    installer: Path = Path("install-test.sh")
    report: Path = Path("strict-profile.json")
    mutation_report: Path = Path("docs/1.3.0/MUTATION_REPORT.md")
    target_mutation_report: Path = Path("docs/1.5.0/mutation-report.json")
    mutation_threshold: float = 0.95
    changed_code_threshold: float = 0.90


def _gate_manifest_problems(manifest: Path, root: Path) -> list[str]:
    problems: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected, _, relative = line.partition(" ")
        relative = relative.strip()
        path = root / relative
        if not path.is_file():
            problems.append(f"{relative}: missing")
        elif hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != expected:
            problems.append(f"{relative}: hash mismatch")
    return problems


def _tag_diff(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for tag, commit in sorted(expected.items()):
        if tag not in actual:
            problems.append(f"{tag}: missing")
        elif actual[tag] != commit:
            problems.append(f"{tag}: moved {commit} -> {actual[tag]}")
    return problems


def _fuzz_problem() -> str:
    rng = random.Random(1400)
    forbidden = ["..", "\\", "/", ";", "${{", "\n", "\r", "\x00", "\u202e"]
    for _ in range(200):
        value = "".join(rng.choice(forbidden + ["a", "B", "1", "-", "_"]) for _ in range(rng.randint(1, 12)))
        if not any(item in value for item in forbidden):
            continue
        try:
            hostile_input.artifact_name(value)
        except hostile_input.HostileInput:
            continue
        return f"fuzz accepted hostile artifact name: {value!r}"
    return ""


def _actual_tags(root: Path, tags: list[str]) -> dict[str, str]:
    actual: dict[str, str] = {}
    for tag in tags:
        result = subprocess.run(
            ["git", "rev-parse", f"{tag}^{{commit}}"], cwd=root,
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            actual[tag] = result.stdout.strip()
    return actual


def run(options: StrictOptions) -> int:
    root = options.root.resolve()
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    # 1. Gate script/workflow self-protection
    try:
        problems = _gate_manifest_problems(root / options.gate_manifest, root)
        add("gates_sha256", not problems, "; ".join(problems) or "verified")
    except (OSError, ValueError) as exc:
        add("gates_sha256", False, str(exc))

    # 2. Target-mutation evidence (strict: failure is exit 3)
    try:
        mutation = target_mutation.run(target_mutation.MutationOptions(
            root=root, report=options.target_mutation_report,
            threshold=options.mutation_threshold,
            changed_code_threshold=options.changed_code_threshold,
        ))
        add("target_mutation", mutation["status"] == "PASS", json.dumps(mutation, ensure_ascii=False))
    except Exception as exc:
        add("target_mutation", False, str(exc))

    # 3. Mutation evidence
    try:
        text = (root / options.mutation_report).read_text(encoding="utf-8")
        match = re.search(r"recall:\s*([0-9.]+)%", text)
        recall = float(match.group(1)) if match else -1.0
        add("mutation", recall >= 95.0, f"recall={recall:.2f}% (target >=95%)")
    except OSError as exc:
        add("mutation", False, f"report missing: {exc}")

    # 3. Hostile corpus
    try:
        corpus = json.loads((root / options.hostile_corpus).read_text(encoding="utf-8"))
        ok = len(corpus) >= 50 and all(item.get("expect") == "FAIL" for item in corpus)
        add("hostile_corpus", ok, f"cases={len(corpus)}")
    except (OSError, ValueError) as exc:
        add("hostile_corpus", False, f"corpus unreadable: {exc}")

    # 4. Deterministic fuzz guard
    fuzz = _fuzz_problem()
    add("fuzz", not fuzz, fuzz or "200 hostile inputs rejected")

    # 5. Action pins
    try:
        pins = artifact_integrity.action_pin_findings(GateConfig(root=root))
        add("action_pins", not pins, "; ".join(pins) or "all full SHA")
    except Exception as exc:  # pragma: no cover - defensive
        add("action_pins", False, str(exc))

    # 6. Lockfile integrity
    try:
        cfg = GateConfig(root=root, dependency_lock=options.lockfile, install_command=options.installer)
        passed, detail = dependency_gate.run(cfg)
        add("lockfile", passed, detail)
    except Exception as exc:  # pragma: no cover - defensive
        add("lockfile", False, str(exc))

    # 7. Tag immutability against the expected map
    try:
        expected = json.loads((root / options.tags_expected).read_text(encoding="utf-8"))
        if not expected:
            raise ValueError("expected tag map is empty")
        actual = _actual_tags(root, sorted(expected))
        moved = _tag_diff(expected, actual)
        add("tag_immutability", not moved, "; ".join(moved) or f"tags={len(expected)}")
    except (OSError, ValueError) as exc:
        add("tag_immutability", False, f"expected map unreadable: {exc}")

    # 8. Windows coverage is declared in CI
    try:
        ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        add("windows", "windows-latest" in ci, "ci.yml matrix")
    except OSError as exc:
        add("windows", False, str(exc))

    # 9. SBOM
    try:
        sbom = json.loads((root / options.sbom).read_text(encoding="utf-8"))
        ok = sbom.get("bomFormat") == "CycloneDX" and bool(sbom.get("components"))
        add("sbom", ok, f"components={len(sbom.get('components', []))}")
    except (OSError, ValueError) as exc:
        add("sbom", False, f"SBOM unreadable: {exc}")

    # 10. Signed provenance + external verifier
    try:
        if not options.artifacts:
            add("provenance", False, "at least one --strict-artifact is required")
        else:
            artifacts = [root / item for item in options.artifacts]
            result = provenance.verify(
                root / options.provenance, root / options.manifest, artifacts,
                bundle_dir=root / options.bundle_dir,
                identity_regexp=options.identity_regexp,
                oidc_issuer=options.oidc_issuer,
            )
            add("provenance", result["status"] == "SIGNED" and not result["problems"],
                json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        add("provenance", False, str(exc))

    passed = all(item["status"] == "PASS" for item in checks)
    report = {
        "profile": "strict",
        "passed": passed,
        "checks": checks,
        "note": "opt-in profile; the default CBP 1.4.0 behavior is unchanged",
    }
    out = root / options.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if passed else 3
