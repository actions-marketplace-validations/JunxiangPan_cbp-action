#!/usr/bin/env python3
"""Generate a CBP quality manifest from real gate execution.

The generator never reads an existing quality manifest. It calls the gate
functions directly, writes a provisional manifest only to let the claims gate
run, then writes the final manifest and release-note count after all eight gates
have actually passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cbp import binary_gate, claims_gate, comment_gate, coverage_gate, custom_rules, dependency_gate, docs_gate, encoding_gate, report_schema, source_hash, upgrade_gate
from cbp.config import GateConfig, load_config

GENERATED_BY = "cbp-action dogfood job"
SCHEMA = "cbp-quality-manifest/v1"
PERCENT = re.compile(r"([A-Za-z0-9_]+)=([0-9]+\.[0-9]+)%")
COUNT = re.compile(r"(?m)^QUALITY_COUNTS:\s*\S+\s*$")


class ManifestError(RuntimeError):
    """Raised when dogfood output cannot be trusted."""


def _now() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if epoch.isdigit():
        return datetime.fromtimestamp(int(epoch), timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def validate_manifest(manifest: dict[str, Any], *, actions: bool = False) -> list[str]:
    """Validate a generated manifest; return a list of problems."""
    if "schema_version" in manifest:
        problems = report_schema.validate_manifest(manifest, require_producer=True)
        if manifest.get("generated_by") != GENERATED_BY:
            problems.append(f"generated_by must be {GENERATED_BY}")
        if actions:
            if not manifest.get("ci_run_id"):
                problems.append("ci_run_id is required in GitHub Actions")
            if not manifest.get("ci_commit_sha"):
                problems.append("ci_commit_sha is required in GitHub Actions")
        return problems
    # Legacy manifest shape, kept so older evidence remains readable.
    problems: list[str] = []
    if manifest.get("schema") != SCHEMA:
        problems.append("schema must be cbp-quality-manifest/v1")
    gates = manifest.get("gates")
    expected = {"coverage", "dependency", "comments", "docs", "binary", "encoding", "claims", "custom", "upgrade"}
    counts = manifest.get("counts")
    if not isinstance(gates, dict) or set(gates) != expected:
        problems.append("gates must contain exactly the nine CBP gates")
    elif any(value != "PASS" for value in gates.values()):
        problems.append("gate statuses must all be PASS")
    if not isinstance(counts, dict) or not isinstance(counts.get("passed"), int) or not isinstance(counts.get("total"), int):
        problems.append("counts.passed/counts.total must be integers")
    else:
        if counts["total"] != 9 or counts["passed"] > counts["total"]:
            problems.append("counts must be within 9/9")
        if isinstance(gates, dict) and counts["passed"] != sum(1 for value in gates.values() if value == "PASS"):
            problems.append("counts.passed must equal the number of PASS gates")
    if manifest.get("generated_by") != GENERATED_BY:
        problems.append(f"generated_by must be {GENERATED_BY}")
    if actions:
        if not manifest.get("ci_run_id"):
            problems.append("ci_run_id is required in GitHub Actions")
        if not manifest.get("ci_commit_sha"):
            problems.append("ci_commit_sha is required in GitHub Actions")
    return problems


def _gate_detail(detail: str) -> dict[str, float]:
    return {name: float(value) for name, value in PERCENT.findall(detail)}


def _run_gate(name: str, cfg: GateConfig) -> tuple[bool, str]:
    functions = {
        "coverage": coverage_gate.run,
        "dependency": dependency_gate.run,
        "comments": comment_gate.run,
        "docs": docs_gate.run,
        "binary": binary_gate.run,
        "encoding": encoding_gate.run,
        "custom": custom_rules.run,
        "upgrade": upgrade_gate.run,
    }
    if name not in functions:
        raise ManifestError(f"unknown gate: {name}")
    return functions[name](cfg)


def _gate_entry(name: str, status: str, reason: str = "") -> dict[str, Any]:
    return {"name": name, "status": status, "reason": reason}


def _artifact_hashes(wheel: Path) -> dict[str, str]:
    version = wheel.name.split("-")[1] if wheel.name.count("-") >= 1 else ""
    sdists = sorted(
        path for path in wheel.parent.glob("*.tar.gz")
        if version and version in path.name
    )
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [wheel, *sdists]
    }


def _canonical_sha(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _manifest_document(
    *,
    version: str,
    run_id: str,
    commit_sha: str,
    gate_status: str,
    gates: list[dict[str, Any]],
    artifact_hashes: dict[str, str],
    release_body_hash: str,
    body_hash_scope: str = "base",
    artifact_repository: str = "",
) -> dict[str, Any]:
    if body_hash_scope not in report_schema.BODY_HASH_SCOPES:
        raise ManifestError(
            "unsupported body_hash_scope: "
            + repr(body_hash_scope)
            + "; supported: "
            + ", ".join(report_schema.BODY_HASH_SCOPES)
        )
    applicable = len(report_schema.ALL_GATES)
    skip_count = sum(1 for entry in gates if entry["status"] == "SKIPPED")
    blocking = any(
        entry["name"] in report_schema.FORCED_GATES and entry["status"] == "SKIPPED"
        for entry in gates
    )
    return {
        "schema_version": report_schema.MANIFEST_SCHEMA_VERSION,
        "package_id": report_schema.PACKAGE_ID,
        "producer_id": report_schema.PRODUCER_ID,
        "version": version,
        "gate_status": gate_status,
        "applicable_gate_count": applicable,
        "skip_count": skip_count,
        "skip_ratio": (skip_count / applicable) if applicable else 0.0,
        "blocking_skip": blocking,
        "gates": gates,
        "artifact_hashes": artifact_hashes,
        "release_body_hash": release_body_hash,
        "body_hash_scope": body_hash_scope,
        "evidence_sha256": "0" * 64,
        "ci_run_id": run_id,
        "ci_commit_sha": commit_sha,
        "generated_at": _now(),
        "generated_by": GENERATED_BY,
        **({"artifact_repository": artifact_repository} if artifact_repository else {}),
    }


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    _atomic_write(path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_notes(template: Path, output: Path, counts: str, gate_count: int) -> None:
    text = template.read_text(encoding="utf-8")
    updated, count = COUNT.subn(f"QUALITY_COUNTS: {counts}", text)
    if count != 1:
        raise ManifestError("release-note template must contain exactly one QUALITY_COUNTS line")
    if "__GATE_COUNT__" not in updated:
        raise ManifestError("release-note template must contain __GATE_COUNT__")
    updated = updated.replace("__GATE_COUNT__", str(gate_count))
    _atomic_write(output, updated)


def generate(
    root: Path,
    coverage_json: Path | None = None,
    output: Path | None = None,
    notes_template: Path | None = None,
    notes_output: Path | None = None,
    run_id: str | None = None,
    commit_sha: str | None = None,
    body_hash_scope: str = "base",
    artifact_repository: str = "",
) -> dict[str, Any]:
    """Run all gates, write the manifest and generated release notes."""
    root = root.resolve()
    if body_hash_scope not in report_schema.BODY_HASH_SCOPES:
        raise ManifestError(
            "unsupported body_hash_scope: "
            + repr(body_hash_scope)
            + "; supported: "
            + ", ".join(report_schema.BODY_HASH_SCOPES)
        )
    cfg = load_config(root, root / "cbp.json")
    if not artifact_repository:
        artifact_repository = (
            str(getattr(cfg, "artifact_repository", "") or "")
            or os.environ.get("GITHUB_REPOSITORY", "")
        )
    if coverage_json is not None:
        cfg.coverage_json = coverage_json
    coverage_path = cfg.path(cfg.coverage_json)
    if not coverage_path.is_file():
        raise ManifestError(f"coverage file missing: {coverage_path}")
    source_hash.stamp(coverage_path, root)
    output = output or root / "quality-manifest.json"
    notes_template = notes_template or root / "docs" / "RELEASE_NOTES.md"
    notes_output = notes_output or root / "docs" / "RELEASE_NOTES.generated.md"
    actions = os.environ.get("GITHUB_ACTIONS") == "true"
    run_id = run_id or os.environ.get("GITHUB_RUN_ID", "")
    commit_sha = commit_sha or os.environ.get("GITHUB_SHA", "")
    if actions and not run_id:
        raise ManifestError("GITHUB_RUN_ID is required when GITHUB_ACTIONS=true")
    if actions and not commit_sha:
        raise ManifestError("GITHUB_SHA is required when GITHUB_ACTIONS=true")
    statuses: dict[str, str] = {}
    for name in ("coverage", "dependency", "comments", "docs", "binary", "encoding", "custom", "upgrade"):
        passed, detail = _run_gate(name, cfg)
        statuses[name] = "PASS" if passed else "FAIL"
        print(f"{name}: {'PASS' if passed else 'FAIL'} {detail}")
        if not passed:
            raise ManifestError(f"{name} gate failed")
    wheel = cfg.path(cfg.release_artifact) if getattr(cfg, "release_artifact", "") else None
    if wheel is None or not wheel.is_file():
        raise ManifestError("release wheel artifact missing: " + str(getattr(cfg, "release_artifact", "")))
    version = "v" + str(getattr(cfg, "release_version", "")).lstrip("v")
    provisional = _manifest_document(
        version=version,
        run_id=run_id,
        commit_sha=commit_sha,
        gate_status="FAIL",
        gates=[
            _gate_entry(name, "SKIPPED" if name == "claims" else statuses[name], "claims pending")
            for name in report_schema.ALL_GATES
        ],
        artifact_hashes={},
        release_body_hash="0" * 64,
        body_hash_scope=body_hash_scope,
        artifact_repository=artifact_repository,
    )
    _write_manifest(output, provisional)
    _write_notes(notes_template, notes_output, "8/9", gate_count=9)
    cfg.claims_manifest = output
    cfg.claims_notes = notes_output
    configured_body = cfg.release_body
    cfg.release_body = ""
    claims_ok, claims_detail = claims_gate.run(cfg)
    print(f"claims: {'PASS' if claims_ok else 'FAIL'} {claims_detail}")
    if not claims_ok:
        raise ManifestError("claims gate failed")
    statuses["claims"] = "PASS"
    cfg.release_body = configured_body
    _write_notes(notes_template, notes_output, "9/9", gate_count=9)
    body_output = root / "dist" / "RELEASE_BODY.md"
    import subprocess
    subprocess.run([
        sys.executable, str(root / "tools" / "generate_release_body.py"),
        "--wheel", str(wheel), "--version", version,
        "--notes", str(notes_output), "--output", str(body_output),
    ], check=True)
    artifact_hashes = _artifact_hashes(wheel)
    release_body_hash = hashlib.sha256(body_output.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    final_manifest = _manifest_document(
        version=version,
        run_id=run_id,
        commit_sha=commit_sha,
        gate_status="PASS",
        gates=[_gate_entry(name, statuses.get(name, "SKIPPED")) for name in report_schema.ALL_GATES],
        artifact_hashes=artifact_hashes,
        release_body_hash=release_body_hash,
        body_hash_scope=body_hash_scope,
        artifact_repository=artifact_repository,
    )
    final_manifest["evidence_sha256"] = _canonical_sha(
        {key: value for key, value in final_manifest.items() if key != "evidence_sha256"}
    )
    problems = validate_manifest(final_manifest, actions=actions)
    if problems:
        raise ManifestError("; ".join(problems))
    _write_manifest(output, final_manifest)
    final_ok, final_detail = claims_gate.run(cfg)
    if not final_ok:
        raise ManifestError("final claims verification failed: " + final_detail)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    _atomic_write(output.with_name(output.name + ".sha256"), digest + "  " + output.name + "\n")
    return final_manifest


def main(argv: list[str] | None = None) -> int:
    """Generate the manifest and print its path and hash."""
    parser = argparse.ArgumentParser(prog="dogfood-manifest")
    parser.add_argument("--root", default=".")
    parser.add_argument("--coverage-json", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--notes-template", default="")
    parser.add_argument("--notes-output", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--body-hash-scope", default="base")
    parser.add_argument("--artifact-repository", default="")
    args = parser.parse_args(argv)
    try:
        manifest = generate(
            Path(args.root),
            Path(args.coverage_json) if args.coverage_json else None,
            Path(args.output) if args.output else None,
            Path(args.notes_template) if args.notes_template else None,
            Path(args.notes_output) if args.notes_output else None,
            args.run_id,
            args.commit_sha,
            body_hash_scope=args.body_hash_scope,
            artifact_repository=args.artifact_repository,
        )
    except ManifestError as exc:
        print(f"DOGFOOD_MANIFEST_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
